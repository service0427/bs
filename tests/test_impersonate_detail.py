#!/usr/bin/env python3
"""
impersonate 방식 응답 내용 확인
"""

from curl_cffi import requests

url = "https://www.coupang.com/np/search?q=아이폰&page=1"

response = requests.get(
    url,
    impersonate='chrome110',
    timeout=30
)

print(f"상태 코드: {response.status_code}")
print(f"응답 크기: {len(response.text):,} bytes")
print("\n응답 내용 (처음 1000자):")
print("="*70)
print(response.text[:1000])
print("="*70)
