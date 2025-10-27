"""
Fingerprint 관리 모듈
BrowserStack으로 TLS + 쿠키 수집
"""

import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.collectors.dynamic import DynamicCollector


def collect_fingerprint(device_config, refresh_policy='auto'):
    """
    BrowserStack으로 TLS + 쿠키 수집

    Args:
        device_config: 디바이스 설정
        refresh_policy: 재수집 정책
            - 'auto': 기본값, 24시간 이내면 재사용
            - 'force': 무조건 재수집
            - 'skip': 무조건 기존 데이터 사용 (없으면 수집)

    Returns:
        bool: 성공 여부
    """

    print("\n" + "="*60)
    print("BrowserStack 데이터 수집")
    print("="*60 + "\n")

    # 수집기 생성
    collector = DynamicCollector(device_config, refresh_policy=refresh_policy)

    # 수집 실행 (유효성 검증 포함)
    result = collector.collect()

    if result['success']:
        print("\n✅ 데이터 수집 완료!")
        return True
    else:
        print("\n❌ 데이터 수집 실패!")
        return False
