#!/usr/bin/env python3
"""
검색 히스토리 조회 및 분석 도구

사용 방법:
    # 최근 10개 히스토리 조회
    python view_history.py recent

    # 전체 통계 조회
    python view_history.py stats

    # 특정 키워드 검색 히스토리 조회
    python view_history.py keyword "아이폰"

    # 모든 히스토리 조회
    python view_history.py all

예시:
    python view_history.py recent
    python view_history.py stats
    python view_history.py keyword "갤럭시"
"""

import sys
import os
from datetime import datetime

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.logs.search_history import SearchHistory


def show_recent(limit=10):
    """최근 검색 히스토리 조회"""
    history = SearchHistory()
    histories = history.get_all(limit=limit)

    if not histories:
        print("❌ 검색 히스토리가 없습니다.")
        return

    print(f"\n{'='*80}")
    print(f"최근 검색 히스토리 (최대 {limit}개)")
    print(f"{'='*80}\n")

    for i, h in enumerate(histories, 1):
        timestamp = datetime.fromisoformat(h['timestamp'])
        print(f"[{i}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | 키워드: {h['keyword']}")
        print(f"    디바이스: {h['device']['name']} ({h['device']['browser']})")
        print(f"    페이지: {h['pages']['start']}~{h['pages']['end']} | Worker: {h['workers']}개")
        print(f"    결과: 랭킹 {h['results']['total_ranking']}개, 광고 {h['results']['total_ads']}개")
        print(f"    성공률: {h['results']['successful_pages']}/{h['results']['total_pages']} ({h['results']['successful_pages']/h['results']['total_pages']*100:.1f}%)")
        print(f"    소요 시간: {h['duration_seconds']}초")
        print()

    print(f"{'='*80}\n")


def show_statistics():
    """전체 통계 조회"""
    history = SearchHistory()
    stats = history.get_statistics()

    if stats['total_searches'] == 0:
        print("❌ 검색 히스토리가 없습니다.")
        return

    print(f"\n{'='*80}")
    print(f"전체 검색 통계")
    print(f"{'='*80}\n")

    print(f"총 검색 횟수: {stats['total_searches']}회")
    print(f"총 크롤링 페이지: {stats['total_pages_crawled']}페이지")
    print(f"총 랭킹 상품: {stats['total_ranking_products']}개")
    print(f"총 광고 상품: {stats['total_ads']}개")
    print(f"총 소요 시간: {stats['total_duration_seconds']}초 ({stats['total_duration_seconds']/60:.1f}분)")
    print(f"평균 소요 시간: {stats['average_duration_seconds']}초/검색")

    print(f"\n가장 많이 검색한 키워드 (Top 10):")
    for keyword, count in stats['most_searched_keywords']:
        print(f"  {keyword}: {count}회")

    print(f"\n{'='*80}\n")


def show_by_keyword(keyword):
    """특정 키워드 검색 히스토리 조회"""
    history = SearchHistory()
    histories = history.get_by_keyword(keyword)

    if not histories:
        print(f"❌ '{keyword}' 검색 히스토리가 없습니다.")
        return

    print(f"\n{'='*80}")
    print(f"키워드 '{keyword}' 검색 히스토리 ({len(histories)}개)")
    print(f"{'='*80}\n")

    for i, h in enumerate(histories, 1):
        timestamp = datetime.fromisoformat(h['timestamp'])
        print(f"[{i}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    디바이스: {h['device']['name']} ({h['device']['browser']})")
        print(f"    페이지: {h['pages']['start']}~{h['pages']['end']} | Worker: {h['workers']}개")
        print(f"    결과: 랭킹 {h['results']['total_ranking']}개, 광고 {h['results']['total_ads']}개")
        print(f"    소요 시간: {h['duration_seconds']}초")
        print()

    # 키워드별 통계
    total_ranking = sum(h['results']['total_ranking'] for h in histories)
    total_ads = sum(h['results']['total_ads'] for h in histories)
    total_duration = sum(h['duration_seconds'] for h in histories)

    print(f"[{keyword} 통계]")
    print(f"  총 검색 횟수: {len(histories)}회")
    print(f"  총 랭킹 상품: {total_ranking}개 (평균 {total_ranking/len(histories):.1f}개/검색)")
    print(f"  총 광고 상품: {total_ads}개 (평균 {total_ads/len(histories):.1f}개/검색)")
    print(f"  총 소요 시간: {total_duration:.1f}초 (평균 {total_duration/len(histories):.1f}초/검색)")

    print(f"\n{'='*80}\n")


def show_all():
    """모든 히스토리 조회"""
    history = SearchHistory()
    histories = history.get_all()

    if not histories:
        print("❌ 검색 히스토리가 없습니다.")
        return

    print(f"\n{'='*80}")
    print(f"전체 검색 히스토리 ({len(histories)}개)")
    print(f"{'='*80}\n")

    for i, h in enumerate(histories, 1):
        timestamp = datetime.fromisoformat(h['timestamp'])
        print(f"[{i}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | 키워드: {h['keyword']}")
        print(f"    디바이스: {h['device']['name']} ({h['device']['browser']})")
        print(f"    페이지: {h['pages']['start']}~{h['pages']['end']} | Worker: {h['workers']}개")
        print(f"    결과: 랭킹 {h['results']['total_ranking']}개, 광고 {h['results']['total_ads']}개")
        print(f"    소요 시간: {h['duration_seconds']}초")
        print()

    print(f"{'='*80}\n")


def show_usage():
    """사용 방법 출력"""
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        show_usage()
        return

    command = sys.argv[1]

    if command == 'recent':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_recent(limit)

    elif command == 'stats':
        show_statistics()

    elif command == 'keyword':
        if len(sys.argv) < 3:
            print("❌ 키워드를 입력하세요.")
            print("예시: python view_history.py keyword \"아이폰\"")
            return
        keyword = sys.argv[2]
        show_by_keyword(keyword)

    elif command == 'all':
        show_all()

    elif command == 'help':
        show_usage()

    else:
        print(f"❌ 알 수 없는 명령어: {command}")
        print("사용 가능한 명령어: recent, stats, keyword, all, help")
        show_usage()


if __name__ == "__main__":
    main()
