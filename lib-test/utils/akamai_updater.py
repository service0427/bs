"""
Akamai 쿠키 업데이트 모듈 (테스트용)
원본 cookies.json의 Akamai 관련 쿠키만 업데이트

⚠️ 주의: 이 모듈은 원본 보호 원칙을 위반합니다.
    테스트 목적으로만 사용하며, 문제 발생 시 쉽게 제거 가능하도록 설계되었습니다.

사용 방법:
    from lib.utils.akamai_updater import update_akamai_cookies

    # 응답에서 Akamai 쿠키 추출
    if response.cookies:
        update_akamai_cookies(device_name, browser, response.cookies, worker_id)
"""

import os
import json
import fcntl
import time
import sys
from datetime import datetime

# config 모듈 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.settings import get_device_fingerprint_dir


# Akamai 관련 쿠키 목록
AKAMAI_COOKIE_NAMES = [
    '_abck',      # Akamai Bot Manager (핵심!)
    'bm_sz',      # Session 정보
    'bm_sv',      # Session 검증
    'bm_mi',      # Machine ID
    'bm_s',       # Session 상태
    'bm_ss',      # Session 서명
    'bm_so',      # Session 옵션
    'bm_lso',     # Last Session
    'ak_bmsc',    # Akamai 메타데이터
]


def update_akamai_cookies(device_name, browser, response_cookies, worker_id=None):
    """
    원본 cookies.json의 Akamai 쿠키만 업데이트

    ⚠️ 주의사항:
    - worker_id가 있으면 (패킷 모드) 업데이트하지 않음 (충돌 방지)
    - worker_id가 None이면 (리얼 모드) 업데이트 수행

    Args:
        device_name: 디바이스 이름
        browser: 브라우저 이름 (safari, chrome, chromium 등)
        response_cookies: requests 응답의 cookies 객체
        worker_id: Worker ID (None=리얼 모드, 숫자=패킷 모드)

    Returns:
        dict: {
            'updated': bool,
            'count': int,
            'cookies': list,
            'reason': str
        }
    """

    # 패킷 모드는 업데이트 안 함 (충돌 방지)
    if worker_id is not None:
        return {
            'updated': False,
            'count': 0,
            'cookies': [],
            'reason': f'패킷 모드 (Worker {worker_id}) - 업데이트 생략'
        }

    # 응답에서 Akamai 쿠키 추출
    akamai_updates = {}
    for cookie_name in AKAMAI_COOKIE_NAMES:
        if cookie_name in response_cookies:
            akamai_updates[cookie_name] = response_cookies[cookie_name]

    if not akamai_updates:
        return {
            'updated': False,
            'count': 0,
            'cookies': [],
            'reason': '응답에 Akamai 쿠키 없음'
        }

    # 원본 쿠키 파일 경로 (디바이스 + 브라우저)
    fingerprint_dir = get_device_fingerprint_dir(device_name, browser)
    cookies_file = os.path.join(fingerprint_dir, 'cookies.json')

    if not os.path.exists(cookies_file):
        return {
            'updated': False,
            'count': 0,
            'cookies': [],
            'reason': f'원본 파일 없음: {cookies_file}'
        }

    try:
        # 파일 락 사용 (동시 쓰기 방지)
        with open(cookies_file, 'r+', encoding='utf-8') as f:
            # 배타적 락 획득 (최대 5초 대기)
            timeout = 5
            start_time = time.time()

            while True:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break  # 락 획득 성공
                except IOError:
                    if time.time() - start_time > timeout:
                        return {
                            'updated': False,
                            'count': 0,
                            'cookies': [],
                            'reason': '파일 락 타임아웃 (5초)'
                        }
                    time.sleep(0.1)

            try:
                # 기존 쿠키 읽기
                f.seek(0)
                cookies = json.load(f)

                # Akamai 쿠키 업데이트
                updated_count = 0
                updated_names = []

                for cookie in cookies:
                    if cookie['name'] in akamai_updates:
                        old_value = cookie['value'][:20] + '...' if len(cookie['value']) > 20 else cookie['value']
                        new_value = akamai_updates[cookie['name']]

                        cookie['value'] = new_value
                        updated_count += 1
                        updated_names.append(cookie['name'])

                # 파일 쓰기
                f.seek(0)
                f.truncate()
                json.dump(cookies, f, indent=2, ensure_ascii=False)

                return {
                    'updated': True,
                    'count': updated_count,
                    'cookies': updated_names,
                    'reason': 'Akamai 쿠키 업데이트 완료',
                    'timestamp': datetime.now().isoformat()
                }

            finally:
                # 락 해제
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    except Exception as e:
        return {
            'updated': False,
            'count': 0,
            'cookies': [],
            'reason': f'업데이트 실패: {str(e)}'
        }


def is_enabled():
    """
    Akamai 업데이트 활성화 여부 확인

    환경변수 AKAMAI_UPDATE=1 설정 시 활성화
    기본값: 비활성화 (테스트용이므로 명시적 활성화 필요)

    Returns:
        bool: 활성화 여부
    """
    return os.environ.get('AKAMAI_UPDATE', '0') == '1'


def get_status(device_name, browser):
    """
    현재 Akamai 쿠키 상태 조회

    Args:
        device_name: 디바이스 이름
        browser: 브라우저 이름 (safari, chrome, chromium 등)

    Returns:
        dict: Akamai 쿠키 목록 및 값
    """
    fingerprint_dir = get_device_fingerprint_dir(device_name, browser)
    cookies_file = os.path.join(fingerprint_dir, 'cookies.json')

    if not os.path.exists(cookies_file):
        return {'error': '쿠키 파일 없음'}

    try:
        with open(cookies_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)

        akamai_cookies = {}
        for cookie in cookies:
            if cookie['name'] in AKAMAI_COOKIE_NAMES:
                value = cookie['value']
                preview = value[:20] + '...' if len(value) > 20 else value
                akamai_cookies[cookie['name']] = {
                    'value': value,
                    'preview': preview
                }

        return {
            'found': len(akamai_cookies),
            'cookies': akamai_cookies
        }

    except Exception as e:
        return {'error': str(e)}
