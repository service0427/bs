#!/usr/bin/env python3
"""
광고 로테이션 검증 스크립트 (임시)

목적:
- Session 유지 시 광고 로테이션 정상 작동 확인
- 1페이지 → 2페이지 → 1페이지 크롤링
- 랭킹 상품 일치, 광고 위치 일치, 광고 내용 로테이션 확인

사용법:
    python test_ad_rotation.py --keyword "방석"
    python test_ad_rotation.py --keyword "쿠션" --device-name "Samsung Galaxy S22"
"""

import argparse
import json
import os
import sys
import time
import random
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TeeLogger:
    """콘솔과 파일에 동시 출력하는 로거"""

    def __init__(self, log_file):
        self.terminal = sys.stdout
        self.log = open(log_file, 'w', encoding='utf-8')
        self.log_file = log_file

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()  # 즉시 파일에 쓰기

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        if self.log:
            self.log.close()

from lib.crawler.custom_tls import CustomTLSCrawler
from lib.utils.ad_position_analyzer import AdPositionAnalyzer
from lib.device.selector import select_device
from lib.settings import ensure_directories, get_device_fingerprint_dir


def save_html(html_content, filename, output_dir='data/test_html'):
    """HTML 저장"""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"  💾 HTML 저장: {filepath}")
    return filepath


def print_session_info(crawler, label="Session 정보"):
    """Session 쿠키 정보 출력"""
    print(f"\n{'='*80}")
    print(f"{label}")
    print(f"{'='*80}")

    if hasattr(crawler.session, 'cookies'):
        cookies = crawler.session.cookies

        # PCID 확인
        if 'PCID' in cookies:
            pcid = str(cookies.get('PCID', ''))
            print(f"  ✓ PCID: {pcid[:40]}... (Session 유지)")
        else:
            print(f"  ❌ PCID 없음")

        # sid 확인
        if 'sid' in cookies:
            sid = str(cookies.get('sid', ''))
            print(f"  ✓ sid: {sid[:40]}...")
        else:
            print(f"  ⚠️ sid 없음")

        print(f"  ✓ 총 쿠키: {len(cookies)}개")
    else:
        print(f"  ❌ Session 쿠키 없음")

    print(f"{'='*80}\n")


def test_ad_rotation(keyword, device_name=None, browser=None, os_version=None):
    """
    광고 로테이션 테스트

    Args:
        keyword: 검색 키워드
        device_name: 디바이스 이름 (None이면 인터랙티브 선택)
        browser: 브라우저 (None이면 인터랙티브 선택)
        os_version: OS 버전 (None이면 인터랙티브 선택)
    """
    print("\n" + "="*80)
    print("광고 로테이션 검증 테스트")
    print("="*80)
    print(f"검색 키워드: {keyword}")
    print(f"테스트 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 디바이스 선택
    if device_name and browser:
        print(f"\n[디바이스] {device_name} / {browser}")
        device_config = {
            'device': device_name,
            'browser': browser,
            'os_version': os_version  # 명령행에서 전달받음
        }
    else:
        print("\n[디바이스 선택]")
        device_config = select_device()
        device_name = device_config['device']
        browser = device_config['browser']

    # Crawler 생성 (단일 Session 사용)
    print(f"\n[Crawler 생성]")
    print(f"  ✓ Session 객체 생성 (TLS 연결 재사용)")
    crawler = CustomTLSCrawler(device_name, browser, device_config=device_config)

    # 타임스탬프
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ===================================================================
    # 1. 첫 번째 페이지 방문
    # ===================================================================
    print(f"\n{'='*80}")
    print(f"[1] 페이지 1 - 첫 방문")
    print(f"{'='*80}")

    result_page1_v1 = crawler.crawl_page(keyword=keyword, page=1)

    if not result_page1_v1.get('success'):
        print(f"❌ 1페이지 크롤링 실패")
        return

    # HTML 저장
    html_page1_v1 = result_page1_v1.get('html', '')
    save_html(html_page1_v1, f'{timestamp}_page1_visit1.html')

    # 분석
    analysis_page1_v1 = AdPositionAnalyzer.analyze_html(html_page1_v1)

    print(f"\n[결과]")
    print(f"  랭킹 상품: {analysis_page1_v1['ranking_count']}개")
    print(f"  광고: {analysis_page1_v1['ad_count']}개")
    print(f"  광고 위치: {analysis_page1_v1['ad_positions'][:10]}..." if len(analysis_page1_v1['ad_positions']) > 10 else f"  광고 위치: {analysis_page1_v1['ad_positions']}")

    # Session 정보
    print_session_info(crawler, "[Session 정보 - 1페이지 후]")

    # 페이지 이동 딜레이 (사람처럼 행동)
    delay = random.uniform(1.5, 3.0)
    print(f"\n⏳ 다음 페이지 대기 중... ({delay:.1f}초)")
    time.sleep(delay)

    # ===================================================================
    # 2. 두 번째 페이지 방문 (Session 유지)
    # ===================================================================
    print(f"\n{'='*80}")
    print(f"[2] 페이지 2 방문 (Session 유지)")
    print(f"{'='*80}")

    result_page2 = crawler.crawl_page(keyword=keyword, page=2)

    if not result_page2.get('success'):
        print(f"❌ 2페이지 크롤링 실패")
        return

    # HTML 저장
    html_page2 = result_page2.get('html', '')
    save_html(html_page2, f'{timestamp}_page2.html')

    # 분석
    analysis_page2 = AdPositionAnalyzer.analyze_html(html_page2)

    print(f"\n[결과]")
    print(f"  랭킹 상품: {analysis_page2['ranking_count']}개")
    print(f"  광고: {analysis_page2['ad_count']}개")

    # Session 정보
    print_session_info(crawler, "[Session 정보 - 2페이지 후]")

    # 페이지 이동 딜레이 (사람처럼 행동)
    delay = random.uniform(1.5, 3.0)
    print(f"\n⏳ 페이지 1 재방문 대기 중... ({delay:.1f}초)")
    time.sleep(delay)

    # ===================================================================
    # 3. 첫 번째 페이지 재방문 (Session 유지)
    # ===================================================================
    print(f"\n{'='*80}")
    print(f"[3] 페이지 1 - 재방문 (Session 유지)")
    print(f"{'='*80}")

    result_page1_v2 = crawler.crawl_page(keyword=keyword, page=1)

    if not result_page1_v2.get('success'):
        print(f"❌ 1페이지 재방문 크롤링 실패")
        return

    # HTML 저장
    html_page1_v2 = result_page1_v2.get('html', '')
    save_html(html_page1_v2, f'{timestamp}_page1_visit2.html')

    # 분석
    analysis_page1_v2 = AdPositionAnalyzer.analyze_html(html_page1_v2)

    print(f"\n[결과]")
    print(f"  랭킹 상품: {analysis_page1_v2['ranking_count']}개")
    print(f"  광고: {analysis_page1_v2['ad_count']}개")
    print(f"  광고 위치: {analysis_page1_v2['ad_positions'][:10]}..." if len(analysis_page1_v2['ad_positions']) > 10 else f"  광고 위치: {analysis_page1_v2['ad_positions']}")

    # Session 정보
    print_session_info(crawler, "[Session 정보 - 1페이지 재방문 후]")

    # ===================================================================
    # 4. 비교 분석
    # ===================================================================
    print(f"\n{'='*80}")
    print(f"[4] 비교 분석: 1페이지 첫 방문 vs 재방문")
    print(f"{'='*80}")

    comparison = AdPositionAnalyzer.compare_results(
        analysis_page1_v1,
        analysis_page1_v2,
        label1="첫 방문",
        label2="재방문"
    )

    AdPositionAnalyzer.print_comparison(comparison, label1="첫 방문", label2="재방문")

    # ===================================================================
    # 5. 결과 저장
    # ===================================================================
    result_data = {
        'timestamp': timestamp,
        'keyword': keyword,
        'device': device_name,
        'browser': browser,
        'page1_visit1': {
            'ranking_count': analysis_page1_v1['ranking_count'],
            'ad_count': analysis_page1_v1['ad_count'],
            'ad_positions': analysis_page1_v1['ad_positions']
        },
        'page2': {
            'ranking_count': analysis_page2['ranking_count'],
            'ad_count': analysis_page2['ad_count']
        },
        'page1_visit2': {
            'ranking_count': analysis_page1_v2['ranking_count'],
            'ad_count': analysis_page1_v2['ad_count'],
            'ad_positions': analysis_page1_v2['ad_positions']
        },
        'comparison': comparison
    }

    result_file = f'data/test_html/{timestamp}_result.json'
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    print(f"\n💾 결과 저장: {result_file}")

    print(f"\n{'='*80}")
    print(f"테스트 완료!")
    print(f"{'='*80}\n")


def main():
    # 로그 디렉토리 생성
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    # 로그 파일 설정
    now = datetime.now()
    log_filename = f"test_ad_rotation_{now.strftime('%Y%m%d_%H%M%S')}.log"
    log_filepath = os.path.join(logs_dir, log_filename)

    # stdout을 TeeLogger로 교체 (콘솔 + 파일 동시 출력)
    tee_logger = TeeLogger(log_filepath)
    original_stdout = sys.stdout
    sys.stdout = tee_logger

    try:
        print(f"📝 로그 파일: {log_filepath}\n")

        parser = argparse.ArgumentParser(description='광고 로테이션 검증 테스트')
        parser.add_argument('--keyword', type=str, default='방석', help='검색 키워드 (기본값: 방석)')
        parser.add_argument('--device-name', type=str, help='디바이스 이름 (예: Samsung Galaxy S22)')
        parser.add_argument('--browser', type=str, help='브라우저 (예: samsung, android, iphone)')
        parser.add_argument('--os-version', type=str, help='OS 버전 (예: 12_0, 10_0)')

        args = parser.parse_args()

        # 디렉토리 생성
        ensure_directories()
        os.makedirs('data/test_html', exist_ok=True)

        # 테스트 실행
        test_ad_rotation(
            keyword=args.keyword,
            device_name=args.device_name,
            browser=args.browser,
            os_version=args.os_version
        )

        print(f"\n{'='*80}")
        print(f"📝 전체 로그가 저장되었습니다:")
        print(f"   {log_filepath}")
        print(f"{'='*80}\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  사용자 중단 (Ctrl+C)")
    except Exception as e:
        print(f"\n\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # stdout 복원
        sys.stdout = original_stdout
        tee_logger.close()


if __name__ == '__main__':
    main()
