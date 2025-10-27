#!/usr/bin/env python3
"""
impersonate 방식 테스트
curl-cffi가 정상 작동하는지 확인
"""

from curl_cffi import requests

print("\n" + "="*70)
print("impersonate 방식 테스트 (curl-cffi 작동 확인)")
print("="*70)

url = "https://www.coupang.com/np/search?q=아이폰&page=1"

try:
    print(f"\n요청 URL: {url}")
    print("impersonate: chrome110\n")

    response = requests.get(
        url,
        impersonate='chrome110',
        timeout=30
    )

    print(f"✅ 성공!")
    print(f"  상태 코드: {response.status_code}")
    print(f"  응답 크기: {len(response.text):,} bytes")

    # 차단 여부 확인
    if 'captcha' in response.text.lower() or 'robot' in response.text.lower():
        print("  ⚠️ 차단 감지")
    else:
        print("  ✓ 차단 없음")

        # 상품 개수 확인
        if 'product-item' in response.text or 'search-product' in response.text:
            print("  ✓ 상품 데이터 존재")
        else:
            print("  ⚠️ 상품 데이터 없음")

except Exception as e:
    print(f"❌ 실패: {str(e)[:100]}")
