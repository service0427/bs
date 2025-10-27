#!/usr/bin/env python3
"""
디바이스 + IP 로테이션 테스트 (VPN 통합)

목표: IP 4개 + 디바이스 13개 조합으로 10만번 조회 달성
전략: Rate Limit 감지 시 자동 IP 전환
"""

import json
import time
import subprocess
import argparse
import sys
from datetime import datetime
from pathlib import Path

# VPNManager 임포트
sys.path.insert(0, '/var/www/html/browserstack')
from scripts.vpn_manager import VPNManager


class DeviceRotationWithVPN:
    def __init__(
        self,
        vpn_configs,
        target_pages=100000,
        pages_per_device=10,
        pages_per_ip=50,
        delay=2.0,
        keyword="칫솔"
    ):
        """
        Args:
            vpn_configs: VPN 설정 리스트
            target_pages: 목표 페이지 수
            pages_per_device: 디바이스당 페이지 수
            pages_per_ip: IP당 최대 페이지 수 (초과 시 IP 전환)
            delay: 디바이스 간 딜레이 (초)
            keyword: 검색 키워드
        """
        self.target_pages = target_pages
        self.pages_per_device = pages_per_device
        self.pages_per_ip = pages_per_ip
        self.delay = delay
        self.keyword = keyword

        # VPN 매니저 초기화
        self.vpn_manager = VPNManager(vpn_configs)

        # 로테이션 설정 로드
        with open('/tmp/rotation_config.json') as f:
            config = json.load(f)
            self.devices = config['rotation_candidates']

        print(f"✅ 디바이스 {len(self.devices)}개 로드 완료")
        print(f"✅ VPN {len(vpn_configs)}개 설정 완료")

        # 통계
        self.stats = {
            'start_time': time.time(),
            'total_attempts': 0,
            'total_successful_pages': 0,
            'total_failed_pages': 0,
            'device_stats': {},
            'rate_limit_events': [],
            'ip_rotation_events': [],
            'error_log': []
        }

        # 현재 IP 사용량
        self.current_ip_pages = 0

        # 진행 상황 파일
        self.progress_file = '/tmp/rotation_vpn_progress.json'
        self.report_file = '/tmp/rotation_vpn_report.txt'

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
                stdin=subprocess.DEVNULL,
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

            history_files = sorted(
                glob.glob('/var/www/html/browserstack/data/search_history/*.json'),
                reverse=True
            )

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
            else:
                return {
                    'success': False,
                    'error': 'No search_history file found',
                    'successful_pages': 0,
                    'total_pages': end_page - start_page + 1
                }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'main.py timeout',
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

    def check_and_rotate_ip(self, force=False):
        """IP 로테이션 필요 시 전환"""

        # 강제 로테이션 또는 자동 판단
        if force or self.vpn_manager.should_rotate_ip() or self.current_ip_pages >= self.pages_per_ip:
            print(f"\n🔄 IP 로테이션 시작...")
            print(f"   현재 IP 사용량: {self.current_ip_pages} 페이지")

            # 다음 VPN으로 전환
            if self.vpn_manager.rotate_to_next_vpn():
                self.current_ip_pages = 0
                self.stats['ip_rotation_events'].append({
                    'time': time.time(),
                    'new_ip': self.vpn_manager.current_ip,
                    'new_vpn': self.vpn_manager.current_vpn_name
                })
                print(f"✅ IP 로테이션 완료: {self.vpn_manager.current_ip}")
                return True
            else:
                print(f"❌ IP 로테이션 실패")
                return False

        return True

    def run_rotation(self):
        """디바이스 + IP 로테이션 실행"""

        print(f"\n{'='*80}")
        print(f"디바이스 + IP 로테이션 테스트 시작")
        print(f"{'='*80}")
        print(f"목표: {self.target_pages} 페이지")
        print(f"디바이스: {len(self.devices)}개")
        print(f"VPN: {len(self.vpn_manager.vpn_configs)}개")
        print(f"디바이스당: {self.pages_per_device} 페이지")
        print(f"IP당 최대: {self.pages_per_ip} 페이지")
        print(f"딜레이: {self.delay}초")
        print(f"키워드: {self.keyword}")
        print(f"{'='*80}\n")

        # 첫 VPN 연결
        best_vpn = self.vpn_manager.get_best_vpn()
        if not self.vpn_manager.connect_vpn(best_vpn):
            print("❌ 초기 VPN 연결 실패")
            return

        iteration = 0
        device_index = 0

        while self.stats['total_successful_pages'] < self.target_pages:
            iteration += 1

            print(f"\n{'='*80}")
            print(f"🔄 반복 {iteration}회 시작 (달성: {self.stats['total_successful_pages']}/{self.target_pages})")
            print(f"{'='*80}")

            # 디바이스 순환
            for i in range(len(self.devices)):
                device_info = self.devices[device_index]
                device_key = device_info['device_key']

                # IP 로테이션 체크
                if not self.check_and_rotate_ip():
                    print("⚠️ IP 로테이션 실패, 계속 진행")

                # 디바이스별 통계 초기화
                if device_key not in self.stats['device_stats']:
                    self.stats['device_stats'][device_key] = {
                        'attempts': 0,
                        'successful_pages': 0,
                        'failed_pages': 0
                    }

                device_stats = self.stats['device_stats'][device_key]

                # main.py 실행
                print(f"  [{device_index + 1}/{len(self.devices)}] {device_key}: ", end='', flush=True)

                result = self.run_main_for_device(
                    device_info,
                    start_page=1,
                    end_page=self.pages_per_device
                )

                # 결과 처리
                device_stats['attempts'] += 1
                self.stats['total_attempts'] += result['total_pages']

                if result['success']:
                    success = result['successful_pages']
                    failed = result['failed_pages']

                    device_stats['successful_pages'] += success
                    device_stats['failed_pages'] += failed
                    self.stats['total_successful_pages'] += success
                    self.stats['total_failed_pages'] += failed
                    self.current_ip_pages += success

                    # VPN 매니저에 기록
                    self.vpn_manager.record_success(success)
                    if failed > 0:
                        self.vpn_manager.record_failure(failed)

                    if success == result['total_pages']:
                        print(f"✅ 성공 ({success}/{result['total_pages']})")
                    else:
                        print(f"⚠️ 부분 성공 ({success}/{result['total_pages']})")
                        if failed >= success:
                            # Rate Limit 의심
                            self.stats['rate_limit_events'].append({
                                'time': time.time(),
                                'device': device_key,
                                'ip': self.vpn_manager.current_ip
                            })
                            self.vpn_manager.record_rate_limit()
                else:
                    # 완전 실패
                    device_stats['failed_pages'] += result['total_pages']
                    self.stats['total_failed_pages'] += result['total_pages']

                    # VPN 매니저에 기록
                    self.vpn_manager.record_failure(result['total_pages'])

                    print(f"❌ 실패 (0/{result['total_pages']}) - {result.get('error', 'Unknown')}")

                    # Rate Limit 감지
                    if 'Rate limit' in result.get('error', '') or 'INTERNAL_ERROR' in result.get('stderr', ''):
                        self.stats['rate_limit_events'].append({
                            'time': time.time(),
                            'device': device_key,
                            'ip': self.vpn_manager.current_ip
                        })
                        self.vpn_manager.record_rate_limit()
                        print(f"  ⚠️ Rate limit 감지 - 다음 디바이스로")

                # 진행 상황 출력
                elapsed = time.time() - self.stats['start_time']
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                      f"진행: {self.stats['total_successful_pages']}/{self.target_pages} "
                      f"({self.stats['total_successful_pages']/self.target_pages*100:.1f}%) | "
                      f"디바이스: {device_index + 1}/{len(self.devices)} ({device_key[:30]})")
                print(f"   IP: {self.vpn_manager.current_vpn_name} ({self.vpn_manager.current_ip}), "
                      f"사용량: {self.current_ip_pages} 페이지")

                # 진행 상황 저장
                self.save_progress()
                self.save_report()

                # 목표 달성 확인
                if self.stats['total_successful_pages'] >= self.target_pages:
                    print(f"\n🎉 목표 달성! {self.stats['total_successful_pages']} 페이지")
                    break

                # 다음 디바이스
                device_index = (device_index + 1) % len(self.devices)

                # 딜레이
                if i < len(self.devices) - 1:
                    time.sleep(self.delay)

            # 반복 완료 후 IP 통계 출력
            self.vpn_manager.print_stats()

        # 최종 리포트
        self.print_final_report()

        # VPN 종료
        self.vpn_manager.disconnect_vpn()

    def save_progress(self):
        """진행 상황 저장"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.stats, f, indent=2)

    def save_report(self):
        """실시간 리포트 저장"""
        elapsed = time.time() - self.stats['start_time']
        elapsed_min = int(elapsed / 60)
        elapsed_sec = int(elapsed % 60)

        total_attempts = self.stats['total_attempts']
        total_success = self.stats['total_successful_pages']
        total_failed = self.stats['total_failed_pages']

        if total_attempts > 0:
            success_rate = total_success / total_attempts * 100
        else:
            success_rate = 0

        # 디바이스별 성능 정렬
        device_performance = []
        for device_key, stats in self.stats['device_stats'].items():
            total = stats['successful_pages'] + stats['failed_pages']
            if total > 0:
                rate = stats['successful_pages'] / total * 100
                device_performance.append({
                    'device': device_key,
                    'rate': rate,
                    'successful': stats['successful_pages'],
                    'total': total
                })

        device_performance.sort(key=lambda x: x['rate'], reverse=True)

        with open(self.report_file, 'w') as f:
            f.write(f"\n{'='*120}\n")
            f.write(f"디바이스 + IP 로테이션 진행 상황 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*120}\n\n")

            f.write(f"📊 전체 진행:\n")
            f.write(f"   목표: {self.target_pages} 페이지\n")
            f.write(f"   달성: {total_success} 페이지 ({total_success/self.target_pages*100:.2f}%)\n")
            f.write(f"   실패: {total_failed} 페이지\n")
            f.write(f"   성공률: {success_rate:.1f}%\n")
            f.write(f"   소요 시간: {elapsed_min}분 {elapsed_sec}초\n\n")

            f.write(f"🌐 현재 IP:\n")
            f.write(f"   VPN: {self.vpn_manager.current_vpn_name}\n")
            f.write(f"   IP: {self.vpn_manager.current_ip}\n")
            f.write(f"   사용량: {self.current_ip_pages} 페이지\n\n")

            f.write(f"📈 디바이스별 성능:\n")
            for item in device_performance[:20]:  # 상위 20개만
                f.write(f"   {item['device']:50s} | {item['rate']:5.1f}% | "
                       f"{item['successful']:4d}/{item['total']:4d}   pages\n")

            f.write(f"\n⚠️ Rate Limit 이벤트: {len(self.stats['rate_limit_events'])}회\n")
            f.write(f"🔄 IP 로테이션 횟수: {len(self.stats['ip_rotation_events'])}회\n\n")

            # 예상 완료 시간
            if total_success > 0 and elapsed > 0:
                pages_per_min = total_success / (elapsed / 60)
                remaining = self.target_pages - total_success
                eta_min = int(remaining / pages_per_min)
                eta_hour = eta_min // 60
                eta_min_remainder = eta_min % 60
                f.write(f"⏱️ 예상 완료: 약 {eta_hour}시간 {eta_min_remainder}분 후\n")

            f.write(f"{'='*120}\n\n")

    def print_final_report(self):
        """최종 리포트 출력"""
        elapsed = time.time() - self.stats['start_time']
        print(f"\n{'='*80}")
        print(f"최종 결과")
        print(f"{'='*80}")
        print(f"총 시도: {self.stats['total_attempts']} 페이지")
        print(f"성공: {self.stats['total_successful_pages']} 페이지")
        print(f"실패: {self.stats['total_failed_pages']} 페이지")
        print(f"성공률: {self.stats['total_successful_pages']/self.stats['total_attempts']*100:.1f}%")
        print(f"소요 시간: {int(elapsed/60)}분 {int(elapsed%60)}초")
        print(f"Rate Limit: {len(self.stats['rate_limit_events'])}회")
        print(f"IP 로테이션: {len(self.stats['ip_rotation_events'])}회")
        print(f"{'='*80}\n")

        # IP별 통계
        self.vpn_manager.print_stats()


def main():
    parser = argparse.ArgumentParser(description='디바이스 + IP 로테이션 테스트')
    parser.add_argument('--target', type=int, default=100, help='목표 페이지 수')
    parser.add_argument('--pages-per-device', type=int, default=10, help='디바이스당 페이지 수')
    parser.add_argument('--pages-per-ip', type=int, default=50, help='IP당 최대 페이지 수')
    parser.add_argument('--delay', type=float, default=2.0, help='디바이스 간 딜레이 (초)')
    parser.add_argument('--keyword', type=str, default='칫솔', help='검색 키워드')
    parser.add_argument('--vpn-config', type=str, default='/tmp/vpn_config.json',
                       help='VPN 설정 파일 경로')

    args = parser.parse_args()

    # VPN 설정 로드
    try:
        with open(args.vpn_config) as f:
            vpn_configs = json.load(f)
        print(f"✅ VPN 설정 로드: {len(vpn_configs)}개")
    except FileNotFoundError:
        print(f"❌ VPN 설정 파일 없음: {args.vpn_config}")
        print("기본 설정으로 생성합니다...")

        # 기본 VPN 설정 (사용자가 실제 경로로 수정 필요)
        vpn_configs = [
            {"name": "vpn1", "config_file": "/path/to/vpn1.ovpn"},
            {"name": "vpn2", "config_file": "/path/to/vpn2.ovpn"},
            {"name": "vpn3", "config_file": "/path/to/vpn3.ovpn"},
            {"name": "vpn4", "config_file": "/path/to/vpn4.ovpn"},
        ]

        with open(args.vpn_config, 'w') as f:
            json.dump(vpn_configs, f, indent=2)

        print(f"✅ 기본 설정 생성: {args.vpn_config}")
        print("⚠️ 파일을 편집하여 실제 VPN 경로를 입력하세요!")
        return

    # 테스트 실행
    tester = DeviceRotationWithVPN(
        vpn_configs=vpn_configs,
        target_pages=args.target,
        pages_per_device=args.pages_per_device,
        pages_per_ip=args.pages_per_ip,
        delay=args.delay,
        keyword=args.keyword
    )

    try:
        tester.run_rotation()
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자 중단")
        tester.save_progress()
        tester.save_report()
        tester.vpn_manager.disconnect_vpn()
    except Exception as e:
        print(f"\n\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        tester.vpn_manager.disconnect_vpn()


if __name__ == '__main__':
    main()
