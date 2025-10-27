#!/usr/bin/env python3
"""
Cross-Device Cookie Test - A 기기 쿠키 + B 기기 TLS/UA

목적: 쿠키가 TLS fingerprint/User-Agent에 바인딩되어 있는지 검증

테스트:
- A 기기(Samsung S21 Plus)에서 쿠키 수집
- B 기기(iPhone 14 Pro Safari) TLS/UA로 크롤링 시도
- 성공 여부 확인

결과 예상:
- ✅ 성공: 쿠키는 IP만 체크 → 기기 로테이션 가능!
- ❌ 실패: 쿠키가 TLS/UA에 바인딩 → 기기별 쿠키 필요
"""

import sys
sys.path.insert(0, '/var/www/html/browserstack')

import json
import os
from datetime import datetime
from curl_cffi.requests import Session
from lib.db.manager import DBManager


class CrossDeviceCookieTest:
    def __init__(self):
        self.db = DBManager()
        self.session = Session()

    def load_device_data(self, device_name, browser):
        """디바이스 TLS + 쿠키 로드"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # TLS 데이터
        cursor.execute("""
            SELECT tls_data, http2_data
            FROM tls_fingerprints
            WHERE device_name = %s AND browser = %s
            ORDER BY collected_at DESC LIMIT 1
        """, (device_name, browser))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"TLS 데이터 없음: {device_name} / {browser}")

        tls_data = json.loads(row[0])
        http2_data = json.loads(row[1])

        # 쿠키 데이터 (파일에서 로드)
        os_version = tls_data.get('os_version', '')

        # 여러 경로 시도
        possible_paths = [
            f"/var/www/html/browserstack/data/fingerprints/{device_name.replace(' ', '_')}_{browser}_{os_version}/cookies.json",
            f"/var/www/html/browserstack/data/fingerprints/{device_name.replace(' ', '_')}_{browser}/cookies.json",
        ]

        cookie_data = []
        for cookie_file in possible_paths:
            if os.path.exists(cookie_file):
                with open(cookie_file, 'r') as f:
                    cookie_data = json.load(f)
                break

        cursor.close()
        conn.close()

        return {
            'tls': tls_data,
            'http2': http2_data,
            'cookies': cookie_data
        }

    def extract_ja3_akamai(self, tls_data, http2_data):
        """JA3 + Akamai 추출"""
        ja3 = tls_data['tls']['ja3']
        akamai = http2_data.get('akamai_fingerprint', '')

        return ja3, akamai

    def build_headers(self, tls_data):
        """User-Agent + 헤더 구성"""
        user_agent = tls_data.get('user_agent', '')

        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.coupang.com/',
            'Cache-Control': 'max-age=0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }

        return headers

    def cookies_to_dict(self, cookie_list):
        """쿠키 리스트 → dict 변환"""
        cookie_dict = {}
        for cookie in cookie_list:
            if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                cookie_dict[cookie['name']] = cookie['value']
        return cookie_dict

    def test_cross_device(self, device_a, browser_a, device_b, browser_b, keyword='아이폰'):
        """
        Cross-Device 테스트

        Args:
            device_a: 쿠키 수집 기기
            browser_a: 쿠키 수집 브라우저
            device_b: TLS/UA 사용 기기
            browser_b: TLS/UA 사용 브라우저
        """
        print("=" * 80)
        print("Cross-Device Cookie Test")
        print("=" * 80)

        # A 기기 데이터 로드 (쿠키 소스)
        print(f"\n[Device A - Cookie Source]")
        print(f"  Device: {device_a}")
        print(f"  Browser: {browser_a}")

        data_a = self.load_device_data(device_a, browser_a)
        cookies_a = self.cookies_to_dict(data_a['cookies'])

        print(f"  Cookies: {len(cookies_a)} 개")
        print(f"  PCID: {'✅' if 'PCID' in cookies_a else '❌'}")
        print(f"  sid: {'✅' if 'sid' in cookies_a else '❌'}")

        # B 기기 데이터 로드 (TLS/UA 소스)
        print(f"\n[Device B - TLS/UA Source]")
        print(f"  Device: {device_b}")
        print(f"  Browser: {browser_b}")

        data_b = self.load_device_data(device_b, browser_b)
        ja3_b, akamai_b = self.extract_ja3_akamai(data_b['tls'], data_b['http2'])
        headers_b = self.build_headers(data_b['tls'])

        print(f"  JA3: {ja3_b[:32]}...")
        print(f"  Akamai: {akamai_b[:40]}...")
        print(f"  User-Agent: {headers_b['User-Agent'][:60]}...")

        # Cross-Device 조합 테스트
        print(f"\n[Test] A 쿠키 + B TLS/UA")
        print(f"  Cookie from: {device_a} / {browser_a}")
        print(f"  TLS/UA from: {device_b} / {browser_b}")
        print()

        url = f"https://www.coupang.com/np/search?q={keyword}&channel=user"

        try:
            # extra_fp 설정 (B 기기 기반)
            extra_fp = self._build_extra_fp(data_b['tls'], data_b['http2'])

            # 요청 (A 쿠키 + B TLS/UA)
            response = self.session.get(
                url,
                ja3=ja3_b,
                akamai=akamai_b,
                extra_fp=extra_fp,
                headers=headers_b,
                cookies=cookies_a,  # ← A 기기 쿠키!
                timeout=30,
                allow_redirects=True
            )

            # 결과 분석
            status = response.status_code
            size = len(response.content)

            print(f"✅ 요청 성공")
            print(f"  Status: {status}")
            print(f"  Size: {size:,} bytes")
            print()

            # 성공 여부 판단
            if status == 200 and size > 100000:
                print("🎉 Cross-Device 성공!")
                print("  → A 기기 쿠키가 B 기기 TLS/UA에서 작동함!")
                print("  → 쿠키는 IP만 체크, TLS/UA 무관!")
                print("  → 기기 로테이션 가능! ✅")

                # 상품 개수 확인
                product_count = response.text.count('search-product')
                print(f"  → 검색 결과: {product_count}개 상품")

                return True

            elif size < 10000:
                print("❌ Cross-Device 실패 (차단)")
                print("  → A 기기 쿠키가 B 기기 TLS/UA에서 거부됨")
                print("  → 쿠키가 TLS/UA에 바인딩되어 있음")
                print("  → 기기별 쿠키 필요 ❌")
                print(f"  → 응답 크기: {size} bytes (너무 작음 - Akamai Challenge)")

                return False

            else:
                print("⚠️ 애매한 결과")
                print(f"  → 응답 크기: {size} bytes")
                print("  → 추가 분석 필요")

                return None

        except Exception as e:
            print(f"❌ 요청 실패: {e}")
            return False

    def _build_extra_fp(self, tls_data, http2_data):
        """extra_fp 옵션 구성"""
        tls = tls_data.get('tls', {})

        # Signature algorithms 추출
        sig_algs = []
        for ext in tls.get('extensions', []):
            if ext.get('name') == 'signature_algorithms':
                sig_algs = ext.get('signature_algorithms', [])
                break

        # Certificate compression
        cert_compression = 'brotli'
        for ext in tls.get('extensions', []):
            if ext.get('name') == 'compress_certificate':
                algorithms = ext.get('algorithms', [])
                if 'zlib' in str(algorithms):
                    cert_compression = 'zlib'
                break

        extra_fp = {
            'tls_grease': True,
            'tls_signature_algorithms': sig_algs[:15] if sig_algs else [],
            'tls_cert_compression': cert_compression,
            'tls_min_version': 4,
            'tls_permute_extensions': False,
            'http2_stream_weight': 256,
            'http2_stream_exclusive': 1,
            'http2_no_priority': False,
        }

        return extra_fp


def main():
    tester = CrossDeviceCookieTest()

    print("\n" + "=" * 80)
    print("Cross-Device Cookie Compatibility Test")
    print("동일 IP에서 A 기기 쿠키를 B 기기 TLS/UA로 사용 가능한지 검증")
    print("=" * 80)

    # 테스트 1: Samsung (쿠키) + iPhone Safari (TLS/UA)
    print("\n\n### Test 1: Samsung S21 Plus 쿠키 + iPhone 14 Pro Safari TLS/UA ###\n")

    result1 = tester.test_cross_device(
        device_a='Samsung Galaxy S21 Plus',
        browser_a='samsung',
        device_b='iPhone 14 Plus',
        browser_b='iphone',
        keyword='아이폰'
    )

    # 테스트 2: iPhone (쿠키) + Samsung (TLS/UA) - 역방향
    print("\n\n### Test 2: iPhone 14 Plus 쿠키 + Samsung S21 Plus TLS/UA (역방향) ###\n")

    result2 = tester.test_cross_device(
        device_a='iPhone 14 Plus',
        browser_a='iphone',
        device_b='Samsung Galaxy S21 Plus',
        browser_b='samsung',
        keyword='아이폰'
    )

    # 결과 요약
    print("\n\n" + "=" * 80)
    print("결과 요약")
    print("=" * 80)

    print(f"\nTest 1 (Samsung 쿠키 + iPhone TLS): {result1}")
    print(f"Test 2 (iPhone 쿠키 + Samsung TLS): {result2}")

    if result1 is True or result2 is True:
        print("\n✅ 결론: Cross-Device 가능!")
        print("  → 쿠키는 IP만 체크, TLS/UA 무관")
        print("  → 하나의 쿠키로 여러 TLS fingerprint 사용 가능")
        print("  → Fingerprint Rotation 전략 유효!")
    elif result1 is False and result2 is False:
        print("\n❌ 결론: Cross-Device 불가능")
        print("  → 쿠키가 TLS/UA에 바인딩됨")
        print("  → 각 기기마다 별도 쿠키 필요")
        print("  → Fingerprint Rotation 시 쿠키도 함께 로테이션 필요")
    else:
        print("\n⚠️ 결론: 추가 테스트 필요")
        print("  → 일부 성공, 일부 실패")
        print("  → 더 많은 조합으로 테스트 권장")


if __name__ == '__main__':
    main()
