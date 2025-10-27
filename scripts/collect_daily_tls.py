"""
일자별 TLS 정보 수집 스크립트
모든 BrowserStack 디바이스를 순회하며 TLS fingerprint 수집

수집 URL:
- https://tls.browserleaks.com/ (HTML + 스크린샷)
- https://tls.peet.ws/api/all (JSON)

각 디바이스당 3회 수집 (실제 할당 기기가 다를 수 있음)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from data.mobile_real_devices import load_mobile_real_devices
from lib.settings import (
    BROWSERSTACK_USERNAME,
    BROWSERSTACK_ACCESS_KEY,
    BROWSERSTACK_HUB,
    BROWSERSTACK_PROJECT_NAME,
    get_device_identifier
)

# BrowserStack Local
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils'))
from browserstack_local import ensure_local_running


class DailyTLSCollector:
    """일자별 TLS 정보 수집기"""

    def __init__(self):
        """초기화"""
        # 오늘 날짜 (한국 시간 기준)
        kst = timezone(timedelta(hours=9))
        self.today = datetime.now(kst).strftime('%Y-%m-%d')

        # 저장 디렉토리
        self.save_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data',
            'tls_daily',
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

        # 시작 시간
        self.start_time = time.time()

    def _generate_build_name(self, device_config, round_num):
        """
        빌드명 생성
        형식: TLS Daily | 2025-10-23 18:30 | Round 1/3 | Samsung Android 12.0
        """
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)
        date_time = now_kst.strftime('%Y-%m-%d %H:%M')

        device_name = device_config['device']
        browser = device_config['browser'].capitalize()
        os_name = device_config['os'].capitalize()
        os_version = device_config['os_version']

        build_name = (
            f"TLS Daily | {date_time} | "
            f"Round {round_num}/3 | "
            f"{device_name} | {browser} | {os_name} {os_version}"
        )

        return build_name

    def create_driver(self, device_config, round_num):
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
            "projectName": f"{BROWSERSTACK_PROJECT_NAME} - TLS Daily",
            "buildName": self._generate_build_name(device_config, round_num),
            "sessionName": f"{device_config['device']} - Round {round_num}",
            "deviceName": device_config['device'],
            "osVersion": device_config['os_version'],
            "browserName": device_config['browser'],
            "realMobile": device_config.get('real_mobile', True),
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

    def collect_tls_info(self, device_config, round_num):
        """
        단일 디바이스에서 TLS 정보 수집

        Args:
            device_config: 디바이스 설정
            round_num: 라운드 번호 (1, 2, 3)

        Returns:
            dict: 수집 결과 또는 None (실패 시)
        """
        driver = None

        try:
            # 드라이버 생성
            driver = self.create_driver(device_config, round_num)

            # 결과 저장 객체
            result = {
                'device': device_config['device'],
                'browser': device_config['browser'],
                'os': device_config['os'],
                'os_version': device_config['os_version'],
                'real_mobile': device_config.get('real_mobile', True),
                'round': round_num,
                'timestamp': datetime.now().isoformat(),
                'browserleaks': {},
                'peet_ws': {}
            }

            # 1. browserleaks.com 수집
            print(f"      → browserleaks.com 로딩...")
            driver.get('https://tls.browserleaks.com/')
            time.sleep(5)  # 페이지 로딩 대기

            result['browserleaks'] = {
                'url': 'https://tls.browserleaks.com/',
                'html': driver.page_source,
                'screenshot': driver.get_screenshot_as_base64()
            }

            # 2. peet.ws/api/all 수집
            print(f"      → peet.ws/api/all 로딩...")
            driver.get('https://tls.peet.ws/api/all')
            time.sleep(3)

            # JSON 데이터 추출
            try:
                page_text = driver.find_element(By.TAG_NAME, 'pre').text
                peet_data = json.loads(page_text)
                result['peet_ws'] = {
                    'url': 'https://tls.peet.ws/api/all',
                    'data': peet_data
                }
            except Exception as e:
                print(f"      ⚠️ peet.ws JSON 파싱 실패: {e}")
                result['peet_ws'] = {
                    'url': 'https://tls.peet.ws/api/all',
                    'error': str(e),
                    'raw_html': driver.page_source
                }

            return result

        except Exception as e:
            print(f"      ❌ 수집 실패: {e}")
            self.stats['errors'].append({
                'device': device_config['device'],
                'browser': device_config['browser'],
                'os_version': device_config['os_version'],
                'round': round_num,
                'error': str(e)
            })
            return None

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def save_result(self, result):
        """결과를 JSON 파일로 저장"""
        if not result:
            return False

        # 파일명 생성
        device_safe = result['device'].replace(' ', '_').replace('/', '_')
        browser = result['browser']
        os_version = result['os_version'].replace('.', '_')
        round_num = result['round']

        filename = f"{device_safe}_{browser}_{os_version}_round{round_num}.json"
        filepath = os.path.join(self.save_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"      ⚠️ 파일 저장 실패: {e}")
            return False

    def print_progress(self, current, total, round_num, device_name):
        """진행 상황 출력"""
        elapsed = time.time() - self.start_time
        progress = (current - 1) / total if total > 0 else 0

        # 예상 남은 시간
        if progress > 0:
            estimated_total = elapsed / progress
            remaining = estimated_total - elapsed
            remaining_str = time.strftime('%H:%M:%S', time.gmtime(remaining))
        else:
            remaining_str = "계산 중..."

        # 진행률
        percentage = (current / total * 100) if total > 0 else 0

        print(f"\n{'='*70}")
        print(f"[라운드 {round_num}/3] [{current}/{total}] {device_name}")
        print(f"진행률: {percentage:.1f}% | 성공: {self.stats['success']} | 실패: {self.stats['failed']}")
        print(f"경과: {time.strftime('%H:%M:%S', time.gmtime(elapsed))} | 남은 시간: {remaining_str}")
        print(f"{'='*70}")

    def collect_all(self):
        """모든 디바이스 순회하며 TLS 정보 수집 (3회)"""
        # 모든 디바이스 로드
        devices = load_mobile_real_devices()
        total_devices = len(devices)

        print(f"\n{'='*70}")
        print(f"일자별 TLS 정보 수집 시작")
        print(f"{'='*70}")
        print(f"날짜: {self.today}")
        print(f"총 디바이스: {total_devices}개")
        print(f"라운드: 3회")
        print(f"총 수집 횟수: {total_devices * 3}회")
        print(f"저장 위치: {self.save_dir}")
        print(f"{'='*70}\n")

        input("⏸️  Enter 키를 눌러 시작... ")

        # 3회 순회
        for round_num in range(1, 4):
            print(f"\n\n{'#'*70}")
            print(f"# 라운드 {round_num}/3 시작")
            print(f"{'#'*70}\n")

            # 전체 디바이스 순회
            for idx, device_config in enumerate(devices, 1):
                self.stats['total'] += 1

                # 진행 상황 출력
                device_name = device_config['device']
                browser = device_config['browser']
                os_version = device_config['os_version']

                self.print_progress(idx, total_devices, round_num,
                                   f"{device_name} ({browser}, {os_version})")

                # TLS 정보 수집
                try:
                    result = self.collect_tls_info(device_config, round_num)

                    if result and self.save_result(result):
                        self.stats['success'] += 1
                        print(f"   ✅ 수집 완료")
                    else:
                        self.stats['failed'] += 1
                        print(f"   ❌ 수집 실패")

                except Exception as e:
                    self.stats['failed'] += 1
                    print(f"   ❌ 예외 발생: {e}")

                # 다음 디바이스까지 대기 (BrowserStack API 부하 방지)
                time.sleep(2)

            print(f"\n{'#'*70}")
            print(f"# 라운드 {round_num}/3 완료")
            print(f"{'#'*70}\n")

            # 라운드 간 대기
            if round_num < 3:
                print(f"⏳ 다음 라운드까지 10초 대기...\n")
                time.sleep(10)

    def print_final_stats(self):
        """최종 통계 출력"""
        elapsed = time.time() - self.start_time

        print(f"\n\n{'='*70}")
        print(f"최종 통계")
        print(f"{'='*70}")
        print(f"총 시도: {self.stats['total']}회")
        print(f"✅ 성공: {self.stats['success']}회 ({self.stats['success']/self.stats['total']*100:.1f}%)")
        print(f"❌ 실패: {self.stats['failed']}회 ({self.stats['failed']/self.stats['total']*100:.1f}%)")
        print(f"소요 시간: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
        print(f"저장 위치: {self.save_dir}")
        print(f"{'='*70}")

        # 에러 상세
        if self.stats['errors']:
            print(f"\n에러 상세 (최대 10개):")
            for error in self.stats['errors'][:10]:
                print(f"  - {error['device']} ({error['browser']}, {error['os_version']}) Round {error['round']}")
                print(f"    {error['error'][:100]}")


def main():
    """메인 함수"""
    collector = DailyTLSCollector()

    try:
        collector.collect_all()
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n\n❌ 예외 발생: {e}")
    finally:
        collector.print_final_stats()


if __name__ == '__main__':
    main()
