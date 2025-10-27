#!/usr/bin/env python3
"""
Akamai Cross-Test: Test if Akamai fingerprint from Device A works with TLS from Device B
Akamai 크로스 테스트: Device A의 Akamai fingerprint가 Device B의 TLS와 작동하는지 테스트
"""

import os
import sys
import json
from datetime import datetime

# 프로젝트 루트 경로 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from lib.settings import get_tls_dir
from curl_cffi.requests import Session


def load_tls_fingerprint(device_name, browser, os_version):
    """
    Load TLS fingerprint for a device
    디바이스의 TLS 지문 로드
    """
    tls_dir = get_tls_dir(device_name, browser, os_version)
    tls_file = os.path.join(tls_dir, 'tls_fingerprint.json')

    if not os.path.exists(tls_file):
        return None

    with open(tls_file, 'r') as f:
        return json.load(f)


def extract_fingerprints(tls_data):
    """
    Extract JA3, Akamai, User-Agent from TLS data
    TLS 데이터에서 JA3, Akamai, User-Agent 추출
    """
    ja3 = tls_data['tls']['ja3']
    akamai = tls_data['http2'].get('akamai_fingerprint', '')
    user_agent = tls_data.get('user_agent', '')

    return {
        'ja3': ja3,
        'akamai': akamai,
        'user_agent': user_agent,
        'ja3_hash': tls_data['tls'].get('ja3_hash', '')
    }


def test_combination(device_a, device_b, keyword='칫솔'):
    """
    Test: Device A's Akamai + Device B's TLS + User-Agent
    테스트: Device A의 Akamai + Device B의 TLS + User-Agent

    Args:
        device_a: dict with 'name', 'browser', 'os_version'
        device_b: dict with 'name', 'browser', 'os_version'
        keyword: Search keyword
    """
    print("\n" + "="*70)
    print("🔬 Akamai Cross-Test")
    print("🔬 Akamai 크로스 테스트")
    print("="*70)

    # Load Device A fingerprint
    print(f"\n[Device A] {device_a['name']} ({device_a['browser']}, OS {device_a['os_version']})")
    tls_a = load_tls_fingerprint(device_a['name'], device_a['browser'], device_a['os_version'])
    if not tls_a:
        print("  ❌ TLS fingerprint not found")
        return None

    fp_a = extract_fingerprints(tls_a)
    print(f"  ✓ Akamai: {fp_a['akamai'][:50]}...")

    # Load Device B fingerprint
    print(f"\n[Device B] {device_b['name']} ({device_b['browser']}, OS {device_b['os_version']})")
    tls_b = load_tls_fingerprint(device_b['name'], device_b['browser'], device_b['os_version'])
    if not tls_b:
        print("  ❌ TLS fingerprint not found")
        return None

    fp_b = extract_fingerprints(tls_b)
    print(f"  ✓ JA3: {fp_b['ja3'][:50]}...")
    print(f"  ✓ User-Agent: {fp_b['user_agent'][:60]}...")

    # Combination to test
    print(f"\n[Test Combination / 테스트 조합]")
    print(f"  Akamai: from Device A ({device_a['name']})")
    print(f"  TLS (JA3): from Device B ({device_b['name']})")
    print(f"  User-Agent: from Device B ({device_b['name']})")

    # Build request
    from urllib.parse import quote
    url = f"https://www.coupang.com/np/search?q={quote(keyword)}&page=1"

    headers = {
        'User-Agent': fp_b['user_agent'],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }

    print(f"\n[Sending Request / 요청 전송]")
    print(f"  URL: {url[:60]}...")

    session = Session()

    try:
        import time
        start_time = time.time()

        response = session.get(
            url,
            ja3=fp_b['ja3'],
            akamai=fp_a['akamai'],  # Device A's Akamai!
            headers=headers,
            timeout=30
        )

        response_time = time.time() - start_time

        print(f"\n[Response / 응답]")
        print(f"  Status: {response.status_code}")
        print(f"  Size: {len(response.text):,} bytes")
        print(f"  Time: {response_time:.2f}s")

        # Check if products exist
        has_products = 'class="search-product"' in response.text or 'data-component-type' in response.text

        if response.status_code == 200 and has_products:
            print(f"\n✅ SUCCESS! Cross-combination works!")
            print(f"✅ 성공! 크로스 조합이 작동합니다!")
            print(f"  → Device A's Akamai + Device B's TLS = Working")
            print(f"  → Device A의 Akamai + Device B의 TLS = 작동함")

            return {
                'success': True,
                'device_a': device_a,
                'device_b': device_b,
                'status_code': response.status_code,
                'response_size': len(response.text),
                'response_time': response_time,
                'has_products': has_products
            }
        else:
            print(f"\n⚠️  PARTIAL: Response received but suspicious")
            print(f"⚠️  부분 성공: 응답은 받았지만 의심스러움")
            print(f"  → Status: {response.status_code}, Products: {has_products}")

            return {
                'success': False,
                'device_a': device_a,
                'device_b': device_b,
                'status_code': response.status_code,
                'response_size': len(response.text),
                'response_time': response_time,
                'has_products': has_products,
                'reason': 'no_products' if not has_products else 'bad_status'
            }

    except Exception as e:
        print(f"\n❌ FAILED: {str(e)[:100]}")
        print(f"❌ 실패: {str(e)[:100]}")

        return {
            'success': False,
            'device_a': device_a,
            'device_b': device_b,
            'error': str(e)
        }


def main():
    """Main entry point"""
    print("\n" + "🧪"*35)
    print("Akamai Cross-Test Tool")
    print("Akamai 크로스 테스트 도구")
    print("🧪"*35)

    # Test with 2 different successful devices
    # 2개의 서로 다른 성공 디바이스로 테스트

    device_a = {
        'name': 'Google Pixel 5',
        'browser': 'android',
        'os_version': '11.0'
    }

    device_b = {
        'name': 'iPhone 13',
        'browser': 'iphone',
        'os_version': '15'
    }

    print(f"\n📋 Test Plan / 테스트 계획:")
    print(f"  1. Use Device A's Akamai fingerprint")
    print(f"     Device A의 Akamai fingerprint 사용")
    print(f"  2. Use Device B's TLS (JA3) + User-Agent")
    print(f"     Device B의 TLS (JA3) + User-Agent 사용")
    print(f"  3. Check if combination works")
    print(f"     조합이 작동하는지 확인")

    result = test_combination(device_a, device_b, keyword='칫솔')

    if result:
        print("\n" + "="*70)
        print("📊 Test Result / 테스트 결과")
        print("="*70)
        if result['success']:
            print(f"✅ Cross-combination WORKS!")
            print(f"✅ 크로스 조합 작동!")
            print(f"\n💡 Insight / 인사이트:")
            print(f"  Akamai fingerprint can be mixed with different TLS fingerprints.")
            print(f"  Akamai fingerprint는 다른 TLS fingerprint와 혼합 가능합니다.")
        else:
            print(f"❌ Cross-combination FAILED")
            print(f"❌ 크로스 조합 실패")
            print(f"\n💡 Insight / 인사이트:")
            print(f"  Akamai fingerprint might be tied to specific TLS characteristics.")
            print(f"  Akamai fingerprint는 특정 TLS 특성과 연결되어 있을 수 있습니다.")
        print("="*70)


if __name__ == '__main__':
    main()
