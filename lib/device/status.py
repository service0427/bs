"""
디바이스 상태 추적 모듈
search_history를 분석하여 잘 되는 디바이스 파악
"""

import os
import json
import glob


def get_device_success_status():
    """
    search_history를 분석하여 디바이스별 성공 상태 반환

    Returns:
        dict: {
            'device_name + browser + os_version': {
                'success': bool,  # 2페이지 이상 성공 여부
                'successful_pages': int,
                'last_tested': str (timestamp)
            }
        }
    """

    # lib/device/ → lib/ → 프로젝트 루트
    history_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'data',
        'search_history'
    )

    if not os.path.exists(history_dir):
        return {}

    # 모든 search_history 파일 가져오기 (최신순 정렬)
    history_files = sorted(
        glob.glob(os.path.join(history_dir, 'search_history_*.json')),
        reverse=True  # 최신 파일이 먼저
    )

    device_status = {}

    for history_file in history_files:
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 디바이스 정보 추출
            device_info = data.get('device', {})
            device_name = device_info.get('name', '')
            browser = device_info.get('browser', '')
            os_version = device_info.get('os_version', '')

            if not device_name:
                continue

            # 디바이스 키 생성 (고유 식별자)
            device_key = f"{device_name}_{browser}_{os_version}"

            # 이미 처리한 디바이스면 스킵 (최신 기록만 사용)
            if device_key in device_status:
                continue

            # 성공 페이지 수 확인
            results = data.get('results', {})
            successful_pages = results.get('successful_pages', 0)
            timestamp = data.get('timestamp', '')

            # 2페이지 이상 성공하면 "잘 되는 디바이스"
            device_status[device_key] = {
                'success': successful_pages >= 2,
                'successful_pages': successful_pages,
                'last_tested': timestamp,
                'device_name': device_name,
                'browser': browser,
                'os_version': os_version
            }

        except Exception as e:
            # 파일 읽기 실패는 무시
            continue

    return device_status


def is_device_successful(device_name, browser, os_version):
    """
    특정 디바이스가 2페이지 이상 성공했는지 확인

    Args:
        device_name: 디바이스 이름
        browser: 브라우저
        os_version: OS 버전

    Returns:
        bool: 2페이지 이상 성공 여부
    """

    device_status = get_device_success_status()
    device_key = f"{device_name}_{browser}_{os_version}"

    status = device_status.get(device_key, {})
    return status.get('success', False)


def get_device_success_info(device_name, browser, os_version):
    """
    특정 디바이스의 상세 성공 정보 반환

    Returns:
        dict or None: {
            'success': bool,
            'successful_pages': int,
            'last_tested': str
        }
    """

    device_status = get_device_success_status()
    device_key = f"{device_name}_{browser}_{os_version}"

    return device_status.get(device_key)


def get_device_model_summary(device_name):
    """
    디바이스 모델의 전체 성공 정보 요약
    (모든 브라우저 + OS 조합 포함)

    Args:
        device_name: 디바이스 이름 (예: "iPhone 15", "Samsung Galaxy S21 Ultra")

    Returns:
        dict: {
            'has_success': bool,           # 하나라도 성공한 브라우저가 있는지
            'successful_browsers': list,   # 성공한 브라우저 목록
            'last_tested': str,            # 가장 최근 테스트 시간
            'summary': str                 # 한줄 요약 (예: "Safari:10p, Chrome:10p")
        }
    """

    device_status = get_device_success_status()

    # 이 디바이스의 모든 테스트 결과 찾기
    device_results = {}
    latest_time = None

    for device_key, info in device_status.items():
        if info['device_name'] == device_name:
            browser = info['browser']
            os_version = info['os_version']
            pages = info['successful_pages']
            timestamp = info['last_tested']

            # 브라우저별로 가장 좋은 결과만 저장
            if browser not in device_results or pages > device_results[browser]['pages']:
                device_results[browser] = {
                    'pages': pages,
                    'os_version': os_version,
                    'success': info['success']
                }

            # 가장 최근 테스트 시간 추적
            if not latest_time or timestamp > latest_time:
                latest_time = timestamp

    # 성공한 브라우저만 필터링
    successful_browsers = []
    for browser, result in device_results.items():
        if result['success']:
            # 브라우저 이름 매핑 (짧게 표시)
            browser_name = {
                'samsung': 'Samsung',
                'iphone': 'Safari',
                'chromium': 'Chrome',
                'android': 'Chrome',
                'ipad': 'Safari'
            }.get(browser, browser.capitalize())

            successful_browsers.append({
                'name': browser_name,
                'pages': result['pages']
            })

    # 요약 문자열 생성
    summary = ""
    if successful_browsers:
        summary = ", ".join([f"{b['name']}:{b['pages']}p" for b in successful_browsers])

    # 날짜 포맷 (YYYY-MM-DD HH:MM)
    date_str = ""
    if latest_time:
        try:
            # ISO 포맷에서 날짜 부분만 추출 (2025-10-25T00:12:00.937987 → 10-25)
            date_str = latest_time[5:10]  # MM-DD
        except:
            date_str = latest_time[:10] if len(latest_time) >= 10 else ""

    return {
        'has_success': len(successful_browsers) > 0,
        'successful_browsers': successful_browsers,
        'last_tested': latest_time,
        'date_str': date_str,
        'summary': summary
    }
