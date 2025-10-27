"""
데이터베이스 관리 모듈
TLS 데이터 및 크롤링 결과 저장/조회
"""

import json
from datetime import datetime
import pymysql
from lib.db.config import get_db_config


class DBManager:
    """DB 관리 클래스"""

    def __init__(self):
        """초기화"""
        self.config = get_db_config()

    def get_connection(self):
        """
        DB 연결 생성

        Returns:
            pymysql.Connection: DB 연결 객체
        """
        return pymysql.connect(**self.config)

    def save_tls_fingerprint(self, device_name, browser, os_version,
                            tls_data, http2_data, collected_at=None):
        """
        TLS Fingerprint 저장 (누적 저장 - INSERT만)

        Args:
            device_name: 디바이스 이름
            browser: 브라우저
            os_version: OS 버전
            tls_data: dict - TLS 전체 데이터
            http2_data: dict - HTTP/2 전체 데이터
            collected_at: datetime - 수집 시각 (None이면 현재 시각)

        Returns:
            int: 저장된 레코드 ID
        """

        if collected_at is None:
            collected_at = datetime.now()

        # 빠른 조회용 필드 추출
        ja3_hash = tls_data.get('ja3_hash') or tls_data.get('tls', {}).get('ja3_hash')
        akamai_fingerprint = http2_data.get('akamai_fingerprint')
        peetprint_hash = tls_data.get('peetprint_hash') or tls_data.get('tls', {}).get('peetprint_hash')

        cipher_count = len(tls_data.get('ciphers', [])) if 'ciphers' in tls_data else None
        extension_count = len(tls_data.get('extensions', [])) if 'extensions' in tls_data else None

        connection = self.get_connection()
        cursor = connection.cursor()

        try:
            # INSERT (누적 저장)
            cursor.execute("""
                INSERT INTO tls_fingerprints (
                    device_name, browser, os_version,
                    tls_data, http2_data,
                    ja3_hash, akamai_fingerprint, peetprint_hash,
                    collected_at,
                    cipher_count, extension_count
                ) VALUES (
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, %s
                )
            """, (
                device_name, browser, os_version,
                json.dumps(tls_data, ensure_ascii=False),
                json.dumps(http2_data, ensure_ascii=False),
                ja3_hash, akamai_fingerprint, peetprint_hash,
                collected_at,
                cipher_count, extension_count
            ))

            connection.commit()
            record_id = cursor.lastrowid

            cursor.close()
            connection.close()

            return record_id

        except Exception as e:
            connection.rollback()
            cursor.close()
            connection.close()
            raise e

    def get_tls_fingerprint(self, device_name, browser, os_version):
        """
        TLS Fingerprint 조회

        Args:
            device_name: 디바이스 이름
            browser: 브라우저
            os_version: OS 버전

        Returns:
            dict or None: TLS 데이터
        """

        connection = self.get_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        cursor.execute("""
            SELECT *
            FROM tls_fingerprints
            WHERE device_name = %s
              AND browser = %s
              AND os_version = %s
        """, (device_name, browser, os_version))

        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if result:
            # JSON 문자열을 dict로 변환
            result['tls_data'] = json.loads(result['tls_data'])
            result['http2_data'] = json.loads(result['http2_data'])

        return result

    def save_variance_sample(self, test_session_id, device_name, browser, os_version,
                            sample_number, tls_data, http2_data, collected_at=None):
        """
        TLS 변동성 샘플 저장

        Args:
            test_session_id: 테스트 세션 ID
            device_name: 디바이스 이름
            browser: 브라우저
            os_version: OS 버전
            sample_number: 샘플 번호
            tls_data: dict - TLS 전체 데이터
            http2_data: dict - HTTP/2 전체 데이터
            collected_at: datetime - 수집 시각

        Returns:
            int: 저장된 레코드 ID
        """

        if collected_at is None:
            collected_at = datetime.now()

        # 빠른 조회용 필드 추출
        ja3_hash = tls_data.get('ja3_hash') or tls_data.get('tls', {}).get('ja3_hash')
        akamai_fingerprint = http2_data.get('akamai_fingerprint')

        connection = self.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO tls_variance_samples (
                    test_session_id, device_name, browser, os_version,
                    sample_number,
                    tls_data, http2_data,
                    ja3_hash, akamai_fingerprint,
                    collected_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s,
                    %s, %s,
                    %s, %s,
                    %s
                )
            """, (
                test_session_id, device_name, browser, os_version,
                sample_number,
                json.dumps(tls_data, ensure_ascii=False),
                json.dumps(http2_data, ensure_ascii=False),
                ja3_hash, akamai_fingerprint,
                collected_at
            ))

            connection.commit()
            record_id = cursor.lastrowid

            cursor.close()
            connection.close()

            return record_id

        except Exception as e:
            connection.rollback()
            cursor.close()
            connection.close()
            raise e

    def save_crawl_result(self, session_id, device_config, keyword,
                         pages_start, pages_end, results_summary,
                         duration_seconds, workers=1, errors=None):
        """
        크롤링 결과 저장

        Args:
            session_id: 세션 ID
            device_config: dict - 디바이스 설정
            keyword: 검색 키워드
            pages_start: 시작 페이지
            pages_end: 종료 페이지
            results_summary: dict - 결과 요약
            duration_seconds: 소요 시간 (초)
            workers: Worker 수
            errors: list - 에러 목록

        Returns:
            int: 저장된 레코드 ID
        """

        device_name = device_config.get('device', '')
        browser = device_config.get('browser', '')
        os_version = device_config.get('os_version', '')

        pages_successful = results_summary.get('successful_pages', 0)
        pages_failed = results_summary.get('failed_pages', 0)
        total_ranking = results_summary.get('total_ranking', 0)
        total_ads = results_summary.get('total_ads', 0)

        # 상태 결정
        if pages_successful == (pages_end - pages_start + 1):
            status = 'success'
        elif pages_successful > 0:
            status = 'partial'
        else:
            status = 'failed'

        # 시간 정보
        now = datetime.now()
        hour = now.hour
        day_of_week = now.strftime('%A')  # Monday, Tuesday, ...

        connection = self.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO crawl_results (
                    session_id,
                    device_name, browser, os_version,
                    keyword, pages_start, pages_end, workers,
                    pages_successful, pages_failed,
                    total_ranking, total_ads,
                    status, duration_seconds,
                    hour, day_of_week,
                    full_results, errors
                ) VALUES (
                    %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s
                )
            """, (
                session_id,
                device_name, browser, os_version,
                keyword, pages_start, pages_end, workers,
                pages_successful, pages_failed,
                total_ranking, total_ads,
                status, duration_seconds,
                hour, day_of_week,
                json.dumps(results_summary, ensure_ascii=False),
                json.dumps(errors or [], ensure_ascii=False)
            ))

            connection.commit()
            record_id = cursor.lastrowid

            cursor.close()
            connection.close()

            return record_id

        except Exception as e:
            connection.rollback()
            cursor.close()
            connection.close()
            raise e

    def get_crawl_results(self, limit=10, device_name=None, keyword=None, status=None):
        """
        크롤링 결과 조회

        Args:
            limit: 최대 레코드 수
            device_name: 디바이스 필터 (선택)
            keyword: 키워드 필터 (선택)
            status: 상태 필터 (선택)

        Returns:
            list: 크롤링 결과 목록
        """

        connection = self.get_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # WHERE 조건 생성
        conditions = []
        params = []

        if device_name:
            conditions.append("device_name = %s")
            params.append(device_name)

        if keyword:
            conditions.append("keyword = %s")
            params.append(keyword)

        if status:
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT *
            FROM crawl_results
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """, params + [limit])

        results = cursor.fetchall()

        cursor.close()
        connection.close()

        # JSON 문자열을 dict로 변환
        for result in results:
            if result.get('full_results'):
                result['full_results'] = json.loads(result['full_results'])
            if result.get('errors'):
                result['errors'] = json.loads(result['errors'])

        return results

    def save_device_selection(self, device_name, browser, os_version, category=''):
        """
        디바이스 선택 기록 저장

        Args:
            device_name: 디바이스 이름
            browser: 브라우저
            os_version: OS 버전
            category: 카테고리 (galaxy, iphone, other)

        Returns:
            int: 저장된 레코드 ID
        """

        connection = self.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO device_selections (
                    device_name, browser, os_version, category
                ) VALUES (%s, %s, %s, %s)
            """, (device_name, browser, os_version, category))

            connection.commit()
            record_id = cursor.lastrowid

            cursor.close()
            connection.close()

            return record_id

        except Exception as e:
            connection.rollback()
            cursor.close()
            connection.close()
            raise e

    def get_last_device_selection(self):
        """
        마지막 디바이스 선택 기록 조회

        Returns:
            dict or None: 디바이스 선택 정보
        """

        connection = self.get_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        cursor.execute("""
            SELECT *
            FROM device_selections
            ORDER BY selected_at DESC
            LIMIT 1
        """)

        result = cursor.fetchone()

        cursor.close()
        connection.close()

        return result

    # ==========================================
    # 쿠키 관리
    # ==========================================

    def save_cookie(self, device_name, browser, os_version,
                   cookie_data, cookie_type='original',
                   session_id=None, page_number=None):
        """
        쿠키 저장

        Args:
            device_name: 디바이스 이름
            browser: 브라우저
            os_version: OS 버전
            cookie_data: dict 또는 list - 쿠키 데이터
            cookie_type: 'original' 또는 'updated'
            session_id: 세션 ID (updated 타입만)
            page_number: 페이지 번호 (updated 타입만)

        Returns:
            int: 저장된 레코드 ID
        """
        connection = self.get_connection()
        cursor = connection.cursor()

        # 쿠키 데이터를 JSON으로 변환
        if isinstance(cookie_data, list):
            cookie_json = json.dumps(cookie_data, ensure_ascii=False)
        elif isinstance(cookie_data, dict):
            cookie_json = json.dumps(cookie_data, ensure_ascii=False)
        else:
            raise ValueError("cookie_data must be list or dict")

        cursor.execute("""
            INSERT INTO cookies (
                device_name, browser, os_version,
                cookie_type, cookie_data,
                collected_at, session_id, page_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            device_name, browser, os_version,
            cookie_type, cookie_json,
            datetime.now(), session_id, page_number
        ))

        cookie_id = cursor.lastrowid

        connection.commit()
        cursor.close()
        connection.close()

        return cookie_id

    def get_latest_original_cookie(self, device_name, browser, os_version):
        """
        최신 원본 쿠키 조회

        Args:
            device_name: 디바이스 이름
            browser: 브라우저
            os_version: OS 버전

        Returns:
            dict: 쿠키 레코드 (없으면 None)
        """
        connection = self.get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM cookies
            WHERE device_name = %s
              AND browser = %s
              AND os_version = %s
              AND cookie_type = 'original'
            ORDER BY collected_at DESC
            LIMIT 1
        """, (device_name, browser, os_version))

        result = cursor.fetchone()

        cursor.close()
        connection.close()

        return result

    def get_session_cookies(self, session_id):
        """
        특정 세션의 모든 쿠키 조회 (시간순)

        Args:
            session_id: 세션 ID

        Returns:
            list: 쿠키 레코드 목록
        """
        connection = self.get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM cookies
            WHERE session_id = %s
            ORDER BY page_number, collected_at
        """, (session_id,))

        results = cursor.fetchall()

        cursor.close()
        connection.close()

        return results

    def mark_cookie_as_invalid(self, cookie_id):
        """
        쿠키를 차단됨으로 표시

        Args:
            cookie_id: 쿠키 ID
        """
        connection = self.get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE cookies
            SET is_valid = FALSE,
                updated_at = %s
            WHERE id = %s
        """, (datetime.now(), cookie_id))

        connection.commit()
        cursor.close()
        connection.close()

    def update_cookie_stats(self, cookie_id, success=True):
        """
        쿠키 사용 통계 업데이트

        Args:
            cookie_id: 쿠키 ID
            success: 성공 여부
        """
        connection = self.get_connection()
        cursor = connection.cursor()

        if success:
            cursor.execute("""
                UPDATE cookies
                SET use_count = use_count + 1,
                    success_pages = success_pages + 1,
                    last_used_at = %s,
                    updated_at = %s
                WHERE id = %s
            """, (datetime.now(), datetime.now(), cookie_id))
        else:
            cursor.execute("""
                UPDATE cookies
                SET use_count = use_count + 1,
                    failed_pages = failed_pages + 1,
                    last_used_at = %s,
                    updated_at = %s
                WHERE id = %s
            """, (datetime.now(), datetime.now(), cookie_id))

        connection.commit()
        cursor.close()
        connection.close()

    # ==========================================
    # 상품 정보 관리
    # ==========================================

    def save_product(self, session_id, device_name, browser, os_version,
                    keyword, page_number, product_type, product_data,
                    collected_at=None):
        """
        상품 정보 저장

        Args:
            session_id: 세션 ID
            device_name: 디바이스 이름
            browser: 브라우저
            os_version: OS 버전
            keyword: 검색 키워드
            page_number: 페이지 번호
            product_type: 'ranking' 또는 'ad'
            product_data: dict - 상품 상세 정보
                {
                    'name': 상품명,
                    'price': 가격,
                    'url': 상품 URL,
                    'image_url': 이미지 URL,
                    'rank_position': 랭킹 순위 (ranking 타입만),
                    'ad_slot': 광고 슬롯 (ad 타입만),
                    'ad_type': 광고 타입 (ad 타입만),
                    'ad_position': 광고 내 순서 (ad 타입만)
                }
            collected_at: datetime - 수집 시각

        Returns:
            int: 저장된 레코드 ID
        """
        if collected_at is None:
            collected_at = datetime.now()

        connection = self.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO products (
                    session_id, device_name, browser, os_version,
                    keyword, page_number, product_type,
                    product_name, product_price, product_url, product_image_url,
                    rank_position, ad_slot, ad_type, ad_position,
                    collected_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s
                )
            """, (
                session_id, device_name, browser, os_version,
                keyword, page_number, product_type,
                product_data.get('name'),
                product_data.get('price'),
                product_data.get('url'),
                product_data.get('image_url'),
                product_data.get('rank_position'),
                product_data.get('ad_slot'),
                product_data.get('ad_type'),
                product_data.get('ad_position'),
                collected_at
            ))

            connection.commit()
            product_id = cursor.lastrowid

            cursor.close()
            connection.close()

            return product_id

        except Exception as e:
            connection.rollback()
            cursor.close()
            connection.close()
            raise e

    def save_products_batch(self, session_id, device_name, browser, os_version,
                           keyword, page_number, products_list, collected_at=None):
        """
        여러 상품을 일괄 저장 (성능 최적화)

        Args:
            products_list: list of dicts - 상품 목록
                [
                    {
                        'type': 'ranking' or 'ad',
                        'name': ...,
                        'price': ...,
                        ...
                    },
                    ...
                ]

        Returns:
            int: 저장된 상품 수
        """
        if collected_at is None:
            collected_at = datetime.now()

        connection = self.get_connection()
        cursor = connection.cursor()

        try:
            values = []
            for product in products_list:
                values.append((
                    session_id, device_name, browser, os_version,
                    keyword, page_number, product.get('type', 'ranking'),
                    product.get('name'),
                    product.get('price'),
                    product.get('url'),
                    product.get('image_url'),
                    product.get('rank_position'),
                    product.get('ad_slot'),
                    product.get('ad_type'),
                    product.get('ad_position'),
                    collected_at
                ))

            cursor.executemany("""
                INSERT INTO products (
                    session_id, device_name, browser, os_version,
                    keyword, page_number, product_type,
                    product_name, product_price, product_url, product_image_url,
                    rank_position, ad_slot, ad_type, ad_position,
                    collected_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s
                )
            """, values)

            connection.commit()
            count = cursor.rowcount

            cursor.close()
            connection.close()

            return count

        except Exception as e:
            connection.rollback()
            cursor.close()
            connection.close()
            raise e

    # ==========================================
    # 크롤링 세부 정보 관리
    # ==========================================

    def save_crawl_detail(self, session_id, device_name, browser, os_version,
                         keyword, page_number, status, detail_data, crawled_at=None):
        """
        크롤링 세부 정보 저장

        Args:
            session_id: 세션 ID
            device_name: 디바이스 이름
            browser: 브라우저
            os_version: OS 버전
            keyword: 검색 키워드
            page_number: 페이지 번호
            status: 'success', 'http2_error', 'akamai_challenge', etc.
            detail_data: dict - 세부 정보
                {
                    'worker_id': Worker ID,
                    'error_message': 에러 메시지,
                    'error_type': 에러 타입,
                    'response_size_bytes': 응답 크기,
                    'response_time_ms': 응답 시간,
                    'http_status_code': HTTP 상태 코드,
                    'is_akamai_blocked': Akamai 차단 여부,
                    'akamai_challenge_type': 챌린지 타입,
                    'bm_sc_cookie': Bot Manager 쿠키,
                    'ranking_products_count': 랭킹 상품 수,
                    'ad_products_count': 광고 상품 수,
                    'total_products_count': 전체 상품 수,
                    'cookie_source': 쿠키 출처,
                    'cookie_count': 쿠키 개수,
                    'has_pcid': PCID 존재 여부,
                    'has_sid': sid 존재 여부,
                    'attempt_number': 시도 횟수,
                    'max_attempts': 최대 시도 횟수
                }
            crawled_at: datetime - 크롤링 시각

        Returns:
            int: 저장된 레코드 ID
        """
        if crawled_at is None:
            crawled_at = datetime.now()

        connection = self.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO crawl_details (
                    session_id, device_name, browser, os_version,
                    keyword, page_number, worker_id,
                    status, error_message, error_type,
                    response_size_bytes, response_time_ms, http_status_code,
                    is_akamai_blocked, akamai_challenge_type, bm_sc_cookie,
                    ranking_products_count, ad_products_count, total_products_count,
                    cookie_source, cookie_count, has_pcid, has_sid,
                    attempt_number, max_attempts,
                    crawled_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s
                )
            """, (
                session_id, device_name, browser, os_version,
                keyword, page_number, detail_data.get('worker_id'),
                status, detail_data.get('error_message'), detail_data.get('error_type'),
                detail_data.get('response_size_bytes'), detail_data.get('response_time_ms'),
                detail_data.get('http_status_code'),
                detail_data.get('is_akamai_blocked', False),
                detail_data.get('akamai_challenge_type'),
                detail_data.get('bm_sc_cookie'),
                detail_data.get('ranking_products_count', 0),
                detail_data.get('ad_products_count', 0),
                detail_data.get('total_products_count', 0),
                detail_data.get('cookie_source'),
                detail_data.get('cookie_count', 0),
                detail_data.get('has_pcid', False),
                detail_data.get('has_sid', False),
                detail_data.get('attempt_number', 1),
                detail_data.get('max_attempts', 3),
                crawled_at
            ))

            connection.commit()
            detail_id = cursor.lastrowid

            cursor.close()
            connection.close()

            return detail_id

        except Exception as e:
            connection.rollback()
            cursor.close()
            connection.close()
            raise e
