#!/usr/bin/env python3
"""
개선된 TLS Fingerprint 테스트
Samsung Galaxy S21 Ultra로 직접 테스트
"""

from lib.crawler.custom_tls import CustomTLSCrawler

if __name__ == "__main__":
    print("\n" + "="*70)
    print("개선된 TLS Fingerprint 테스트")
    print("="*70)
    print("\n테스트 디바이스: Samsung Galaxy S21 Ultra")
    print("테스트 키워드: 아이폰")
    print("테스트 페이지: 1\n")

    # 크롤러 생성
    crawler = CustomTLSCrawler(device_name="Samsung Galaxy S21 Ultra")

    # 단일 페이지 크롤링
    result = crawler.crawl_page(keyword="아이폰", page=1)

    # 결과 출력
    print("\n" + "="*70)
    print("테스트 결과")
    print("="*70)

    if result.get('success'):
        print(f"✅ 성공!")
        print(f"  - 랭킹 상품: {len(result['ranking'])}개")
        print(f"  - 광고 상품: {len(result['ads'])}개")
        print(f"  - 전체 상품: {result['total']}개")
    else:
        print(f"❌ 실패")
        print(f"  - 에러: {result.get('error', 'unknown')}")
