"""
통합 로그 모듈
모든 크롤링 시도를 하나의 파일에 기록하여 장기 패턴 분석
"""

import os
import json
from datetime import datetime


class UnifiedLogger:
    """통합 로그 관리"""
    
    def __init__(self, log_file=None):
        """
        Args:
            log_file: 로그 파일 경로 (기본: data/unified_crawl_log.jsonl)
        """
        if log_file is None:
            # lib/logs/ → lib/ → 프로젝트 루트
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            log_file = os.path.join(base_dir, 'data', 'unified_crawl_log.jsonl')
        
        self.log_file = log_file
        
        # 디렉토리 생성
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    def log_crawl_attempt(self, 
                          device_config,
                          keyword,
                          pages_start,
                          pages_end,
                          results,
                          duration_seconds,
                          workers=1,
                          session_id=None,
                          errors=None):
        """
        크롤링 시도 기록
        
        Args:
            device_config: 디바이스 설정 dict
            keyword: 검색 키워드
            pages_start: 시작 페이지
            pages_end: 종료 페이지
            results: 크롤링 결과 dict
            duration_seconds: 소요 시간
            workers: Worker 수
            session_id: 세션 ID
            errors: 에러 목록
        """
        now = datetime.now()
        
        # 상태 판단
        pages_successful = results.get('successful_pages', 0)
        pages_requested = pages_end - pages_start + 1
        
        if pages_successful == 0:
            status = 'failed'
        elif pages_successful < 2:
            status = 'partial'
        elif pages_successful >= pages_requested:
            status = 'success'
        else:
            status = 'partial'
        
        # 로그 엔트리
        log_entry = {
            'timestamp': now.isoformat(),
            'session_id': session_id or now.strftime('%Y%m%d_%H%M%S'),
            'device': device_config.get('device', 'Unknown'),
            'browser': device_config.get('browser', 'Unknown'),
            'browser_version': device_config.get('browser_version'),
            'os': device_config.get('os', 'Unknown'),
            'os_version': device_config.get('os_version', 'Unknown'),
            'real_mobile': device_config.get('real_mobile', True),
            'keyword': keyword,
            'pages_start': pages_start,
            'pages_end': pages_end,
            'pages_requested': pages_requested,
            'pages_successful': pages_successful,
            'pages_failed': results.get('failed_pages', 0),
            'total_ranking': results.get('total_ranking', 0),
            'total_ads': results.get('total_ads', 0),
            'workers': workers,
            'duration_seconds': round(duration_seconds, 2),
            'status': status,
            'hour': now.hour,
            'day_of_week': now.strftime('%A'),
            'date': now.strftime('%Y-%m-%d'),
            'errors': errors or []
        }
        
        # JSON Lines 형식으로 추가 (한 줄에 하나의 JSON)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def get_all_logs(self):
        """
        모든 로그 읽기
        
        Returns:
            list: 로그 엔트리 리스트
        """
        if not os.path.exists(self.log_file):
            return []
        
        logs = []
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        logs.append(json.loads(line))
                    except:
                        continue
        
        return logs
    
    def get_stats_by_time(self):
        """
        시간대별 통계
        
        Returns:
            dict: 시간대별 성공/실패 통계
        """
        logs = self.get_all_logs()
        
        stats = {}
        for hour in range(24):
            stats[hour] = {
                'total': 0,
                'success': 0,
                'partial': 0,
                'failed': 0,
                'success_rate': 0.0
            }
        
        for log in logs:
            hour = log.get('hour', 0)
            status = log.get('status', 'failed')
            
            stats[hour]['total'] += 1
            
            if status == 'success':
                stats[hour]['success'] += 1
            elif status == 'partial':
                stats[hour]['partial'] += 1
            else:
                stats[hour]['failed'] += 1
        
        # 성공률 계산
        for hour, data in stats.items():
            if data['total'] > 0:
                data['success_rate'] = data['success'] / data['total'] * 100
        
        return stats
    
    def get_stats_by_device(self):
        """
        디바이스별 통계
        
        Returns:
            dict: 디바이스별 성공/실패 통계
        """
        logs = self.get_all_logs()
        
        stats = {}
        
        for log in logs:
            device = log.get('device', 'Unknown')
            browser = log.get('browser', 'Unknown')
            key = f"{device}_{browser}"
            
            if key not in stats:
                stats[key] = {
                    'device': device,
                    'browser': browser,
                    'total': 0,
                    'success': 0,
                    'partial': 0,
                    'failed': 0,
                    'success_rate': 0.0,
                    'avg_pages': 0.0,
                    'total_pages': 0
                }
            
            status = log.get('status', 'failed')
            pages_successful = log.get('pages_successful', 0)
            
            stats[key]['total'] += 1
            stats[key]['total_pages'] += pages_successful
            
            if status == 'success':
                stats[key]['success'] += 1
            elif status == 'partial':
                stats[key]['partial'] += 1
            else:
                stats[key]['failed'] += 1
        
        # 성공률 및 평균 페이지 계산
        for key, data in stats.items():
            if data['total'] > 0:
                data['success_rate'] = data['success'] / data['total'] * 100
                data['avg_pages'] = data['total_pages'] / data['total']
        
        return stats
    
    def get_stats_by_day_of_week(self):
        """
        요일별 통계
        
        Returns:
            dict: 요일별 성공/실패 통계
        """
        logs = self.get_all_logs()
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        stats = {}
        
        for day in days:
            stats[day] = {
                'total': 0,
                'success': 0,
                'partial': 0,
                'failed': 0,
                'success_rate': 0.0
            }
        
        for log in logs:
            day = log.get('day_of_week', 'Monday')
            status = log.get('status', 'failed')
            
            if day not in stats:
                continue
            
            stats[day]['total'] += 1
            
            if status == 'success':
                stats[day]['success'] += 1
            elif status == 'partial':
                stats[day]['partial'] += 1
            else:
                stats[day]['failed'] += 1
        
        # 성공률 계산
        for day, data in stats.items():
            if data['total'] > 0:
                data['success_rate'] = data['success'] / data['total'] * 100
        
        return stats


def migrate_search_history_to_unified_log():
    """
    기존 search_history를 unified_log로 마이그레이션
    """
    import glob

    # lib/logs/ → lib/ → 프로젝트 루트
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    history_dir = os.path.join(base_dir, 'data', 'search_history')
    
    if not os.path.exists(history_dir):
        return 0
    
    logger = UnifiedLogger()
    
    history_files = sorted(glob.glob(os.path.join(history_dir, '*.json')))
    migrated_count = 0
    
    for file_path in history_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            device_config = data.get('device', {})
            keyword = data.get('keyword', 'Unknown')
            pages_info = data.get('pages', {})
            results = data.get('results', {})
            duration = data.get('duration_seconds', 0)
            workers = data.get('workers', 1)
            
            # 타임스탬프에서 session_id 추출
            timestamp = data.get('timestamp', '')
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                session_id = dt.strftime('%Y%m%d_%H%M%S')
            else:
                session_id = None
            
            logger.log_crawl_attempt(
                device_config=device_config,
                keyword=keyword,
                pages_start=pages_info.get('start', 1),
                pages_end=pages_info.get('end', 10),
                results=results,
                duration_seconds=duration,
                workers=workers,
                session_id=session_id
            )
            
            migrated_count += 1
            
        except Exception as e:
            continue
    
    return migrated_count
