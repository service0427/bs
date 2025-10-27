#!/usr/bin/env python3
"""
Fingerprint 100번 검증 테스트 v3

핵심 변경:
1. 최초 1회 PCID 수집 (메인 페이지 접속)
2. 수집한 PCID로 100번 × 2페이지 연속 테스트
3. PCID 재사용으로 Cross-Device 검증
"""

import sys
sys.path.insert(0, '/var/www/html/browserstack')

import json
import time
from curl_cffi.requests import Session
from datetime import datetime


def collect_pcid(ja3, akamai, extra_fp, headers):
    """
    신선한 PCID 수집 (1회만)

    Returns:
        dict: {PCID, sid, ...} 또는 None
    """
    print(f"\n  🍪 PCID 수집 중...")

    session = Session()

    try:
        response = session.get(
            "https://www.coupang.com/",
            ja3=ja3,
            akamai=akamai,
            extra_fp=extra_fp,
            headers=headers,
            timeout=15,
            allow_redirects=True
        )

        if response.status_code != 200:
            print(f"    ❌ 메인 페이지 접속 실패: {response.status_code}")
            return None

        # 쿠키 확인
        cookies = {k: v for k, v in session.cookies.items()}

        if 'PCID' in cookies:
            print(f"    ✅ PCID 수집 성공: {cookies['PCID'][:20]}...")
            print(f"    → 쿠키 개수: {len(cookies)}개")
            return cookies
        else:
            print(f"    ❌ PCID 없음 (쿠키: {len(cookies)}개)")
            return None

    except Exception as e:
        print(f"    ❌ PCID 수집 실패: {str(e)[:100]}")
        return None


def test_two_pages_with_pcid(ja3, akamai, extra_fp, headers, pcid_cookies, keyword="테스트"):
    """
    PCID 사용하여 2페이지 연속 테스트

    Args:
        pcid_cookies: 수집한 PCID 쿠키

    Returns:
        tuple: (success, error_type, details)
    """
    session = Session()

    try:
        # 페이지 1 (PCID 전달)
        url1 = f"https://www.coupang.com/np/search?q={keyword}&channel=user"
        response1 = session.get(
            url1,
            ja3=ja3,
            akamai=akamai,
            extra_fp=extra_fp,
            headers=headers,
            cookies=pcid_cookies,  # ← PCID 사용!
            timeout=15,
            allow_redirects=True
        )

        status1 = response1.status_code
        size1 = len(response1.content)

        # 페이지 1 실패 체크
        if status1 != 200:
            return (False, 'http_error', {'page': 1, 'status': status1, 'size': size1})

        if size1 < 50000:
            # 앱 리다이렉트 체크 (15KB)
            if 'applink.coupang.com' in response1.text:
                # 앱 리다이렉트는 성공으로 간주하지 않음 (Desktop UA 필요)
                return (False, 'app_redirect', {'page': 1, 'size': size1})
            else:
                # Akamai Challenge
                return (False, 'akamai_challenge', {'page': 1, 'status': status1, 'size': size1})

        # 페이지 1 성공, 이제 페이지 2 테스트
        time.sleep(1)  # 페이지 간 1초 딜레이

        # 페이지 2 (Session이 자동으로 쿠키 유지)
        url2 = f"https://www.coupang.com/np/search?q={keyword}&channel=user&page=2"
        response2 = session.get(
            url2,
            ja3=ja3,
            akamai=akamai,
            extra_fp=extra_fp,
            headers=headers,
            # cookies 파라미터 제거! Session이 자동 관리
            timeout=15,
            allow_redirects=True
        )

        status2 = response2.status_code
        size2 = len(response2.content)

        # 페이지 2 체크
        if status2 != 200:
            return (False, 'page2_http_error', {'page': 2, 'status': status2, 'size': size2})

        if size2 < 50000:
            # 앱 리다이렉트 체크
            if 'applink.coupang.com' in response2.text:
                return (False, 'page2_app_redirect', {'page': 2, 'size': size2})
            else:
                # 페이지 2에서 Akamai Challenge (핵심 실패!)
                return (False, 'page2_akamai_challenge', {'page': 2, 'status': status2, 'size': size2})

        # 두 페이지 모두 성공!
        return (True, None, {
            'page1_size': size1,
            'page2_size': size2
        })

    except Exception as e:
        error_str = str(e)

        if 'HTTP/2' in error_str or 'INTERNAL_ERROR' in error_str:
            return (False, 'http2_error', {'error': error_str[:100]})
        elif 'timeout' in error_str.lower():
            return (False, 'timeout', {'error': error_str[:100]})
        else:
            return (False, 'other_error', {'error': error_str[:100]})


def validate_fingerprint(device_name, browser, os_version, iterations=100, delay=2):
    """
    단일 fingerprint 100번 검증 (PCID 수집 + 2페이지 테스트)
    """
    print(f"\n{'='*80}")
    print(f"[검증 시작] {device_name} / {browser} / {os_version}")
    print(f"{'='*80}")

    # Metadata 로드
    device_dir = f"/var/www/html/browserstack/data/fingerprints/{device_name.replace(' ', '_')}_{browser}_{os_version}"
    metadata_file = f"{device_dir}/metadata.json"

    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    except FileNotFoundError:
        print(f"❌ metadata.json 파일 없음: {metadata_file}")
        return None

    tls = metadata['tls_info']
    ja3 = tls['tls']['ja3']
    akamai = tls['http2']['akamai_fingerprint']
    user_agent = metadata.get('user_agent', '')

    # X25519MLKEM768 체크
    has_mlkem = False
    for ext in tls['tls'].get('extensions', []):
        if ext.get('name') == 'supported_groups':
            groups = ext.get('supported_groups', [])
            if any('4588' in str(g) or 'X25519MLKEM768' in str(g) for g in groups):
                has_mlkem = True
                break

    print(f"  JA3: {ja3[:40]}...")
    print(f"  Akamai: {akamai[:50]}...")
    print(f"  User-Agent: {user_agent[:60]}...")
    print(f"  X25519MLKEM768: {'✅ 있음 (위험!)' if has_mlkem else '❌ 없음 (안전)'}")

    # Headers
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.coupang.com/',
    }

    # extra_fp
    sig_algs = []
    for ext in tls['tls'].get('extensions', []):
        if ext.get('name') == 'signature_algorithms':
            sig_algs = ext.get('signature_algorithms', [])
            break

    cert_compression = 'zlib' if 'iphone' in browser.lower() or 'ipad' in browser.lower() else 'brotli'

    extra_fp = {
        'tls_grease': True,
        'tls_signature_algorithms': sig_algs[:15] if sig_algs else [],
        'tls_cert_compression': cert_compression,
        'tls_min_version': 4,
        'tls_permute_extensions': False,
    }

    # 1. 신선한 PCID 수집 (1회)
    pcid_cookies = collect_pcid(ja3, akamai, extra_fp, headers)

    if pcid_cookies is None:
        print(f"\n❌ PCID 수집 실패! 테스트 중단.")
        return None

    # 2. 100번 테스트 (수집한 PCID 재사용!)
    print(f"\n  🔄 100번 테스트 시작 (각 시도마다 2페이지, PCID 재사용, 딜레이: {delay}초)...")

    results = {
        'both_pages_success': 0,
        'page1_only': 0,
        'page2_akamai_challenge': 0,
        'akamai_challenge': 0,  # 페이지 1부터 차단
        'app_redirect': 0,
        'http2_error': 0,
        'timeout': 0,
        'other_error': 0,
        'total': iterations
    }

    start_time = time.time()

    for i in range(1, iterations + 1):
        success, error_type, details = test_two_pages_with_pcid(
            ja3=ja3,
            akamai=akamai,
            extra_fp=extra_fp,
            headers=headers,
            pcid_cookies=pcid_cookies,  # ← PCID 재사용!
            keyword="테스트"
        )

        if success:
            results['both_pages_success'] += 1
            marker = '✅'
        else:
            # 에러 타입별 분류
            if error_type == 'page2_akamai_challenge':
                results['page2_akamai_challenge'] += 1
                results['page1_only'] += 1
                marker = '🔴'  # 1페이지만 성공
            elif error_type in ['app_redirect', 'page2_app_redirect']:
                results['app_redirect'] += 1
                marker = '📱'
            elif error_type in ['http2_error', 'http_error', 'page2_http_error']:
                results['http2_error'] += 1
                marker = '❌'
            elif error_type == 'timeout':
                results['timeout'] += 1
                marker = '⏱️'
            elif error_type == 'akamai_challenge':
                # 1페이지부터 차단
                results['akamai_challenge'] += 1
                marker = '🚫'
            else:
                results['other_error'] += 1
                marker = '⚠️'

        # 10회마다 진행 상황 출력
        if i % 10 == 0:
            success_rate = results['both_pages_success'] / i * 100
            page1_only_rate = results['page1_only'] / i * 100
            print(f"    {i:3}/100: {marker} (2페이지 성공: {success_rate:5.1f}%, 1페이지만: {page1_only_rate:5.1f}%)")

        # 딜레이
        if i < iterations:
            time.sleep(delay)

    elapsed = time.time() - start_time
    success_rate = results['both_pages_success'] / results['total'] * 100
    page1_only_rate = results['page1_only'] / results['total'] * 100

    # 결과 출력
    print(f"\n  📊 최종 결과:")
    print(f"    총 시도: {results['total']}회")
    print(f"    2페이지 성공: {results['both_pages_success']}회 ({success_rate:.1f}%)")
    print(f"    1페이지만 성공: {results['page1_only']}회 ({page1_only_rate:.1f}%)")
    print(f"    2페이지 Akamai 차단: {results['page2_akamai_challenge']}회")
    print(f"    1페이지 Akamai 차단: {results['akamai_challenge']}회")
    print(f"    앱 리다이렉트: {results['app_redirect']}회")
    print(f"    HTTP/2 에러: {results['http2_error']}회")
    print(f"    Timeout: {results['timeout']}회")
    print(f"    기타 에러: {results['other_error']}회")
    print(f"    소요 시간: {elapsed/60:.1f}분")

    # 결론
    print(f"\n  🎯 결론:")
    if success_rate >= 80:
        verdict = "✅ 사용 가능"
        print(f"    {verdict}")
        print(f"    → 2페이지 연속 성공 ({success_rate:.1f}%)")
        print(f"    → curl-cffi 재현 가능, 세션 유지 OK")
    elif success_rate >= 20:
        verdict = "⚠️ 주의 사용"
        print(f"    {verdict}")
        print(f"    → 2페이지 성공률 낮음 ({success_rate:.1f}%)")
        if page1_only_rate > 50:
            print(f"    → ⚠️  1페이지만 성공하는 케이스 많음 ({page1_only_rate:.1f}%)")
            print(f"    → 2페이지 검증에서 차단됨 (Akamai 점진적 봇 탐지)")
    else:
        verdict = "❌ 완전 배제"
        print(f"    {verdict}")
        print(f"    → 2페이지 성공률 극히 낮음 ({success_rate:.1f}%)")
        if page1_only_rate > 0:
            print(f"    → 🔴 1페이지는 통과하나 2페이지에서 봇 탐지!")
            print(f"    → Akamai 점진적 검증 실패 (세션 불일치)")
        print(f"    → 사용 금지")

    return {
        'device_name': device_name,
        'browser': browser,
        'os_version': os_version,
        'has_mlkem768': has_mlkem,
        'results': results,
        'success_rate': success_rate,
        'page1_only_rate': page1_only_rate,
        'elapsed_seconds': elapsed,
        'verdict': verdict,
        'tested_at': datetime.now().isoformat()
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fingerprint 100번 검증 v3 (PCID 재사용)')
    parser.add_argument('--device', required=True, help='기기명')
    parser.add_argument('--browser', required=True, help='브라우저')
    parser.add_argument('--os-version', required=True, help='OS 버전')
    parser.add_argument('--iterations', type=int, default=100, help='반복 횟수 (기본: 100)')
    parser.add_argument('--delay', type=float, default=2.0, help='요청 간 딜레이 초 (기본: 2.0)')

    args = parser.parse_args()

    result = validate_fingerprint(
        device_name=args.device,
        browser=args.browser,
        os_version=args.os_version,
        iterations=args.iterations,
        delay=args.delay
    )

    if result:
        # JSON 저장
        output_file = f"/var/www/html/browserstack/data/validation_results/{args.device.replace(' ', '_')}_{args.browser}_{args.os_version}_100x_v3.json"

        import os
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 결과 저장: {output_file}")


if __name__ == '__main__':
    main()
