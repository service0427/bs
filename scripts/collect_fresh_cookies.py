#!/usr/bin/env python3
"""
신선한 쿠키 수집 스크립트 (비대화형)

목적: BrowserStack을 통해 신선한 TLS + 쿠키 수집 (자동화)
"""

import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.collectors.dynamic import DynamicCollector
from lib.settings import ensure_directories

def main():
    print("\n" + "="*80)
    print("신선한 쿠키 수집 (비대화형)")
    print("="*80)

    # 디렉토리 생성
    ensure_directories()

    # S20 Ultra 설정
    device_config = {
        'device': 'Samsung Galaxy S20 Ultra',
        'os': 'android',
        'os_version': '10.0',
        'browser': 'android',
        'real_mobile': True
    }

    print(f"\n[수집 대상]")
    print(f"  디바이스: {device_config['device']}")
    print(f"  브라우저: {device_config['browser']}")
    print(f"  OS 버전: {device_config['os_version']}")
    print(f"\n{'='*80}\n")

    # Collector 생성 (강제 재수집 모드)
    collector = DynamicCollector(
        device_config=device_config,
        refresh_policy='force'
    )

    # 수집 실행
    print("[BrowserStack 세션 시작...]")
    success = collector.collect()

    if success:
        print(f"\n{'='*80}")
        print("✅ 수집 완료!")
        print(f"{'='*80}\n")
        return 0
    else:
        print(f"\n{'='*80}")
        print("❌ 수집 실패")
        print(f"{'='*80}\n")
        return 1

if __name__ == '__main__':
    exit(main())
