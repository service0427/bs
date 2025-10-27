"""
디바이스 화이트리스트 테스트 스크립트
각 디바이스를 10페이지 크롤링하여 통과 여부 확인
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.crawler.custom_tls import CustomTLSCrawler
from lib.settings import get_device_fingerprint_dir


def test_device(device_name, browser, os_version):
    """
    디바이스 테스트 (10페이지 크롤링)

    Returns:
        dict: {
            'device': str,
            'browser': str,
            'os_version': str,
            'success': bool,
            'pages_passed': int,
            'error': str or None
        }
    """

    result = {
        'device': device_name,
        'browser': browser,
        'os_version': os_version,
        'success': False,
        'pages_passed': 0,
        'error': None
    }

    try:
        # 디바이스 설정
        device_config = {
            'device': device_name,
            'browser': browser,
            'os_version': os_version
        }

        # 크롤러 생성
        crawler = CustomTLSCrawler(device_name, browser)

        # 10페이지 크롤링 시도
        keyword = "테스트"

        for page in range(1, 11):
            print(f"  [{device_name}] 페이지 {page} 테스트 중...")

            try:
                crawl_result = crawler.crawl_page(
                    keyword=keyword,
                    page=page,
                    max_retries=1  # 빠른 테스트
                )

                if crawl_result['success']:
                    result['pages_passed'] = page
                    print(f"    ✅ 페이지 {page} 성공")
                else:
                    print(f"    ❌ 페이지 {page} 실패")
                    result['error'] = f"페이지 {page}에서 차단"
                    break

            except Exception as e:
                print(f"    ❌ 페이지 {page} 에러: {str(e)[:50]}")
                result['error'] = str(e)[:100]
                break

        # 10페이지 모두 통과하면 성공
        if result['pages_passed'] == 10:
            result['success'] = True
            print(f"  ✅ [{device_name}] 화이트리스트 등록!")
        else:
            print(f"  ❌ [{device_name}] {result['pages_passed']}/10 페이지만 통과")

    except Exception as e:
        result['error'] = str(e)[:100]
        print(f"  ❌ [{device_name}] 테스트 실패: {result['error']}")

    return result


def main():
    """메인 테스트"""

    print("\n" + "="*70)
    print("디바이스 화이트리스트 테스트")
    print("="*70 + "\n")

    # 테스트할 디바이스 목록
    test_devices = [
        # Samsung Browser (우선 테스트)
        ('Samsung Galaxy S21 Plus', 'samsung', '11.0'),
        ('Samsung Galaxy S22', 'samsung', '12.0'),
        ('Samsung Galaxy S23', 'samsung', '13.0'),
        ('Samsung Galaxy S24', 'samsung', '14.0'),
        ('Samsung Galaxy A52', 'samsung', '11.0'),

        # iPhone Safari
        ('iPhone 15', 'iphone', '26'),
        ('iPhone 14 Pro', 'iphone', '26'),
        ('iPhone 16 Pro Max', 'iphone', '18'),

        # iPhone Chrome
        ('iPhone 15', 'chromium', '26'),
        ('iPhone 14 Pro', 'chromium', '26'),

        # Android Chrome (차단 예상)
        ('Samsung Galaxy S21 Plus', 'android', '11.0'),
        ('Samsung Galaxy S22', 'android', '12.0'),
    ]

    results = []

    for device_name, browser, os_version in test_devices:
        print(f"\n{'='*70}")
        print(f"테스트: {device_name} + {browser} ({os_version})")
        print(f"{'='*70}")

        result = test_device(device_name, browser, os_version)
        results.append(result)

    # 결과 요약
    print(f"\n\n{'='*70}")
    print("테스트 결과 요약")
    print(f"{'='*70}\n")

    whitelist = []
    blacklist = []

    for result in results:
        device_str = f"{result['device']} + {result['browser']} ({result['os_version']})"

        if result['success']:
            print(f"✅ {device_str}")
            print(f"   → 10/10 페이지 통과 - 화이트리스트 등록")
            whitelist.append(result)
        else:
            print(f"❌ {device_str}")
            print(f"   → {result['pages_passed']}/10 페이지 통과")
            if result['error']:
                print(f"   → 에러: {result['error']}")
            blacklist.append(result)

    print(f"\n{'='*70}")
    print(f"✅ 화이트리스트: {len(whitelist)}개")
    print(f"❌ 블랙리스트: {len(blacklist)}개")
    print(f"{'='*70}\n")

    # JSON 저장
    output_file = 'data/device_test_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'total_tested': len(results),
            'whitelist_count': len(whitelist),
            'blacklist_count': len(blacklist),
            'whitelist': whitelist,
            'blacklist': blacklist
        }, f, indent=2, ensure_ascii=False)

    print(f"결과 저장: {output_file}")


if __name__ == '__main__':
    main()
