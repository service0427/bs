"""
BrowserStack TLS Crawler - 메인 워크플로우
디바이스 선택 → TLS/쿠키 수집 → 커스텀 TLS 크롤링
"""

import sys
import os
import json
import argparse
import time
from datetime import datetime

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 모듈 import
from lib.logs.logger import TeeLogger
from lib.device.selector import select_device
from lib.crawler.custom_tls import CustomTLSCrawler
from lib.logs.search_history import SearchHistory
from lib.device.crawl_config import get_crawl_config
from lib.device.fingerprint_manager import collect_fingerprint
from lib.logs.unified import UnifiedLogger
from lib.settings import get_device_fingerprint_dir


def main(keyword=None, start_page=1, end_page=1, num_workers=None, device_select=True, refresh_policy='auto', clear_checkpoint=False, device_config=None):
    """
    메인 워크플로우

    Args:
        keyword: 검색 키워드 (None이면 인터랙티브하게 물어봄)
        start_page: 시작 페이지 번호
        end_page: 종료 페이지 번호
        num_workers: 병렬 worker 수 (None이면 인터랙티브하게 물어봄)
        device_select: 디바이스 선택 인터페이스 표시 여부
        refresh_policy: 재수집 정책 ('auto', 'force', 'skip')
        clear_checkpoint: 체크포인트 초기화 여부
        device_config: 디바이스 설정 (직접 지정 시, select_device 건너뜀)
    """

    # 시작 시간 기록
    import time
    workflow_start_time = time.time()

    # 로그 파일 설정
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    now = datetime.now()
    log_filename = f"crawl_{now.strftime('%Y%m%d_%H%M%S')}.log"
    log_filepath = os.path.join(logs_dir, log_filename)

    # stdout을 TeeLogger로 교체 (콘솔 + 파일 동시 출력)
    tee_logger = TeeLogger(log_filepath)
    original_stdout = sys.stdout
    sys.stdout = tee_logger

    try:
        print(f"📝 로그 파일: {log_filepath}\n")

        print("\n" + "="*70)
        print(" "*15 + "BrowserStack TLS Crawler")
        print(" "*10 + "Full Workflow: Select → Collect → Crawl")
        print("="*70)

        # STEP 1: 디바이스 선택
        if device_config:
            # CLI 인자로 디바이스가 지정된 경우
            print(f"\n📱 지정된 디바이스 사용:")
            print(f"   디바이스: {device_config['device']}")
            print(f"   브라우저: {device_config['browser']}")
            print(f"   OS 버전: {device_config['os_version']}")
            print(f"   모드: Real Device\n")
        elif device_select:
            # 인터랙티브 디바이스 선택
            device_config = select_device()
            if not device_config:
                return False
        else:
            # 이 경우는 발생하지 않아야 함
            print("\n⚠️ 디바이스 정보가 제공되지 않았습니다.")
            print("디바이스 선택을 진행합니다.\n")
            device_config = select_device()
            if not device_config:
                return False

        # STEP 2: TLS + 쿠키 수집 (유효성 검증 포함)
        if not collect_fingerprint(device_config, refresh_policy=refresh_policy):
            return False

        # STEP 3: 크롤링 설정 (인터랙티브)
        crawl_config = get_crawl_config(keyword, num_workers)
        keyword = crawl_config['keyword']
        num_workers = crawl_config['num_workers']

        # 체크포인트 초기화 (요청 시)
        if clear_checkpoint:
            from lib.logs.checkpoint import Checkpoint
            device_name = device_config['device']
            browser = device_config['browser']
            checkpoint_temp = Checkpoint(keyword, device_name, browser, start_page, end_page)
            checkpoint_temp.clear()

        # STEP 4: curl-cffi 커스텀 TLS 다중 페이지 크롤링
        device_name = device_config['device']
        browser = device_config['browser']

        if num_workers == 1:
            # 단일 worker 모드 (체크포인트 활성화)
            crawler = CustomTLSCrawler(device_name, browser, device_config=device_config)
            result = crawler.crawl_pages(
                keyword=keyword,
                start_page=start_page,
                end_page=end_page,
                use_checkpoint=True  # 체크포인트 활성화
            )

            # 결과 처리
            if isinstance(result, dict):
                all_results = result.get('results', [])
            else:
                # 레거시 list 형식
                all_results = result
        else:
            # 병렬 worker 모드
            print(f"\n병렬 크롤링: {num_workers}개 Worker 사용")
            print("="*70)

            from concurrent.futures import ThreadPoolExecutor, as_completed

            all_results = []

            def worker_task(worker_id):
                """각 worker의 크롤링 작업"""
                # Worker 시작 딜레이 (쿠키 충돌 방지)
                # Worker 1: 0초, Worker 2: 3초, Worker 3: 6초...
                import time
                delay = (worker_id - 1) * 3
                if delay > 0:
                    print(f"\n[Worker {worker_id}] {delay}초 대기 (쿠키 충돌 방지)...")
                    time.sleep(delay)

                crawler = CustomTLSCrawler(device_name, browser, device_config=device_config, worker_id=worker_id)
                result = crawler.crawl_pages(
                    keyword=keyword,
                    start_page=start_page,
                    end_page=end_page,
                    use_checkpoint=False  # Worker 모드에서는 체크포인트 비활성화
                )

                # dict 형식 반환값 처리
                if isinstance(result, dict):
                    return result.get('results', [])
                return result  # 레거시 list 형식

            # 병렬 실행
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {executor.submit(worker_task, i+1): i+1 for i in range(num_workers)}

                for future in as_completed(futures):
                    worker_id = futures[future]
                    try:
                        results = future.result()
                        all_results.extend(results)
                        print(f"\n✅ Worker {worker_id} 완료")
                    except Exception as e:
                        print(f"\n❌ Worker {worker_id} 실패: {e}")

            print(f"\n모든 Worker 완료 (총 {len(all_results)}개 결과)")
            print("="*70)

        # 최종 완료
        successful_pages = [r for r in all_results if r.get('success')]
        total_ranking = sum(len(r.get('ranking', [])) for r in successful_pages)
        total_ads = sum(len(r.get('ads', [])) for r in successful_pages)

        print("\n" + "="*70)
        print("✅ 전체 워크플로우 완료!")
        print("="*70)
        print("\n[완료된 작업]")
        print("  1. ✓ 디바이스 선택")
        print("  2. ✓ BrowserStack 실기기에서 TLS + 쿠키 수집")
        print("  3. ✓ curl-cffi JA3 TLS Fingerprint로 쿠팡 검색 크롤링")
        # 브라우저명 표시용 매핑
        browser_display = {
            'samsung': 'Samsung Browser',
            'android': 'Chrome',
            'iphone': 'Safari',
            'chromium': 'Chrome'
        }.get(device_config['browser'], device_config['browser'])

        print("\n[크롤링 결과]")
        print(f"  - 디바이스: {device_name}")
        print(f"  - 브라우저: {browser_display} ({device_config['browser']})")
        print(f"  - OS 버전: {device_config['os']} {device_config.get('os_version', 'N/A')}")
        print(f"  - 검색 키워드: {keyword}")
        print(f"  - Worker 수: {num_workers}개 {'(병렬)' if num_workers > 1 else '(단일)'}")
        print(f"  - 크롤링 페이지: {start_page} ~ {end_page} ({len(successful_pages)}/{(end_page - start_page + 1) * num_workers}개 성공)")
        print(f"  - 총 랭킹 상품: {total_ranking}개")
        print(f"  - 총 광고 상품: {total_ads}개")
        print(f"\n[페이지별 상세]")
        for result in all_results:
            page = result.get('page')
            if result.get('success'):
                ranking = len(result.get('ranking', []))
                ads = len(result.get('ads', []))
                print(f"  페이지 {page}: 랭킹 {ranking}개, 광고 {ads}개")
            else:
                error = result.get('error', 'unknown')
                print(f"  페이지 {page}: 실패 ({error})")

        # 정확한 저장 경로 표시
        from lib.settings import get_device_fingerprint_dir, get_tls_dir
        fingerprint_path = get_device_fingerprint_dir(
            device_config['device'],
            device_config['browser'],
            device_config.get('os_version')
        )
        tls_path = get_tls_dir(
            device_config['device'],
            device_config['browser'],
            device_config.get('os_version')
        )

        print(f"\n[저장 위치]")
        print(f"  - Fingerprint: {fingerprint_path}/")
        print(f"  - TLS: {tls_path}/")

        # TLS 및 쿠키 정보 표시
        fingerprint_dir = get_device_fingerprint_dir(
            device_config['device'],
            device_config['browser'],
            device_config.get('os_version')
        )
        metadata_file = os.path.join(fingerprint_dir, 'metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # TLS Fingerprint 정보
            tls_info = metadata.get('tls_info', {}).get('tls', {})
            ja3_hash = tls_info.get('ja3_hash', 'N/A')
            cipher_count = len(tls_info.get('ciphers', []))

            print(f"\n[TLS Fingerprint]")
            print(f"  - JA3 Hash: {ja3_hash}")
            print(f"  - Cipher Suites: {cipher_count}개")
            print(f"  - 경로: {tls_path}/tls_fingerprint.json")

            # 쿠키 경과 시간
            collected_at_str = metadata.get('collected_at')
            if collected_at_str:
                collected_at = datetime.fromisoformat(collected_at_str)
                elapsed = (datetime.now() - collected_at).total_seconds()
                print(f"\n{'='*60}")
                print(f"🕐 쿠키 경과 시간 (크롤링 완료 시점)")
                print(f"{'='*60}")
                print(f"  수집 시각: {collected_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  현재 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                print(f"  경과 시간: {int(elapsed)}초 ({hours}시간 {minutes}분 {seconds}초)")

                # 쿠키 유효성 표시
                COOKIE_EXPIRY = 86400  # 24시간
                if elapsed > COOKIE_EXPIRY:
                    print(f"  상태: ⚠️  만료 (>{int(COOKIE_EXPIRY/3600)}시간) - 다음 실행 시 재수집됨")
                else:
                    remaining = int(COOKIE_EXPIRY - elapsed)
                    rem_hours = int(remaining // 3600)
                    rem_minutes = int((remaining % 3600) // 60)
                    rem_seconds = int(remaining % 60)
                    print(f"  상태: ✅ 유효 (남은 시간: {rem_hours}시간 {rem_minutes}분 {rem_seconds}초)")
                print(f"{'='*60}")

        print("="*70 + "\n")

        # 검색 히스토리 저장
        workflow_duration = time.time() - workflow_start_time
        history = SearchHistory()
        try:
            history.save(
                keyword=keyword,
                device_config=device_config,
                start_page=start_page,
                end_page=end_page,
                num_workers=num_workers,
                all_results=all_results,
                duration_seconds=workflow_duration,
                refresh_policy=refresh_policy
            )
        except Exception as e:
            print(f"⚠️  히스토리 저장 실패: {e}")

        # 통합 로그 기록
        try:
            unified_logger = UnifiedLogger()

            # 결과 요약
            results_summary = {
                'total_pages': len(all_results),
                'successful_pages': len(successful_pages),
                'failed_pages': len(all_results) - len(successful_pages),
                'total_ranking': total_ranking,
                'total_ads': total_ads
            }

            # 에러 수집 (실패한 페이지만)
            errors = []
            for result in all_results:
                if not result.get('success'):
                    errors.append({
                        'page': result.get('page'),
                        'error': result.get('error', 'unknown')
                    })

            unified_logger.log_crawl_attempt(
                device_config=device_config,
                keyword=keyword,
                pages_start=start_page,
                pages_end=end_page,
                results=results_summary,
                duration_seconds=workflow_duration,
                workers=num_workers,
                session_id=now.strftime('%Y%m%d_%H%M%S'),
                errors=errors
            )
        except Exception as e:
            print(f"⚠️  통합 로그 기록 실패: {e}")

        # DB에 크롤링 결과 저장
        try:
            from lib.db.manager import DBManager
            db = DBManager()

            record_id = db.save_crawl_result(
                session_id=now.strftime('%Y%m%d_%H%M%S'),
                device_config=device_config,
                keyword=keyword,
                pages_start=start_page,
                pages_end=end_page,
                results_summary=results_summary,
                duration_seconds=workflow_duration,
                workers=num_workers,
                errors=errors
            )

            print(f"✅ 크롤링 결과 DB 저장 완료 (ID: {record_id})")

        except Exception as e:
            print(f"⚠️  DB 저장 실패 (파일 저장은 성공): {e}")

        # 로그 파일 정리
        success = len(successful_pages) > 0

        print("\n" + "="*70)
        print(f"📝 전체 로그가 저장되었습니다:")
        print(f"   {log_filepath}")
        print("="*70)

        return success

    finally:
        # stdout 복구 및 로그 파일 닫기
        sys.stdout = original_stdout
        tee_logger.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='BrowserStack TLS Crawler - 전체 워크플로우',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 기본 실행 (인터랙티브 모드: 검색어와 Worker 수를 물어봄)
  python main.py

  # 키워드만 지정 (Worker 수는 물어봄)
  python main.py --keyword "갤럭시 s24"

  # 키워드 + Worker 수 지정 (인터랙티브 없이 바로 실행)
  python main.py --keyword "아이폰" --workers 3

  # 다중 페이지 크롤링 (1~3페이지)
  python main.py --keyword "맥북" --start 1 --end 3

  # 다중 페이지 + 병렬 (1~5페이지를 2개 worker로)
  python main.py --keyword "아이폰" --start 1 --end 5 --workers 2

  # 쿠키/TLS 무조건 재수집 (300초 미만이어도 재수집)
  python main.py --keyword "아이폰" --force-refresh

  # 쿠키/TLS 재수집 안 함 (300초 초과되어도 기존 데이터 사용)
  python main.py --keyword "아이폰" --skip-refresh
        """
    )

    parser.add_argument(
        '--keyword', '-k',
        type=str,
        default=None,
        help='검색 키워드 (미지정 시 인터랙티브하게 물어봄, Enter = 랜덤)'
    )

    parser.add_argument(
        '--start', '-s',
        type=int,
        default=None,
        help='시작 페이지 번호'
    )

    parser.add_argument(
        '--end', '-e',
        type=int,
        default=None,
        help='종료 페이지 번호'
    )

    parser.add_argument(
        '--page', '-p',
        type=int,
        default=None,
        help='단일 페이지 번호 (--start, --end와 함께 사용 불가)'
    )

    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=None,
        help='병렬 worker 수 (미지정 시 인터랙티브하게 물어봄, 1-20, 각 worker는 독립적인 쿠키 사용)'
    )

    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='쿠키/TLS 무조건 재수집 (300초 유효 시간 무시)'
    )

    parser.add_argument(
        '--skip-refresh',
        action='store_true',
        help='쿠키/TLS 재수집 안 함 (기존 데이터 사용, 300초 초과되어도 사용)'
    )

    parser.add_argument(
        '--clear-checkpoint',
        action='store_true',
        help='체크포인트 초기화 후 시작 (처음부터 크롤링)'
    )

    # 디바이스 지정 옵션 (로테이션용)
    parser.add_argument(
        '--device-name',
        type=str,
        default=None,
        help='디바이스 이름 (예: "Samsung Galaxy S21 Plus")'
    )

    parser.add_argument(
        '--browser',
        type=str,
        default=None,
        help='브라우저 (예: "samsung", "android", "iphone")'
    )

    parser.add_argument(
        '--os-version',
        type=str,
        default=None,
        help='OS 버전 (예: "11.0", "16")'
    )

    args = parser.parse_args()

    # 재수집 정책 결정
    if args.force_refresh and args.skip_refresh:
        print("❌ --force-refresh와 --skip-refresh는 동시에 사용할 수 없습니다.")
        sys.exit(1)

    if args.force_refresh:
        refresh_policy = 'force'
        print("🔄 재수집 모드: 무조건 재수집")
    elif args.skip_refresh:
        refresh_policy = 'skip'
        print("⏭️  재수집 모드: 기존 데이터 사용 (재수집 안 함)")
    else:
        refresh_policy = 'auto'

    # 페이지 범위 결정
    if args.page is not None:
        # 단일 페이지 모드
        start_page = args.page
        end_page = args.page
    elif args.start is not None or args.end is not None:
        # 범위 모드
        start_page = args.start if args.start is not None else 1
        end_page = args.end if args.end is not None else start_page
    else:
        # 기본값: 1페이지
        start_page = 1
        end_page = 1

    # 유효성 검증
    if start_page < 1:
        print("❌ 시작 페이지는 1 이상이어야 합니다.")
        sys.exit(1)

    if end_page < start_page:
        print("❌ 종료 페이지는 시작 페이지보다 크거나 같아야 합니다.")
        sys.exit(1)

    # Worker 수 검증 (CLI로 지정한 경우만)
    if args.workers is not None:
        if args.workers < 1:
            print("❌ Worker 수는 1 이상이어야 합니다.")
            sys.exit(1)

        if args.workers > 20:
            print("⚠️  Worker 수가 20개를 초과합니다. 서버 부하에 주의하세요.")
            confirm = input("계속하시겠습니까? (y/n): ").strip().lower()
            if confirm not in ['y', 'yes', 'ㅛ']:
                print("취소되었습니다.")
                sys.exit(0)

    # 디바이스 지정 옵션 처리
    device_config = None
    device_select = True

    if args.device_name and args.browser and args.os_version:
        # 모든 디바이스 정보가 제공된 경우 자동 선택 모드
        # 브라우저 타입에서 OS 유추
        if args.browser in ['iphone', 'chromium'] or 'iPhone' in args.device_name:
            os_type = 'ios'
        else:
            os_type = 'android'

        device_config = {
            'os': os_type,
            'device': args.device_name,
            'browser': args.browser,
            'os_version': args.os_version,
            'real_mobile': True  # 항상 리얼 디바이스 사용
        }
        device_select = False
        print(f"📱 디바이스 자동 선택: {args.device_name} ({args.browser} {args.os_version})")
    elif args.device_name or args.browser or args.os_version:
        # 일부만 제공된 경우 에러
        print("❌ --device-name, --browser, --os-version은 모두 함께 지정해야 합니다.")
        sys.exit(1)

    try:
        success = main(
            keyword=args.keyword,
            start_page=start_page,
            end_page=end_page,
            num_workers=args.workers,
            device_select=device_select,
            refresh_policy=refresh_policy,
            clear_checkpoint=args.clear_checkpoint,
            device_config=device_config
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        error_msg = str(e)
        # curl 에러 간결화
        if 'curl:' in error_msg:
            import re
            match = re.search(r'curl: \((\d+)\)', error_msg)
            if match:
                error_code = match.group(1)
                if error_code == '92':
                    print(f"\n❌ HTTP/2 연결 에러 (curl 92) - 서버에서 연결 종료")
                else:
                    print(f"\n❌ curl 에러 ({error_code})")
            else:
                print(f"\n❌ {error_msg[:100]}")
        else:
            print(f"\n❌ 오류: {error_msg[:100]}")
        sys.exit(1)
