#!/usr/bin/env python3
"""
TLS Fingerprint 변동성 테스트

같은 디바이스 모델을 여러 번 수집하여 TLS 값이 고정인지 검증
- 반복 수집 (N회)
- 차이점 자동 분석
- 고정/변동 항목 리포트
"""

import os
import sys
import json
import time
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.device.selector import select_device
from lib.collectors.dynamic import collect_from_config


def collect_multiple_samples(device_name, browser, os_version, num_samples=5):
    """
    동일 디바이스를 여러 번 수집

    Args:
        device_name: 디바이스 이름
        browser: 브라우저
        os_version: OS 버전
        num_samples: 수집 횟수

    Returns:
        list: 수집된 샘플 목록
    """

    print(f"\n{'='*70}")
    print(f"TLS Fingerprint 변동성 테스트")
    print(f"{'='*70}")
    print(f"  디바이스: {device_name}")
    print(f"  브라우저: {browser}")
    print(f"  OS: {os_version}")
    print(f"  수집 횟수: {num_samples}회")
    print(f"{'='*70}\n")

    samples = []

    # 디바이스 설정 생성
    device_config = {
        'device': device_name,
        'os': 'android' if browser in ['android', 'samsung'] else 'ios',
        'os_version': os_version,
        'browser': browser,
        'real_mobile': True
    }

    for i in range(1, num_samples + 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{num_samples}] 샘플 수집 중...")
        print(f"{'='*70}\n")

        try:
            # 강제 수집 (기존 데이터 무시)
            result = collect_from_config(device_config, force_collect=True)

            if result.get('success'):
                # metadata에서 TLS 정보 추출
                metadata = result.get('metadata', {})
                tls_info = metadata.get('tls_info', {})

                if tls_info:
                    # 타임스탬프 추가
                    sample_data = {
                        'sample_number': i,
                        'collected_at': datetime.now().isoformat(),
                        'tls': tls_info.get('tls', {}),
                        'http2': tls_info.get('http2', {})
                    }
                    samples.append(sample_data)

                    print(f"✅ 샘플 {i} 수집 완료")
                else:
                    print(f"⚠️ 샘플 {i}: TLS 정보 없음")

                # 다음 수집 전 대기 (BrowserStack 세션 정리)
                if i < num_samples:
                    wait_time = 10
                    print(f"\n⏳ 다음 수집까지 {wait_time}초 대기...")
                    time.sleep(wait_time)
            else:
                print(f"❌ 샘플 {i} 수집 실패: {result.get('error', 'unknown')}")

        except Exception as e:
            print(f"❌ 샘플 {i} 수집 중 에러: {e}")
            import traceback
            traceback.print_exc()
            continue

    return samples


def analyze_variance(samples):
    """
    수집된 샘플들의 차이점 분석

    Args:
        samples: 수집된 샘플 목록

    Returns:
        dict: 분석 결과
    """

    if len(samples) < 2:
        return {
            'error': '샘플이 2개 미만입니다 (비교 불가)'
        }

    print(f"\n{'='*70}")
    print(f"TLS Fingerprint 차이점 분석")
    print(f"{'='*70}\n")

    analysis = {
        'total_samples': len(samples),
        'fields': {}
    }

    # 분석할 필드 목록
    check_fields = [
        ('tls.ja3', 'JA3 Hash'),
        ('tls.tls.ja3_hash', 'JA3 Hash (내부)'),
        ('http2.akamai_fingerprint', 'Akamai Fingerprint'),
        ('http2.window_size', 'Window Size'),
        ('http2.settings.initial_window_size', 'Initial Window Size'),
        ('tls.tls.ciphers', 'Cipher Suites (개수)'),
        ('tls.tls.extensions', 'Extensions (개수)'),
        ('http2.priority.weight', 'HTTP/2 Priority Weight'),
        ('http2.priority.exclusive', 'HTTP/2 Priority Exclusive'),
    ]

    for field_path, field_name in check_fields:
        values = []

        for sample in samples:
            # nested dict에서 값 추출
            value = sample
            for key in field_path.split('.'):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    value = None
                    break

            # list는 길이만 비교
            if isinstance(value, list):
                value = len(value)

            values.append(value)

        # 고유값 개수 확인
        unique_values = set([str(v) for v in values if v is not None])
        is_fixed = len(unique_values) == 1

        analysis['fields'][field_name] = {
            'path': field_path,
            'is_fixed': is_fixed,
            'unique_count': len(unique_values),
            'values': values,
            'unique_values': list(unique_values)
        }

    return analysis


def print_analysis_report(analysis, samples):
    """
    분석 결과 출력
    """

    if 'error' in analysis:
        print(f"⚠️ {analysis['error']}")
        return

    print(f"총 {analysis['total_samples']}개 샘플 분석\n")

    # 고정 필드
    print(f"{'='*70}")
    print("✅ 고정 필드 (모든 샘플에서 동일)")
    print(f"{'='*70}")

    fixed_fields = {k: v for k, v in analysis['fields'].items() if v['is_fixed']}
    if fixed_fields:
        for field_name, info in fixed_fields.items():
            value = info['unique_values'][0] if info['unique_values'] else 'N/A'
            print(f"  • {field_name}: {value}")
    else:
        print("  (없음)")

    # 변동 필드
    print(f"\n{'='*70}")
    print("⚠️ 변동 필드 (샘플마다 다름)")
    print(f"{'='*70}")

    variable_fields = {k: v for k, v in analysis['fields'].items() if not v['is_fixed']}
    if variable_fields:
        for field_name, info in variable_fields.items():
            print(f"\n  • {field_name}:")
            print(f"    고유값 개수: {info['unique_count']}")
            print(f"    샘플별 값:")
            for i, value in enumerate(info['values'], 1):
                print(f"      [{i}] {value}")
    else:
        print("  (없음)")

    # Cipher 상세 분석 (변동 필드인 경우만)
    print(f"\n{'='*70}")
    print("🔍 Cipher Suites 상세 분석")
    print(f"{'='*70}")

    cipher_lists = []
    for sample in samples:
        ciphers = sample.get('tls', {}).get('tls', {}).get('ciphers', [])
        cipher_lists.append(ciphers)

    if len(cipher_lists) >= 2:
        # 첫 번째와 두 번째 비교
        cipher1 = cipher_lists[0]
        cipher2 = cipher_lists[1]

        # GREASE 필터링
        def filter_grease(ciphers):
            return [c for c in ciphers if not c.startswith('GREASE')]

        cipher1_no_grease = filter_grease(cipher1)
        cipher2_no_grease = filter_grease(cipher2)

        print(f"  샘플 1: {len(cipher1)}개 (GREASE 제외: {len(cipher1_no_grease)}개)")
        print(f"  샘플 2: {len(cipher2)}개 (GREASE 제외: {len(cipher2_no_grease)}개)")

        if cipher1_no_grease == cipher2_no_grease:
            print(f"  ✅ GREASE 제외 시 동일")
        else:
            print(f"  ⚠️ GREASE 제외해도 다름")

            # 차이점 출력
            diff1 = set(cipher1_no_grease) - set(cipher2_no_grease)
            diff2 = set(cipher2_no_grease) - set(cipher1_no_grease)

            if diff1:
                print(f"  샘플 1에만 있음: {diff1}")
            if diff2:
                print(f"  샘플 2에만 있음: {diff2}")


def save_samples(samples, device_name, browser, os_version):
    """
    샘플을 파일로 저장
    """

    if not samples:
        return None

    # 저장 디렉토리
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, 'data', 'tls_variance_tests')
    os.makedirs(output_dir, exist_ok=True)

    # 파일명 생성
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_device_name = device_name.replace(' ', '_')
    filename = f"tls_variance_{safe_device_name}_{browser}_{os_version}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    # 저장
    output_data = {
        'metadata': {
            'device_name': device_name,
            'browser': browser,
            'os_version': os_version,
            'num_samples': len(samples),
            'test_date': timestamp
        },
        'samples': samples
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return filepath


def main():
    """
    메인 함수
    """

    print("\n" + "="*70)
    print("TLS Fingerprint 변동성 테스트")
    print("="*70)
    print("\n같은 디바이스 모델을 여러 번 수집하여 TLS 값의 변동성을 검증합니다.\n")

    # 1. 디바이스 선택
    device_config = select_device()

    if not device_config:
        print("❌ 디바이스 선택 실패")
        return 1

    device_name = device_config['device']
    browser = device_config['browser']
    os_version = device_config['os_version']

    # 2. 수집 횟수 입력
    print("\n" + "="*70)
    print("수집 설정")
    print("="*70)

    try:
        num_samples = int(input("\n수집 횟수 입력 (2-10, 권장: 5): ") or "5")
        if num_samples < 2:
            num_samples = 2
        elif num_samples > 10:
            num_samples = 10
    except:
        num_samples = 5

    print(f"✓ {num_samples}회 수집 예정")

    # 3. 샘플 수집
    samples = collect_multiple_samples(device_name, browser, os_version, num_samples)

    if len(samples) < 2:
        print(f"\n❌ 수집된 샘플이 {len(samples)}개뿐입니다 (최소 2개 필요)")
        return 1

    # 4. 차이점 분석
    analysis = analyze_variance(samples)

    # 5. 결과 출력
    print_analysis_report(analysis, samples)

    # 6. 파일 저장
    filepath = save_samples(samples, device_name, browser, os_version)

    if filepath:
        print(f"\n{'='*70}")
        print(f"📁 샘플 데이터 저장됨:")
        print(f"   {filepath}")
        print(f"{'='*70}")

    # 7. 결론
    print(f"\n{'='*70}")
    print("📊 결론")
    print(f"{'='*70}")

    variable_fields = {k: v for k, v in analysis['fields'].items() if not v['is_fixed']}

    if not variable_fields:
        print("\n✅ 모든 필드가 고정값입니다!")
        print("   → TLS 영구 보관 정책(v2.7) 유효")
        print("   → 1회 수집 후 재사용 가능")
    else:
        print(f"\n⚠️ {len(variable_fields)}개 필드가 변동합니다:")
        for field_name in variable_fields.keys():
            print(f"   - {field_name}")

        # JA3 Hash 변동 여부 확인
        ja3_field = analysis['fields'].get('JA3 Hash', {})
        if not ja3_field.get('is_fixed', True):
            print("\n⚠️ JA3 Hash가 변동합니다!")
            print("   → 원인: GREASE 값 랜덤화 (정상 동작)")
            print("   → 해결: Session 객체 사용 (세션 내 고정)")

        # Akamai Fingerprint 변동 여부 확인
        akamai_field = analysis['fields'].get('Akamai Fingerprint', {})
        if not akamai_field.get('is_fixed', True):
            print("\n🚨 Akamai Fingerprint가 변동합니다!")
            print("   → TLS 영구 보관 정책 재검토 필요")
            print("   → 매번 재수집 권장")

    print(f"\n{'='*70}\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
