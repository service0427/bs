"""
동적 BrowserStack 쿠키 수집기
선택한 디바이스 정보를 직접 사용하여 쿠키/헤더 수집
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.common.exceptions import TimeoutException

from lib.settings import (
    BROWSERSTACK_USERNAME,
    BROWSERSTACK_ACCESS_KEY,
    BROWSERSTACK_HUB,
    BROWSERSTACK_PROJECT_NAME,
    BROWSERSTACK_BUILD_NAME,
    COOKIE_VALID_DURATION,
    ensure_directories,
    TARGET_URLS,
    get_device_fingerprint_dir,
    get_device_identifier,
    get_tls_dir  # TLS 전용 디렉토리
)

# BrowserStack Local
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils'))
from browserstack_local import ensure_local_running


class DynamicCollector:
    """동적 디바이스 설정 기반 쿠키 수집기"""

    def __init__(self, device_config, refresh_policy='auto'):
        """
        Args:
            device_config: dict {
                'device': 'Samsung Galaxy S10',
                'os': 'android',
                'os_version': '9.0',
                'browser': 'samsung',
                'real_mobile': True
            }
            refresh_policy: 재수집 정책
                - 'auto': 기본값, 300초 이내면 재사용
                - 'force': 무조건 재수집
                - 'skip': 무조건 기존 데이터 사용 (없으면 수집)
        """
        self.device_config = device_config
        self.device_name = device_config['device']
        self.browser = device_config['browser']  # 브라우저 정보 저장
        self.os_version = device_config['os_version']  # OS 버전 저장
        self.driver = None
        self.refresh_policy = refresh_policy

    def _generate_build_name(self):
        """
        빌드명 생성 (한국 시간 기준)
        형식: 2025-01-22 14:30 | Real | Samsung | Android 9.0
        """
        # 한국 시간 (UTC+9)
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)

        # 날짜/시간
        date_time = now_kst.strftime('%Y-%m-%d %H:%M')

        # Real/Emulator
        device_type = "Real" if self.device_config.get('real_mobile', True) else "Emulator"

        # 브라우저명 (첫 글자 대문자)
        browser = self.device_config['browser'].capitalize()

        # OS + 버전
        os_name = self.device_config['os'].capitalize()
        os_version = self.device_config['os_version']
        os_info = f"{os_name} {os_version}"

        # 조합
        build_name = f"{date_time} | {device_type} | {browser} | {os_info}"

        return build_name

    def create_driver(self):
        """BrowserStack 드라이버 생성"""
        from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

        # BrowserStack Local 연결 확인 및 시작
        # 모든 스크립트에서 동일한 identifier 사용 (충돌 방지)
        local_identifier = 'browserstack-local'
        success, local_instance = ensure_local_running(local_identifier)

        if not success:
            raise RuntimeError("BrowserStack Local 연결 실패")

        # Selenium 4 방식: options 사용
        options = webdriver.ChromeOptions()

        # 빌드명 생성 (동적)
        # 형식: 2025-01-22 14:30 | Real | Samsung | Android 9.0
        build_name = self._generate_build_name()

        # BrowserStack capabilities 설정
        bstack_options = {
            'userName': BROWSERSTACK_USERNAME,
            'accessKey': BROWSERSTACK_ACCESS_KEY,
            'projectName': BROWSERSTACK_PROJECT_NAME,     # config.py에서 관리
            'buildName': build_name,                      # 동적 생성
            'deviceName': self.device_config['device'],
            'osVersion': self.device_config['os_version'],
            'browserName': self.device_config['browser'],
            'realMobile': str(self.device_config.get('real_mobile', True)).lower(),
            'local': 'true',                              # BrowserStack Local 사용
            'localIdentifier': local_identifier,          # Local 식별자
            'sessionName': f"{self.device_name} - {self.device_config['browser']}"
        }

        print(f"\n[BUILD] {build_name}")
        print(f"[LOCAL] Using local connection (Identifier: {local_identifier})")

        # browser_version이 있으면 추가
        if self.device_config.get('browser_version'):
            bstack_options['browserVersion'] = self.device_config['browser_version']

        options.set_capability('bstack:options', bstack_options)

        print(f"\n[{self.device_name}] BrowserStack 드라이버 생성 중...")
        print(f"  - Device: {self.device_config['device']}")
        print(f"  - OS: {self.device_config['os']} {self.device_config['os_version']}")
        print(f"  - Browser: {self.device_config['browser']}")
        print(f"  - Real Mobile: {self.device_config.get('real_mobile', True)}")

        # BrowserStack Local 연결 타이밍 이슈 대비 재시도
        max_retries = 3
        retry_delay = 3  # 3초 대기

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[{self.device_name}] 🔄 BrowserStack 서버 연결 중... (시도 {attempt}/{max_retries})")
                print(f"[{self.device_name}]    (리얼 디바이스는 30~60초 소요될 수 있습니다)")

                start_time = time.time()

                self.driver = webdriver.Remote(
                    command_executor=BROWSERSTACK_HUB,
                    options=options
                )

                elapsed = time.time() - start_time
                print(f"[{self.device_name}] ✓ 세션 생성 완료 ({elapsed:.1f}초)")
                print(f"[{self.device_name}] 🔄 디바이스 준비 중...")

                self.driver.set_page_load_timeout(60)
                print(f"[{self.device_name}] ✅ 드라이버 생성 완료 (총 {elapsed:.1f}초)")
                return self.driver

            except Exception as e:
                error_msg = str(e)
                if 'local testing through BrowserStack is not connected' in error_msg:
                    if attempt < max_retries:
                        print(f"[{self.device_name}] ⚠️ Local 연결 대기 중... (시도 {attempt}/{max_retries})")
                        print(f"[{self.device_name}]   {retry_delay}초 후 재시도...")
                        time.sleep(retry_delay)
                    else:
                        print(f"[{self.device_name}] ❌ {max_retries}회 재시도 후에도 Local 연결 실패")
                        raise
                else:
                    # 다른 에러는 즉시 발생
                    raise

        return self.driver

    def _is_data_valid(self):
        """
        기존 수집 데이터가 유효한지 검증

        v2.14 변경: 매번 TLS 수집 (DB 누적 저장)
        항상 False를 반환하여 매번 새로 수집

        Returns:
            bool: 항상 False (매번 수집)
        """
        # v2.14: 매번 TLS 수집 (DB 누적)
        print(f"[{self.device_name}] 🔄 TLS 새로 수집 (DB 누적 저장)")
        return False

        # 이하 코드 사용 안 함 (레거시)
        # 'force' 정책: 무조건 재수집
        if self.refresh_policy == 'force':
            print(f"[{self.device_name}] 🔄 재수집 모드 (--force-refresh)")
            return False

        # TLS 전용 디렉토리 (공유)
        tls_dir = get_tls_dir(self.device_name, self.browser, self.os_version)

        # TLS 파일 존재 확인 (필수)
        tls_file = os.path.join(tls_dir, 'tls_fingerprint.json')

        if not os.path.exists(tls_file):
            if self.refresh_policy == 'skip':
                print(f"[{self.device_name}] ⚠️  TLS 파일 없음 (재수집 필요)")
            return False

        try:
            # TLS 파일 로드 및 검증
            with open(tls_file, 'r', encoding='utf-8') as f:
                tls_info = json.load(f)

            # TLS 정보 정상 확인
            if not tls_info.get('tls') or not tls_info.get('tls', {}).get('ciphers'):
                print(f"[{self.device_name}] ⚠️  TLS 정보 비정상 (재수집 필요)")
                return False

            # TLS 체크 통과 (영구 재사용)
            print(f"[{self.device_name}] ✓ TLS 데이터 유효")
            print(f"[{self.device_name}]   - Ciphers: {len(tls_info['tls']['ciphers'])}개")
            if 'ja3_hash' in tls_info.get('tls', {}):
                print(f"[{self.device_name}]   - JA3: {tls_info['tls']['ja3_hash']}")

            # 쿠키 경과 시간 표시 (만료 체크 안 함)
            fingerprint_dir = get_device_fingerprint_dir(self.device_name, self.browser, self.os_version)
            metadata_file = os.path.join(fingerprint_dir, 'metadata.json')

            if not os.path.exists(metadata_file):
                print(f"[{self.device_name}] ⚠️  쿠키 메타데이터 없음")
                print(f"[{self.device_name}] → --force-refresh 옵션으로 재수집하세요")
                return False

            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            collected_at_str = metadata.get('collected_at')
            if not collected_at_str:
                print(f"[{self.device_name}] ⚠️  수집 시간 정보 없음")
                print(f"[{self.device_name}] → --force-refresh 옵션으로 재수집하세요")
                return False

            collected_at = datetime.fromisoformat(collected_at_str)
            elapsed = (datetime.now() - collected_at).total_seconds()

            # 쿠키 만료 체크 (24시간 = 86400초)
            COOKIE_EXPIRY = 86400  # 24시간

            print(f"[{self.device_name}] ✓ 쿠키 데이터 존재")
            print(f"[{self.device_name}]   - 수집 시각: {collected_at.strftime('%Y-%m-%d %H:%M:%S')}")

            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            print(f"[{self.device_name}]   - 경과 시간: {int(elapsed)}초 ({hours}시간 {minutes}분 {seconds}초)")

            if elapsed > COOKIE_EXPIRY:
                print(f"[{self.device_name}] ⚠️  쿠키 만료 (>{int(COOKIE_EXPIRY/3600)}시간)")
                print(f"[{self.device_name}] → 재수집 필요")
                return False

            print(f"[{self.device_name}] ✓ 기존 데이터 재사용 (쿠키 유효)")
            return True

        except Exception as e:
            print(f"[{self.device_name}] TLS 데이터 검증 오류: {e}")
            return False

    def _get_current_ip(self):
        """
        현재 외부 IP 주소 확인

        BrowserStack Real Device로 IP 확인 서비스 접속하여 IP 추출

        Returns:
            str: IP 주소 (예: "220.121.120.83") 또는 None
        """
        try:
            # BrowserStack 실기기로 ifconfig.me 접속
            self.driver.get('https://ifconfig.me')
            time.sleep(2)  # 페이지 로딩 대기

            # 페이지 소스에서 IP 주소 추출
            import re
            page_source = self.driver.page_source

            # ifconfig.me는 간단한 텍스트로 IP만 출력
            # 예: "<html><body>220.121.120.83</body></html>"
            ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', page_source)
            if ip_match:
                return ip_match.group(1)

            # 대체 방법: ipify.org API
            self.driver.get('https://api.ipify.org')
            time.sleep(2)
            page_source = self.driver.page_source
            ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', page_source)
            if ip_match:
                return ip_match.group(1)

            return None

        except Exception as e:
            print(f"[{self.device_name}]   IP 확인 오류: {e}")
            return None

    def collect(self):
        """
        TLS 정보 및 쿠키 수집

        Returns:
            dict: 수집된 데이터
        """
        collection_start_time = time.time()
        print(f"\n{'='*70}")
        print(f"[{self.device_name}] 데이터 수집 시작")
        print(f"{'='*70}")

        ensure_directories()

        # 기존 데이터 유효성 검증
        if self._is_data_valid():
            print(f"\n[{self.device_name}] 기존 TLS 데이터 사용 (재수집 생략)\n")

            # 기존 TLS 데이터 로드 (TLS 전용 디렉토리)
            tls_dir = get_tls_dir(self.device_name, self.browser, self.os_version)

            with open(os.path.join(tls_dir, 'tls_fingerprint.json'), 'r', encoding='utf-8') as f:
                tls_info = json.load(f)

            # 간단한 metadata 생성 (TLS만)
            metadata = {
                'device_name': self.device_name,
                'browser': self.browser,
                'tls_info': tls_info,
                'reused': True,
                'message': 'TLS 데이터 재사용 (영구 보관)'
            }

            return {
                'success': True,
                'device': self.device_name,
                'metadata': metadata,
                'message': '기존 TLS 데이터 사용 (영구 보관)'
            }

        try:
            # 1. 드라이버 생성
            self.create_driver()

            # 0. IP 확인 (VPN 사용 여부 검증)
            print(f"\n[{self.device_name}] Step 0: IP 확인")
            current_ip = self._get_current_ip()
            if current_ip:
                print(f"[{self.device_name}] 🌐 현재 IP: {current_ip}")
                # IP 저장 (나중에 VPN 검증용)
                self.current_ip = current_ip
            else:
                print(f"[{self.device_name}] ⚠️  IP 확인 실패 (계속 진행)")
                self.current_ip = None

            # 2. TLS 정보 수집
            print(f"\n[{self.device_name}] Step 1: TLS 정보 수집")

            print(f"[{self.device_name}] 🔄 https://tls.browserleaks.com/ 접속 중...")

            tls_start = time.time()
            self.driver.get('https://tls.browserleaks.com/')
            print(f"[{self.device_name}] ✓ 페이지 로드 완료 ({time.time() - tls_start:.1f}초)")

            print(f"[{self.device_name}] 🔄 TLS 데이터 파싱 중 (5초 대기)...")
            time.sleep(5)  # 페이지 렌더링 대기

            # TLS 정보 추출
            tls_info = {}
            browserleaks_raw = None
            try:
                print(f"[{self.device_name}] 🔄 JSON 추출 시도 중...")

                # 방법 1: JavaScript 변수에서 추출 (가장 정확)
                try:
                    # window 객체나 특정 변수에 데이터가 있을 수 있음
                    browserleaks_raw = self.driver.execute_script("""
                        // 여러 가능성 시도
                        if (typeof tlsData !== 'undefined') return tlsData;
                        if (typeof data !== 'undefined') return data;
                        // /json API 직접 호출
                        try {
                            var xhr = new XMLHttpRequest();
                            xhr.open('GET', '/json', false);
                            xhr.send();
                            return JSON.parse(xhr.responseText);
                        } catch(e) {
                            return null;
                        }
                    """)
                    if browserleaks_raw:
                        print(f"[{self.device_name}]   JSON 발견: JavaScript 변수")
                except Exception as js_err:
                    print(f"[{self.device_name}]   JavaScript 추출 실패: {js_err}")

                # 방법 2: 페이지 소스에서 JSON 추출
                if not browserleaks_raw:
                    page_source = self.driver.page_source
                    import re

                    # JSON 객체 패턴 찾기
                    json_match = re.search(r'\{[^{}]*"ja3_hash"[^{}]*"ja3_text"[^{}]*"akamai_text"[^{}]*\}', page_source, re.DOTALL)
                    if json_match:
                        import html
                        json_text = html.unescape(json_match.group(0))
                        browserleaks_raw = json.loads(json_text)
                        print(f"[{self.device_name}]   JSON 발견: 페이지 소스")

                if browserleaks_raw:
                    # browserleaks 원본 데이터를 peet.ws 형식으로 변환
                    if 'ja3_text' in browserleaks_raw:
                        # JA3 문자열 파싱
                        ja3_parts = browserleaks_raw['ja3_text'].split(',')

                        # cipher_suites 배열이 있으면 사용, 없으면 JA3에서 추출
                        ciphers = browserleaks_raw.get('cipher_suites', [])
                        if not ciphers and len(ja3_parts) > 1:
                            ciphers = ja3_parts[1].split('-')

                        # extensions 배열이 있으면 사용, 없으면 JA3에서 추출
                        extensions = browserleaks_raw.get('extensions', [])
                        if not extensions and len(ja3_parts) > 2:
                            extensions = ja3_parts[2].split('-')

                        tls_info = {
                            'tls': {
                                'ja3': browserleaks_raw['ja3_text'],
                                'ja3_hash': browserleaks_raw.get('ja3_hash', ''),
                                'ciphers': ciphers,
                                'extensions': extensions
                            },
                            'http2': {
                                'akamai_fingerprint': browserleaks_raw.get('akamai_text', '')
                            },
                            'http_version': 'h2',
                            'user_agent': browserleaks_raw.get('user_agent', ''),
                            'browserleaks_raw': browserleaks_raw  # 원본 데이터 보존
                        }

                        print(f"[{self.device_name}] ✓ TLS 정보 수집 완료")
                        print(f"[{self.device_name}]   Ciphers: {len(tls_info['tls']['ciphers'])}개")
                        print(f"[{self.device_name}]   JA3: {tls_info['tls']['ja3_hash']}")
                        print(f"[{self.device_name}]   HTTP Version: {tls_info['http_version']}")
                    else:
                        print(f"[{self.device_name}] ❌ TLS 정보 비정상: ja3_text 필드 누락")
                        tls_info = {}
                else:
                    print(f"[{self.device_name}] ❌ TLS 데이터를 찾을 수 없음")
                    tls_info = {}

            except json.JSONDecodeError as e:
                print(f"[{self.device_name}] ❌ JSON 파싱 실패: {e}")
                tls_info = {}
            except Exception as e:
                print(f"[{self.device_name}] ❌ TLS 정보 파싱 실패: {e}")
                import traceback
                traceback.print_exc()
                tls_info = {}

            # 3. User-Agent 추출
            user_agent = self.driver.execute_script("return navigator.userAgent;")
            print(f"[{self.device_name}] User-Agent: {user_agent[:80]}...")

            # 4. 쿠팡 메인 접속
            print(f"\n[{self.device_name}] Step 2: 쿠팡 쿠키 수집")
            print(f"[{self.device_name}] 🔄 쿠팡 메인 접속 중...")

            coupang_start = time.time()
            self.driver.get(TARGET_URLS['main'])
            print(f"[{self.device_name}] ✓ 페이지 로드 완료 ({time.time() - coupang_start:.1f}초)")

            # 필수 쿠키 대기 (최대 30초)
            required_cookies = ['_abck', 'PCID', 'sid']
            max_wait = 30
            wait_interval = 2

            print(f"[{self.device_name}] 🔄 필수 쿠키 대기 중 ({', '.join(required_cookies)})...")
            print(f"[{self.device_name}]    (최대 {max_wait}초 대기)")

            cookies = []
            for attempt in range(max_wait // wait_interval):
                time.sleep(wait_interval)
                cookies = self.driver.get_cookies()
                cookie_names = [c['name'] for c in cookies]

                # 필수 쿠키 체크
                missing_cookies = [name for name in required_cookies if name not in cookie_names]

                if not missing_cookies:
                    elapsed = (attempt + 1) * wait_interval
                    print(f"[{self.device_name}] ✅ 모든 필수 쿠키 수집 완료 ({elapsed}초 소요)")
                    break
                else:
                    elapsed = (attempt + 1) * wait_interval
                    print(f"[{self.device_name}] 🔄 대기 중... 미발견: {', '.join(missing_cookies)} ({elapsed}/{max_wait}초)")

            # 5. 쿠키 검증
            print(f"\n[{self.device_name}] 수집된 쿠키: {len(cookies)}개")

            # 필수 쿠키 확인
            cookie_dict = {c['name']: c for c in cookies}

            print(f"[{self.device_name}] 필수 쿠키 검증:")
            all_found = True
            for required in required_cookies:
                if required in cookie_dict:
                    value_preview = cookie_dict[required]['value'][:50]
                    print(f"[{self.device_name}]   ✓ {required}: {value_preview}... (길이: {len(cookie_dict[required]['value'])})")
                else:
                    print(f"[{self.device_name}]   ✗ {required}: 없음!")
                    all_found = False

            if not all_found:
                print(f"\n[{self.device_name}] ⚠️ 경고: 필수 쿠키가 모두 수집되지 않았습니다!")
                print(f"[{self.device_name}] 현재 쿠키 목록:")
                for cookie in cookies:
                    print(f"[{self.device_name}]   - {cookie['name']}")
            else:
                print(f"[{self.device_name}] ✓ 모든 필수 쿠키 수집 성공!")

            # 5-1. 배너 제거만 수행 (검색 불필요)
            from lib.crawler.coupang_interaction import close_banners

            print(f"\n[{self.device_name}] ========================================")
            print(f"[{self.device_name}] Step 3: 배너 제거")
            print(f"[{self.device_name}] ========================================")

            # 배너 제거
            print(f"[{self.device_name}] 배너 제거 중 (fullBanner, bottomSheet)")
            banner_result = close_banners(self.driver, self.device_name)

            # 쿠키 재수집 (배너 닫기 후)
            cookies = self.driver.get_cookies()
            print(f"\n[{self.device_name}] ✅ 배너 제거 완료 - 쿠키 재수집: {len(cookies)}개")
            print(f"[{self.device_name}] ========================================")

            # 6. 헤더 구성
            headers = self._build_headers(user_agent)

            # 7. 메타데이터 생성
            metadata = {
                'device_name': self.device_name,
                'device': self.device_config['device'],
                'os': self.device_config['os'],
                'os_version': self.device_config['os_version'],
                'browser': self.device_config['browser'],
                'browser_version': self.device_config.get('browser_version'),
                'real_mobile': self.device_config.get('real_mobile', True),
                'collected_at': datetime.now().isoformat(),
                'cookie_count': len(cookies),
                'required_cookies': {
                    '_abck': '_abck' in cookie_dict,
                    'PCID': 'PCID' in cookie_dict,
                    'sid': 'sid' in cookie_dict
                },
                'all_required_cookies_found': all_found,
                'user_agent': user_agent,
                'tls_info': tls_info  # TLS fingerprint 정보
            }

            # 8. 저장
            self._save_data(cookies, headers, metadata, tls_info)

            # 9. 수집 결과
            # TLS 정보가 없으면 실패
            tls_valid = bool(tls_info and tls_info.get('tls') and tls_info.get('tls', {}).get('ciphers'))
            success = all_found and tls_valid

            total_elapsed = time.time() - collection_start_time

            if success:
                print(f"\n{'='*70}")
                print(f"[{self.device_name}] ✅ 수집 완료!")
                print(f"{'='*70}")
                print(f"  - 쿠키: {len(cookies)}개")
                print(f"  - 필수 쿠키: 모두 수집 ✓")
                print(f"  - TLS 정보: 정상 수집 ✓")
                print(f"  - 수집 시간: {metadata['collected_at']}")
                print(f"  - 유효 시간: 5분 (300초)")
                print(f"  - 총 소요 시간: {total_elapsed:.1f}초")
                print(f"{'='*70}\n")
            else:
                print(f"\n{'='*70}")
                print(f"[{self.device_name}] ❌ 수집 실패")
                print(f"{'='*70}")
                if not all_found:
                    print(f"  - 필수 쿠키: 일부 누락 ✗")
                if not tls_valid:
                    print(f"  - TLS 정보: 수집 실패 ✗ (크롤링 불가)")
                print(f"  - 수집 시간: {metadata['collected_at']}")
                print(f"  - 총 소요 시간: {total_elapsed:.1f}초")
                print(f"{'='*70}\n")

            return {
                'success': success,  # 필수 쿠키 + TLS 정보 모두 있어야 성공
                'device_name': self.device_name,
                'cookies': cookies,
                'headers': headers,
                'metadata': metadata,
                'all_required_cookies_found': all_found,
                'tls_valid': tls_valid
            }

        except Exception as e:
            print(f"\n[{self.device_name}] ✗ 수집 실패: {e}")
            return {
                'success': False,
                'device_name': self.device_name,
                'error': str(e)
            }

        finally:
            if self.driver:
                print(f"[{self.device_name}] 드라이버 종료")
                self.driver.quit()

    def _build_headers(self, user_agent):
        """HTTP 헤더 구성"""
        browser = self.device_config['browser']

        # Chrome/Android
        if browser in ['android', 'chrome']:
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"'
            }

        # Samsung Browser (Chrome 기반이므로 동일한 헤더 사용)
        elif browser == 'samsung':
            # Samsung Browser는 Chromium 기반이므로 Chrome과 동일한 헤더 구조
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'sec-ch-ua': '"Chromium";v="130", "Samsung Internet";v="28", "Not?A_Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"'
            }

        # Safari/iPhone
        elif browser in ['safari', 'iphone']:
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }

        else:
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }

        return headers

    def _save_data(self, cookies, headers, metadata, tls_info):
        """수집한 데이터를 JSON 파일로 저장"""
        # 디바이스 + 브라우저 + OS 버전으로 고유 디렉토리 생성
        fingerprint_dir = get_device_fingerprint_dir(self.device_name, self.browser, self.os_version)
        os.makedirs(fingerprint_dir, exist_ok=True)

        # 세션 식별 쿠키 제외 (PCID, sid 등)
        # 이 쿠키들은 각 크롤링 세션마다 새로 발급받음
        session_cookie_names = ['PCID', 'sid', 'sessionid', 'session', 'JSESSIONID']

        # [TEST 4] 모든 쿠키 저장 (PCID, sid 포함)
        # 주석처리: 세션 쿠키 필터링 제거
        # filtered_cookies = [
        #     cookie for cookie in cookies
        #     if cookie['name'] not in session_cookie_names
        # ]

        # excluded_count = len(cookies) - len(filtered_cookies)
        # if excluded_count > 0:
        #     excluded = [c['name'] for c in cookies if c['name'] in session_cookie_names]
        #     print(f"[{self.device_name}] 세션 쿠키 제외: {', '.join(excluded)}")

        # 쿠키 저장 (모든 쿠키 포함, PCID/sid 포함)
        cookie_file = os.path.join(fingerprint_dir, 'cookies.json')
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)  # filtered_cookies → cookies

        # PCID, sid 포함 여부 확인
        has_pcid = any(c['name'] == 'PCID' for c in cookies)
        has_sid = any(c['name'] == 'sid' for c in cookies)
        print(f"[{self.device_name}] 쿠키 파일 저장: {cookie_file} ({len(cookies)}개, PCID: {'✅' if has_pcid else '❌'}, sid: {'✅' if has_sid else '❌'})")

        # DB에도 쿠키 저장 (원본 쿠키로)
        try:
            from lib.db.manager import DBManager
            db = DBManager()

            cookie_id = db.save_cookie(
                device_name=self.device_name,
                browser=self.browser,
                os_version=self.os_version,
                cookie_data=cookies,
                cookie_type='original'
            )

            print(f"[{self.device_name}] ✅ 쿠키 DB 저장 완료 (ID: {cookie_id})")

        except Exception as e:
            print(f"[{self.device_name}] ⚠️  쿠키 DB 저장 실패 (파일 저장은 성공): {e}")

        # 헤더 저장
        headers_file = os.path.join(fingerprint_dir, 'headers.json')
        with open(headers_file, 'w', encoding='utf-8') as f:
            json.dump(headers, f, indent=2, ensure_ascii=False)
        print(f"[{self.device_name}] 헤더 저장: {headers_file}")

        # 메타데이터 저장
        metadata_file = os.path.join(fingerprint_dir, 'metadata.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"[{self.device_name}] 메타데이터 저장: {metadata_file}")

        # TLS 정보 저장 (TLS 전용 디렉토리)
        if tls_info:
            tls_dir = get_tls_dir(self.device_name, self.browser, self.os_version)
            os.makedirs(tls_dir, exist_ok=True)  # TLS 디렉토리 생성
            tls_file = os.path.join(tls_dir, 'tls_fingerprint.json')
            with open(tls_file, 'w', encoding='utf-8') as f:
                json.dump(tls_info, f, indent=2, ensure_ascii=False)
            print(f"[{self.device_name}] TLS 정보 저장: {tls_file}")

            # DB에도 저장
            try:
                from lib.db.manager import DBManager
                db = DBManager()

                record_id = db.save_tls_fingerprint(
                    device_name=self.device_name,
                    browser=self.browser,
                    os_version=self.os_version,
                    tls_data=tls_info.get('tls', {}),
                    http2_data=tls_info.get('http2', {}),
                    collected_at=metadata.get('collected_at')
                )

                print(f"[{self.device_name}] ✅ DB 저장 완료 (ID: {record_id})")

            except Exception as e:
                print(f"[{self.device_name}] ⚠️  DB 저장 실패 (파일 저장은 성공): {e}")


def collect_from_config(device_config, force_collect=False):
    """
    디바이스 설정으로 쿠키 수집

    Args:
        device_config: dict (BrowserStack API에서 가져온 설정)
        force_collect: bool (True면 기존 데이터 무시하고 강제 재수집)

    Returns:
        dict: 수집 결과
    """
    refresh_policy = 'force' if force_collect else 'auto'
    collector = DynamicCollector(device_config, refresh_policy=refresh_policy)
    return collector.collect()


if __name__ == '__main__':
    # 테스트용
    test_config = {
        'device': 'Samsung Galaxy S10',
        'os': 'android',
        'os_version': '9.0',
        'browser': 'samsung',
        'real_mobile': True
    }

    result = collect_from_config(test_config)

    if result['success']:
        print("\n✅ 테스트 성공!")
    else:
        print(f"\n❌ 테스트 실패: {result.get('error')}")
