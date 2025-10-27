"""
robots.txt 접속 시 Akamai 쿠키 테스트
"""

from curl_cffi import requests

print("="*70)
print("Coupang robots.txt 쿠키 테스트")
print("="*70)

# 1. robots.txt 접속 (Chrome impersonate)
print("\n1. https://www.coupang.com/robots.txt 접속...")
response = requests.get(
    'https://www.coupang.com/robots.txt',
    impersonate='chrome110',
    timeout=10
)

print(f"   상태 코드: {response.status_code}")
print(f"   응답 크기: {len(response.text)} bytes")

# 2. 쿠키 확인
cookies = response.cookies
print(f"\n2. 받은 쿠키: {len(cookies)}개")

if len(cookies) == 0:
    print("   ⚠️ 쿠키 없음")
else:
    print("\n   쿠키 목록:")
    for name, value in cookies.items():
        value_preview = value[:50] + "..." if len(value) > 50 else value
        print(f"   - {name}: {value_preview}")

        # Akamai 관련 쿠키인지 확인
        if name in ['_abck', 'bm_sz', 'ak_bmsc', 'bm_mi']:
            print(f"     ✅ Akamai 쿠키 발견!")
        print()

# 3. 메인 페이지와 비교
print("\n3. 메인 페이지와 비교...")
response_main = requests.get(
    'https://www.coupang.com/',
    impersonate='chrome110',
    timeout=10
)
cookies_main = response_main.cookies

print(f"   메인 페이지 쿠키: {len(cookies_main)}개")
if len(cookies_main) > 0:
    print("   쿠키 목록:")
    for name, value in cookies_main.items():
        value_preview = value[:50] + "..." if len(value) > 50 else value
        print(f"   - {name}: {value_preview}")

# 4. 결론
print("\n" + "="*70)
print("결론:")
print("="*70)

robots_cookie_names = list(cookies.keys())
main_cookie_names = list(cookies_main.keys())

akamai_in_robots = [name for name in robots_cookie_names if name in ['_abck', 'bm_sz', 'ak_bmsc', 'bm_mi']]
akamai_in_main = [name for name in main_cookie_names if name in ['_abck', 'bm_sz', 'ak_bmsc', 'bm_mi']]

if akamai_in_robots:
    print(f"✅ robots.txt에서 Akamai 쿠키 발견: {', '.join(akamai_in_robots)}")
    print(f"   → 쿠키 사전 설정 시 robots.txt를 사용하면 빠름!")
else:
    print(f"❌ robots.txt에서 Akamai 쿠키 없음")

if akamai_in_main:
    print(f"✅ 메인 페이지에서 Akamai 쿠키: {', '.join(akamai_in_main)}")

print()
