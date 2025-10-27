#!/usr/bin/env python3
"""
TLS Variance Test
TLS 변동성 테스트

Test the same device multiple times to see what changes in TLS fingerprint.
같은 디바이스를 여러 번 테스트하여 TLS fingerprint에서 무엇이 변하는지 확인.
"""

import os
import sys
import json
import time
from datetime import datetime

# 프로젝트 루트 경로 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from lib.collectors.dynamic import DynamicCollector
from lib.settings import get_tls_dir


class TLSVarianceTester:
    """
    TLS Variance Tester
    TLS 변동성 테스터

    Collect TLS fingerprints multiple times from the same device.
    같은 디바이스에서 TLS fingerprint를 여러 번 수집합니다.
    """

    def __init__(self, device_config, iterations=5):
        """
        Initialize tester
        테스터 초기화

        Args:
            device_config: Device configuration dict (디바이스 설정 딕셔너리)
            iterations: Number of collections (수집 횟수)
        """
        self.device_config = device_config
        self.iterations = iterations
        self.device_name = device_config['device']
        self.browser = device_config['browser']
        self.os_version = device_config['os_version']

        # Results storage (결과 저장소)
        self.samples = []

    def collect_sample(self, iteration):
        """
        Collect one TLS sample
        TLS 샘플 1개 수집

        Args:
            iteration: Current iteration number (현재 반복 번호)

        Returns:
            dict: TLS data or None if failed
        """
        print(f"\n{'='*70}")
        print(f"🔄 Sample {iteration}/{self.iterations}")
        print(f"🔄 샘플 {iteration}/{self.iterations}")
        print(f"{'='*70}")

        try:
            collector = DynamicCollector(
                device_config=self.device_config,
                refresh_policy='force'  # Always force refresh (항상 강제 재수집)
            )

            collector.collect()

            # Load the collected TLS data (수집된 TLS 데이터 로드)
            tls_dir = get_tls_dir(self.device_name, self.browser, self.os_version)
            tls_file = os.path.join(tls_dir, 'tls_fingerprint.json')

            if os.path.exists(tls_file):
                with open(tls_file, 'r') as f:
                    tls_data = json.load(f)

                print(f"  ✅ Sample {iteration} collected successfully")
                print(f"  ✅ 샘플 {iteration} 수집 완료")

                return tls_data
            else:
                print(f"  ❌ TLS file not found")
                print(f"  ❌ TLS 파일을 찾을 수 없음")
                return None

        except Exception as e:
            print(f"  ❌ Collection failed: {str(e)[:100]}")
            print(f"  ❌ 수집 실패: {str(e)[:100]}")
            return None

    def analyze_variance(self):
        """
        Analyze variance across all samples
        모든 샘플의 변동성 분석

        Returns:
            dict: Analysis results (분석 결과)
        """
        if len(self.samples) < 2:
            print("\n⚠️  Need at least 2 samples for variance analysis")
            print("⚠️  변동성 분석을 위해 최소 2개 샘플이 필요합니다")
            return None

        print(f"\n{'='*70}")
        print("📊 Variance Analysis / 변동성 분석")
        print(f"{'='*70}")

        # Extract key fields from each sample
        # 각 샘플에서 주요 필드 추출
        ja3_hashes = []
        ja3_strings = []
        akamai_fps = []
        cipher_lists = []
        extension_lists = []

        for i, sample in enumerate(self.samples, 1):
            tls = sample['tls']
            http2 = sample['http2']

            ja3_hashes.append(tls.get('ja3_hash'))
            ja3_strings.append(tls.get('ja3'))
            akamai_fps.append(http2.get('akamai_fingerprint'))

            # Ciphers (시퍼, cipher: 암호)
            # Ciphers are already strings, not dicts
            ciphers = tls.get('ciphers', [])
            cipher_lists.append(ciphers)

            # Extensions (익스텐션, extension: 확장)
            # Extensions are dicts with 'name' field
            extensions = [e.get('name', e.get('id')) for e in tls.get('extensions', [])]
            extension_lists.append(extensions)

        # Analysis results (분석 결과)
        analysis = {
            'total_samples': len(self.samples),
            'ja3_hash': {
                'unique_values': len(set(ja3_hashes)),
                'values': ja3_hashes,
                'consistent': len(set(ja3_hashes)) == 1
            },
            'ja3_string': {
                'unique_values': len(set(ja3_strings)),
                'consistent': len(set(ja3_strings)) == 1
            },
            'akamai': {
                'unique_values': len(set(akamai_fps)),
                'values': akamai_fps,
                'consistent': len(set(akamai_fps)) == 1
            },
            'ciphers': {
                'consistent': all(c == cipher_lists[0] for c in cipher_lists),
                'count': len(cipher_lists[0]) if cipher_lists else 0
            },
            'extensions': {
                'consistent': all(e == extension_lists[0] for e in extension_lists),
                'count': len(extension_lists[0]) if extension_lists else 0
            }
        }

        return analysis

    def print_analysis(self, analysis):
        """
        Print variance analysis results
        변동성 분석 결과 출력

        Args:
            analysis: Analysis results dict (분석 결과 딕셔너리)
        """
        print(f"\n📈 Results Summary / 결과 요약:")
        print(f"  Total Samples: {analysis['total_samples']}")
        print(f"  총 샘플: {analysis['total_samples']}개\n")

        # JA3 Hash
        print(f"  [1] JA3 Hash:")
        if analysis['ja3_hash']['consistent']:
            print(f"      ✅ CONSISTENT (Same across all samples)")
            print(f"      ✅ 일관됨 (모든 샘플에서 동일)")
            print(f"      Value: {analysis['ja3_hash']['values'][0]}")
        else:
            print(f"      ⚠️  VARIES ({analysis['ja3_hash']['unique_values']} different values)")
            print(f"      ⚠️  변동됨 ({analysis['ja3_hash']['unique_values']}개 다른 값)")
            for i, val in enumerate(analysis['ja3_hash']['values'], 1):
                print(f"        Sample {i}: {val}")

        # JA3 String
        print(f"\n  [2] JA3 String:")
        if analysis['ja3_string']['consistent']:
            print(f"      ✅ CONSISTENT")
            print(f"      ✅ 일관됨")
        else:
            print(f"      ⚠️  VARIES ({analysis['ja3_string']['unique_values']} different values)")
            print(f"      ⚠️  변동됨 ({analysis['ja3_string']['unique_values']}개 다른 값)")

        # Akamai Fingerprint
        print(f"\n  [3] Akamai Fingerprint:")
        if analysis['akamai']['consistent']:
            print(f"      ✅ CONSISTENT (Same across all samples)")
            print(f"      ✅ 일관됨 (모든 샘플에서 동일)")
            print(f"      Value: {analysis['akamai']['values'][0]}")
        else:
            print(f"      ⚠️  VARIES ({analysis['akamai']['unique_values']} different values)")
            print(f"      ⚠️  변동됨 ({analysis['akamai']['unique_values']}개 다른 값)")
            for i, val in enumerate(analysis['akamai']['values'], 1):
                print(f"        Sample {i}: {val}")

        # Ciphers
        print(f"\n  [4] Cipher Suites:")
        if analysis['ciphers']['consistent']:
            print(f"      ✅ CONSISTENT ({analysis['ciphers']['count']} ciphers)")
            print(f"      ✅ 일관됨 ({analysis['ciphers']['count']}개)")
        else:
            print(f"      ⚠️  VARIES")
            print(f"      ⚠️  변동됨")

        # Extensions
        print(f"\n  [5] Extensions:")
        if analysis['extensions']['consistent']:
            print(f"      ✅ CONSISTENT ({analysis['extensions']['count']} extensions)")
            print(f"      ✅ 일관됨 ({analysis['extensions']['count']}개)")
        else:
            print(f"      ⚠️  VARIES")
            print(f"      ⚠️  변동됨")

        # Conclusion
        print(f"\n" + "="*70)
        print(f"💡 Conclusion / 결론:")
        print(f"="*70)

        all_consistent = (
            analysis['ja3_hash']['consistent'] and
            analysis['akamai']['consistent'] and
            analysis['ciphers']['consistent'] and
            analysis['extensions']['consistent']
        )

        if all_consistent:
            print(f"✅ TLS fingerprint is STABLE across multiple collections")
            print(f"✅ TLS fingerprint는 여러 번 수집해도 안정적입니다")
            print(f"\n💡 This means:")
            print(f"  → You can collect once and reuse")
            print(f"  → 한 번 수집하고 재사용 가능")
            print(f"  → No need to recollect frequently")
            print(f"  → 자주 재수집할 필요 없음")
        elif not analysis['ja3_hash']['consistent']:
            print(f"⚠️  JA3 Hash VARIES due to GREASE randomization")
            print(f"⚠️  GREASE 랜덤화로 인해 JA3 Hash가 변동됨")
            print(f"\n💡 This is NORMAL Chrome behavior:")
            print(f"  → GREASE values change each session")
            print(f"  → GREASE 값은 세션마다 변경됨")
            print(f"  → But underlying fingerprint is same")
            print(f"  → 하지만 기본 fingerprint는 동일함")

            if analysis['akamai']['consistent']:
                print(f"  → Akamai fingerprint is stable ✅")
                print(f"  → Akamai fingerprint는 안정적 ✅")
        else:
            print(f"⚠️  Some TLS characteristics vary")
            print(f"⚠️  일부 TLS 특성이 변동됨")
            print(f"\n💡 Recommendation:")
            print(f"  → Collect fresh fingerprints periodically")
            print(f"  → 주기적으로 새로운 fingerprint 수집")

    def run(self):
        """
        Run variance test
        변동성 테스트 실행

        Returns:
            dict: Test results (테스트 결과)
        """
        print(f"\n{'🔬'*35}")
        print("TLS Variance Test")
        print("TLS 변동성 테스트")
        print(f"{'🔬'*35}")

        print(f"\n📋 Configuration / 설정:")
        print(f"  Device: {self.device_name}")
        print(f"  디바이스: {self.device_name}")
        print(f"  Browser: {self.browser}")
        print(f"  브라우저: {self.browser}")
        print(f"  OS Version: {self.os_version}")
        print(f"  OS 버전: {self.os_version}")
        print(f"  Iterations: {self.iterations}")
        print(f"  반복 횟수: {self.iterations}회")

        # Collect samples (샘플 수집)
        for i in range(1, self.iterations + 1):
            sample = self.collect_sample(i)

            if sample:
                self.samples.append(sample)
            else:
                print(f"\n⚠️  Failed to collect sample {i}")
                print(f"⚠️  샘플 {i} 수집 실패")

            # Wait between collections (수집 간 대기)
            if i < self.iterations:
                wait_time = 3
                print(f"\n⏳ Waiting {wait_time}s before next collection...")
                print(f"⏳ 다음 수집까지 {wait_time}초 대기...")
                time.sleep(wait_time)

        # Analyze variance (변동성 분석)
        if len(self.samples) >= 2:
            analysis = self.analyze_variance()
            if analysis:
                self.print_analysis(analysis)

                # Save detailed comparison (상세 비교 저장)
                self.save_comparison()

                return analysis
        else:
            print(f"\n❌ Not enough samples for analysis")
            print(f"❌ 분석을 위한 샘플이 부족합니다")
            return None

    def save_comparison(self):
        """
        Save detailed comparison to file
        상세 비교를 파일로 저장
        """
        output_dir = os.path.join(PROJECT_ROOT, 'data', 'variance_tests')
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"variance_{self.device_name.replace(' ', '_')}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        data = {
            'device_name': self.device_name,
            'browser': self.browser,
            'os_version': self.os_version,
            'test_time': datetime.now().isoformat(),
            'iterations': self.iterations,
            'samples': self.samples
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Detailed comparison saved:")
        print(f"💾 상세 비교 저장됨:")
        print(f"   {filepath}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Test TLS fingerprint variance for a device'
    )
    parser.add_argument('--device', type=str, default='Google Pixel 5',
                       help='Device name')
    parser.add_argument('--browser', type=str, default='android',
                       help='Browser key')
    parser.add_argument('--os-version', type=str, default='11.0',
                       help='OS version')
    parser.add_argument('--iterations', type=int, default=5,
                       help='Number of collections (default: 5)')

    args = parser.parse_args()

    device_config = {
        'device': args.device,
        'browser': args.browser,
        'os_version': args.os_version,
        'os': 'android' if args.browser in ['android', 'samsung'] else 'ios',
        'real_mobile': True
    }

    tester = TLSVarianceTester(device_config, iterations=args.iterations)
    tester.run()


if __name__ == '__main__':
    main()
