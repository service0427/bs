#!/usr/bin/env python3
"""
디바이스 로테이션 테스트
main.py 방식으로 25개 디바이스를 순환하며 대량 크롤링

목표: IP 변경 없이 10만번 조회 달성
전략: 디바이스 로테이션으로 Rate limit 회피
"""

import json
import time
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

class DeviceRotationTester:
    def __init__(self, target_pages=100000, pages_per_device=10, delay=2.0, keyword="칫솔"):
        self.target_pages = target_pages
        self.pages_per_device = pages_per_device
        self.delay = delay
        self.keyword = keyword

        # 로테이션 설정 로드
        with open('/tmp/rotation_config.json') as f:
            config = json.load(f)
            self.devices = config['rotation_candidates']

        # 통계
        self.stats = {
            'start_time': time.time(),
            'total_attempts': 0,
            'total_successful_pages': 0,
            'total_failed_pages': 0,
            'device_stats': {},
            'rate_limit_events': [],
            'error_log': []
        }

        # 진행 상황 파일
        self.progress_file = '/tmp/rotation_progress.json'
        self.report_file = '/tmp/rotation_report.txt'

    def run_main_for_device(self, device_info, start_page=1, end_page=10):
        """특정 디바이스로 main.py 실행"""

        device_name = device_info['device_info']['name']
        browser = device_info['device_info']['browser']
        os_version = device_info['device_info']['os_version']

        try:
            # 현재 시간 기록 (subprocess 실행 전)
            import glob
            import os
            before_time = time.time()

            # main.py 실행 (디바이스 지정)
            cmd = [
                'python', 'main.py',
                '--keyword', self.keyword,
                '--start', str(start_page),
                '--end', str(end_page),
                '--workers', '1',
                '--device-name', device_name,
                '--browser', browser,
                '--os-version', str(os_version)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,  # 인터랙티브 프롬프트 방지
                timeout=120,
                cwd='/var/www/html/browserstack'
            )

            # subprocess 결과 확인
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'main.py failed with return code {result.returncode}',
                    'successful_pages': 0,
                    'total_pages': end_page - start_page + 1,
                    'stdout': result.stdout[-500:] if result.stdout else '',
                    'stderr': result.stderr[-500:] if result.stderr else ''
                }

            # 최근 search_history 읽기 (subprocess 실행 후 생성된 것만)
            time.sleep(1)  # 파일 생성 대기

            history_files = sorted(glob.glob('/var/www/html/browserstack/data/search_history/*.json'), reverse=True)

            if history_files:
                latest_file = history_files[0]
                file_mtime = os.path.getmtime(latest_file)

                # 파일이 subprocess 실행 전에 생성되었으면 사용 안 함
                if file_mtime < before_time - 120:  # 2분 이상 오래된 파일
                    return {
                        'success': False,
                        'error': 'No new search_history file created',
                        'successful_pages': 0,
                        'total_pages': end_page - start_page + 1,
                        'stdout': result.stdout[-500:] if result.stdout else '',
                        'stderr': result.stderr[-500:] if result.stderr else ''
                    }

                with open(latest_file) as f:
                    data = json.load(f)

                successful = data['results']['successful_pages']
                total = data['results']['total_pages']
                failed = data['results']['failed_pages']

                return {
                    'success': True,
                    'successful_pages': successful,
                    'total_pages': total,
                    'failed_pages': failed,
                    'data': data
                }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'timeout',
                'successful_pages': 0,
                'total_pages': end_page - start_page + 1
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'successful_pages': 0,
                'total_pages': end_page - start_page + 1
            }

        return {'success': False, 'error': 'unknown', 'successful_pages': 0}

    def detect_rate_limit(self, result):
        """Rate limit 감지"""

        if not result.get('success'):
            return True

        # 연속 실패 패턴
        if result.get('successful_pages', 0) == 0:
            return True

        # 성공률 급감 (50% 미만)
        successful = result.get('successful_pages', 0)
        total = result.get('total_pages', 1)
        if successful / total < 0.5:
            return True

        return False

    def save_progress(self):
        """진행 상황 저장"""

        self.stats['elapsed_seconds'] = time.time() - self.stats['start_time']
        self.stats['progress_percentage'] = self.stats['total_successful_pages'] / self.target_pages * 100

        with open(self.progress_file, 'w') as f:
            json.dump(self.stats, f, indent=2)

    def generate_report(self, device_index, device_info, iteration):
        """실시간 리포트 생성"""

        elapsed = time.time() - self.stats['start_time']
        progress = self.stats['total_successful_pages'] / self.target_pages * 100
        success_rate = self.stats['total_successful_pages'] / max(1, self.stats['total_attempts']) * 100

        device_key = device_info['device_key']

        report = f"""
{'='*120}
디바이스 로테이션 진행 상황 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*120}

📊 전체 진행:
   목표: {self.target_pages:,} 페이지
   달성: {self.stats['total_successful_pages']:,} 페이지 ({progress:.2f}%)
   실패: {self.stats['total_failed_pages']:,} 페이지
   성공률: {success_rate:.1f}%
   소요 시간: {int(elapsed/60)}분 {int(elapsed%60)}초

🔄 현재 디바이스:
   번호: {device_index+1}/25
   디바이스: {device_key}
   반복: {iteration}회째

📈 디바이스별 성능:
"""

        # 상위 10개 디바이스 통계
        device_list = sorted(
            self.stats['device_stats'].items(),
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )[:10]

        for dev_key, dev_stats in device_list:
            rate = dev_stats['success_rate']
            successful = dev_stats['successful_pages']
            attempts = dev_stats['attempts']
            report += f"   {dev_key[:50]:<50} | {rate:>5.1f}% | {successful:>4}/{attempts*self.pages_per_device:<4} pages\n"

        report += f"\n⚠️ Rate Limit 이벤트: {len(self.stats['rate_limit_events'])}회\n"

        # 예상 완료 시간
        if self.stats['total_successful_pages'] > 0:
            pages_per_second = self.stats['total_successful_pages'] / elapsed
            remaining_pages = self.target_pages - self.stats['total_successful_pages']
            eta_seconds = remaining_pages / pages_per_second if pages_per_second > 0 else 0
            eta_hours = int(eta_seconds / 3600)
            eta_minutes = int((eta_seconds % 3600) / 60)

            report += f"\n⏱️ 예상 완료: 약 {eta_hours}시간 {eta_minutes}분 후\n"

        report += f"{'='*120}\n"

        # 파일에 저장
        with open(self.report_file, 'w') as f:
            f.write(report)

        # 콘솔 출력 (간략 버전)
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 진행: {self.stats['total_successful_pages']:,}/{self.target_pages:,} ({progress:.1f}%) | 디바이스: {device_index+1}/25 ({device_key[:30]})")

    def run(self):
        """로테이션 테스트 실행"""

        print("="*120)
        print("디바이스 로테이션 테스트 시작")
        print("="*120)
        print(f"목표: {self.target_pages:,} 페이지")
        print(f"디바이스: {len(self.devices)}개")
        print(f"디바이스당: {self.pages_per_device} 페이지")
        print(f"딜레이: {self.delay}초")
        print(f"키워드: {self.keyword}")
        print("="*120)

        iteration = 0

        while self.stats['total_successful_pages'] < self.target_pages:
            iteration += 1

            print(f"\n{'='*120}")
            print(f"🔄 반복 {iteration}회 시작 (달성: {self.stats['total_successful_pages']:,}/{self.target_pages:,})")
            print(f"{'='*120}")

            for device_index, device_info in enumerate(self.devices):
                device_key = device_info['device_key']

                # 디바이스 통계 초기화
                if device_key not in self.stats['device_stats']:
                    self.stats['device_stats'][device_key] = {
                        'attempts': 0,
                        'successful_pages': 0,
                        'total_pages': 0,
                        'success_rate': 0.0
                    }

                # main.py 실행
                result = self.run_main_for_device(device_info, 1, self.pages_per_device)

                # 통계 업데이트
                self.stats['total_attempts'] += self.pages_per_device
                successful = result.get('successful_pages', 0)
                total = result.get('total_pages', self.pages_per_device)
                failed = total - successful

                self.stats['total_successful_pages'] += successful
                self.stats['total_failed_pages'] += failed

                dev_stats = self.stats['device_stats'][device_key]
                dev_stats['attempts'] += 1
                dev_stats['successful_pages'] += successful
                dev_stats['total_pages'] += total
                if dev_stats['total_pages'] > 0:
                    dev_stats['success_rate'] = dev_stats['successful_pages'] / dev_stats['total_pages'] * 100

                # Rate limit 감지
                if self.detect_rate_limit(result):
                    self.stats['rate_limit_events'].append({
                        'device': device_key,
                        'iteration': iteration,
                        'time': datetime.now().isoformat()
                    })
                    print(f"  ⚠️ [{device_index+1}/25] {device_key[:40]}: Rate limit 감지 ({successful}/{total}) - 다음 디바이스로")
                else:
                    print(f"  ✅ [{device_index+1}/25] {device_key[:40]}: 성공 ({successful}/{total})")

                # 진행 상황 저장 및 리포트
                self.save_progress()
                self.generate_report(device_index, device_info, iteration)

                # 목표 달성 확인
                if self.stats['total_successful_pages'] >= self.target_pages:
                    print(f"\n🎉 목표 달성! {self.stats['total_successful_pages']:,} 페이지")
                    break

                # 딜레이
                time.sleep(self.delay)

        # 최종 리포트
        self.print_final_report()

    def print_final_report(self):
        """최종 리포트 출력"""

        elapsed = time.time() - self.stats['start_time']
        success_rate = self.stats['total_successful_pages'] / max(1, self.stats['total_attempts']) * 100

        print(f"\n{'='*120}")
        print("📊 최종 결과")
        print(f"{'='*120}")
        print(f"  목표: {self.target_pages:,} 페이지")
        print(f"  달성: {self.stats['total_successful_pages']:,} 페이지")
        print(f"  실패: {self.stats['total_failed_pages']:,} 페이지")
        print(f"  성공률: {success_rate:.1f}%")
        print(f"  소요 시간: {int(elapsed/3600)}시간 {int((elapsed%3600)/60)}분")
        print(f"  Rate Limit 이벤트: {len(self.stats['rate_limit_events'])}회")
        print(f"\n✅ 최종 리포트: {self.report_file}")
        print(f"✅ 진행 데이터: {self.progress_file}")
        print(f"{'='*120}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='디바이스 로테이션 테스트')
    parser.add_argument('--target', type=int, default=1000, help='목표 페이지 수 (기본: 1000)')
    parser.add_argument('--pages-per-device', type=int, default=10, help='디바이스당 페이지 (기본: 10)')
    parser.add_argument('--delay', type=float, default=2.0, help='디바이스 간 딜레이 (초)')
    parser.add_argument('--keyword', default='칫솔', help='검색 키워드')

    args = parser.parse_args()

    tester = DeviceRotationTester(
        target_pages=args.target,
        pages_per_device=args.pages_per_device,
        delay=args.delay,
        keyword=args.keyword
    )

    tester.run()
