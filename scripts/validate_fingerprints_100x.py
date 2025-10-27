#!/usr/bin/env python3
"""
Fingerprint 100번 검증 테스트

목적: IP 차단 vs 기기 차단 구분
- 성공률 90%+ : 사용 가능 (IP Rate Limit 일부)
- 성공률 50%  : 주의 사용 (IP Rate Limit 심함)
- 성공률 0%   : 완전 배제 (기기 차단)
"""

import sys
sys.path.insert(0, '/var/www/html/browserstack')

import json
import time
from curl_cffi.requests import Session
from datetime import datetime
from lib.db.manager import DBManager


def validate_fingerprint(device_name, browser, os_version, iterations=100, delay=2):
    """
    단일 fingerprint 100번 검증

    Args:
        device_name: 기기명
        browser: 브라우저
        os_version: OS 버전
        iterations: 반복 횟수 (기본 100)
        delay: 요청 간 딜레이 (초)

    Returns:
        dict: 검증 결과
    """
    print(f"\n{'='*80}")
    print(f"[검증 시작] {device_name} / {browser} / {os_version}")
    print(f"{'='*80}")

    # Metadata 로드
    device_dir = f"/var/www/html/browserstack/data/fingerprints/{device_name.replace(' ', '_')}_{browser}_{os_version}"
    metadata_file = f"{device_dir}/metadata.json"

    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    except FileNotFoundError:
        print(f"❌ metadata.json 파일 없음: {metadata_file}")
        return None

    tls = metadata['tls_info']
    ja3 = tls['tls']['ja3']
    akamai = tls['http2']['akamai_fingerprint']
    user_agent = metadata.get('user_agent', '')

    # X25519MLKEM768 체크
    has_mlkem = False
    for ext in tls['tls'].get('extensions', []):
        if ext.get('name') == 'supported_groups':
            groups = ext.get('supported_groups', [])
            if any('4588' in str(g) or 'X25519MLKEM768' in str(g) for g in groups):
                has_mlkem = True
                break

    print(f"  JA3: {ja3[:40]}...")
    print(f"  Akamai: {akamai[:50]}...")
    print(f"  User-Agent: {user_agent[:60]}...")
    print(f"  X25519MLKEM768: {'✅ 있음 (위험!)' if has_mlkem else '❌ 없음 (안전)'}")

    # Headers
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.coupang.com/',
    }

    # extra_fp
    sig_algs = []
    for ext in tls['tls'].get('extensions', []):
        if ext.get('name') == 'signature_algorithms':
            sig_algs = ext.get('signature_algorithms', [])
            break

    cert_compression = 'zlib' if 'iphone' in browser.lower() or 'ipad' in browser.lower() else 'brotli'

    extra_fp = {
        'tls_grease': True,
        'tls_signature_algorithms': sig_algs[:15] if sig_algs else [],
        'tls_cert_compression': cert_compression,
        'tls_min_version': 4,
        'tls_permute_extensions': False,
    }

    # 100번 테스트
    print(f"\n  🔄 100번 테스트 시작 (딜레이: {delay}초)...")

    url = "https://www.coupang.com/np/search?q=테스트&channel=user"

    results = {
        'success': 0,
        'http2_error': 0,
        'akamai_challenge': 0,
        'timeout': 0,
        'other_error': 0,
        'total': iterations
    }

    start_time = time.time()

    for i in range(1, iterations + 1):
        try:
            session = Session()

            response = session.get(
                url,
                ja3=ja3,
                akamai=akamai,
                extra_fp=extra_fp,
                headers=headers,
                timeout=15,
                allow_redirects=True
            )

            status = response.status_code
            size = len(response.content)

            # 성공 판단
            if status == 200 and size > 50000:
                results['success'] += 1
                marker = '✅'
            elif size < 10000:
                results['akamai_challenge'] += 1
                marker = '🚫'
            else:
                results['other_error'] += 1
                marker = '⚠️'

            # 10회마다 진행 상황 출력
            if i % 10 == 0:
                success_rate = results['success'] / i * 100
                print(f"    {i:3}/100: {marker} (성공률: {success_rate:5.1f}%)")

        except Exception as e:
            error_str = str(e)

            if 'HTTP/2' in error_str or 'INTERNAL_ERROR' in error_str:
                results['http2_error'] += 1
                marker = '❌'
            elif 'timeout' in error_str.lower():
                results['timeout'] += 1
                marker = '⏱️'
            else:
                results['other_error'] += 1
                marker = '⚠️'

            if i % 10 == 0:
                success_rate = results['success'] / i * 100
                print(f"    {i:3}/100: {marker} (성공률: {success_rate:5.1f}%)")

        # 딜레이
        if i < iterations:
            time.sleep(delay)

    elapsed = time.time() - start_time
    success_rate = results['success'] / results['total'] * 100

    # 결과 출력
    print(f"\n  📊 최종 결과:")
    print(f"    총 시도: {results['total']}회")
    print(f"    성공: {results['success']}회")
    print(f"    HTTP/2 에러: {results['http2_error']}회")
    print(f"    Akamai Challenge: {results['akamai_challenge']}회")
    print(f"    Timeout: {results['timeout']}회")
    print(f"    기타 에러: {results['other_error']}회")
    print(f"    성공률: {success_rate:.1f}%")
    print(f"    소요 시간: {elapsed/60:.1f}분")

    # 결론
    print(f"\n  🎯 결론:")
    if success_rate >= 80:
        verdict = "✅ 사용 가능"
        print(f"    {verdict}")
        print(f"    → curl-cffi 재현 가능")
        print(f"    → IP Rate Limit 일부 있으나 기기 정상")
    elif success_rate >= 20:
        verdict = "⚠️ 주의 사용"
        print(f"    {verdict}")
        print(f"    → IP Rate Limit 심함")
        print(f"    → 낮은 요청 빈도로 사용 권장")
    else:
        verdict = "❌ 완전 배제"
        print(f"    {verdict}")
        print(f"    → 기기 차단 또는 curl-cffi 재현 불가")
        print(f"    → 사용 금지")

    return {
        'device_name': device_name,
        'browser': browser,
        'os_version': os_version,
        'has_mlkem768': has_mlkem,
        'results': results,
        'success_rate': success_rate,
        'elapsed_seconds': elapsed,
        'verdict': verdict,
        'tested_at': datetime.now().isoformat()
    }


def main():
    """여러 fingerprint 검증"""
    import argparse

    parser = argparse.ArgumentParser(description='Fingerprint 100번 검증')
    parser.add_argument('--device', required=True, help='기기명')
    parser.add_argument('--browser', required=True, help='브라우저')
    parser.add_argument('--os-version', required=True, help='OS 버전')
    parser.add_argument('--iterations', type=int, default=100, help='반복 횟수 (기본: 100)')
    parser.add_argument('--delay', type=float, default=2.0, help='요청 간 딜레이 초 (기본: 2.0)')

    args = parser.parse_args()

    result = validate_fingerprint(
        device_name=args.device,
        browser=args.browser,
        os_version=args.os_version,
        iterations=args.iterations,
        delay=args.delay
    )

    if result:
        # JSON 저장
        output_file = f"/var/www/html/browserstack/data/validation_results/{args.device.replace(' ', '_')}_{args.browser}_{args.os_version}_100x.json"

        import os
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 결과 저장: {output_file}")


if __name__ == '__main__':
    main()
