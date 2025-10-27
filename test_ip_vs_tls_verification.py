#!/usr/bin/env python3
"""
IP vs TLS 문제 검증 스크립트

사용자 제안 방법론:
1. Local IP로 테스트 → 성공할 때까지 계속
2. Rate Limit 걸리면 → 실패한 페이지 번호 기록
3. VPN 4로 같은 페이지 재시도
4. VPN 4 성공 → IP 문제 확인 ✅
5. VPN 4 실패 → TLS 문제 ❌

목표: IP 로테이션이 Rate Limit 우회에 효과적인지 검증
"""

import subprocess
import json
import time
from datetime import datetime

def run_crawl(vpn_num=None, keyword="칫솔", start_page=1, end_page=1):
    """
    main.py 실행 (VPN 선택 가능)

    Args:
        vpn_num: None (local IP) 또는 4 (VPN 4)
        keyword: 검색 키워드
        start_page: 시작 페이지
        end_page: 끝 페이지

    Returns:
        dict: {'success': bool, 'ip': str, 'pages': int, 'error': str}
    """

    # main.py 명령어
    cmd_base = [
        'python', 'main.py',
        '--keyword', keyword,
        '--start', str(start_page),
        '--end', str(end_page),
        '--workers', '1',
        '--device-name', 'Samsung Galaxy S22',
        '--browser', 'samsung',
        '--os-version', '12.0'
    ]

    # VPN 사용 여부
    if vpn_num is not None:
        cmd = ['./vpn/client/vpn', str(vpn_num)] + cmd_base
        ip_label = f"VPN {vpn_num}"
    else:
        cmd = cmd_base
        ip_label = "Local"

    print(f"\n{'='*80}")
    print(f"🔄 테스트: {ip_label} - 페이지 {start_page}~{end_page}")
    print(f"{'='*80}")
    print(f"명령어: {' '.join(cmd)}")

    try:
        start_time = time.time()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=180,
            cwd='/var/www/html/browserstack'
        )

        elapsed = time.time() - start_time

        # IP 주소 추출 (출력에서)
        current_ip = None
        if "현재 IP:" in result.stdout:
            import re
            ip_match = re.search(r'현재 IP:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', result.stdout)
            if ip_match:
                current_ip = ip_match.group(1)

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
                if current_ip:
                    print(f"🌐 IP: {current_ip}")

                return {
                    'success': success > 0,
                    'ip': ip_label,
                    'current_ip': current_ip,
                    'successful_pages': success,
                    'total_pages': total,
                    'elapsed': elapsed,
                    'error': None
                }
            else:
                print(f"⚠️ search_history 파일 없음")
                return {
                    'success': False,
                    'ip': ip_label,
                    'current_ip': current_ip,
                    'successful_pages': 0,
                    'total_pages': end_page - start_page + 1,
                    'elapsed': elapsed,
                    'error': 'No history file'
                }
        else:
            print(f"❌ 실패: return code {result.returncode}")
            print(f"stderr: {result.stderr[-500:] if result.stderr else 'N/A'}")

            return {
                'success': False,
                'ip': ip_label,
                'current_ip': current_ip,
                'successful_pages': 0,
                'total_pages': end_page - start_page + 1,
                'elapsed': elapsed,
                'error': result.stderr[-200:] if result.stderr else 'Unknown error'
            }

    except subprocess.TimeoutExpired:
        print(f"⏱️ 타임아웃 (180초)")
        return {
            'success': False,
            'ip': ip_label,
            'current_ip': None,
            'successful_pages': 0,
            'total_pages': end_page - start_page + 1,
            'elapsed': 180,
            'error': 'Timeout'
        }
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        return {
            'success': False,
            'ip': ip_label,
            'current_ip': None,
            'successful_pages': 0,
            'total_pages': end_page - start_page + 1,
            'elapsed': 0,
            'error': str(e)
        }


def main():
    print(f"\n{'='*80}")
    print(f"IP vs TLS 문제 검증 테스트")
    print(f"{'='*80}")
    print(f"방법론:")
    print(f"  1. Local IP로 연속 크롤링 → Rate Limit 발생 시점 찾기")
    print(f"  2. 실패한 페이지를 VPN 4로 재시도")
    print(f"  3. VPN 4 성공 → IP 문제 (로테이션으로 해결 가능 ✅)")
    print(f"  4. VPN 4 실패 → TLS 문제 (디바이스 재검증 필요 ❌)")
    print(f"{'='*80}\n")

    results = []

    # Phase 1: Local IP로 연속 테스트 (페이지 11~20)
    print(f"\n{'='*80}")
    print(f"Phase 1: Local IP 연속 테스트")
    print(f"{'='*80}")
    print(f"목표: Rate Limit 발생 시점 찾기 (페이지 11~20)")
    print(f"")

    failed_page = None

    for page in range(11, 21):
        print(f"\n[Local IP] 페이지 {page} 테스트 중...")
        time.sleep(3)  # 요청 간 간격

        result = run_crawl(vpn_num=None, start_page=page, end_page=page)
        results.append(result)

        if not result['success']:
            print(f"\n⚠️  페이지 {page}에서 Rate Limit 발생!")
            failed_page = page
            break
        else:
            print(f"✅ 페이지 {page} 성공")

    if failed_page is None:
        print(f"\n✅ 페이지 11~20 모두 성공! Rate Limit 없음")
        print(f"   → 더 많은 페이지 테스트 필요 (21~30 계속)")

        # 결과 저장
        with open('/tmp/ip_vs_tls_result.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'phase': 'Local IP 11-20',
                'result': 'All success',
                'failed_page': None,
                'results': results
            }, f, indent=2)

        return

    # Phase 2: VPN 4로 실패한 페이지 재시도
    print(f"\n{'='*80}")
    print(f"Phase 2: VPN 4로 실패 페이지 재시도")
    print(f"{'='*80}")
    print(f"실패한 페이지: {failed_page}")
    print(f"")

    time.sleep(5)  # VPN 전환 대기

    print(f"[VPN 4] 페이지 {failed_page} 재시도 중...")
    vpn_result = run_crawl(vpn_num=4, start_page=failed_page, end_page=failed_page)
    results.append(vpn_result)

    # Phase 3: 결과 분석
    print(f"\n\n{'='*80}")
    print(f"📊 최종 결과")
    print(f"{'='*80}\n")

    # Local IP 통계
    local_results = [r for r in results if r['ip'] == 'Local']
    local_success = sum(r['successful_pages'] for r in local_results)
    local_total = sum(r['total_pages'] for r in local_results)

    print(f"Local IP 결과:")
    print(f"  성공: {local_success}/{local_total} 페이지")
    print(f"  실패 페이지: {failed_page}")
    if local_results and local_results[0].get('current_ip'):
        print(f"  IP 주소: {local_results[0]['current_ip']}")

    # VPN 4 결과
    print(f"\nVPN 4 결과:")
    print(f"  페이지 {failed_page} 재시도: {'✅ 성공' if vpn_result['success'] else '❌ 실패'}")
    if vpn_result.get('current_ip'):
        print(f"  IP 주소: {vpn_result['current_ip']}")

    # 결론
    print(f"\n{'='*80}")
    print(f"✅ 결론")
    print(f"{'='*80}\n")

    if vpn_result['success']:
        print(f"🎉 IP 문제 확인!")
        print(f"   → Local IP 페이지 {failed_page}에서 실패")
        print(f"   → VPN 4로 동일 페이지 성공")
        print(f"   → Rate Limit은 IP 기반 ✅")
        print(f"")
        print(f"💡 해결책:")
        print(f"   - IP 로테이션으로 Rate Limit 우회 가능")
        print(f"   - 디바이스 + IP 조합으로 100,000 페이지 목표 달성 가능")
        print(f"   - VPN 4개 IP × 13개 디바이스 = 52개 조합 사용")
        conclusion = "IP 문제 (로테이션으로 해결 가능)"
    else:
        print(f"❌ TLS 문제 발견!")
        print(f"   → Local IP 페이지 {failed_page}에서 실패")
        print(f"   → VPN 4로 동일 페이지도 실패")
        print(f"   → IP 바꿔도 막힘 = TLS Fingerprint 문제")
        print(f"")
        print(f"⚠️  해결 필요:")
        print(f"   - Samsung Galaxy S22 디바이스 TLS 재검증")
        print(f"   - rotation_config.json 재확인")
        print(f"   - 다른 디바이스로 재테스트")
        conclusion = "TLS 문제 (디바이스 재검증 필요)"

    print(f"\n{'='*80}\n")

    # JSON 저장
    with open('/tmp/ip_vs_tls_result.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'local_ip_success': local_success,
            'local_ip_total': local_total,
            'failed_page': failed_page,
            'vpn4_retry_success': vpn_result['success'],
            'conclusion': conclusion,
            'results': results
        }, f, indent=2)

    print(f"📁 결과 저장: /tmp/ip_vs_tls_result.json\n")


if __name__ == '__main__':
    main()
