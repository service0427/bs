#!/usr/bin/env python3
"""
main.py 로직을 그대로 사용한 100번 테스트
lib-test를 사용하여 원본 lib에 영향 없음
"""

import sys
# lib-test 경로 추가
sys.path.insert(0, '/var/www/html/browserstack/lib-test')
sys.path.insert(1, '/var/www/html/browserstack')

# lib-test의 모듈 import
from crawler.custom_tls import CustomTLSCrawler

import json
import time
from datetime import datetime

def test_100_iterations(device_name, browser, os_version, keyword="테스트", delay=2.0):
    """
    main.py와 동일한 방식으로 100번 테스트
    """
    print("="*80)
    print(f"100번 반복 테스트 (main.py 로직 사용)")
    print(f"디바이스: {device_name}")
    print(f"브라우저: {browser}")
    print(f"OS: {os_version}")
    print(f"키워드: {keyword}")
    print("="*80)

    # 크롤러 생성 (main.py와 동일)
    # CustomTLSCrawler가 내부에서 자동으로 TLS 정보 로드
    print(f"\n🔧 크롤러 초기화 중...")
    try:
        crawler = CustomTLSCrawler(
            device_name=device_name,
            browser=browser
        )
        print(f"✅ 크롤러 초기화 성공")
    except Exception as e:
        print(f"❌ 크롤러 초기화 실패: {e}")
        return None

    # 결과 추적
    results = {
        'both_pages_success': 0,       # 페이지 1, 2 모두 성공
        'page1_only': 0,                # 페이지 1만 성공
        'page2_failure': 0,             # 페이지 2 실패
        'page1_failure': 0,             # 페이지 1부터 실패
        'total': 100
    }

    start_time = time.time()

    print(f"\n🔄 100번 반복 테스트 시작 (딜레이: {delay}초)...\n")

    for i in range(1, 101):
        try:
            # 페이지 1 크롤링
            result1 = crawler.crawl_page(
                keyword=keyword,
                page=1
            )

            page1_success = result1.get('success', False)

            if not page1_success:
                results['page1_failure'] += 1
                marker = '🚫'
                print(f"  {i:3}/100: {marker} 페이지1 실패")
                time.sleep(delay)
                continue

            # 페이지 1 성공, 이제 페이지 2 시도
            time.sleep(1)  # 페이지 간 딜레이

            result2 = crawler.crawl_page(
                keyword=keyword,
                page=2
            )

            page2_success = result2.get('success', False)

            if page2_success:
                results['both_pages_success'] += 1
                marker = '✅'
            else:
                results['page1_only'] += 1
                results['page2_failure'] += 1
                marker = '🔴'

            # 10회마다 진행 상황 출력
            if i % 10 == 0:
                both_rate = results['both_pages_success'] / i * 100
                page1_only_rate = results['page1_only'] / i * 100
                print(f"  {i:3}/100: {marker} (2페이지 성공: {both_rate:5.1f}%, 1페이지만: {page1_only_rate:5.1f}%)")

        except Exception as e:
            print(f"  {i:3}/100: ❌ 에러: {str(e)[:50]}")
            results['page1_failure'] += 1

        # 딜레이
        if i < 100:
            time.sleep(delay)

    elapsed = time.time() - start_time
    both_rate = results['both_pages_success'] / results['total'] * 100
    page1_only_rate = results['page1_only'] / results['total'] * 100

    # 결과 출력
    print(f"\n{'='*80}")
    print(f"📊 최종 결과")
    print(f"{'='*80}")
    print(f"  총 시도: {results['total']}회")
    print(f"  2페이지 모두 성공: {results['both_pages_success']}회 ({both_rate:.1f}%)")
    print(f"  1페이지만 성공: {results['page1_only']}회 ({page1_only_rate:.1f}%)")
    print(f"  2페이지 실패: {results['page2_failure']}회")
    print(f"  1페이지부터 실패: {results['page1_failure']}회")
    print(f"  소요 시간: {elapsed/60:.1f}분")

    # 결론
    print(f"\n🎯 결론:")
    if both_rate >= 80:
        verdict = "✅ 사용 가능"
        print(f"  {verdict}")
        print(f"  → 2페이지 연속 성공률 높음 ({both_rate:.1f}%)")
    elif both_rate >= 20:
        verdict = "⚠️ 주의 사용"
        print(f"  {verdict}")
        print(f"  → 2페이지 성공률 낮음 ({both_rate:.1f}%)")
        if page1_only_rate > 50:
            print(f"  → 1페이지만 성공하는 케이스 많음")
    else:
        verdict = "❌ 사용 불가"
        print(f"  {verdict}")
        print(f"  → 2페이지 성공률 극히 낮음 ({both_rate:.1f}%)")

    # 결과 저장
    result_data = {
        'device_name': device_name,
        'browser': browser,
        'os_version': os_version,
        'keyword': keyword,
        'results': results,
        'both_pages_success_rate': both_rate,
        'page1_only_rate': page1_only_rate,
        'elapsed_seconds': elapsed,
        'verdict': verdict,
        'tested_at': datetime.now().isoformat()
    }

    output_file = f"/tmp/test_100x_main_{device_name.replace(' ', '_')}_{browser}_{os_version}.json"
    with open(output_file, 'w') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 결과 저장: {output_file}")
    print("="*80)

    return result_data


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='100번 반복 테스트 (main.py 로직)')
    parser.add_argument('--device', required=True, help='디바이스명')
    parser.add_argument('--browser', required=True, help='브라우저')
    parser.add_argument('--os-version', required=True, help='OS 버전')
    parser.add_argument('--keyword', default='테스트', help='검색 키워드')
    parser.add_argument('--delay', type=float, default=2.0, help='요청 간 딜레이 (초)')

    args = parser.parse_args()

    test_100_iterations(
        device_name=args.device,
        browser=args.browser,
        os_version=args.os_version,
        keyword=args.keyword,
        delay=args.delay
    )
