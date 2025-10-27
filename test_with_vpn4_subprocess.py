#!/usr/bin/env python3
"""
VPN 4를 subprocess로 실행하는 간단한 테스트

VPN wrapper 환경 문제 우회
"""

import subprocess
import sys

def run_with_vpn4(keyword, start_page, end_page):
    """VPN 4로 main.py 실행"""

    # VPN 4 wrapper를 통해 main.py 실행
    cmd = [
        '/var/www/html/browserstack/vpn/client/vpn',
        '4',
        'python',
        '/var/www/html/browserstack/main.py',
        '--keyword', keyword,
        '--start', str(start_page),
        '--end', str(end_page),
        '--workers', '1',
        '--device-name', 'Samsung Galaxy S22',
        '--browser', 'samsung',
        '--os-version', '12.0'
    ]

    print(f"실행: {' '.join(cmd)}")
    print("")

    result = subprocess.run(
        cmd,
        capture_output=False,  # 출력을 직접 보여줌
        text=True,
        cwd='/var/www/html/browserstack'
    )

    return result.returncode


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("사용법: python test_with_vpn4_subprocess.py <키워드> <시작페이지> <끝페이지>")
        print("예시: python test_with_vpn4_subprocess.py 테스트용품 11 15")
        sys.exit(1)

    keyword = sys.argv[1]
    start_page = int(sys.argv[2])
    end_page = int(sys.argv[3])

    exit_code = run_with_vpn4(keyword, start_page, end_page)
    sys.exit(exit_code)
