"""
robots.txt 병렬 대량 접근 테스트
차단 여부 확인
"""

from curl_cffi import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def test_robots_access(worker_id):
    """robots.txt 접속 테스트"""
    try:
        start_time = time.time()
        response = requests.get(
            'https://www.coupang.com/robots.txt',
            impersonate='chrome110',
            timeout=10
        )
        elapsed = time.time() - start_time

        # 쿠키 확인
        cookies = response.cookies
        has_akamai = any(name in ['_abck', 'bm_sz', 'ak_bmsc', 'bm_mi'] for name in cookies.keys())

        result = {
            'worker_id': worker_id,
            'status': response.status_code,
            'size': len(response.text),
            'cookies': len(cookies),
            'akamai': has_akamai,
            'elapsed': elapsed,
            'success': response.status_code == 200
        }

        # 간단 출력
        status_icon = "✅" if result['success'] else "❌"
        akamai_icon = "🔑" if has_akamai else "❌"
        print(f"{status_icon} Worker {worker_id:2d}: {result['status']} | {result['size']:4d}B | {result['cookies']}쿠키 {akamai_icon} | {elapsed:.2f}초")

        return result

    except Exception as e:
        error_msg = str(e)[:50]
        print(f"❌ Worker {worker_id:2d}: 에러 - {error_msg}")
        return {
            'worker_id': worker_id,
            'status': 0,
            'error': str(e),
            'success': False
        }

def main():
    print("="*70)
    print("robots.txt 병렬 대량 접근 테스트")
    print("="*70)

    # 테스트 설정
    num_workers = 20  # 병렬 worker 수
    total_requests = 100  # 총 요청 수

    print(f"\n설정:")
    print(f"  - 병렬 Worker: {num_workers}개")
    print(f"  - 총 요청 수: {total_requests}회")
    print(f"  - URL: https://www.coupang.com/robots.txt")
    print()

    input("Enter 키를 눌러 시작... ")
    print()

    # 병렬 실행
    start_time = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(test_robots_access, i+1): i+1 for i in range(total_requests)}

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    total_elapsed = time.time() - start_time

    # 통계
    print("\n" + "="*70)
    print("결과 통계")
    print("="*70)

    success_count = sum(1 for r in results if r.get('success'))
    failed_count = len(results) - success_count

    success_results = [r for r in results if r.get('success')]
    akamai_count = sum(1 for r in success_results if r.get('akamai'))

    avg_elapsed = sum(r.get('elapsed', 0) for r in success_results) / len(success_results) if success_results else 0

    print(f"\n총 요청: {total_requests}회")
    print(f"소요 시간: {total_elapsed:.2f}초")
    print(f"초당 요청: {total_requests/total_elapsed:.2f} req/s")
    print()
    print(f"✅ 성공: {success_count}회 ({success_count/total_requests*100:.1f}%)")
    print(f"❌ 실패: {failed_count}회 ({failed_count/total_requests*100:.1f}%)")
    print()

    if success_results:
        print(f"평균 응답 시간: {avg_elapsed:.2f}초")
        print(f"Akamai 쿠키 발급: {akamai_count}/{success_count}회 ({akamai_count/success_count*100:.1f}%)")

        # 쿠키 수 분포
        cookie_counts = {}
        for r in success_results:
            count = r.get('cookies', 0)
            cookie_counts[count] = cookie_counts.get(count, 0) + 1

        print(f"\n쿠키 수 분포:")
        for count in sorted(cookie_counts.keys()):
            print(f"  {count}개: {cookie_counts[count]}회")

    # 차단 감지
    print("\n" + "="*70)
    print("차단 분석")
    print("="*70)

    if failed_count == 0:
        print("✅ 차단 없음 - 모든 요청 성공!")
    elif failed_count < total_requests * 0.1:
        print(f"⚠️  일부 실패 ({failed_count}회) - 네트워크 문제 가능성")
    elif failed_count < total_requests * 0.5:
        print(f"⚠️  상당수 실패 ({failed_count}회) - 차단 의심!")
    else:
        print(f"❌ 대부분 실패 ({failed_count}회) - 차단 확실!")

    # 실패 원인 분석
    if failed_count > 0:
        print(f"\n실패 상세:")
        failed_results = [r for r in results if not r.get('success')]
        error_types = {}
        for r in failed_results[:10]:  # 처음 10개만
            error = r.get('error', 'Unknown')[:30]
            error_types[error] = error_types.get(error, 0) + 1

        for error, count in error_types.items():
            print(f"  - {error}: {count}회")

    print()

if __name__ == '__main__':
    main()
