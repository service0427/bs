"""
통합 로그 분석 스크립트
시간대별, 요일별, 디바이스별 패턴 분석
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.logs.unified import UnifiedLogger


def print_time_stats():
    """시간대별 통계 출력"""
    logger = UnifiedLogger()
    stats = logger.get_stats_by_time()
    
    print("\n" + "=" * 80)
    print("⏰ 시간대별 크롤링 성공률")
    print("=" * 80)
    
    # 시간대를 6시간 단위로 그룹화
    time_groups = {
        '00-05시 (심야)': list(range(0, 6)),
        '06-11시 (오전)': list(range(6, 12)),
        '12-17시 (오후)': list(range(12, 18)),
        '18-23시 (저녁)': list(range(18, 24))
    }
    
    for group_name, hours in time_groups.items():
        group_total = sum(stats[h]['total'] for h in hours)
        group_success = sum(stats[h]['success'] for h in hours)
        group_partial = sum(stats[h]['partial'] for h in hours)
        group_failed = sum(stats[h]['failed'] for h in hours)
        
        if group_total == 0:
            continue
        
        success_rate = group_success / group_total * 100
        bar_len = int(success_rate / 2.5)
        bar = "█" * bar_len + "░" * (40 - bar_len)
        
        print(f"\n{group_name}:")
        print(f"  {bar} {success_rate:5.1f}%")
        print(f"  총 {group_total:2}회  (✅ {group_success:2}회  🟡 {group_partial:2}회  ❌ {group_failed:2}회)")
    
    # 시간별 상세
    print("\n" + "-" * 80)
    print("시간별 상세:")
    print("-" * 80)
    
    active_hours = [h for h in range(24) if stats[h]['total'] > 0]
    
    for hour in active_hours:
        data = stats[hour]
        if data['total'] == 0:
            continue
        
        bar_len = int(data['success_rate'] / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        
        print(f"{hour:2}시: {bar} {data['success_rate']:5.1f}% "
              f"(총 {data['total']:2}회, ✅ {data['success']:2}  🟡 {data['partial']:2}  ❌ {data['failed']:2})")


def print_device_stats():
    """디바이스별 통계 출력"""
    logger = UnifiedLogger()
    stats = logger.get_stats_by_device()
    
    print("\n" + "=" * 80)
    print("📱 디바이스+브라우저 조합별 성공률")
    print("=" * 80)
    
    # 성공률 순으로 정렬
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['success_rate'], reverse=True)
    
    for key, data in sorted_stats[:20]:  # 상위 20개만
        browser_display = {
            'samsung': 'Samsung',
            'iphone': 'Safari',
            'chromium': 'Chrome',
            'android': 'Chrome',
            'ipad': 'Safari'
        }.get(data['browser'], data['browser'])
        
        emoji = "🟢" if data['success_rate'] >= 70 else "🟡" if data['success_rate'] >= 50 else "🔴"
        bar_len = int(data['success_rate'] / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        
        print(f"\n{emoji} {data['device']} + {browser_display}")
        print(f"   {bar} {data['success_rate']:5.1f}%")
        print(f"   총 {data['total']:2}회  (✅ {data['success']:2}  🟡 {data['partial']:2}  ❌ {data['failed']:2})  "
              f"평균 {data['avg_pages']:.1f}p")


def print_day_of_week_stats():
    """요일별 통계 출력"""
    logger = UnifiedLogger()
    stats = logger.get_stats_by_day_of_week()
    
    print("\n" + "=" * 80)
    print("📅 요일별 크롤링 성공률")
    print("=" * 80)
    
    days_kr = {
        'Monday': '월요일',
        'Tuesday': '화요일',
        'Wednesday': '수요일',
        'Thursday': '목요일',
        'Friday': '금요일',
        'Saturday': '토요일',
        'Sunday': '일요일'
    }
    
    for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        data = stats[day]
        
        if data['total'] == 0:
            print(f"\n{days_kr[day]:4}: 데이터 없음")
            continue
        
        bar_len = int(data['success_rate'] / 2.5)
        bar = "█" * bar_len + "░" * (40 - bar_len)
        
        print(f"\n{days_kr[day]:4}:")
        print(f"  {bar} {data['success_rate']:5.1f}%")
        print(f"  총 {data['total']:2}회  (✅ {data['success']:2}  🟡 {data['partial']:2}  ❌ {data['failed']:2})")


def print_summary():
    """전체 요약"""
    logger = UnifiedLogger()
    logs = logger.get_all_logs()
    
    total = len(logs)
    success_count = sum(1 for log in logs if log.get('status') == 'success')
    partial_count = sum(1 for log in logs if log.get('status') == 'partial')
    failed_count = sum(1 for log in logs if log.get('status') == 'failed')
    
    print("\n" + "=" * 80)
    print("📊 전체 통계 요약")
    print("=" * 80)
    print(f"\n총 크롤링 시도: {total}회")
    print(f"  ✅ 완전 성공 (2페이지+): {success_count}회 ({success_count/total*100:.1f}%)")
    print(f"  🟡 부분 성공 (1페이지):  {partial_count}회 ({partial_count/total*100:.1f}%)")
    print(f"  ❌ 완전 실패 (0페이지):  {failed_count}회 ({failed_count/total*100:.1f}%)")
    
    # 총 페이지 수
    total_pages = sum(log.get('pages_successful', 0) for log in logs)
    total_ranking = sum(log.get('total_ranking', 0) for log in logs)
    total_ads = sum(log.get('total_ads', 0) for log in logs)
    
    print(f"\n크롤링 성과:")
    print(f"  총 페이지: {total_pages}개")
    print(f"  총 랭킹 상품: {total_ranking}개")
    print(f"  총 광고 상품: {total_ads}개")
    
    # 평균 소요 시간
    avg_duration = sum(log.get('duration_seconds', 0) for log in logs) / total if total > 0 else 0
    print(f"\n평균 소요 시간: {avg_duration:.1f}초")


def main():
    """메인"""
    logger = UnifiedLogger()
    
    # 로그 파일 존재 확인
    if not os.path.exists(logger.log_file):
        print("\n❌ 통합 로그 파일이 없습니다.")
        print(f"   파일: {logger.log_file}")
        print("\n기존 search_history를 마이그레이션하려면:")
        print("   python -c \"from lib.logs.unified import migrate_search_history_to_unified_log; "
              "print(f'✅ {migrate_search_history_to_unified_log()}개 마이그레이션 완료')\"")
        return
    
    # 전체 요약
    print_summary()
    
    # 시간대별 통계
    print_time_stats()
    
    # 디바이스별 통계
    print_device_stats()
    
    # 요일별 통계
    print_day_of_week_stats()
    
    print("\n" + "=" * 80)
    print("✅ 분석 완료")
    print("=" * 80)
    print(f"\n통합 로그 파일: {logger.log_file}")
    print()


if __name__ == '__main__':
    main()
