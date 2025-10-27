#!/usr/bin/env python3
"""
간단한 IP 로테이션 테스트 (local + VPN 4)

목표: IP만 바꾸면 성공하는지 검증
"""

import subprocess
import json
import time
from datetime import datetime

def run_crawl(vpn_num=None, device_name="Samsung Galaxy S22", browser="samsung", os_version="12.0", keyword="칫솔"):
    """
    main.py 실행 (VPN 선택 가능)

    Args:
        vpn_num: None (local IP) 또는 4 (VPN 4)
    """

    # main.py 명령어
    cmd_base = [
        'python', 'main.py',
        '--keyword', keyword,
        '--start', '1',
        '--end', '1',  # 1페이지만
        '--workers', '1',
        '--device-name', device_name,
        '--browser', browser,
        '--os-version', os_version
    ]

    # VPN 사용 여부
    if vpn_num is not None:
        cmd = ['./vpn/client/vpn', str(vpn_num)] + cmd_base
        ip_label = f"VPN {vpn_num}"
    else:
        cmd = cmd_base
        ip_label = "Local"

    print(f"\n{'='*80}")
    print(f"🔄 테스트: {ip_label} - {device_name}")
    print(f"{'='*80}")
    print(f"명령어: {' '.join(cmd)}")

    try:
        start_time = time.time()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=120,
            cwd='/var/www/html/browserstack'
        )

        elapsed = time.time() - start_time

        # 결과 파싱
        if result.returncode == 0:
            # search_history 확인
            import glob
            history_files = sorted(
                glob.glob('/var/www/html/browserstack/data/search_history/*.json'),
                reverse=True
            )

            if history_files:
                with open(history_files[0]) as f:
                    data = json.load(f)

                success = data['results']['successful_pages']
                total = data['results']['total_pages']

                print(f"✅ 성공: {success}/{total} 페이지 (소요: {elapsed:.1f}초)")

                return {
                    'ip': ip_label,
                    'device': device_name,
                    'success': success,
                    'total': total,
                    'elapsed': elapsed,
                    'status': 'success' if success > 0 else 'failed'
                }
            else:
                print(f"⚠️ search_history 파일 없음")
                return {
                    'ip': ip_label,
                    'device': device_name,
                    'success': 0,
                    'total': 1,
                    'elapsed': elapsed,
                    'status': 'no_history'
                }
        else:
            print(f"❌ 실패: return code {result.returncode}")
            print(f"stderr: {result.stderr[-500:]}")

            return {
                'ip': ip_label,
                'device': device_name,
                'success': 0,
                'total': 1,
                'elapsed': elapsed,
                'status': 'error',
                'error': result.stderr[-200:]
            }

    except subprocess.TimeoutExpired:
        print(f"⏱️ 타임아웃 (120초)")
        return {
            'ip': ip_label,
            'device': device_name,
            'success': 0,
            'total': 1,
            'elapsed': 120,
            'status': 'timeout'
        }
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        return {
            'ip': ip_label,
            'device': device_name,
            'success': 0,
            'total': 1,
            'elapsed': 0,
            'status': 'exception',
            'error': str(e)
        }


def main():
    print(f"\n{'='*80}")
    print(f"IP 로테이션 간단 검증 테스트")
    print(f"{'='*80}")
    print(f"IP 2개: Local (220.121.120.83) + VPN 4 (112.161.221.82)")
    print(f"디바이스: Samsung Galaxy S22 (Samsung Browser)")
    print(f"목표: IP만 바꾸면 성공하는가?")
    print(f"{'='*80}\n")

    results = []

    # 테스트 1: Local IP (기본)
    print(f"\n[1/4] Local IP 테스트 #1...")
    time.sleep(2)
    result1 = run_crawl(vpn_num=None)
    results.append(result1)
    time.sleep(3)

    # 테스트 2: VPN 4
    print(f"\n[2/4] VPN 4 테스트 #1...")
    time.sleep(2)
    result2 = run_crawl(vpn_num=4)
    results.append(result2)
    time.sleep(3)

    # 테스트 3: Local IP (다시)
    print(f"\n[3/4] Local IP 테스트 #2...")
    time.sleep(2)
    result3 = run_crawl(vpn_num=None)
    results.append(result3)
    time.sleep(3)

    # 테스트 4: VPN 4 (다시)
    print(f"\n[4/4] VPN 4 테스트 #2...")
    time.sleep(2)
    result4 = run_crawl(vpn_num=4)
    results.append(result4)

    # 최종 리포트
    print(f"\n\n{'='*80}")
    print(f"📊 최종 결과")
    print(f"{'='*80}\n")

    for i, result in enumerate(results, 1):
        status_icon = "✅" if result['status'] == 'success' else "❌"
        print(f"{status_icon} 테스트 {i}: {result['ip']:10s} - "
              f"{result['success']}/{result['total']} 페이지 "
              f"({result['elapsed']:.1f}초)")

    # 분석
    print(f"\n{'='*80}")
    print(f"🔍 분석")
    print(f"{'='*80}\n")

    local_success = sum(r['success'] for r in results if r['ip'] == 'Local')
    local_total = sum(r['total'] for r in results if r['ip'] == 'Local')

    vpn4_success = sum(r['success'] for r in results if r['ip'] == 'VPN 4')
    vpn4_total = sum(r['total'] for r in results if r['ip'] == 'VPN 4')

    print(f"Local IP: {local_success}/{local_total} 페이지 "
          f"({local_success/local_total*100:.0f}% 성공률)")
    print(f"VPN 4:    {vpn4_success}/{vpn4_total} 페이지 "
          f"({vpn4_success/vpn4_total*100:.0f}% 성공률)")

    total_success = sum(r['success'] for r in results)
    total_attempts = sum(r['total'] for r in results)

    print(f"\n전체: {total_success}/{total_attempts} 페이지 "
          f"({total_success/total_attempts*100:.0f}% 성공률)")

    # 결론
    print(f"\n{'='*80}")
    print(f"✅ 결론")
    print(f"{'='*80}\n")

    if total_success >= 3:
        print("🎉 IP 로테이션 효과 확인!")
        print("   → 동일 디바이스 + IP 변경 = 성공")
        print("   → IP 로테이션으로 Rate Limit 우회 가능")
        print("   → 100,000 페이지 목표 달성 가능!")
    elif total_success >= 1:
        print("⚠️ 부분 성공 (추가 분석 필요)")
        print("   → 일부 IP는 작동")
        print("   → Rate Limit 패턴 재분석 필요")
    else:
        print("❌ TLS Fingerprint 문제!")
        print("   → IP 바꿔도 실패")
        print("   → 디바이스 TLS 재검증 필요")
        print("   → rotation_config.json 재확인")

    print(f"\n{'='*80}\n")

    # JSON 저장
    with open('/tmp/ip_rotation_test_result.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'summary': {
                'local_success': local_success,
                'local_total': local_total,
                'vpn4_success': vpn4_success,
                'vpn4_total': vpn4_total,
                'total_success': total_success,
                'total_attempts': total_attempts,
                'success_rate': total_success / total_attempts * 100
            }
        }, f, indent=2)

    print(f"📁 결과 저장: /tmp/ip_rotation_test_result.json\n")


if __name__ == '__main__':
    main()
