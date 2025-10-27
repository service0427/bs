#!/usr/bin/env python3
"""
일괄 Fingerprint 검증 - 모든 수집된 기기 100번씩 테스트

목적:
- 사용 가능한 기기 필터링
- IP 차단 vs 기기 차단 구분
- curl-cffi 재현 가능 여부 확인
"""

import sys
sys.path.insert(0, '/var/www/html/browserstack')

import os
import json
import subprocess
from datetime import datetime


def find_all_fingerprints():
    """수집된 모든 fingerprint 찾기"""
    base_dir = "/var/www/html/browserstack/data/fingerprints"
    fingerprints = []

    for dirname in os.listdir(base_dir):
        dirpath = os.path.join(base_dir, dirname)
        if not os.path.isdir(dirpath):
            continue

        metadata_file = os.path.join(dirpath, "metadata.json")
        if not os.path.exists(metadata_file):
            continue

        # Parse directory name
        # Format: DeviceName_browser_osversion
        parts = dirname.rsplit('_', 2)
        if len(parts) != 3:
            continue

        device_name = parts[0].replace('_', ' ')
        browser = parts[1]
        os_version = parts[2]

        fingerprints.append({
            'device_name': device_name,
            'browser': browser,
            'os_version': os_version,
            'dir': dirpath
        })

    return fingerprints


def run_validation(fp, iterations=100, delay=2):
    """단일 fingerprint 검증 실행"""
    cmd = [
        'python',
        '/var/www/html/browserstack/scripts/validate_fingerprints_100x.py',
        '--device', fp['device_name'],
        '--browser', fp['browser'],
        '--os-version', fp['os_version'],
        '--iterations', str(iterations),
        '--delay', str(delay)
    ]

    print(f"\n{'='*80}")
    print(f"Running: {fp['device_name']} / {fp['browser']} / {fp['os_version']}")
    print(f"{'='*80}")

    result = subprocess.run(cmd, capture_output=False, text=True)

    return result.returncode == 0


def load_validation_result(fp):
    """검증 결과 로드"""
    result_file = f"/var/www/html/browserstack/data/validation_results/{fp['device_name'].replace(' ', '_')}_{fp['browser']}_{fp['os_version']}_100x.json"

    if not os.path.exists(result_file):
        return None

    with open(result_file, 'r') as f:
        return json.load(f)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='일괄 Fingerprint 검증')
    parser.add_argument('--iterations', type=int, default=100, help='반복 횟수 (기본: 100)')
    parser.add_argument('--delay', type=float, default=2.0, help='요청 간 딜레이 (기본: 2.0초)')
    parser.add_argument('--limit', type=int, help='테스트 기기 수 제한')
    parser.add_argument('--skip-existing', action='store_true', help='기존 결과 있으면 스킵')

    args = parser.parse_args()

    # 모든 fingerprint 찾기
    fingerprints = find_all_fingerprints()

    print(f"=" * 80)
    print(f"일괄 Fingerprint 검증")
    print(f"=" * 80)
    print(f"발견된 Fingerprint: {len(fingerprints)}개")

    if args.limit:
        fingerprints = fingerprints[:args.limit]
        print(f"테스트 대상: {len(fingerprints)}개 (limit 적용)")

    if args.skip_existing:
        # 기존 결과 필터링
        fingerprints_to_test = []
        for fp in fingerprints:
            result = load_validation_result(fp)
            if result is None:
                fingerprints_to_test.append(fp)

        print(f"스킵된 기기: {len(fingerprints) - len(fingerprints_to_test)}개")
        fingerprints = fingerprints_to_test

    print(f"실제 테스트: {len(fingerprints)}개")
    print()

    # 각 fingerprint 검증
    completed = 0
    failed = 0

    for i, fp in enumerate(fingerprints, 1):
        print(f"\n[{i}/{len(fingerprints)}] {fp['device_name']} / {fp['browser']}")

        try:
            success = run_validation(fp, iterations=args.iterations, delay=args.delay)

            if success:
                completed += 1
            else:
                failed += 1

        except KeyboardInterrupt:
            print("\n\n⚠️  사용자 중단")
            break
        except Exception as e:
            print(f"❌ 에러: {e}")
            failed += 1

    # 최종 요약
    print(f"\n\n{'='*80}")
    print(f"최종 요약")
    print(f"{'='*80}")
    print(f"완료: {completed}개")
    print(f"실패: {failed}개")

    # 결과 분석
    print(f"\n\n{'='*80}")
    print(f"결과 분석")
    print(f"{'='*80}")

    usable = []
    caution = []
    blocked = []

    for fp in fingerprints[:completed + failed]:
        result = load_validation_result(fp)
        if result is None:
            continue

        success_rate = result['success_rate']

        if success_rate >= 80:
            usable.append((fp, success_rate))
        elif success_rate >= 20:
            caution.append((fp, success_rate))
        else:
            blocked.append((fp, success_rate))

    # ✅ 사용 가능
    print(f"\n✅ 사용 가능 ({len(usable)}개, 성공률 80%+):")
    for fp, rate in sorted(usable, key=lambda x: x[1], reverse=True):
        print(f"  {rate:5.1f}% - {fp['device_name']:30} / {fp['browser']:10}")

    # ⚠️ 주의 사용
    print(f"\n⚠️  주의 사용 ({len(caution)}개, 성공률 20-80%):")
    for fp, rate in sorted(caution, key=lambda x: x[1], reverse=True):
        print(f"  {rate:5.1f}% - {fp['device_name']:30} / {fp['browser']:10}")

    # ❌ 완전 배제
    print(f"\n❌ 완전 배제 ({len(blocked)}개, 성공률 < 20%):")
    for fp, rate in sorted(blocked, key=lambda x: x[1], reverse=True):
        print(f"  {rate:5.1f}% - {fp['device_name']:30} / {fp['browser']:10}")

    # 통계 저장
    summary = {
        'tested_at': datetime.now().isoformat(),
        'total_tested': len(fingerprints),
        'completed': completed,
        'failed': failed,
        'usable': len(usable),
        'caution': len(caution),
        'blocked': len(blocked),
        'usable_list': [
            {
                'device': fp['device_name'],
                'browser': fp['browser'],
                'os_version': fp['os_version'],
                'success_rate': rate
            }
            for fp, rate in usable
        ],
        'blocked_list': [
            {
                'device': fp['device_name'],
                'browser': fp['browser'],
                'os_version': fp['os_version'],
                'success_rate': rate
            }
            for fp, rate in blocked
        ]
    }

    summary_file = '/var/www/html/browserstack/data/validation_results/batch_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 요약 저장: {summary_file}")


if __name__ == '__main__':
    main()
