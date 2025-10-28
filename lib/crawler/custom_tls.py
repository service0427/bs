"""
커스텀 TLS 크롤러 모듈
curl-cffi JA3 fingerprint를 사용한 TLS 기반 크롤링
"""

import sys
import os
import time
from urllib.parse import quote

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curl_cffi import requests
from curl_cffi.requests import Session
from lib.device.tls_builder import load_fingerprint_data
from lib.logs.checkpoint import Checkpoint
from lib.product_extractor import ProductExtractor


def delete_blocked_cookies(device_name, worker_id=None):
    """
    차단된 쿠키 파일 삭제

    Args:
        device_name: 디바이스 이름
        worker_id: Worker ID (None이면 원본 쿠키 삭제하지 않음)
    """
    safe_device_name = device_name.replace(' ', '_').replace('/', '_')
    # lib/crawler/ → lib/ → 프로젝트 루트
    fingerprint_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'data',
        'fingerprints',
        safe_device_name
    )

    if worker_id is not None:
        # Worker용 쿠키만 삭제
        cookies_file = os.path.join(fingerprint_dir, f'cookies_packet_{worker_id}.json')
        if os.path.exists(cookies_file):
            os.remove(cookies_file)
            print(f"\n  🗑️ Worker {worker_id} 쿠키 삭제됨 (차단 감지)")
            return True
    else:
        # 원본 쿠키는 삭제하지 않음 (단일 worker 모드에서도 원본 유지)
        print(f"\n  ⚠️ 차단 감지 - 쿠키 재수집 필요")

    return False


class CustomTLSCrawler:
    """커스텀 TLS 설정을 사용하는 크롤러"""

    def __init__(self, device_name, browser, device_config=None, worker_id=None):
        """
        Args:
            device_name: 디바이스 이름
            browser: 브라우저 이름 (safari, chrome, chromium 등)
            device_config: 디바이스 설정 dict (os_version 추출용, None이면 레거시 모드)
            worker_id: Worker ID (병렬 크롤링용, None이면 원본 쿠키 사용)
        """
        self.device_name = device_name
        self.browser = browser
        self.os_version = device_config.get('os_version') if device_config else None
        self.worker_id = worker_id
        self.session = Session()  # TLS 연결 재사용 + 쿠키 자동 관리

        # 크롤링 세션 ID 생성 (쿠키 추적용)
        from datetime import datetime
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')

    def crawl_page(self, keyword='아이폰', page=1, max_retries=None):
        """
        단일 페이지 크롤링

        원본 쿠키는 수정하지 않고 매번 fingerprint에서 로드하여 사용

        Args:
            keyword: 검색 키워드
            page: 페이지 번호
            max_retries: HTTP2 프로토콜 에러 시 재시도 횟수 (None이면 자동 설정)
                        - 리얼 기기 (worker_id=None): 1회 (재시도 불필요)
                        - 패킷 모드 (worker_id 있음): 5회 (한순간 풀릴 수 있음)

        Returns:
            dict: {
                'success': bool,
                'keyword': str,
                'page': int,
                'ranking': list,
                'ads': list,
                'total': int
            }
        """

        # max_retries 자동 설정 (HTTP2 에러 대비)
        if max_retries is None:
            max_retries = 3  # HTTP2 에러 시 3회 연속 실패까지 재시도

        mode_label = f"패킷 모드 (Worker {self.worker_id})" if self.worker_id else "리얼 기기 모드"

        print("\n" + "="*60)
        print(f"curl-cffi 커스텀 TLS 크롤링 - 페이지 {page}")
        print("="*60)
        print(f"검색 키워드: {keyword}")
        print(f"페이지: {page}")
        print(f"모드: {mode_label} (최대 시도: {max_retries}회, HTTP2 에러 시 3초마다 재시도)")
        print("="*60 + "\n")

        # 1. Fingerprint 데이터 로드 (매번 원본에서 로드)
        worker_label = f" [Worker {self.worker_id}]" if self.worker_id else ""
        print(f"[STEP 1] Fingerprint 데이터 로드{worker_label}")
        data = load_fingerprint_data(self.device_name, self.browser, self.os_version, worker_id=self.worker_id)

        # 쿠키는 DB에서 먼저 시도, 없으면 파일에서 로드
        cookies = []
        cookie_source = "파일"

        try:
            from lib.db.manager import DBManager
            db = DBManager()
            cookie_record = db.get_latest_original_cookie(self.device_name, self.browser, self.os_version)

            if cookie_record:
                import json
                cookies = json.loads(cookie_record[4])  # cookie_data 컬럼 (index 4)
                cookie_source = "DB"
        except Exception as e:
            print(f"  ⚠️  DB 쿠키 로드 실패: {e}")

        # DB에 없으면 파일에서 로드
        if not cookies:
            cookies = data.get('cookies', [])
            cookie_source = "파일"

        headers = data.get('headers', {})
        tls = data.get('tls', {})

        # [FINAL] 쿠키 관리 전략 - PCID, sid 모두 원본 유지
        # 결론: sid는 서버에서 /n-api/recommend/feeds 호출 시 발급되는 중요한 세션 정보
        #       PCID와 sid는 쌍(pair)으로 유지되어야 함
        #       둘 다 BrowserStack 수집값 그대로 사용 = 유효한 세션

        # 모든 쿠키 그대로 사용 (PCID, sid 포함)
        cookie_dict = {
            c['name']: c['value']
            for c in cookies
        }

        if page == 1:
            has_pcid = 'PCID' in cookie_dict
            has_sid = 'sid' in cookie_dict
            print(f"  ✓ 쿠키: {len(cookie_dict)}개 (출처: {cookie_source})")
            print(f"      PCID: {'있음 ✅' if has_pcid else '없음 ❌'}")
            print(f"      sid: {'있음 ✅' if has_sid else '없음 ❌'}")
        else:
            # Session 쿠키 확인 (curl-cffi Session이 자동 관리)
            session_cookie_count = len(self.session.cookies) if hasattr(self.session, 'cookies') else 0
            print(f"  ✓ 쿠키: Session 자동 관리 중")
            print(f"      Session 쿠키: {session_cookie_count}개 (1페이지 Set-Cookie 포함)")
            print()

        print(f"  ✓ TLS 정보: 로드 완료")

        # browserleaks 형식과 peet.ws 형식 모두 지원
        # peet.ws: data['tls'] = {'tls': {...}, 'http2': {...}}
        # browserleaks: data['tls'] = {...}, data['http2'] = {...}
        if 'ja3' in tls:
            # browserleaks 형식: tls가 바로 TLS 데이터
            tls_data = tls
            http2_data = data.get('http2', {})
        else:
            # peet.ws 형식: tls 안에 tls/http2가 중첩
            tls_data = tls.get('tls', tls)
            http2_data = tls.get('http2', {})

        # cipher_suites (full format) 또는 ciphers (minimal format)
        cipher_list = tls_data.get('cipher_suites', tls_data.get('ciphers', []))
        print(f"  ✓ JA3 Hash: {tls_data.get('ja3_hash', 'N/A')}")
        print(f"  ✓ Cipher Suites: {len(cipher_list)}개")
        print()

        # 2. JA3 / Akamai / extra_fp 추출
        print("[STEP 2] TLS Fingerprint 추출")
        ja3 = tls_data.get('ja3', '')
        akamai = http2_data.get('akamai_fingerprint', '')

        if not ja3:
            raise ValueError("JA3 fingerprint가 없습니다.")

        print(f"  ✓ JA3: {ja3[:60]}...")
        if akamai:
            print(f"  ✓ Akamai: {akamai}")

        # extra_fp 구성 (개선된 전체 옵션)
        extra_fp = {}

        # 1) TLS GREASE 감지 (Chrome 필수!)
        # cipher 형식 확인: 객체 배열 vs ID 문자열 배열
        has_grease = False
        if cipher_list:
            if isinstance(cipher_list[0], dict):
                # Full format: {"id": 10794, "name": "GREASE"}
                has_grease = any('GREASE' in c.get('name', '') for c in cipher_list)
            else:
                # Minimal format: ["4865", "4866", ...]
                has_grease = any('GREASE' in str(c) or '0x' in str(c) for c in cipher_list)

        if has_grease:
            extra_fp['tls_grease'] = True
            print(f"  ✓ TLS GREASE: 활성화 (Chrome 특징)")

        # 2) signature_algorithms 추출
        extensions = tls_data.get('extensions', [])

        # extensions 형식 확인: 객체 배열 vs ID 문자열 배열
        has_extension_objects = (extensions and
                                isinstance(extensions, list) and
                                len(extensions) > 0 and
                                isinstance(extensions[0], dict))

        if has_extension_objects:
            # Full structure: extension 객체 배열 (browserleaks full format)
            for ext in extensions:
                ext_name = ext.get('name', '')
                ext_data = ext.get('data', {})

                # signature_algorithms
                if ext_name == 'signature_algorithms':
                    algorithms = ext_data.get('algorithms', [])
                    if algorithms:
                        # 알고리즘 ID 리스트 추출
                        algo_ids = [str(a.get('id', a)) if isinstance(a, dict) else str(a) for a in algorithms]
                        extra_fp['tls_signature_algorithms'] = algo_ids
                        print(f"  ✓ Signature Algorithms: {len(algo_ids)}개")

                # compress_certificate
                elif ext_name == 'compress_certificate':
                    algorithms = ext_data.get('algorithms', [])
                    if algorithms:
                        # 첫 번째 알고리즘 이름 추출
                        algo = algorithms[0]
                        if isinstance(algo, dict):
                            algo_name = algo.get('name', '').lower()
                        else:
                            algo_name = str(algo).split()[0].lower()
                        if algo_name:
                            extra_fp['tls_cert_compression'] = algo_name
                            print(f"  ✓ Certificate Compression: {algo_name}")

                # supported_versions
                elif ext_name == 'supported_versions':
                    versions = ext_data.get('supported_versions', [])
                    if versions:
                        # GREASE 제외하고 실제 버전 확인
                        real_versions = [v.get('name', v) if isinstance(v, dict) else v
                                       for v in versions
                                       if 'GREASE' not in str(v)]
                        if any('TLS 1.2' in str(v) for v in real_versions):
                            extra_fp['tls_min_version'] = 4  # CurlSslVersion.TLSv1_2
                            print(f"  ✓ TLS Min Version: TLSv1.2")
        else:
            # Minimal structure: extension ID 문자열 배열 (parsed from JA3)
            print(f"  ℹ️  Extensions: ID만 포함 (상세 정보 없음, {len(extensions)}개)")
            # ID만으로는 상세 정보 추출 불가, 기본 설정 사용

        # 5) Extension 순서 완전 고정
        extra_fp['tls_permute_extensions'] = False  # 랜덤화 비활성화

        # JA3 string에 이미 extensions 순서가 포함되어 있음
        # 포맷: SSLVersion,Ciphers,Extensions,EllipticCurves,EllipticCurvePointFormats
        ja3_parts = ja3.split(',')
        if len(ja3_parts) >= 3:
            extensions_part = ja3_parts[2]  # Extensions 부분
            print(f"  ✓ Extensions 순서: 고정 (JA3: {extensions_part[:40]}...)")
        else:
            print(f"  ✓ Extensions 순서: 고정 (permute=False)")

        # 6) ALPN 추출 (JA3에 포함 안 됨 - 별도 설정 필수!)
        alpn_protocols = None
        if has_extension_objects:
            for ext in extensions:
                ext_name = ext.get('name', '').lower()
                if 'application_layer_protocol' in ext_name:
                    ext_data = ext.get('data', {})
                    alpn_protocols = ext_data.get('protocol_name_list', [])
                    if alpn_protocols:
                        print(f"  ✓ ALPN: {', '.join(alpn_protocols)}")
                    break

        # 7) HTTP/2 priority 추출
        sent_frames = http2_data.get('sent_frames', [])
        for frame in sent_frames:
            if frame.get('frame_type') == 'HEADERS' and 'priority' in frame:
                priority = frame['priority']
                extra_fp['http2_stream_weight'] = priority.get('weight', 256)
                extra_fp['http2_stream_exclusive'] = priority.get('exclusive', 1)
                print(f"  ✓ HTTP/2 Priority: weight={extra_fp['http2_stream_weight']}, exclusive={extra_fp['http2_stream_exclusive']}")
                break

        # 8) HTTP/2 Priority 프레임 사용 (no_priority 비활성화)
        extra_fp['http2_no_priority'] = False

        # 디버깅: extra_fp 전체 출력
        print(f"\n  [extra_fp 설정 요약]")
        for key, value in extra_fp.items():
            if key == 'tls_signature_algorithms':
                print(f"    • {key}: {len(value)}개 알고리즘")
            else:
                print(f"    • {key}: {value}")

        if alpn_protocols:
            print(f"    • ALPN (별도): {alpn_protocols}")

        print()

        # 3. curl-cffi 요청 (JA3 방식, 재시도 로직 포함)
        print("[STEP 3] curl-cffi JA3 TLS 요청")

        # 검색 URL 생성 (직접 접속 시 서버가 PCID, sid 자동 발급)
        search_url = f"https://www.coupang.com/np/search?q={quote(keyword)}&page={page}"
        print(f"  URL: {search_url}")
        print(f"  최대 시도: {max_retries}회 (실패 시 3초마다 재시도)\n")

        # Referer 설정 (모든 페이지)
        if page == 1:
            # 1페이지: 메인 페이지에서 검색한 것처럼
            headers['Referer'] = 'https://www.coupang.com/'
            headers['Sec-Fetch-Site'] = 'same-origin'
            print(f"  Referer: https://www.coupang.com/ (메인 페이지)")
        else:
            # 2페이지 이상: 이전 페이지 URL
            prev_url = f"https://www.coupang.com/np/search?q={quote(keyword)}&page={page-1}"
            headers['Referer'] = prev_url
            headers['Sec-Fetch-Site'] = 'same-origin'
            print(f"  Referer: {prev_url[:60]}...")

        status_code = None
        response_text = None
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    # HTTP2 에러 재시도 대기 (3초)
                    wait_time = 3
                    print(f"  ⏳ 재시도 {attempt}/{max_retries} (대기 {wait_time}초)...")
                    time.sleep(wait_time)

                # [디버깅] 요청 헤더 확인
                print(f"\n[디버깅] 요청 헤더 (페이지 {page}):")
                print(f"  {'='*56}")
                for key, value in list(headers.items())[:15]:  # 최대 15개
                    print(f"  {key}: {str(value)[:60]}")
                print(f"  {'='*56}\n")

                # JA3 방식으로 요청 (Session 사용 - TLS 연결 재사용)
                # ALPN 설정 방법 (curl-cffi 버전에 따라 다를 수 있음):
                # 옵션 1: alpn 파라미터 (지원 시)
                # 옵션 2: http_version="v2" (h2 강제)
                # 옵션 3: akamai fingerprint가 ALPN 포함 (이미 사용 중)

                # [FINAL] 쿠키 전달 전략 - PCID, sid 원본 유지 (서버 발급값 사용)
                request_params = {
                    'ja3': ja3,
                    'akamai': akamai if akamai else None,
                    'extra_fp': extra_fp if extra_fp else None,
                    'headers': headers,
                    'cookies': cookie_dict if page == 1 else None,  # 첫 페이지만 전달, 이후 Session 자동
                    'timeout': 30,
                    'verify': True
                }

                print(f"  [쿠키 전략] PCID, sid 원본 유지 (서버 발급값)")
                if page == 1:
                    print(f"      첫 페이지 - 쿠키 {len(cookie_dict)}개 전달")
                    has_pcid = 'PCID' in cookie_dict
                    has_sid = 'sid' in cookie_dict
                    print(f"          PCID: {'전달 ✅' if has_pcid else '없음 ❌'}")
                    print(f"          sid: {'전달 ✅' if has_sid else '없음 ❌'}")
                else:
                    session_count = len(self.session.cookies) if hasattr(self.session, 'cookies') else 0
                    print(f"      Session 쿠키: {session_count}개 (자동 전달)")

                # HTTP/2 강제 (ALPN h2 자동 설정)
                if alpn_protocols and 'h2' in alpn_protocols:
                    request_params['http_version'] = 'v2'

                # ALPN 명시적 설정 시도 (curl-cffi 버전에 따라 지원 여부 다름)
                # 주석: 지원되지 않으면 에러 발생할 수 있음
                # if alpn_protocols:
                #     try:
                #         request_params['alpn'] = alpn_protocols
                #     except:
                #         pass  # alpn 파라미터 미지원 시 무시

                # 응답 시간 측정 시작
                import time as time_module
                request_start_time = time_module.time()

                response = self.session.get(search_url, **request_params)

                # 응답 시간 계산 (ms)
                response_time_ms = int((time_module.time() - request_start_time) * 1000)

                status_code = response.status_code
                response_text = response.text
                response_size_bytes = len(response.content) if hasattr(response, 'content') else len(response_text)

                # [디버깅] Set-Cookie 헤더 전체 분석
                session_cookie_names = ['PCID', 'sid', 'sessionid', 'session', 'JSESSIONID']
                received_cookies = []

                # 응답에서 수신된 세션 쿠키 확인
                for cookie_name in session_cookie_names:
                    if cookie_name in response.cookies:
                        received_cookies.append(cookie_name)

                print(f"\n[디버깅] Set-Cookie 분석 (페이지 {page}):")
                print(f"  {'='*56}")

                # 1. response.cookies 확인
                all_response_cookies = dict(response.cookies)
                print(f"  [1] response.cookies: {len(all_response_cookies)}개")
                for name, value in all_response_cookies.items():
                    print(f"      - {name}: {str(value)[:40]}...")

                # 2. Set-Cookie 헤더 직접 확인 (다양한 방법으로)
                if hasattr(response, 'headers'):
                    print(f"\n  [2] Set-Cookie 헤더 분석:")

                    # 방법 1: get_list()
                    set_cookie_headers = []
                    if hasattr(response.headers, 'get_list'):
                        set_cookie_headers = response.headers.get_list('Set-Cookie')

                    # 방법 2: get()
                    if not set_cookie_headers and hasattr(response.headers, 'get'):
                        single_header = response.headers.get('Set-Cookie')
                        if single_header:
                            set_cookie_headers = [single_header]

                    # 방법 3: getlist() (소문자)
                    if not set_cookie_headers and hasattr(response.headers, 'getlist'):
                        set_cookie_headers = response.headers.getlist('Set-Cookie')

                    # 방법 4: 직접 순회
                    if not set_cookie_headers:
                        try:
                            for key, value in response.headers.items():
                                if key.lower() == 'set-cookie':
                                    set_cookie_headers.append(value)
                        except:
                            pass

                    if set_cookie_headers:
                        print(f"      총 {len(set_cookie_headers)}개 발견")
                        for i, header in enumerate(set_cookie_headers[:10], 1):  # 최대 10개
                            cookie_name = header.split('=')[0] if '=' in header else 'unknown'
                            # sid 확인
                            if 'sid=' in header:
                                print(f"      {i}. {cookie_name}: {header[:80]}... ✅ sid 발견!")
                            else:
                                print(f"      {i}. {cookie_name}: {header[:60]}...")
                    else:
                        print(f"      ❌ Set-Cookie 헤더 없음 (모든 방법 시도했으나 발견 못함)")

                        # 전체 헤더 확인
                        print(f"\n      [전체 응답 헤더 확인]")
                        try:
                            all_headers = dict(response.headers)
                            for key in list(all_headers.keys())[:10]:
                                print(f"        - {key}: {str(all_headers[key])[:50]}...")
                        except:
                            print(f"        (헤더 출력 실패)")

                # 3. Session.cookies 확인
                if hasattr(self.session, 'cookies'):
                    session_cookies_count = len(self.session.cookies)
                    print(f"\n  [3] Session.cookies (자동 저장): {session_cookies_count}개")

                    # PCID 확인
                    if 'PCID' in self.session.cookies:
                        pcid = self.session.cookies.get('PCID', '')
                        print(f"      - PCID: {str(pcid)[:40]}... ✅")
                    else:
                        print(f"      - PCID: ❌ 없음")

                    # sid 확인
                    if 'sid' in self.session.cookies:
                        sid = self.session.cookies.get('sid', '')
                        print(f"      - sid: {str(sid)[:40]}... ✅")
                    else:
                        print(f"      - sid: ❌ 없음")

                print(f"  {'='*56}\n")

                # 결과 요약
                if received_cookies:
                    print(f"  ✓ 세션 쿠키 수신: {', '.join(received_cookies)}")
                else:
                    print(f"  ⚠️  PCID, sid 미수신 (서버에서 발급 안 함)")

                # [디버깅] 실제 전송된 TLS fingerprint 확인 (extensions 순서 검증)
                # 참고: curl-cffi Session은 내부적으로 JA3를 사용하므로
                # 실제 핸드셰이크에서 extensions 순서가 고정되어야 함
                print(f"\n  [TLS 검증] 전송된 JA3 Hash: {tls_data.get('ja3_hash', 'N/A')}")
                print(f"  [TLS 검증] tls_permute_extensions: False (고정)")
                print(f"  [TLS 검증] Extensions 수: {len(extensions)}개")

                # [테스트용] Akamai 쿠키 업데이트 (환경변수로 활성화)
                from lib.utils.akamai_updater import update_akamai_cookies, is_enabled
                if is_enabled():
                    result = update_akamai_cookies(self.device_name, self.browser, response.cookies, self.worker_id)
                    if result['updated']:
                        print(f"  🔄 Akamai 쿠키 업데이트: {', '.join(result['cookies'])} ({result['count']}개)")
                    # 업데이트 실패는 조용히 무시 (테스트용이므로)

                print(f"  ✓ 응답 수신 (시도 {attempt}/{max_retries})\n")
                break  # 성공하면 루프 종료

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # HTTP2 프로토콜 에러 확인
                is_http2_error = 'http2' in error_msg or 'protocol' in error_msg or 'stream' in error_msg

                # 에러 메시지 간결화
                if 'curl: (92)' in str(e):
                    error_short = "INTERNAL_ERROR (curl 92)"
                elif 'curl:' in str(e):
                    import re
                    match = re.search(r'curl: \((\d+)\)', str(e))
                    if match:
                        error_short = f"curl error {match.group(1)}"
                    else:
                        error_short = str(e)[:60]
                else:
                    error_short = str(e)[:60]

                # HTTP2 에러가 아니면 재시도 없이 바로 실패
                if not is_http2_error:
                    print(f"  ❌ 요청 실패 (재시도 불가능한 에러): {error_short}")
                    raise

                # HTTP2 에러는 3회까지 재시도
                print(f"  ⚠️ HTTP2 에러 (시도 {attempt}/{max_retries}): {error_short}")

                # 마지막 시도였다면 에러 발생
                if attempt == max_retries:
                    print(f"\n  ❌ 3회 연속 실패로 종료\n")
                    raise

                # 다음 재시도 안내
                print(f"  → 3초 후 재시도...")

        if response_text is None:
            raise Exception(f"응답을 받지 못했습니다: {last_error}")

        try:
            # 4. 응답 분석
            print("[STEP 4] 응답 분석")
            print(f"  상태 코드: {status_code}")
            print(f"  응답 크기: {len(response_text):,} bytes")

            # 차단 여부 확인
            print("\n[STEP 5] 차단 여부 확인")

            blocked = False
            block_indicators = ['captcha', 'robot', 'access denied', 'blocked']

            response_lower = response_text.lower()
            for indicator in block_indicators:
                if indicator in response_lower:
                    print(f"  ⚠️ 차단 감지: '{indicator}'")
                    blocked = True

            if not blocked:
                print("  ✓ 차단 없음 - 정상 응답")

            # 6. 상품 정보 추출
            print("\n[STEP 6] 상품 정보 추출")

            extracted = ProductExtractor.extract_products_from_html(response_text)

            ranking_count = len(extracted['ranking'])
            ads_count = len(extracted['ads'])
            total_count = extracted['total']

            print(f"  랭킹 상품: {ranking_count}개")
            print(f"  광고 상품: {ads_count}개")
            print(f"  전체 상품: {total_count}개")

            if ranking_count > 0:
                print(f"\n  랭킹 상품 샘플 (최대 3개):")
                for i, product in enumerate(extracted['ranking'][:3], 1):
                    print(f"    {i}. {product['name'][:40]}...")
                    print(f"       가격: {product['price']}")
                    print(f"       순위: {product['rank']}")
                    print(f"       ID: {product['uniqueKey'][:30]}...")

            # Akamai 차단 감지
            is_akamai_blocked, akamai_challenge_type = self._detect_akamai_block(response)
            bm_sc_cookie = response.cookies.get('bm_sc', '') if hasattr(response, 'cookies') else ''

            if is_akamai_blocked:
                print(f"\n  ⚠️ Akamai 차단 감지: {akamai_challenge_type}")
                if bm_sc_cookie:
                    print(f"     bm_sc 쿠키: {bm_sc_cookie[:50]}...")

            # 상품을 DB에 저장 (성공 시에만)
            if status_code == 200 and not blocked and total_count > 0 and not is_akamai_blocked:
                try:
                    from lib.db.manager import DBManager
                    db = DBManager()

                    # 상품 목록 변환 (랭킹 + 광고)
                    products_to_save = []

                    # 랭킹 상품
                    for rank_product in extracted['ranking']:
                        products_to_save.append({
                            'type': 'ranking',
                            'name': rank_product.get('name'),
                            'price': rank_product.get('price'),
                            'url': rank_product.get('productUrl'),
                            'image_url': rank_product.get('imageUrl'),
                            'rank_position': rank_product.get('rank')
                        })

                    # 광고 상품
                    for ad_product in extracted['ads']:
                        products_to_save.append({
                            'type': 'ad',
                            'name': ad_product.get('name'),
                            'price': ad_product.get('price'),
                            'url': ad_product.get('productUrl'),
                            'image_url': ad_product.get('imageUrl'),
                            'ad_slot': ad_product.get('adId'),
                            'ad_type': ad_product.get('adDisplayInfo', {}).get('groupName'),
                            'ad_position': ad_product.get('adDisplayInfo', {}).get('positionNumber')
                        })

                    # 일괄 저장
                    if products_to_save:
                        saved_count = db.save_products_batch(
                            session_id=self.session_id,
                            device_name=self.device_name,
                            browser=self.browser,
                            os_version=self.os_version,
                            keyword=keyword,
                            page_number=page,
                            products_list=products_to_save
                        )
                        print(f"  ✓ 상품 DB 저장 완료: {saved_count}개")

                except Exception as e:
                    print(f"  ⚠️ 상품 DB 저장 실패: {e}")

            # 결과
            print("\n" + "="*60)
            if status_code == 200 and not blocked and total_count > 0:
                print("✅ 성공! JA3 TLS Fingerprint로 쿠팡 검색 크롤링 완료")
                print("="*60)
                print(f"\n[크롤링 결과]")
                print(f"  - 검색 키워드: {keyword}")
                print(f"  - 페이지: {page}")
                print(f"  - 랭킹 상품: {ranking_count}개")
                print(f"  - 광고 상품: {ads_count}개")
                print(f"\n[적용된 TLS Fingerprint]")
                print(f"  - JA3: {ja3[:60]}...")
                print(f"  - JA3 Hash: {tls_data.get('ja3_hash', 'N/A')}")
                if akamai:
                    print(f"  - Akamai: {akamai[:60]}...")
                print(f"  - 쿠키: {len(cookie_dict)}개")
                print(f"  - 헤더: {len(headers)}개")

                # 세션 쿠키 상태 확인 (PCID, sid)
                cookies_status = {
                    'PCID': False,
                    'sid': False
                }
                if hasattr(self.session, 'cookies'):
                    cookies_status['PCID'] = 'PCID' in self.session.cookies
                    cookies_status['sid'] = 'sid' in self.session.cookies

                # 업데이트된 쿠키를 DB에 저장 (성공 시만)
                try:
                    from lib.db.manager import DBManager
                    import json

                    # Session 쿠키를 dict로 변환
                    session_cookies = []
                    if hasattr(self.session, 'cookies'):
                        for name, value in self.session.cookies.items():
                            session_cookies.append({
                                'name': name,
                                'value': value,
                                'domain': '.coupang.com'  # 기본값
                            })

                    if session_cookies:
                        db = DBManager()
                        cookie_id = db.save_cookie(
                            device_name=self.device_name,
                            browser=self.browser,
                            os_version=self.os_version,
                            cookie_data=session_cookies,
                            cookie_type='updated',
                            session_id=self.session_id,
                            page_number=page
                        )
                        print(f"  ✓ 업데이트 쿠키 DB 저장 완료 (ID: {cookie_id}, 페이지: {page})")

                except Exception as e:
                    print(f"  ⚠️  쿠키 DB 저장 실패: {e}")

                # 크롤링 세부 정보 저장 (성공)
                try:
                    from lib.db.manager import DBManager
                    db = DBManager()

                    detail_data = {
                        'worker_id': self.worker_id,
                        'response_size_bytes': response_size_bytes,
                        'response_time_ms': response_time_ms,
                        'http_status_code': status_code,
                        'is_akamai_blocked': is_akamai_blocked,
                        'akamai_challenge_type': akamai_challenge_type,
                        'bm_sc_cookie': bm_sc_cookie,
                        'ranking_products_count': ranking_count,
                        'ad_products_count': ads_count,
                        'total_products_count': total_count,
                        'cookie_source': cookie_source,
                        'cookie_count': len(cookie_dict),
                        'has_pcid': cookies_status.get('PCID', False),
                        'has_sid': cookies_status.get('sid', False),
                        'attempt_number': attempt,
                        'max_attempts': max_retries
                    }

                    db.save_crawl_detail(
                        session_id=self.session_id,
                        device_name=self.device_name,
                        browser=self.browser,
                        os_version=self.os_version,
                        keyword=keyword,
                        page_number=page,
                        status='success',
                        detail_data=detail_data
                    )
                    print(f"  ✓ 크롤링 세부 정보 DB 저장 완료")

                except Exception as e:
                    print(f"  ⚠️ 크롤링 세부 정보 저장 실패: {e}")

                return {
                    'success': True,
                    'keyword': keyword,
                    'page': page,
                    'ranking': extracted['ranking'],
                    'ads': extracted['ads'],
                    'total': total_count,
                    'cookies': cookies_status,
                    'html': response_text  # HTML 추가 (test_ad_rotation.py용)
                }
            else:
                print("⚠️ 응답 수신했으나 문제 발생")
                print("="*60)
                if blocked:
                    print("  - 차단 감지")
                if total_count == 0:
                    print("  - 상품 정보 추출 실패")

                    # 디버깅: 응답 내용 샘플 출력
                    print("\n  응답 내용 디버깅 (처음 500자):")
                    print("  " + "-"*56)
                    preview = response_text[:500].replace('\n', '\n  ')
                    print(f"  {preview}")
                    print("  " + "-"*56)

                    # #productList 또는 #product-list 존재 확인
                    if '#productList' in response_text or '#product-list' in response_text or 'productList' in response_text:
                        print("\n  ⚠️ productList 요소는 존재하지만 상품이 추출되지 않음")
                    else:
                        print("\n  ⚠️ productList 요소가 응답에 없음 (차단 또는 빈 페이지 가능성)")

                # 차단 감지 시 쿠키 삭제
                if blocked or total_count == 0:
                    delete_blocked_cookies(self.device_name, self.worker_id)
                    # Session 쿠키는 자동 관리됨 (리셋 불필요)

                # 세션 쿠키 상태 확인 (실패 시에도 기록)
                cookies_status = {
                    'PCID': False,
                    'sid': False
                }
                if hasattr(self.session, 'cookies'):
                    cookies_status['PCID'] = 'PCID' in self.session.cookies
                    cookies_status['sid'] = 'sid' in self.session.cookies

                # 크롤링 세부 정보 저장 (실패 - 차단 또는 상품 없음)
                try:
                    from lib.db.manager import DBManager
                    db = DBManager()

                    # 상태 결정
                    if is_akamai_blocked:
                        status = 'akamai_challenge'
                    elif blocked:
                        status = 'blocked'  # 다른 차단 (captcha, robot 등)
                    elif total_count == 0:
                        status = 'no_products'
                    else:
                        status = 'unknown_error'

                    detail_data = {
                        'worker_id': self.worker_id,
                        'response_size_bytes': response_size_bytes,
                        'response_time_ms': response_time_ms,
                        'http_status_code': status_code,
                        'is_akamai_blocked': is_akamai_blocked,
                        'akamai_challenge_type': akamai_challenge_type,
                        'bm_sc_cookie': bm_sc_cookie,
                        'ranking_products_count': ranking_count,
                        'ad_products_count': ads_count,
                        'total_products_count': total_count,
                        'cookie_source': cookie_source,
                        'cookie_count': len(cookie_dict),
                        'has_pcid': cookies_status.get('PCID', False),
                        'has_sid': cookies_status.get('sid', False),
                        'attempt_number': attempt,
                        'max_attempts': max_retries
                    }

                    db.save_crawl_detail(
                        session_id=self.session_id,
                        device_name=self.device_name,
                        browser=self.browser,
                        os_version=self.os_version,
                        keyword=keyword,
                        page_number=page,
                        status=status,
                        detail_data=detail_data
                    )
                    print(f"  ✓ 크롤링 세부 정보 DB 저장 완료 (상태: {status})")

                except Exception as e:
                    print(f"  ⚠️ 크롤링 세부 정보 저장 실패: {e}")

                return {
                    'success': False,
                    'keyword': keyword,
                    'page': page,
                    'error': 'blocked' if blocked else 'no_products',
                    'cookies': cookies_status,
                    'html': response_text  # HTML 추가 (차단/빈 페이지 디버깅용)
                }

        except Exception as e:
            error_short = str(e)[:80] if len(str(e)) > 80 else str(e)
            print(f"\n  ❌ 처리 실패: {error_short}")

            # 세션 쿠키 상태 확인 (에러 시에도 기록)
            cookies_status = {
                'PCID': False,
                'sid': False
            }
            if hasattr(self.session, 'cookies'):
                cookies_status['PCID'] = 'PCID' in self.session.cookies
                cookies_status['sid'] = 'sid' in self.session.cookies

            # 크롤링 세부 정보 저장 (예외 발생)
            try:
                from lib.db.manager import DBManager
                db = DBManager()

                # 에러 타입 분류
                error_type = self._classify_error(e)

                # 변수가 정의되어 있는지 확인하고 기본값 사용
                detail_data = {
                    'worker_id': self.worker_id,
                    'error_message': str(e),
                    'error_type': error_type,
                    'response_size_bytes': response_size_bytes if 'response_size_bytes' in locals() else None,
                    'response_time_ms': response_time_ms if 'response_time_ms' in locals() else None,
                    'http_status_code': status_code if 'status_code' in locals() else None,
                    'is_akamai_blocked': False,
                    'ranking_products_count': 0,
                    'ad_products_count': 0,
                    'total_products_count': 0,
                    'cookie_source': cookie_source if 'cookie_source' in locals() else 'none',
                    'cookie_count': len(cookie_dict) if 'cookie_dict' in locals() else 0,
                    'has_pcid': cookies_status.get('PCID', False),
                    'has_sid': cookies_status.get('sid', False),
                    'attempt_number': attempt if 'attempt' in locals() else 1,
                    'max_attempts': max_retries
                }

                db.save_crawl_detail(
                    session_id=self.session_id,
                    device_name=self.device_name,
                    browser=self.browser,
                    os_version=self.os_version,
                    keyword=keyword,
                    page_number=page,
                    status=error_type,
                    detail_data=detail_data
                )
                print(f"  ✓ 크롤링 세부 정보 DB 저장 완료 (에러: {error_type})")

            except Exception as db_error:
                print(f"  ⚠️ 크롤링 세부 정보 저장 실패: {db_error}")

            return {
                'success': False,
                'keyword': keyword,
                'page': page,
                'error': str(e),
                'cookies': cookies_status,
                'html': ''  # 예외 발생 시 빈 HTML
            }

    def crawl_pages(self, keyword='아이폰', start_page=1, end_page=1, use_checkpoint=True):
        """
        다중 페이지 크롤링

        Args:
            keyword: 검색 키워드
            start_page: 시작 페이지
            end_page: 종료 페이지
            use_checkpoint: 체크포인트 사용 여부 (기본: True)

        Returns:
            dict: {
                'success': bool,
                'results': list,  # 크롤링 결과 리스트
                'need_refresh': bool,  # 쿠키 재수집 필요 여부
                'last_page': int  # 마지막 시도 페이지
            }
        """

        print("\n" + "="*70)
        print(f"다중 페이지 크롤링: {start_page} ~ {end_page} 페이지")
        print(f"(Fingerprint 쿠키 + 세션 쿠키 동적 관리)")
        print("="*70)

        # 체크포인트 초기화
        checkpoint = None
        if use_checkpoint and not self.worker_id:  # Worker 모드에서는 체크포인트 비활성화
            checkpoint = Checkpoint(keyword, self.device_name, self.browser, start_page, end_page)

            # 기존 체크포인트 로드
            if checkpoint.load():
                summary = checkpoint.get_summary()
                print(f"\n📋 체크포인트 발견: {summary['progress']} ({summary['percentage']})")
                print(f"   마지막 업데이트: {summary['last_updated']}")

                if checkpoint.is_completed():
                    print(f"✅ 이미 모든 페이지 완료됨")
                    # 완료된 결과 반환
                    return {
                        'success': True,
                        'results': [],
                        'need_refresh': False,
                        'last_page': end_page,
                        'from_checkpoint': True
                    }

                remaining = checkpoint.get_remaining_pages()
                print(f"   남은 페이지: {remaining[:10]}{'...' if len(remaining) > 10 else ''}")
            else:
                print(f"\n📋 새 체크포인트 생성")

        # Session 쿠키는 자동 관리됨 (초기화 불필요)
        print(f"\n새 크롤링 세션 시작 - Session이 쿠키 자동 관리\n")

        all_results = []
        consecutive_failures = 0

        for page in range(start_page, end_page + 1):
            # 체크포인트: 이미 완료된 페이지 스킵
            if checkpoint and page in checkpoint.get_completed_pages():
                print(f"\n⏭️  페이지 {page} 스킵 (이미 완료)")
                continue

            # 페이지별 재시도 로직 (최대 3회)
            page_max_retries = 3
            page_result = None

            for attempt in range(1, page_max_retries + 1):
                result = self.crawl_page(keyword=keyword, page=page)

                if not result:
                    print(f"\n⚠️ 페이지 {page} 크롤링 실패 - 중단")
                    # 체크포인트 반환 (재시도용)
                    return {
                        'success': False,
                        'results': all_results,
                        'need_refresh': True,
                        'last_page': page
                    }

                # 성공 시 재시도 루프 종료
                if result.get('success'):
                    page_result = result
                    break

                # 실패 처리
                error_type = result.get('error', 'unknown')

                # 차단 감지 시 재시도
                if error_type in ['blocked', 'no_products']:
                    if attempt < page_max_retries:
                        print(f"\n  ⚠️ 차단 감지 (시도 {attempt}/{page_max_retries})")
                        print(f"  → 3초 후 재시도...")
                        time.sleep(3)
                        continue  # 다음 재시도
                    else:
                        # 3회 연속 차단 시 최종 실패
                        print(f"\n  ❌ {page_max_retries}회 연속 차단으로 종료")
                        page_result = result
                        break
                else:
                    # 다른 에러는 재시도 없이 바로 실패
                    page_result = result
                    break

            # 최종 결과 처리
            all_results.append(page_result)

            if page_result.get('success'):
                print(f"\n✅ 페이지 {page} 크롤링 완료")
                consecutive_failures = 0  # 성공 시 연속 실패 카운트 리셋

                # 체크포인트 저장
                if checkpoint:
                    checkpoint.add_result(page, page_result)
                    print(f"   💾 체크포인트 저장됨 ({checkpoint.get_summary()['progress']})")

            else:
                consecutive_failures += 1
                error_type = page_result.get('error', 'unknown')
                print(f"\n❌ 페이지 {page} 크롤링 실패 ({error_type})")

                # 차단 감지 시 (3회 재시도 후에도 실패)
                if error_type in ['blocked', 'no_products']:
                    print(f"\n{'='*70}")
                    print("⚠️ 차단 감지 - 쿠키 재수집 필요")
                    print("="*70)

                    if checkpoint:
                        summary = checkpoint.get_summary()
                        print(f"  📊 현재 진행률: {summary['progress']} ({summary['percentage']})")
                        print(f"  🔄 재시도 시 페이지 {page}부터 재개됩니다")

                    print("="*70)

                    # 쿠키 재수집 필요 신호 반환
                    return {
                        'success': False,
                        'results': all_results,
                        'need_refresh': True,
                        'last_page': page
                    }

                # 연속 2회 실패 시 중단
                if consecutive_failures >= 2:
                    print(f"\n⚠️ 연속 {consecutive_failures}회 실패 - 크롤링 중단")
                    return {
                        'success': False,
                        'results': all_results,
                        'need_refresh': True,
                        'last_page': page
                    }

                # 단일 실패는 계속 진행
                print(f"  다음 페이지로 계속 시도합니다...")

            # 다음 페이지로 넘어가기 전 랜덤 딜레이 (사람처럼 행동)
            if page < end_page:
                import random
                delay = random.uniform(1.5, 2.5)
                print(f"\n⏳ 다음 페이지 대기 중... ({delay:.1f}초)")
                time.sleep(delay)

        # 모든 페이지 완료
        return {
            'success': True,
            'results': all_results,
            'need_refresh': False,
            'last_page': end_page
        }

    # ==========================================
    # 분석용 Helper Methods
    # ==========================================

    def _detect_akamai_block(self, response):
        """
        Akamai 차단 여부 감지

        Args:
            response: curl_cffi response 객체

        Returns:
            tuple: (is_blocked, challenge_type)
                is_blocked: bool - 차단 여부
                challenge_type: str - 챌린지 타입 ('bm_sc_challenge', 'akamai_page', 'no_products_suspicious', None)
        """
        # 1. 응답 크기가 작으면 의심
        response_size = len(response.content) if hasattr(response, 'content') else len(response.text)

        if response_size < 5000:  # 5KB 미만
            # bm_sc 쿠키 존재 확인 (Akamai Bot Manager)
            if hasattr(response, 'cookies') and 'bm_sc' in response.cookies:
                return True, 'bm_sc_challenge'

            # 응답 텍스트에서 Akamai 단어 확인
            response_text = response.text.lower()
            if 'akamai' in response_text:
                return True, 'akamai_page'

            # 상품 정보가 없으면 의심
            if 'class="search-product"' not in response.text and 'data-component-type' not in response.text:
                return True, 'no_products_suspicious'

        return False, None

    def _classify_error(self, exception):
        """
        에러 타입 분류

        Args:
            exception: Exception 객체

        Returns:
            str: 에러 타입
                - 'http2_error'
                - 'network_error'
                - 'timeout'
                - 'parsing_error'
                - 'unknown_error'
        """
        error_str = str(exception).lower()

        if 'http2' in error_str or 'internal_error' in error_str or 'stream' in error_str or 'protocol' in error_str:
            return 'http2_error'
        elif 'timeout' in error_str or 'timed out' in error_str:
            return 'timeout'
        elif 'connection' in error_str or 'network' in error_str:
            return 'network_error'
        elif 'parse' in error_str or 'json' in error_str or 'html' in error_str:
            return 'parsing_error'
        else:
            return 'unknown_error'
