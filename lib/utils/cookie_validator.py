"""
쿠키 유효성 검증 모듈
Akamai 쿠키는 정확히 10분간 유효함
"""

import json
import os
from datetime import datetime, timedelta
from lib.settings import COOKIE_VALID_DURATION, get_device_fingerprint_dir


class CookieValidator:
    """쿠키 유효성 검증"""

    @staticmethod
    def is_cookie_valid(device_name):
        """
        쿠키가 유효한지 확인

        Args:
            device_name: 디바이스 이름 (예: 'Samsung_Galaxy_S20_Chrome_124')

        Returns:
            bool: 유효하면 True, 만료되었거나 없으면 False
        """
        fingerprint_dir = get_device_fingerprint_dir(device_name)
        metadata_file = os.path.join(fingerprint_dir, 'metadata.json')

        # 메타데이터 파일이 없으면 유효하지 않음
        if not os.path.exists(metadata_file):
            return False

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # 수집 시간 파싱
            collected_at = datetime.fromisoformat(metadata.get('collected_at'))

            # 현재 시간
            now = datetime.now()

            # 경과 시간 계산
            elapsed = (now - collected_at).total_seconds()

            # 10분(600초) 이내인지 확인
            is_valid = elapsed < COOKIE_VALID_DURATION

            if is_valid:
                remaining = COOKIE_VALID_DURATION - elapsed
                print(f"[{device_name}] 쿠키 유효 (남은 시간: {int(remaining)}초)")
            else:
                print(f"[{device_name}] 쿠키 만료 (경과 시간: {int(elapsed)}초)")

            return is_valid

        except Exception as e:
            print(f"[{device_name}] 메타데이터 읽기 오류: {e}")
            return False

    @staticmethod
    def get_cookie_age(device_name):
        """
        쿠키의 경과 시간(초) 반환

        Args:
            device_name: 디바이스 이름

        Returns:
            int: 경과 시간(초), 오류 시 None
        """
        fingerprint_dir = get_device_fingerprint_dir(device_name)
        metadata_file = os.path.join(fingerprint_dir, 'metadata.json')

        if not os.path.exists(metadata_file):
            return None

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            collected_at = datetime.fromisoformat(metadata.get('collected_at'))
            now = datetime.now()
            elapsed = (now - collected_at).total_seconds()

            return int(elapsed)

        except Exception as e:
            print(f"[{device_name}] 메타데이터 읽기 오류: {e}")
            return None

    @staticmethod
    def get_remaining_time(device_name):
        """
        쿠키의 남은 유효 시간(초) 반환

        Args:
            device_name: 디바이스 이름

        Returns:
            int: 남은 시간(초), 만료되었거나 오류 시 0
        """
        age = CookieValidator.get_cookie_age(device_name)

        if age is None:
            return 0

        remaining = COOKIE_VALID_DURATION - age
        return max(0, int(remaining))

    @staticmethod
    def load_cookies(device_name):
        """
        디바이스별 쿠키 로드

        Args:
            device_name: 디바이스 이름

        Returns:
            list: 쿠키 리스트 (Selenium 형식)
        """
        fingerprint_dir = get_device_fingerprint_dir(device_name)
        cookie_file = os.path.join(fingerprint_dir, 'cookies.json')

        if not os.path.exists(cookie_file):
            raise FileNotFoundError(f"쿠키 파일 없음: {cookie_file}")

        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)

        return cookies

    @staticmethod
    def load_headers(device_name):
        """
        디바이스별 HTTP 헤더 로드

        Args:
            device_name: 디바이스 이름

        Returns:
            dict: HTTP 헤더
        """
        fingerprint_dir = get_device_fingerprint_dir(device_name)
        headers_file = os.path.join(fingerprint_dir, 'headers.json')

        if not os.path.exists(headers_file):
            raise FileNotFoundError(f"헤더 파일 없음: {headers_file}")

        with open(headers_file, 'r', encoding='utf-8') as f:
            headers = json.load(f)

        return headers

    @staticmethod
    def cookies_to_dict(selenium_cookies):
        """
        Selenium 쿠키 리스트를 딕셔너리로 변환

        Args:
            selenium_cookies: Selenium get_cookies() 결과

        Returns:
            dict: {name: value} 형식의 쿠키
        """
        return {cookie['name']: cookie['value'] for cookie in selenium_cookies}
