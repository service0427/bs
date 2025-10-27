#!/usr/bin/env python3
"""
VPN 연결 관리 모듈

GitHub: https://github.com/service0427/vpn
IP 4개 로테이션 지원
"""

import subprocess
import time
import requests
import json
from typing import Optional, Dict, List

class VPNManager:
    """VPN 연결 관리 및 IP 로테이션"""

    def __init__(self, vpn_configs: List[Dict[str, str]]):
        """
        Args:
            vpn_configs: VPN 설정 리스트
                [
                    {"name": "vpn1", "config_file": "/path/to/config1.ovpn"},
                    {"name": "vpn2", "config_file": "/path/to/config2.ovpn"},
                    ...
                ]
        """
        self.vpn_configs = vpn_configs
        self.current_vpn_index = 0
        self.current_vpn_name = None
        self.current_ip = None

        # IP별 사용 통계
        self.ip_stats = {
            config['name']: {
                'successful_pages': 0,
                'failed_pages': 0,
                'rate_limit_count': 0,
                'last_used': None
            }
            for config in vpn_configs
        }

    def connect_vpn(self, vpn_name: str) -> bool:
        """특정 VPN에 연결"""
        config = next((c for c in self.vpn_configs if c['name'] == vpn_name), None)
        if not config:
            print(f"❌ VPN 설정을 찾을 수 없음: {vpn_name}")
            return False

        print(f"🔌 VPN 연결 중: {vpn_name}...")

        try:
            # 기존 VPN 연결 종료
            self.disconnect_vpn()

            # 새 VPN 연결 (백그라운드)
            # 실제 구현은 service0427/vpn 저장소의 API에 맞게 수정 필요
            cmd = [
                'openvpn',
                '--config', config['config_file'],
                '--daemon',
                '--log', f'/tmp/vpn_{vpn_name}.log'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                print(f"❌ VPN 연결 실패: {result.stderr}")
                return False

            # 연결 대기 (최대 30초)
            for i in range(30):
                time.sleep(1)
                if self.check_vpn_connected():
                    self.current_vpn_name = vpn_name
                    self.current_ip = self.get_current_ip()
                    print(f"✅ VPN 연결 성공: {vpn_name} (IP: {self.current_ip})")
                    return True

            print(f"⚠️ VPN 연결 타임아웃: {vpn_name}")
            return False

        except Exception as e:
            print(f"❌ VPN 연결 에러: {e}")
            return False

    def disconnect_vpn(self):
        """현재 VPN 연결 종료"""
        try:
            subprocess.run(['killall', 'openvpn'], stderr=subprocess.DEVNULL)
            time.sleep(2)
            self.current_vpn_name = None
            self.current_ip = None
        except Exception as e:
            print(f"⚠️ VPN 종료 에러: {e}")

    def check_vpn_connected(self) -> bool:
        """VPN 연결 상태 확인"""
        try:
            result = subprocess.run(
                ['pgrep', 'openvpn'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def get_current_ip(self) -> Optional[str]:
        """현재 외부 IP 조회"""
        try:
            response = requests.get('https://api.ipify.org?format=json', timeout=10)
            return response.json()['ip']
        except:
            try:
                response = requests.get('https://ifconfig.me/ip', timeout=10)
                return response.text.strip()
            except:
                return None

    def rotate_to_next_vpn(self) -> bool:
        """다음 VPN으로 로테이션"""
        self.current_vpn_index = (self.current_vpn_index + 1) % len(self.vpn_configs)
        next_vpn = self.vpn_configs[self.current_vpn_index]
        return self.connect_vpn(next_vpn['name'])

    def get_best_vpn(self) -> str:
        """성공률이 가장 높은 VPN 선택"""
        best_vpn = None
        best_success_rate = -1

        for config in self.vpn_configs:
            stats = self.ip_stats[config['name']]
            total = stats['successful_pages'] + stats['failed_pages']

            if total == 0:
                # 사용 기록 없으면 우선 선택
                return config['name']

            success_rate = stats['successful_pages'] / total
            if success_rate > best_success_rate:
                best_success_rate = success_rate
                best_vpn = config['name']

        return best_vpn or self.vpn_configs[0]['name']

    def record_success(self, pages: int):
        """성공 기록"""
        if self.current_vpn_name:
            self.ip_stats[self.current_vpn_name]['successful_pages'] += pages
            self.ip_stats[self.current_vpn_name]['last_used'] = time.time()

    def record_failure(self, pages: int):
        """실패 기록"""
        if self.current_vpn_name:
            self.ip_stats[self.current_vpn_name]['failed_pages'] += pages
            self.ip_stats[self.current_vpn_name]['last_used'] = time.time()

    def record_rate_limit(self):
        """Rate Limit 기록"""
        if self.current_vpn_name:
            self.ip_stats[self.current_vpn_name]['rate_limit_count'] += 1

    def should_rotate_ip(self) -> bool:
        """IP 로테이션이 필요한지 판단"""
        if not self.current_vpn_name:
            return True

        stats = self.ip_stats[self.current_vpn_name]

        # Rate Limit 3회 이상 → 즉시 로테이션
        if stats['rate_limit_count'] >= 3:
            print(f"⚠️ Rate Limit 3회 감지 → IP 로테이션 필요")
            return True

        # 성공률 30% 미만 → 로테이션
        total = stats['successful_pages'] + stats['failed_pages']
        if total >= 10:
            success_rate = stats['successful_pages'] / total
            if success_rate < 0.3:
                print(f"⚠️ 성공률 {success_rate*100:.1f}% → IP 로테이션 필요")
                return True

        return False

    def print_stats(self):
        """IP별 통계 출력"""
        print("\n" + "=" * 80)
        print("IP별 사용 통계")
        print("=" * 80)

        for config in self.vpn_configs:
            name = config['name']
            stats = self.ip_stats[name]
            total = stats['successful_pages'] + stats['failed_pages']

            if total > 0:
                success_rate = stats['successful_pages'] / total * 100
            else:
                success_rate = 0

            current_mark = "← 현재" if name == self.current_vpn_name else ""

            print(f"{name:10s} | 성공: {stats['successful_pages']:3d} | "
                  f"실패: {stats['failed_pages']:3d} | "
                  f"Rate Limit: {stats['rate_limit_count']:2d} | "
                  f"성공률: {success_rate:5.1f}% {current_mark}")

        print("=" * 80 + "\n")


# 사용 예시
if __name__ == '__main__':
    # VPN 설정 (실제 경로로 수정 필요)
    vpn_configs = [
        {"name": "vpn1", "config_file": "/path/to/vpn1.ovpn"},
        {"name": "vpn2", "config_file": "/path/to/vpn2.ovpn"},
        {"name": "vpn3", "config_file": "/path/to/vpn3.ovpn"},
        {"name": "vpn4", "config_file": "/path/to/vpn4.ovpn"},
    ]

    manager = VPNManager(vpn_configs)

    # VPN 연결
    if manager.connect_vpn("vpn1"):
        print(f"현재 IP: {manager.current_ip}")

    # 통계 출력
    manager.print_stats()

    # VPN 종료
    manager.disconnect_vpn()
