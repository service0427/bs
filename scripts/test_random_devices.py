#!/usr/bin/env python3
"""
Random Device Tester
랜덤 디바이스 테스터

Tests 10 randomly selected devices with TLS collection + 1 page crawl.
랜덤으로 선택된 10개 디바이스를 TLS 수집 + 1페이지 크롤링으로 테스트합니다.

Purpose: Validate analysis infrastructure before full collection.
목적: 전체 수집 전에 분석 인프라 검증.
"""

import os
import sys
import random
import time
from datetime import datetime

# 프로젝트 루트 경로 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from data.mobile_real_devices import get_all_device_configs
from lib.collectors.dynamic import DynamicCollector
from lib.crawler.custom_tls import CustomTLSCrawler


class RandomDeviceTester:
    """
    Random Device Tester
    랜덤 디바이스 테스터

    Tests a random sample of devices to validate analysis infrastructure.
    분석 인프라 검증을 위해 랜덤 샘플 디바이스를 테스트합니다.
    """

    def __init__(self, sample_size=10, keyword='아이폰', force_refresh=True, max_retries=3):
        """
        Initialize tester
        테스터 초기화

        Args:
            sample_size: Number of devices to test (테스트할 디바이스 수)
            keyword: Search keyword for crawling (크롤링 검색 키워드)
            force_refresh: Always recollect TLS/cookies (항상 TLS/쿠키 재수집)
            max_retries: Maximum retry attempts per device (디바이스당 최대 재시도 횟수)
        """
        self.sample_size = sample_size
        self.keyword = keyword
        self.force_refresh = force_refresh
        self.max_retries = max_retries

        # Results tracking (결과 추적)
        self.successful_devices = []  # 성공한 디바이스
        self.failed_devices = []      # 실패한 디바이스
        self.skipped_devices = []     # 건너뛴 디바이스

        # Timing (시간 측정)
        self.start_time = None
        self.end_time = None

    def get_random_devices(self):
        """
        Get random device sample
        랜덤 디바이스 샘플 가져오기

        Returns:
            list: Random device configurations (랜덤 디바이스 설정 목록)
        """
        all_devices = get_all_device_configs()

        # Filter out devices without required fields
        # 필수 필드가 없는 디바이스 필터링
        valid_devices = []
        for device in all_devices:
            if all(key in device for key in ['device', 'os', 'os_version', 'browser']):
                valid_devices.append(device)

        # Random sample (랜덤 샘플링)
        sample = random.sample(valid_devices, min(self.sample_size, len(valid_devices)))

        return sample

    def test_device(self, device_config, index, total):
        """
        Test a single device
        단일 디바이스 테스트

        Args:
            device_config: Device configuration dict (디바이스 설정 딕셔너리)
            index: Current device index (현재 디바이스 인덱스)
            total: Total devices to test (테스트할 전체 디바이스 수)

        Returns:
            dict: Test result (테스트 결과)
        """
        device_name = device_config['device']
        browser = device_config.get('browser', 'android')
        os_version = device_config['os_version']

        print("\n" + "="*70)
        print(f"Testing Device {index}/{total}")
        print(f"디바이스 테스트 중 {index}/{total}")
        print("="*70)
        print(f"  Device: {device_name}")
        print(f"  Browser: {browser}")
        print(f"  OS: {device_config['os']} {os_version}")
        print("="*70 + "\n")

        result = {
            'device_name': device_name,
            'browser': browser,
            'os_version': os_version,
            'tls_collected': False,
            'cookies_collected': False,
            'crawl_success': False,
            'error': None,
            'attempts': 0
        }

        # Retry loop (재시도 루프)
        for attempt in range(1, self.max_retries + 1):
            result['attempts'] = attempt

            try:
                if attempt > 1:
                    print(f"\n🔄 Retry {attempt}/{self.max_retries}")
                    print(f"🔄 재시도 {attempt}/{self.max_retries}")
                    time.sleep(3)  # Wait before retry (재시도 전 대기)

                # STEP 1: Collect TLS + Cookies
                # 단계 1: TLS + 쿠키 수집
                print(f"\n[STEP 1] Collecting TLS fingerprint and cookies")
                print(f"[단계 1] TLS 지문 및 쿠키 수집 중")

                # DynamicCollector expects device_config dict
                # DynamicCollector는 device_config 딕셔너리를 받음
                refresh_policy = 'force' if self.force_refresh else 'auto'

                collector = DynamicCollector(
                    device_config=device_config,
                    refresh_policy=refresh_policy
                )

                collector.collect()  # Correct method name
                result['tls_collected'] = True
                result['cookies_collected'] = True
                print(f"  ✅ TLS and cookies collected")
                print(f"  ✅ TLS 및 쿠키 수집 완료")

                # STEP 2: Crawl 1 page
                # 단계 2: 1페이지 크롤링
                print(f"\n[STEP 2] Crawling 1 page with keyword '{self.keyword}'")
                print(f"[단계 2] 키워드 '{self.keyword}'로 1페이지 크롤링 중")

                crawler = CustomTLSCrawler(
                    device_name=device_name,
                    browser=browser,
                    device_config=device_config
                )

                crawl_result = crawler.crawl_page(keyword=self.keyword, page=1)

                if crawl_result.get('success'):
                    result['crawl_success'] = True
                    result['ranking_count'] = len(crawl_result.get('ranking', []))
                    result['ads_count'] = len(crawl_result.get('ads', []))
                    result['total_count'] = crawl_result.get('total', 0)

                    print(f"\n  ✅ Crawl successful!")
                    print(f"  ✅ 크롤링 성공!")
                    print(f"     - Ranking products: {result['ranking_count']}")
                    print(f"     - 랭킹 상품: {result['ranking_count']}개")
                    print(f"     - Ad products: {result['ads_count']}")
                    print(f"     - 광고 상품: {result['ads_count']}개")

                    # Success - break retry loop (성공 - 재시도 루프 종료)
                    break
                else:
                    error_msg = crawl_result.get('error', 'Unknown error')
                    result['error'] = error_msg
                    print(f"\n  ❌ Crawl failed: {error_msg}")
                    print(f"  ❌ 크롤링 실패: {error_msg}")

                    # If last attempt, give up (마지막 시도면 포기)
                    if attempt == self.max_retries:
                        print(f"\n  ⚠️  Max retries reached, moving to next device")
                        print(f"  ⚠️  최대 재시도 횟수 도달, 다음 디바이스로 이동")
                        break

            except Exception as e:
                result['error'] = str(e)
                print(f"\n  ❌ Exception occurred: {str(e)[:100]}")
                print(f"  ❌ 예외 발생: {str(e)[:100]}")

                # If last attempt, give up (마지막 시도면 포기)
                if attempt == self.max_retries:
                    print(f"\n  ⚠️  Max retries reached, moving to next device")
                    print(f"  ⚠️  최대 재시도 횟수 도달, 다음 디바이스로 이동")
                    break

        return result

    def run(self):
        """
        Run random device test
        랜덤 디바이스 테스트 실행

        Returns:
            dict: Test summary (테스트 요약)
        """
        print("\n" + "🎲"*35)
        print("Random Device Tester - Phase 2")
        print("랜덤 디바이스 테스터 - Phase 2")
        print("🎲"*35)
        print(f"\nConfiguration (설정):")
        print(f"  - Sample size: {self.sample_size} devices")
        print(f"  - 샘플 크기: {self.sample_size}개 디바이스")
        print(f"  - Keyword: '{self.keyword}'")
        print(f"  - 키워드: '{self.keyword}'")
        print(f"  - Force refresh: {self.force_refresh}")
        print(f"  - 강제 재수집: {self.force_refresh}")
        print(f"  - Max retries: {self.max_retries}")
        print(f"  - 최대 재시도: {self.max_retries}회")
        print()

        # Get random devices (랜덤 디바이스 가져오기)
        self.start_time = datetime.now()
        devices = self.get_random_devices()

        print(f"Selected {len(devices)} random devices:")
        print(f"{len(devices)}개 랜덤 디바이스 선택됨:\n")
        for i, device in enumerate(devices, 1):
            print(f"  {i}. {device['device']} ({device.get('browser', 'android')}, {device['os']} {device['os_version']})")

        print("\n" + "="*70)
        print("Starting sequential testing...")
        print("순차 테스트 시작...")
        print("="*70)

        # Test each device sequentially (각 디바이스를 순차적으로 테스트)
        for index, device in enumerate(devices, 1):
            result = self.test_device(device, index, len(devices))

            # Categorize result (결과 분류)
            if result['crawl_success']:
                self.successful_devices.append(result)
            else:
                self.failed_devices.append(result)

            # Progress update (진행 상황 업데이트)
            success_count = len(self.successful_devices)
            fail_count = len(self.failed_devices)
            print(f"\n📊 Progress: {index}/{len(devices)} | Success: {success_count} | Failed: {fail_count}")
            print(f"📊 진행 상황: {index}/{len(devices)} | 성공: {success_count} | 실패: {fail_count}")

            # Delay between devices (디바이스 간 딜레이)
            if index < len(devices):
                delay = 2
                print(f"\n⏳ Waiting {delay}s before next device...")
                print(f"⏳ 다음 디바이스까지 {delay}초 대기...\n")
                time.sleep(delay)

        self.end_time = datetime.now()

        # Print final summary (최종 요약 출력)
        self.print_summary()

        return {
            'total': len(devices),
            'successful': len(self.successful_devices),
            'failed': len(self.failed_devices),
            'duration': (self.end_time - self.start_time).total_seconds()
        }

    def print_summary(self):
        """
        Print test summary
        테스트 요약 출력
        """
        duration = (self.end_time - self.start_time).total_seconds()
        total = len(self.successful_devices) + len(self.failed_devices)

        print("\n\n" + "="*70)
        print("📋 Test Summary / 테스트 요약")
        print("="*70)
        print(f"\n⏱️  Duration: {duration:.1f}s")
        print(f"⏱️  소요 시간: {duration:.1f}초")
        print(f"\n📊 Results:")
        print(f"📊 결과:")
        print(f"  - Total tested: {total}")
        print(f"  - 전체 테스트: {total}개")
        print(f"  - ✅ Successful: {len(self.successful_devices)} ({len(self.successful_devices)/total*100:.1f}%)")
        print(f"  - ✅ 성공: {len(self.successful_devices)}개 ({len(self.successful_devices)/total*100:.1f}%)")
        print(f"  - ❌ Failed: {len(self.failed_devices)} ({len(self.failed_devices)/total*100:.1f}%)")
        print(f"  - ❌ 실패: {len(self.failed_devices)}개 ({len(self.failed_devices)/total*100:.1f}%)")

        if self.successful_devices:
            print(f"\n✅ Successful Devices:")
            print(f"✅ 성공한 디바이스:")
            for i, result in enumerate(self.successful_devices, 1):
                print(f"  {i}. {result['device_name']} ({result['browser']}) - {result['total_count']} products")

        if self.failed_devices:
            print(f"\n❌ Failed Devices:")
            print(f"❌ 실패한 디바이스:")
            for i, result in enumerate(self.failed_devices, 1):
                error_short = result['error'][:50] if result.get('error') else 'Unknown'
                print(f"  {i}. {result['device_name']} ({result['browser']}) - {error_short}")

        print("\n" + "="*70)
        print("🎉 Testing complete! Check database for detailed metrics.")
        print("🎉 테스트 완료! 상세 메트릭은 데이터베이스에서 확인하세요.")
        print("="*70 + "\n")


def main():
    """Main entry point / 메인 진입점"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Test random devices to validate analysis infrastructure'
    )
    parser.add_argument('--sample-size', type=int, default=10,
                       help='Number of devices to test (default: 10)')
    parser.add_argument('--keyword', type=str, default='아이폰',
                       help='Search keyword (default: 아이폰)')
    parser.add_argument('--no-force', action='store_true',
                       help='Do not force refresh (use existing data if valid)')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Maximum retry attempts per device (default: 3)')

    args = parser.parse_args()

    tester = RandomDeviceTester(
        sample_size=args.sample_size,
        keyword=args.keyword,
        force_refresh=not args.no_force,
        max_retries=args.max_retries
    )

    tester.run()


if __name__ == '__main__':
    main()
