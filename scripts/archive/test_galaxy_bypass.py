#!/usr/bin/env python3
"""
Galaxy 차단 우회 테스트

목적: Galaxy TLS에서 ECH/ALPS를 제거하여 차단 우회 시도
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from curl_cffi.requests import Session
from curl_cffi.curl import CurlOpt
from lib.device.tls_builder import load_fingerprint_data
from lib.device.selector import select_device

def test_galaxy_bypass():
    print("\n" + "="*80)
    print("🧪 Galaxy 차단 우회 실험")
    print("="*80)

    # Galaxy S20 Ultra 사용
    device_name = "Samsung Galaxy S20 Ultra"
    browser = "android"
    os_version = "10.0"

    print(f"\n[디바이스] {device_name}")
    print(f"[브라우저] {browser}")
    print(f"[OS] {os_version}\n")

    # TLS Fingerprint 로드
    try:
        data = load_fingerprint_data(device_name, browser, os_version)
    except Exception as e:
        print(f"❌ TLS 데이터 로드 실패: {e}")
        return

    # 원본 TLS 정보
    tls_info = data['tls']['tls']
    print("="*80)
    print("📋 원본 Galaxy TLS")
    print("="*80)

    # ECH 체크
    ech_ext = None
    alps_ext = None
    for ext in tls_info.get('extensions', []):
        if 'EncryptedClientHello' in ext.get('name', ''):
            ech_ext = ext
        if 'application_settings' in ext.get('name', ''):
            alps_ext = ext

    print(f"ECH Extension:  {'✅ 있음' if ech_ext else '❌ 없음'}")
    if ech_ext:
        print(f"  → {ech_ext.get('name')}")

    print(f"ALPS Extension: {'✅ 있음' if alps_ext else '❌ 없음'}")
    if alps_ext:
        print(f"  → {alps_ext.get('name')}")

    print(f"\nAkamai Fingerprint: {data['tls']['http2']['akamai_fingerprint']}")
    print(f"JA3 Hash: {tls_info['ja3_hash']}\n")

    # 테스트 URL
    test_url = "https://www.coupang.com/np/search?q=청소기&page=1"

    print("="*80)
    print("🧪 실험 1: 원본 TLS (ECH + ALPS 포함)")
    print("="*80)

    session1 = Session()
    try:
        response1 = session1.get(
            test_url,
            ja3=tls_info['ja3'],
            timeout=10
        )
        size1 = len(response1.content)
        print(f"✅ 요청 성공")
        print(f"   응답 크기: {size1:,} bytes")

        if size1 < 10000:
            print(f"   ⚠️  차단 의심 (응답이 너무 작음)")
        else:
            print(f"   ✅ 정상 응답")

    except Exception as e:
        print(f"❌ 요청 실패: {e}")

    print("\n" + "="*80)
    print("🧪 실험 2: ALPS 비활성화 + ECH 비활성화")
    print("="*80)

    session2 = Session()

    # curl-cffi에 ALPS/ECH 비활성화 설정
    print("\n[설정 적용]")
    print("  1. SSL_ENABLE_ALPS = 0 (비활성화)")
    print("  2. ECH = 0 (비활성화)")

    try:
        # 먼저 curl 객체 가져오기
        curl_handle = session2.curl

        # ALPS 비활성화
        from curl_cffi.curl import CurlOpt
        curl_handle.setopt(CurlOpt.SSL_ENABLE_ALPS, 0)
        print("  ✓ ALPS 비활성화 완료")

        # ECH 비활성화 (값을 0 또는 빈 문자열로)
        try:
            curl_handle.setopt(CurlOpt.ECH, 0)
            print("  ✓ ECH 비활성화 완료")
        except Exception as e:
            print(f"  ⚠️  ECH 설정 실패: {e}")

        response2 = session2.get(
            test_url,
            ja3=tls_info['ja3'],
            timeout=10
        )
        size2 = len(response2.content)
        print(f"\n✅ 요청 성공")
        print(f"   응답 크기: {size2:,} bytes")

        if size2 < 10000:
            print(f"   ⚠️  차단 의심 (응답이 너무 작음)")
        else:
            print(f"   ✅ 정상 응답")
            print(f"\n🎉 성공! ALPS/ECH 제거로 차단 우회!")

    except Exception as e:
        print(f"\n❌ 요청 실패: {e}")

    print("\n" + "="*80)
    print("📊 결과 비교")
    print("="*80)
    print("실험 1 (원본): 차단 예상")
    print("실험 2 (변조): 통과 여부 확인")
    print("="*80)

if __name__ == '__main__':
    test_galaxy_bypass()
