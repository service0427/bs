#!/usr/bin/env python3
"""
Akamai 쿠키 업데이트 테스트 스크립트

⚠️ 테스트용 기능입니다. 원본 보호 원칙을 위반합니다.

사용 방법:
    1. 현재 상태 확인:
       python test_akamai_update.py status <device_name> <browser>

    2. 테스트 크롤링 (업데이트 활성화):
       AKAMAI_UPDATE=1 python main.py --keyword "테스트"

    3. 기능 비활성화 (기본):
       python main.py --keyword "테스트"

예시:
    # 현재 상태 확인
    python test_akamai_update.py status "Samsung Galaxy S21 Ultra" "samsung"
    python test_akamai_update.py status "iPhone 17 Pro" "safari"

    # 업데이트 활성화하고 크롤링
    AKAMAI_UPDATE=1 python main.py --keyword "아이폰"
"""

import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.utils.akamai_updater import get_status, is_enabled, AKAMAI_COOKIE_NAMES


def show_status(device_name, browser):
    """Akamai 쿠키 현재 상태 조회"""
    print(f"\n{'='*70}")
    print(f"Akamai 쿠키 상태 조회")
    print(f"{'='*70}")
    print(f"디바이스: {device_name}")
    print(f"브라우저: {browser}")
    print(f"활성화: {'✅ ON' if is_enabled() else '❌ OFF (환경변수 AKAMAI_UPDATE=1 필요)'}")
    print(f"{'='*70}\n")

    status = get_status(device_name, browser)

    if 'error' in status:
        print(f"❌ 오류: {status['error']}\n")
        return

    print(f"발견된 Akamai 쿠키: {status['found']}개\n")

    for name in AKAMAI_COOKIE_NAMES:
        if name in status['cookies']:
            cookie = status['cookies'][name]
            print(f"  ✓ {name}")
            print(f"    값: {cookie['preview']}")
        else:
            print(f"  ✗ {name} (없음)")

    print(f"\n{'='*70}\n")


def show_usage():
    """사용 방법 출력"""
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        show_usage()
        return

    command = sys.argv[1]

    if command == 'status':
        if len(sys.argv) < 4:
            print("❌ 디바이스 이름과 브라우저를 입력하세요.")
            print("예시: python test_akamai_update.py status \"Samsung Galaxy S21 Ultra\" \"samsung\"")
            print("예시: python test_akamai_update.py status \"iPhone 17 Pro\" \"safari\"")
            return

        device_name = sys.argv[2]
        browser = sys.argv[3]
        show_status(device_name, browser)

    elif command == 'help':
        show_usage()

    else:
        print(f"❌ 알 수 없는 명령어: {command}")
        print("사용 가능한 명령어: status, help")
        show_usage()


if __name__ == "__main__":
    main()
