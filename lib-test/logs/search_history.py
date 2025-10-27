"""
검색 히스토리 저장 모듈
크롤링 검색 기록을 저장하여 나중에 분석 가능
"""

import os
import json
from datetime import datetime


class SearchHistory:
    """검색 히스토리 관리"""

    def __init__(self):
        """히스토리 디렉토리 초기화"""
        # lib/logs/ → lib/ → 프로젝트 루트
        self.history_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data',
            'search_history'
        )
        os.makedirs(self.history_dir, exist_ok=True)

    def save(self, keyword, device_config, start_page, end_page, num_workers,
             all_results, duration_seconds, refresh_policy='auto'):
        """
        검색 히스토리 저장

        Args:
            keyword: 검색 키워드
            device_config: 디바이스 설정 dict
            start_page: 시작 페이지
            end_page: 종료 페이지
            num_workers: Worker 수
            all_results: 크롤링 결과 리스트
            duration_seconds: 전체 소요 시간(초)
            refresh_policy: 재수집 정책
        """
        # 타임스탬프 생성
        now = datetime.now()
        timestamp = now.isoformat()

        # 파일명: search_history_YYYYMMDD_HHMMSS.json
        filename = f"search_history_{now.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.history_dir, filename)

        # 결과 집계
        successful_pages = [r for r in all_results if r.get('success')]
        total_ranking = sum(len(r.get('ranking', [])) for r in successful_pages)
        total_ads = sum(len(r.get('ads', [])) for r in successful_pages)

        # 페이지별 상세 결과
        details = []
        for result in all_results:
            page = result.get('page')
            cookies_status = result.get('cookies', {'PCID': False, 'sid': False})

            if result.get('success'):
                details.append({
                    'page': page,
                    'success': True,
                    'ranking': len(result.get('ranking', [])),
                    'ads': len(result.get('ads', [])),
                    'cookies': cookies_status
                })
            else:
                details.append({
                    'page': page,
                    'success': False,
                    'error': result.get('error', 'unknown'),
                    'cookies': cookies_status
                })

        # 히스토리 데이터 구성
        history_data = {
            'timestamp': timestamp,
            'keyword': keyword,
            'device': {
                'name': device_config.get('device'),
                'os': device_config.get('os'),
                'os_version': device_config.get('os_version'),
                'browser': device_config.get('browser'),
                'real_mobile': device_config.get('real_mobile', True)
            },
            'pages': {
                'start': start_page,
                'end': end_page,
                'total': end_page - start_page + 1
            },
            'workers': num_workers,
            'results': {
                'total_pages': len(all_results),
                'successful_pages': len(successful_pages),
                'failed_pages': len(all_results) - len(successful_pages),
                'total_ranking': total_ranking,
                'total_ads': total_ads,
                'details': details
            },
            'duration_seconds': round(duration_seconds, 2),
            'refresh_policy': refresh_policy
        }

        # JSON 파일로 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 검색 히스토리 저장: {filename}")
        return filepath

    def get_all(self, limit=None):
        """
        모든 히스토리 조회 (최신순)

        Args:
            limit: 최대 개수 (None이면 전체)

        Returns:
            list: 히스토리 데이터 리스트
        """
        history_files = []

        # 모든 히스토리 파일 찾기
        for filename in os.listdir(self.history_dir):
            if filename.startswith('search_history_') and filename.endswith('.json'):
                filepath = os.path.join(self.history_dir, filename)
                history_files.append((filename, filepath))

        # 파일명 기준 최신순 정렬 (파일명에 타임스탬프 포함)
        history_files.sort(reverse=True)

        # limit 적용
        if limit:
            history_files = history_files[:limit]

        # 데이터 로드
        histories = []
        for filename, filepath in history_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['filename'] = filename
                    histories.append(data)
            except Exception as e:
                print(f"⚠️  히스토리 로드 실패: {filename} - {e}")

        return histories

    def get_by_keyword(self, keyword):
        """
        특정 키워드 검색 히스토리 조회

        Args:
            keyword: 검색 키워드

        Returns:
            list: 히스토리 데이터 리스트
        """
        all_histories = self.get_all()
        return [h for h in all_histories if h.get('keyword') == keyword]

    def get_statistics(self):
        """
        전체 통계 조회

        Returns:
            dict: 통계 데이터
        """
        all_histories = self.get_all()

        if not all_histories:
            return {
                'total_searches': 0,
                'total_pages_crawled': 0,
                'total_ranking_products': 0,
                'total_ads': 0
            }

        total_searches = len(all_histories)
        total_pages = sum(h['results']['successful_pages'] for h in all_histories)
        total_ranking = sum(h['results']['total_ranking'] for h in all_histories)
        total_ads = sum(h['results']['total_ads'] for h in all_histories)
        total_duration = sum(h['duration_seconds'] for h in all_histories)

        # 가장 많이 검색한 키워드
        keyword_counts = {}
        for h in all_histories:
            keyword = h['keyword']
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

        most_searched = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            'total_searches': total_searches,
            'total_pages_crawled': total_pages,
            'total_ranking_products': total_ranking,
            'total_ads': total_ads,
            'total_duration_seconds': round(total_duration, 2),
            'average_duration_seconds': round(total_duration / total_searches, 2) if total_searches > 0 else 0,
            'most_searched_keywords': most_searched[:10]  # 상위 10개
        }
