"""
TLS Fingerprint 샘플 수집 스크립트
동일 디바이스를 여러 번 수집하여 물리 기기별 차이 분석

수집 데이터:
  - https://tls.browserleaks.com/ (전체 TLS 정보 - JavaScript로 추출)
  - https://tls.peet.ws/api/all (TLS + HTTP/2 JSON)

사용 예:
  # Galaxy S23 Ultra 10회 수집
  python collect_tls_samples.py

  # 디바이스 지정 + 20회 수집
  python collect_tls_samples.py --device "Samsung Galaxy S22" --samples 20

  # 브라우저/OS 버전 지정
  python collect_tls_samples.py --device "Samsung Galaxy S23 Ultra" --browser android --os-version 13.0 --samples 10
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime, timezone, timedelta

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By

from data.mobile_real_devices import load_mobile_real_devices, get_full_config
from lib.settings import (
    BROWSERSTACK_USERNAME,
    BROWSERSTACK_ACCESS_KEY,
    BROWSERSTACK_HUB,
    BROWSERSTACK_PROJECT_NAME
)

# BrowserStack Local
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils'))
from browserstack_local import ensure_local_running


class TLSSampleCollector:
    """TLS Fingerprint 샘플 수집기"""

    def __init__(self, device_config, num_samples=10):
        """
        Args:
            device_config: 디바이스 설정 dict
            num_samples: 수집 횟수
        """
        self.device_config = device_config
        self.num_samples = num_samples

        # 한국 시간 기준
        kst = timezone(timedelta(hours=9))
        self.today = datetime.now(kst).strftime('%Y-%m-%d')

        # 저장 디렉토리
        self.save_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data',
            'tls_samples',
            self.today
        )
        os.makedirs(self.save_dir, exist_ok=True)

        # 통계
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'errors': []
        }

        self.start_time = time.time()

    def _generate_build_name(self, sample_num):
        """
        빌드명 생성
        형식: TLS Sample | 2025-10-23 18:30 | Sample 1/10 | Galaxy S23 Ultra
        """
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)
        date_time = now_kst.strftime('%Y-%m-%d %H:%M')

        device_name = self.device_config['device']
        browser = self.device_config['browser'].capitalize()
        os_version = self.device_config['os_version']

        build_name = (
            f"TLS Sample | {date_time} | "
            f"Sample {sample_num}/{self.num_samples} | "
            f"{device_name} | {browser} | {os_version}"
        )

        return build_name

    def create_driver(self, sample_num):
        """BrowserStack 드라이버 생성"""
        # BrowserStack Local 연결
        local_identifier = 'browserstack-local'
        success, local_instance = ensure_local_running(local_identifier)

        if not success:
            raise RuntimeError("BrowserStack Local 연결 실패")

        # Selenium 4 방식
        options = webdriver.ChromeOptions()

        # BrowserStack 설정
        bstack_options = {
            "userName": BROWSERSTACK_USERNAME,
            "accessKey": BROWSERSTACK_ACCESS_KEY,
            "projectName": f"{BROWSERSTACK_PROJECT_NAME} - TLS Samples",
            "buildName": self._generate_build_name(sample_num),
            "sessionName": f"Sample {sample_num}/{self.num_samples}",
            "deviceName": self.device_config['device'],
            "osVersion": self.device_config['os_version'],
            "browserName": self.device_config['browser'],
            "realMobile": self.device_config.get('real_mobile', True),
            "local": "true",
            "localIdentifier": local_identifier,
            "debug": "true",
            "networkLogs": "true",
            "consoleLogs": "verbose",
        }

        options.set_capability('bstack:options', bstack_options)

        # 드라이버 생성
        driver = webdriver.Remote(
            command_executor=BROWSERSTACK_HUB,
            options=options
        )

        driver.implicitly_wait(10)
        return driver

    def collect_sample(self, sample_num):
        """
        단일 샘플 수집

        Args:
            sample_num: 샘플 번호 (1, 2, 3, ...)

        Returns:
            dict: 수집 결과 또는 None (실패 시)
        """
        driver = None

        try:
            print(f"\n{'='*70}")
            print(f"샘플 {sample_num}/{self.num_samples} 수집 시작")
            print(f"{'='*70}")

            # 드라이버 생성 (새 세션 = 새 물리 기기 가능)
            print(f"  → BrowserStack 세션 시작...")
            driver = self.create_driver(sample_num)
            print(f"  ✓ 세션 연결 완료\n")

            # 결과 저장 객체
            result = {
                'device': self.device_config['device'],
                'browser': self.device_config['browser'],
                'os': self.device_config['os'],
                'os_version': self.device_config['os_version'],
                'real_mobile': self.device_config.get('real_mobile', True),
                'sample_num': sample_num,
                'timestamp': datetime.now().isoformat(),
                'browserleaks': {},
                'peet_ws': {}
            }

            # 1. browserleaks.com 수집 (전체 페이지)
            print(f"  [1/2] https://tls.browserleaks.com/ 로딩...")
            driver.get('https://tls.browserleaks.com/')
            time.sleep(5)  # 페이지 렌더링 및 JavaScript 실행 대기

            try:
                # JavaScript로 window 객체에서 TLS 데이터 추출 시도
                try:
                    # 페이지에 tlsInfo 또는 유사한 전역 변수가 있을 수 있음
                    tls_data_js = driver.execute_script("""
                        // 페이지의 전역 변수 확인
                        if (typeof tlsInfo !== 'undefined') return tlsInfo;
                        if (typeof window.tlsData !== 'undefined') return window.tlsData;
                        if (typeof window.data !== 'undefined') return window.data;

                        // DOM에서 데이터 추출 시도
                        var jsonElements = document.querySelectorAll('pre, code, script[type="application/json"]');
                        for (var i = 0; i < jsonElements.length; i++) {
                            try {
                                var data = JSON.parse(jsonElements[i].textContent);
                                if (data.ja3_hash || data.ja3 || data.tls) {
                                    return data;
                                }
                            } catch(e) {}
                        }

                        return null;
                    """)

                    if tls_data_js:
                        browserleaks_data = tls_data_js
                        print(f"      ✓ JavaScript로 JSON 추출 성공")
                    else:
                        # HTML에서 직접 추출 시도
                        page_source = driver.page_source
                        browserleaks_data = {'html': page_source, 'note': 'Full HTML - JSON extraction failed'}
                        print(f"      ⚠️ JavaScript 추출 실패 - HTML 저장")

                except Exception as js_error:
                    print(f"      ⚠️ JavaScript 실행 오류: {js_error}")
                    page_source = driver.page_source
                    browserleaks_data = {'html': page_source, 'note': 'Full HTML - JS error'}

                result['browserleaks'] = {
                    'url': 'https://tls.browserleaks.com/',
                    'data': browserleaks_data,
                    'collected_at': datetime.now().isoformat()
                }

                # JA3 Hash 출력 (있으면)
                if isinstance(browserleaks_data, dict) and 'ja3_hash' in browserleaks_data:
                    print(f"      ✓ JA3 Hash: {browserleaks_data['ja3_hash']}")

            except Exception as e:
                print(f"      ⚠️ 수집 실패: {e}")
                result['browserleaks'] = {
                    'url': 'https://tls.browserleaks.com/',
                    'error': str(e),
                    'collected_at': datetime.now().isoformat()
                }

            # 2. peet.ws/api/all 수집
            print(f"\n  [2/2] https://tls.peet.ws/api/all 로딩...")
            driver.get('https://tls.peet.ws/api/all')
            time.sleep(3)  # JSON 로딩 대기

            # JSON 데이터 추출
            try:
                page_text = driver.find_element(By.TAG_NAME, 'pre').text
                peet_data = json.loads(page_text)

                result['peet_ws'] = {
                    'url': 'https://tls.peet.ws/api/all',
                    'data': peet_data,
                    'collected_at': datetime.now().isoformat()
                }

                # TLS 정보 출력
                tls_info = peet_data.get('tls', {})
                http2_info = peet_data.get('http2', {})

                print(f"      ✓ JSON 수집 완료")
                print(f"      ✓ JA3: {tls_info.get('ja3', 'N/A')[:50]}...")
                print(f"      ✓ JA3 Hash: {tls_info.get('ja3_hash', 'N/A')}")
                print(f"      ✓ Cipher Suites: {len(tls_info.get('ciphers', []))}개")
                print(f"      ✓ Akamai: {http2_info.get('akamai_fingerprint', 'N/A')[:50]}...")

            except Exception as e:
                print(f"      ⚠️ JSON 파싱 실패: {e}")
                result['peet_ws'] = {
                    'url': 'https://tls.peet.ws/api/all',
                    'error': str(e),
                    'raw_html': driver.page_source,
                    'collected_at': datetime.now().isoformat()
                }

            print(f"\n  ✅ 샘플 {sample_num} 수집 완료")
            return result

        except Exception as e:
            print(f"\n  ❌ 샘플 {sample_num} 수집 실패: {e}")
            self.stats['errors'].append({
                'sample_num': sample_num,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return None

        finally:
            if driver:
                try:
                    driver.quit()
                    print(f"  ✓ 세션 종료\n")
                except:
                    pass

    def save_sample(self, result):
        """샘플을 JSON 파일로 저장"""
        if not result:
            return False

        # 파일명 생성
        device_safe = result['device'].replace(' ', '_').replace('/', '_')
        browser = result['browser']
        os_version = result['os_version'].replace('.', '_')
        sample_num = result['sample_num']

        filename = f"{device_safe}_{browser}_{os_version}_sample_{sample_num:02d}.json"
        filepath = os.path.join(self.save_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  💾 저장: {filename}")
            return True
        except Exception as e:
            print(f"  ⚠️ 파일 저장 실패: {e}")
            return False

    def collect_all(self):
        """모든 샘플 순차 수집"""
        device_name = self.device_config['device']
        browser = self.device_config['browser']
        os_version = self.device_config['os_version']

        print(f"\n{'='*70}")
        print(f"TLS Fingerprint 샘플 수집")
        print(f"{'='*70}")
        print(f"날짜: {self.today}")
        print(f"디바이스: {device_name}")
        print(f"브라우저: {browser}")
        print(f"OS 버전: {os_version}")
        print(f"수집 횟수: {self.num_samples}회 (순차 실행)")
        print(f"저장 위치: {self.save_dir}")
        print(f"{'='*70}\n")

        print("⚠️  주의: 각 샘플마다 새로운 BrowserStack 세션을 시작합니다.")
        print("        물리적으로 다른 기기가 할당될 수 있습니다.\n")

        input("⏸️  Enter 키를 눌러 시작... ")

        # 순차 수집
        for sample_num in range(1, self.num_samples + 1):
            self.stats['total'] += 1

            # 진행률 표시
            elapsed = time.time() - self.start_time
            progress = (sample_num - 1) / self.num_samples if self.num_samples > 0 else 0

            if progress > 0:
                estimated_total = elapsed / progress
                remaining = estimated_total - elapsed
                remaining_str = time.strftime('%H:%M:%S', time.gmtime(remaining))
            else:
                remaining_str = "계산 중..."

            percentage = (sample_num / self.num_samples * 100) if self.num_samples > 0 else 0

            print(f"\n{'#'*70}")
            print(f"진행률: {percentage:.1f}% ({sample_num}/{self.num_samples})")
            print(f"성공: {self.stats['success']} | 실패: {self.stats['failed']}")
            print(f"경과: {time.strftime('%H:%M:%S', time.gmtime(elapsed))} | 남은 시간: {remaining_str}")
            print(f"{'#'*70}")

            # 샘플 수집
            try:
                result = self.collect_sample(sample_num)

                if result and self.save_sample(result):
                    self.stats['success'] += 1
                else:
                    self.stats['failed'] += 1

            except Exception as e:
                self.stats['failed'] += 1
                print(f"  ❌ 예외 발생: {e}")

            # 다음 샘플까지 대기 (BrowserStack 부하 방지)
            if sample_num < self.num_samples:
                wait_time = 3
                print(f"\n  ⏳ 다음 샘플까지 {wait_time}초 대기...")
                time.sleep(wait_time)

    def print_final_stats(self):
        """최종 통계 출력"""
        elapsed = time.time() - self.start_time

        print(f"\n\n{'='*70}")
        print(f"최종 통계")
        print(f"{'='*70}")
        print(f"디바이스: {self.device_config['device']}")
        print(f"브라우저: {self.device_config['browser']} {self.device_config['os_version']}")
        print(f"총 시도: {self.stats['total']}회")
        print(f"✅ 성공: {self.stats['success']}회 ({self.stats['success']/self.stats['total']*100:.1f}%)")
        print(f"❌ 실패: {self.stats['failed']}회 ({self.stats['failed']/self.stats['total']*100:.1f}%)")
        print(f"소요 시간: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
        print(f"저장 위치: {self.save_dir}")
        print(f"{'='*70}")

        # 에러 상세
        if self.stats['errors']:
            print(f"\n에러 상세:")
            for error in self.stats['errors']:
                print(f"  - Sample {error['sample_num']}: {error['error'][:100]}")

        print()


def find_galaxy_s23():
    """Galaxy S23 Ultra 찾기 (android, 가장 최신 OS 버전)"""
    devices = load_mobile_real_devices()

    # Galaxy S23 Ultra 필터링
    s23_devices = [
        d for d in devices
        if 'Galaxy S23 Ultra' in d['device']
        and d['browser'] == 'android'
    ]

    if not s23_devices:
        raise ValueError("Galaxy S23 Ultra를 찾을 수 없습니다")

    # OS 버전이 가장 높은 것 선택
    s23_devices.sort(key=lambda x: x['os_version'], reverse=True)
    return s23_devices[0]


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='TLS Fingerprint 샘플 수집',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # Galaxy S23 Ultra 10회 수집 (기본값)
  python collect_tls_samples.py

  # 디바이스 지정 + 20회 수집
  python collect_tls_samples.py --device "Samsung Galaxy S22" --samples 20

  # 브라우저/OS 버전 지정
  python collect_tls_samples.py --device "Samsung Galaxy S23 Ultra" --browser android --os-version 13.0 --samples 15
        """
    )

    parser.add_argument(
        '--device', '-d',
        type=str,
        default=None,
        help='디바이스 이름 (기본값: Galaxy S23 Ultra)'
    )

    parser.add_argument(
        '--browser', '-b',
        type=str,
        default='android',
        help='브라우저 (android, samsung 등, 기본값: android)'
    )

    parser.add_argument(
        '--os-version',
        type=str,
        default=None,
        help='OS 버전 (예: 13.0)'
    )

    parser.add_argument(
        '--samples', '-n',
        type=int,
        default=10,
        help='수집 횟수 (기본값: 10)'
    )

    args = parser.parse_args()

    # 디바이스 설정 결정
    if args.device is None:
        # Galaxy S23 Ultra 자동 선택
        print("디바이스 미지정 - Galaxy S23 Ultra 자동 선택")
        device_config = find_galaxy_s23()
    else:
        # 사용자 지정 디바이스
        if args.os_version:
            device_config = get_full_config(args.device, args.browser, args.os_version)
            if not device_config:
                print(f"❌ 디바이스를 찾을 수 없습니다: {args.device} ({args.browser}, {args.os_version})")
                sys.exit(1)
        else:
            # OS 버전 미지정 - 가장 최신 OS 버전 선택
            devices = load_mobile_real_devices()
            matching = [
                d for d in devices
                if d['device'] == args.device
                and d['browser'] == args.browser
            ]

            if not matching:
                print(f"❌ 디바이스를 찾을 수 없습니다: {args.device} ({args.browser})")
                sys.exit(1)

            # 가장 높은 OS 버전 선택
            matching.sort(key=lambda x: x['os_version'], reverse=True)
            device_config = matching[0]

    # 수집 시작
    collector = TLSSampleCollector(device_config, num_samples=args.samples)

    try:
        collector.collect_all()
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n\n❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        collector.print_final_stats()


if __name__ == '__main__':
    main()
