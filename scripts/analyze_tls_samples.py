"""
TLS 샘플 비교 분석 스크립트
수집된 샘플들의 TLS/HTTP2 파라미터 비교

사용 예:
  # 특정 날짜의 샘플 분석
  python analyze_tls_samples.py --date 2025-10-23

  # 디바이스 지정
  python analyze_tls_samples.py --date 2025-10-23 --device "Samsung Galaxy S23 Ultra"

  # 상세 모드 (모든 파라미터 출력)
  python analyze_tls_samples.py --date 2025-10-23 --verbose
"""

import json
import os
import sys
import argparse
from datetime import datetime
from collections import defaultdict

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_samples(date, device_filter=None):
    """
    특정 날짜의 샘플 로드

    Args:
        date: 날짜 (YYYY-MM-DD)
        device_filter: 디바이스 필터 (None이면 전체)

    Returns:
        list: 샘플 리스트
    """
    samples_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'data',
        'tls_samples',
        date
    )

    if not os.path.exists(samples_dir):
        print(f"❌ 샘플 디렉토리가 없습니다: {samples_dir}")
        return []

    samples = []
    for filename in os.listdir(samples_dir):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(samples_dir, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                sample = json.load(f)

            # 디바이스 필터
            if device_filter and sample['device'] != device_filter:
                continue

            samples.append({
                'filename': filename,
                'data': sample
            })

        except Exception as e:
            print(f"⚠️ 파일 로드 실패 ({filename}): {e}")

    return samples


def analyze_samples(samples, verbose=False):
    """
    샘플 비교 분석

    Args:
        samples: 샘플 리스트
        verbose: 상세 모드
    """
    if not samples:
        print("분석할 샘플이 없습니다.")
        return

    print(f"\n{'='*70}")
    print(f"TLS 샘플 비교 분석")
    print(f"{'='*70}")
    print(f"총 샘플 수: {len(samples)}개")

    # 디바이스 정보
    first_sample = samples[0]['data']
    print(f"디바이스: {first_sample['device']}")
    print(f"브라우저: {first_sample['browser']}")
    print(f"OS: {first_sample['os']} {first_sample['os_version']}")
    print(f"{'='*70}\n")

    # HTTP/2 파라미터 분석
    print("## HTTP/2 파라미터 분석\n")

    # Window Size
    window_sizes = []
    initial_windows = []
    akamai_fps = []

    for sample in samples:
        try:
            peet_data = sample['data']['peet_ws']['data']

            # WINDOW_UPDATE increment
            sent_frames = peet_data['http2']['sent_frames']
            for frame in sent_frames:
                if frame.get('frame_type') == 'WINDOW_UPDATE':
                    window_sizes.append(frame['increment'])
                    break

            # INITIAL_WINDOW_SIZE
            for frame in sent_frames:
                if frame.get('frame_type') == 'SETTINGS':
                    for setting in frame.get('settings', []):
                        if 'INITIAL_WINDOW_SIZE' in setting:
                            value = int(setting.split('=')[1].strip())
                            initial_windows.append(value)
                            break
                    break

            # Akamai Fingerprint
            akamai_fp = peet_data['http2']['akamai_fingerprint']
            akamai_fps.append(akamai_fp)

        except Exception as e:
            print(f"⚠️ 샘플 파싱 오류: {e}")

    # Window Size 통계
    print("### WINDOW_UPDATE Increment")
    unique_windows = set(window_sizes)
    print(f"  고유값 개수: {len(unique_windows)}개")
    if len(unique_windows) == 1:
        print(f"  ✅ 모든 샘플 동일: {list(unique_windows)[0]:,}")
    else:
        print(f"  ⚠️ 다른 값 발견:")
        for value in sorted(unique_windows):
            count = window_sizes.count(value)
            print(f"    - {value:,}: {count}회")

    # INITIAL_WINDOW_SIZE 통계
    print(f"\n### INITIAL_WINDOW_SIZE")
    unique_initial = set(initial_windows)
    print(f"  고유값 개수: {len(unique_initial)}개")
    if len(unique_initial) == 1:
        print(f"  ✅ 모든 샘플 동일: {list(unique_initial)[0]:,}")
    else:
        print(f"  ⚠️ 다른 값 발견:")
        for value in sorted(unique_initial):
            count = initial_windows.count(value)
            print(f"    - {value:,}: {count}회")

    # Akamai Fingerprint
    print(f"\n### Akamai Fingerprint")
    unique_akamai = set(akamai_fps)
    print(f"  고유값 개수: {len(unique_akamai)}개")
    if len(unique_akamai) == 1:
        print(f"  ✅ 모든 샘플 동일")
        print(f"  값: {list(unique_akamai)[0]}")
    else:
        print(f"  ⚠️ 다른 값 발견:")
        for value in unique_akamai:
            count = akamai_fps.count(value)
            print(f"    - {value}: {count}회")

    # TLS 파라미터 분석
    print(f"\n\n## TLS 파라미터 분석\n")

    ja3_hashes = []
    ja3_strings = []
    cipher_suites = []

    for sample in samples:
        try:
            peet_data = sample['data']['peet_ws']['data']
            tls_data = peet_data['tls']

            ja3_hashes.append(tls_data['ja3_hash'])
            ja3_strings.append(tls_data['ja3'])
            cipher_suites.append(tuple(tls_data['ciphers']))

        except Exception as e:
            print(f"⚠️ TLS 파싱 오류: {e}")

    # JA3 Hash
    print("### JA3 Hash")
    unique_ja3_hashes = set(ja3_hashes)
    print(f"  고유값 개수: {len(unique_ja3_hashes)}개")
    if len(unique_ja3_hashes) == 1:
        print(f"  ✅ 모든 샘플 동일: {list(unique_ja3_hashes)[0]}")
    else:
        print(f"  ⚠️ 매번 다름 (GREASE 랜덤화):")
        for i, hash_val in enumerate(ja3_hashes[:5], 1):
            print(f"    Sample {i}: {hash_val}")
        if len(ja3_hashes) > 5:
            print(f"    ... 외 {len(ja3_hashes) - 5}개")

    # JA3 String (Extension 순서)
    print(f"\n### JA3 String (Extension 순서)")

    # Extensions 부분만 추출 (3번째 부분)
    extensions_orders = []
    for ja3 in ja3_strings:
        parts = ja3.split(',')
        if len(parts) >= 3:
            extensions = parts[2]
            # GREASE 제거 (숫자가 아닌 것)
            ext_list = extensions.split('-')
            ext_without_grease = [e for e in ext_list if e.isdigit()]
            extensions_orders.append('-'.join(ext_without_grease))

    unique_ext_orders = set(extensions_orders)
    print(f"  고유값 개수 (GREASE 제외): {len(unique_ext_orders)}개")
    if len(unique_ext_orders) == 1:
        print(f"  ✅ Extension 순서 동일 (GREASE 제외)")
        if verbose:
            print(f"  순서: {list(unique_ext_orders)[0]}")
    else:
        print(f"  ⚠️ Extension 순서가 다름:")
        for order in list(unique_ext_orders)[:3]:
            count = extensions_orders.count(order)
            print(f"    - {order[:60]}... ({count}회)")

    # Cipher Suites
    print(f"\n### Cipher Suites")
    unique_ciphers = set(cipher_suites)
    print(f"  고유값 개수: {len(unique_ciphers)}개")
    if len(unique_ciphers) == 1:
        print(f"  ✅ 모든 샘플 동일 ({len(cipher_suites[0])}개 cipher)")
        if verbose:
            print(f"  Ciphers:")
            for cipher in cipher_suites[0]:
                print(f"    - {cipher}")
    else:
        print(f"  ⚠️ Cipher Suites가 다름")

    # 최종 결론
    print(f"\n\n{'='*70}")
    print("최종 결론")
    print(f"{'='*70}\n")

    conclusions = []

    if len(unique_windows) == 1:
        conclusions.append("✅ Window Size 고정 → 랜덤화 불필요")
    else:
        conclusions.append("⚠️ Window Size 변동 감지 → 추가 분석 필요")

    if len(unique_akamai) == 1:
        conclusions.append("✅ Akamai Fingerprint 고정 → 기기 고유값")
    else:
        conclusions.append("⚠️ Akamai Fingerprint 변동 감지")

    if len(unique_ja3_hashes) > 1:
        conclusions.append("✅ JA3 Hash 변동 → GREASE 정상 작동")
    else:
        conclusions.append("⚠️ JA3 Hash 고정 → GREASE 미작동?")

    if len(unique_ext_orders) == 1:
        conclusions.append("✅ Extension 순서 고정 → tls_permute_extensions=False 유지")
    else:
        conclusions.append("⚠️ Extension 순서 변동 → tls_permute_extensions=True?")

    for conclusion in conclusions:
        print(conclusion)

    print()


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='TLS 샘플 비교 분석',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 오늘 날짜 샘플 분석
  python analyze_tls_samples.py --date 2025-10-23

  # 디바이스 지정
  python analyze_tls_samples.py --date 2025-10-23 --device "Samsung Galaxy S23 Ultra"

  # 상세 모드
  python analyze_tls_samples.py --date 2025-10-23 --verbose
        """
    )

    parser.add_argument(
        '--date', '-d',
        type=str,
        required=True,
        help='분석할 날짜 (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--device',
        type=str,
        default=None,
        help='디바이스 이름 필터'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='상세 모드'
    )

    args = parser.parse_args()

    # 샘플 로드
    samples = load_samples(args.date, args.device)

    if not samples:
        print(f"\n샘플을 찾을 수 없습니다.")
        print(f"날짜: {args.date}")
        if args.device:
            print(f"디바이스: {args.device}")
        sys.exit(1)

    # 분석
    analyze_samples(samples, verbose=args.verbose)


if __name__ == '__main__':
    main()
