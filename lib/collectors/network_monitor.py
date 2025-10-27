"""
BrowserStack Network Traffic Monitor
selenium-wire를 사용한 네트워크 트래픽 캡처
"""

import json
import time
from datetime import datetime
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.settings import (
    BROWSERSTACK_USERNAME,
    BROWSERSTACK_ACCESS_KEY,
    BROWSERSTACK_HUB,
    BROWSERSTACK_PROJECT_NAME,
)
from lib.utils.browserstack_local import ensure_local_running
from lib.device.selector import select_device


class NetworkMonitor:
    """BrowserStack 네트워크 트래픽 모니터링"""

    def __init__(self, device_config):
        """
        Args:
            device_config: dict {
                'device': 'Samsung Galaxy S21',
                'os': 'android',
                'os_version': '11.0',
                'browser': 'chrome',
                'real_mobile': True
            }
        """
        self.device_config = device_config
        self.driver = None
        self.network_logs = []

    def create_driver_with_network_logging(self):
        """네트워크 로깅이 활성화된 드라이버 생성"""

        # BrowserStack Local 시작
        local_identifier = 'browserstack-local'
        success, local_instance = ensure_local_running(local_identifier)
        if not success:
            raise RuntimeError("BrowserStack Local 연결 실패")

        # selenium-wire 옵션
        seleniumwire_options = {
            'verify_ssl': True,
        }

        # Chrome options
        options = webdriver.ChromeOptions()

        # BrowserStack capabilities
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)
        build_name = now_kst.strftime('%Y-%m-%d %H:%M') + f" | Network Monitor | {self.device_config['browser']}"

        bstack_options = {
            'userName': BROWSERSTACK_USERNAME,
            'accessKey': BROWSERSTACK_ACCESS_KEY,
            'projectName': BROWSERSTACK_PROJECT_NAME,
            'buildName': build_name,
            'deviceName': self.device_config['device'],
            'osVersion': self.device_config['os_version'],
            'browserName': self.device_config['browser'],
            'realMobile': str(self.device_config.get('real_mobile', True)).lower(),
            'local': 'true',
            'localIdentifier': local_identifier,
            'sessionName': f"Network Monitor - {self.device_config['device']}",
        }

        if self.device_config.get('browser_version'):
            bstack_options['browserVersion'] = self.device_config['browser_version']

        options.set_capability('bstack:options', bstack_options)

        print(f"\n[Network Monitor] 드라이버 생성 중...")
        print(f"  - Device: {self.device_config['device']}")
        print(f"  - Browser: {self.device_config['browser']}")
        print(f"  - Network Logging: Enabled (selenium-wire)")

        self.driver = webdriver.Remote(
            command_executor=BROWSERSTACK_HUB,
            options=options,
            seleniumwire_options=seleniumwire_options
        )

        self.driver.set_page_load_timeout(60)
        print(f"[Network Monitor] 드라이버 생성 완료\n")

        return self.driver

    def capture_coupang_workflow(self, keyword="아이폰"):
        """
        쿠팡 워크플로우 실행 및 네트워크 트래픽 캡처

        워크플로우:
        1. 쿠팡 메인 접속
        2. 배너 제거 (쿠키 배너 등)
        3. 검색
        4. 상품 클릭

        Args:
            keyword: 검색 키워드

        Returns:
            dict: 캡처된 네트워크 로그
        """

        if not self.driver:
            self.create_driver_with_network_logging()

        print("="*70)
        print("쿠팡 워크플로우 네트워크 모니터링 시작")
        print("="*70)

        # 1. 쿠팡 메인 접속
        print("\n[STEP 1] 쿠팡 메인 접속")
        self.driver.get("https://www.coupang.com")
        time.sleep(3)

        # 네트워크 로그 수집
        self._collect_network_logs("main_page")

        # 2. 배너 제거 시도 (쿠키 배너 등)
        print("\n[STEP 2] 배너 제거 시도")
        try:
            # 쿠키 배너 닫기 버튼 찾기 (예시)
            close_buttons = self.driver.find_elements(By.CSS_SELECTOR,
                "[class*='close'], [class*='dismiss'], [aria-label*='close'], [aria-label*='닫기']")

            for btn in close_buttons[:3]:  # 최대 3개까지만 시도
                try:
                    if btn.is_displayed():
                        btn.click()
                        print(f"  ✓ 배너 닫기 버튼 클릭")
                        time.sleep(1)
                except:
                    pass
        except Exception as e:
            print(f"  ⚠️ 배너 제거 실패 (무시): {e}")

        # 3. 검색
        print(f"\n[STEP 3] 검색: {keyword}")
        try:
            # 검색창 찾기
            search_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='q'], input[type='search']"))
            )

            # 검색창으로 스크롤
            self.driver.execute_script("arguments[0].scrollIntoView(true);", search_input)
            time.sleep(1)

            # JavaScript로 클릭 및 입력
            self.driver.execute_script("arguments[0].click();", search_input)
            search_input.clear()
            search_input.send_keys(keyword)
            print(f"  ✓ 검색어 입력: {keyword}")

            # 검색 버튼 클릭
            search_button = self.driver.find_element(By.CSS_SELECTOR,
                "button[type='submit'], button.search-btn, button[class*='search']")
            self.driver.execute_script("arguments[0].click();", search_button)
            print(f"  ✓ 검색 실행")

            time.sleep(5)  # 결과 로딩 대기

            # 네트워크 로그 수집
            self._collect_network_logs("search_results")

        except Exception as e:
            print(f"  ❌ 검색 실패: {e}")

        # 4. 상품 클릭
        print("\n[STEP 4] 첫 번째 상품 클릭")
        try:
            # 첫 번째 상품 링크 찾기
            product_links = self.driver.find_elements(By.CSS_SELECTOR,
                "a[href*='/vp/products/']")

            if product_links:
                first_product = product_links[0]
                product_name = first_product.get_attribute('title') or first_product.text
                print(f"  ✓ 상품 찾음: {product_name[:50]}...")

                # 상품으로 스크롤
                self.driver.execute_script("arguments[0].scrollIntoView(true);", first_product)
                time.sleep(1)

                # JavaScript로 클릭
                self.driver.execute_script("arguments[0].click();", first_product)
                print(f"  ✓ 상품 클릭 완료")

                time.sleep(5)  # 상품 페이지 로딩 대기

                # 네트워크 로그 수집
                self._collect_network_logs("product_detail")

            else:
                print(f"  ⚠️ 상품을 찾을 수 없습니다")

        except Exception as e:
            print(f"  ❌ 상품 클릭 실패: {e}")

        print("\n" + "="*70)
        print("워크플로우 완료")
        print("="*70)

        return self._analyze_logs()

    def _collect_network_logs(self, step_name):
        """
        selenium-wire로 네트워크 요청 수집

        Args:
            step_name: 단계 이름 (main_page, search_results, product_detail)
        """

        print(f"\n  [네트워크 로그 수집: {step_name}]")

        try:
            request_count = 0

            # selenium-wire의 driver.requests에서 모든 요청 가져오기
            for request in self.driver.requests:
                # 쿠팡 관련 요청만 필터링
                if 'coupang.com' in request.url:
                    # Request 정보 저장
                    log_data = {
                        'step': step_name,
                        'timestamp': time.time(),
                        'type': 'request',
                        'url': request.url,
                        'method': request.method,
                        'headers': dict(request.headers),
                        'body': request.body.decode('utf-8', errors='ignore') if request.body else None,
                    }

                    # Response 정보 추가 (있는 경우)
                    if request.response:
                        log_data['response'] = {
                            'status_code': request.response.status_code,
                            'reason': request.response.reason,
                            'headers': dict(request.response.headers),
                        }

                    self.network_logs.append(log_data)
                    request_count += 1

            print(f"  ✓ {request_count}개 요청 캡처됨")

            # 처리된 요청 삭제 (메모리 관리)
            del self.driver.requests

        except Exception as e:
            print(f"  ❌ 로그 수집 실패: {e}")

    def _analyze_logs(self):
        """네트워크 로그 분석"""

        print("\n" + "="*70)
        print("네트워크 트래픽 분석")
        print("="*70)

        # 단계별 통계
        steps = {}
        for log in self.network_logs:
            step = log['step']
            if step not in steps:
                steps[step] = {'requests': 0}

            steps[step]['requests'] += 1

        print("\n[단계별 통계]")
        for step, stats in steps.items():
            print(f"  {step}: {stats['requests']}개 요청")

        # 주요 헤더 분석
        print("\n[주요 Request Headers 샘플]")
        shown = 0
        for log in self.network_logs:
            if shown >= 5:  # 최대 5개만
                break

            print(f"\n  URL: {log['url'][:80]}...")
            print(f"  Method: {log['method']}")

            if log.get('response'):
                print(f"  Status: {log['response']['status_code']} {log['response']['reason']}")

            headers = log['headers']

            important_headers = [
                'user-agent', 'accept', 'accept-language', 'accept-encoding',
                'referer', 'cookie', 'sec-ch-ua', 'sec-ch-ua-mobile',
                'sec-ch-ua-platform', 'sec-fetch-dest', 'sec-fetch-mode',
                'sec-fetch-site', 'sec-fetch-user'
            ]

            for header in important_headers:
                # 대소문자 구분 없이 헤더 찾기
                value = None
                for key in headers:
                    if key.lower() == header.lower():
                        value = headers[key]
                        break

                if value:
                    display_value = value[:100] + "..." if len(value) > 100 else value
                    print(f"    {header}: {display_value}")

            shown += 1

        return {
            'total_logs': len(self.network_logs),
            'steps': steps,
            'logs': self.network_logs
        }

    def save_logs(self, output_file=None):
        """네트워크 로그를 JSON 파일로 저장"""

        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            device_name = self.device_config['device'].replace(' ', '_')
            output_file = f"data/network_logs/{device_name}_{timestamp}.json"

        # 디렉토리 생성
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.network_logs, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 네트워크 로그 저장: {output_file}")
        print(f"   총 {len(self.network_logs)}개 이벤트")

        return output_file

    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            print("\n[Network Monitor] 드라이버 종료")


def main():
    """테스트 실행"""

    print("\n" + "="*70)
    print(" "*15 + "Network Traffic Monitor")
    print(" "*10 + "실제 브라우저 워크플로우 네트워크 분석")
    print("="*70)

    # 디바이스 선택
    device_config = select_device()
    if not device_config:
        print("\n❌ 디바이스 선택 실패")
        return False

    monitor = NetworkMonitor(device_config)

    try:
        # 워크플로우 실행 및 네트워크 캡처
        result = monitor.capture_coupang_workflow(keyword="아이폰")

        # 로그 저장
        monitor.save_logs()

        print(f"\n✅ 완료!")
        print(f"   총 {result['total_logs']}개 네트워크 이벤트 캡처됨")

        return True

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        monitor.close()


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
