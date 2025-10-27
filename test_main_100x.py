#!/usr/bin/env python3
"""
main.py를 100번 반복 호출하여 성공률 테스트

Args:
    --device: 디바이스명
    --browser: 브라우저
    --os-version: OS 버전
    --keyword: 검색 키워드
    --delay: 반복 간 딜레이 (초)
"""

import subprocess
import json
import time
from datetime import datetime
import argparse

def run_main(device_name, browser, os_version, keyword):
    """main.py를 1회 실행하고 결과 반환"""

    # main.py 실행 (2페이지만)
    cmd = [
        'python', 'main.py',
        '--keyword', keyword,
        '--start', '1',
        '--end', '2',
        '--workers', '1'
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60
    )

    # search_history에서 최근 결과 읽기
    import glob
    history_files = sorted(glob.glob('data/search_history/*.json'), reverse=True)

    if history_files:
        with open(history_files[0]) as f:
            data = json.load(f)
        return data

    return None

def test_100_iterations(device_name, browser, os_version, keyword="테스트", delay=2.0):
    """
    main.py를 100번 반복 실행하여 성공률 테스트
    """
    print("="*80)
    print(f"100번 반복 테스트 (main.py 반복 호출)")
    print(f"디바이스: {device_name}")
    print(f"브라우저: {browser}")
    print(f"OS: {os_version}")
    print(f"키워드: {keyword}")
    print("="*80)

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
            # main.py 실행
            data = run_main(device_name, browser, os_version, keyword)

            if not data:
                print(f"  {i:3}/100: ❌ 에러: 결과 읽기 실패")
                results['page1_failure'] += 1
                time.sleep(delay)
                continue

            successful = data['results']['successful_pages']
            total = data['results']['total_pages']

            if successful == 0:
                results['page1_failure'] += 1
                marker = '🚫'
                print(f"  {i:3}/100: {marker} 페이지1 실패")
            elif successful == 1:
                results['page1_only'] += 1
                results['page2_failure'] += 1
                marker = '🔴'
                if i % 10 == 0:
                    page1_only_rate = results['page1_only'] / i * 100
                    print(f"  {i:3}/100: {marker} 1페이지만 성공 ({page1_only_rate:5.1f}%)")
            elif successful == 2:
                results['both_pages_success'] += 1
                marker = '✅'
                if i % 10 == 0:
                    both_rate = results['both_pages_success'] / i * 100
                    print(f"  {i:3}/100: {marker} 2페이지 성공 ({both_rate:5.1f}%)")

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

    output_file = f"/tmp/test_main_100x_{device_name.replace(' ', '_')}_{browser}_{os_version}.json"
    with open(output_file, 'w') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 결과 저장: {output_file}")
    print("="*80)

    return result_data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='100번 반복 테스트 (main.py 호출)')
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
