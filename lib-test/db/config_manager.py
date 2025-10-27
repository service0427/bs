#!/usr/bin/env python3
"""
Config Manager - DB 기반 설정 관리 시스템
Runtime에 코드 수정 없이 설정 변경 가능
"""
from typing import Any, Optional, Dict
from datetime import datetime
from .manager import DBManager


class ConfigManager:
    """
    설정 관리자 - DB 기반 key-value 저장소

    Usage:
        config = ConfigManager()

        # 값 가져오기
        cookie_expiry = config.get('cookie_expiry', default=86400)

        # 값 설정
        config.set('cookie_expiry', 43200, description='12시간으로 변경')

        # 카테고리별 조회
        crawler_configs = config.get_by_category('crawler')
    """

    def __init__(self):
        self.db = DBManager()
        self._cache = {}  # 메모리 캐시 (빠른 조회)
        self._cache_time = None
        self._ensure_table()
        self._load_defaults()

    def _ensure_table(self):
        """config 테이블 생성 (없을 경우)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                config_key VARCHAR(100) NOT NULL UNIQUE,
                config_value TEXT NOT NULL,
                value_type ENUM('int', 'float', 'string', 'bool') NOT NULL DEFAULT 'string',
                category VARCHAR(50) NOT NULL DEFAULT 'general',
                description TEXT,
                default_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_category (category),
                INDEX idx_key (config_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        conn.commit()
        cursor.close()
        conn.close()

    def _load_defaults(self):
        """기본 설정값 로드 (테이블이 비어있으면 초기화)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # 테이블에 데이터가 있는지 확인
        cursor.execute("SELECT COUNT(*) FROM config")
        count = cursor.fetchone()[0]

        if count == 0:
            # 기본 설정값들 삽입
            defaults = [
                # 쿠키 관련
                ('cookie_expiry', '86400', 'int', 'cookie', '쿠키 유효 시간 (초)', '86400'),

                # 크롤러 재시도 설정
                ('crawler_max_retries', '3', 'int', 'crawler', 'HTTP2 에러 시 최대 재시도 횟수', '3'),
                ('crawler_retry_delay', '3', 'int', 'crawler', '재시도 대기 시간 (초)', '3'),

                # 수집기 설정
                ('collector_max_retries', '3', 'int', 'collector', 'BrowserStack 연결 재시도 횟수', '3'),
                ('collector_retry_delay', '3', 'int', 'collector', '수집기 재시도 대기 시간 (초)', '3'),

                # 타임아웃 설정
                ('worker_timeout', '5', 'int', 'network', 'Worker 입력 타임아웃 (초)', '5'),
                ('akamai_timeout', '5', 'int', 'network', 'Akamai 업데이트 타임아웃 (초)', '5'),
                ('browserstack_wait_timeout', '5', 'int', 'network', 'BrowserStack 대기 타임아웃 (초)', '5'),

                # BrowserStack 설정
                ('browserstack_implicit_wait', '10', 'int', 'browserstack', 'Implicit wait 시간 (초)', '10'),
                ('browserstack_page_load_timeout', '30', 'int', 'browserstack', 'Page load timeout (초)', '30'),

                # 병렬 처리 설정
                ('max_workers', '20', 'int', 'parallel', '최대 병렬 Worker 수', '20'),
                ('worker_start_delay', '3', 'int', 'parallel', 'Worker 시작 간격 (초)', '3'),

                # 크롤링 딜레이
                ('page_delay_min', '2', 'int', 'crawler', '페이지 간 최소 딜레이 (초)', '2'),
                ('page_delay_max', '5', 'int', 'crawler', '페이지 간 최대 딜레이 (초)', '5'),

                # TLS 설정
                ('tls_collection_timeout', '120', 'int', 'tls', 'TLS 수집 타임아웃 (초)', '120'),

                # 디버그 설정
                ('debug_mode', 'false', 'bool', 'debug', '디버그 모드 활성화', 'false'),
                ('verbose_logging', 'false', 'bool', 'debug', '상세 로깅 활성화', 'false'),
            ]

            cursor.executemany("""
                INSERT INTO config (config_key, config_value, value_type, category, description, default_value)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, defaults)

            conn.commit()
            print(f"✅ 기본 설정 {len(defaults)}개 초기화 완료")

        cursor.close()
        conn.close()

        # 캐시 로드
        self._refresh_cache()

    def _refresh_cache(self):
        """캐시 갱신"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT config_key, config_value, value_type FROM config")
        rows = cursor.fetchall()

        self._cache = {}
        for key, value, value_type in rows:
            self._cache[key] = self._cast_value(value, value_type)

        self._cache_time = datetime.now()

        cursor.close()
        conn.close()

    def _cast_value(self, value: str, value_type: str) -> Any:
        """문자열을 적절한 타입으로 변환"""
        if value_type == 'int':
            return int(value)
        elif value_type == 'float':
            return float(value)
        elif value_type == 'bool':
            return value.lower() in ('true', '1', 'yes', 'on')
        else:  # string
            return value

    def get(self, key: str, default: Any = None) -> Any:
        """
        설정값 가져오기

        Args:
            key: 설정 키
            default: 기본값 (키가 없을 경우)

        Returns:
            설정값 (타입 변환됨)
        """
        # 캐시가 오래되었으면 갱신 (1분마다)
        if self._cache_time is None or \
           (datetime.now() - self._cache_time).seconds > 60:
            self._refresh_cache()

        return self._cache.get(key, default)

    def set(self, key: str, value: Any, description: Optional[str] = None) -> bool:
        """
        설정값 설정

        Args:
            key: 설정 키
            value: 설정값
            description: 설명 (선택)

        Returns:
            성공 여부
        """
        # 타입 추론
        if isinstance(value, bool):
            value_type = 'bool'
            value_str = str(value).lower()
        elif isinstance(value, int):
            value_type = 'int'
            value_str = str(value)
        elif isinstance(value, float):
            value_type = 'float'
            value_str = str(value)
        else:
            value_type = 'string'
            value_str = str(value)

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            # Upsert (INSERT ... ON DUPLICATE KEY UPDATE)
            if description:
                cursor.execute("""
                    INSERT INTO config (config_key, config_value, value_type, description)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        config_value = VALUES(config_value),
                        value_type = VALUES(value_type),
                        description = VALUES(description),
                        updated_at = CURRENT_TIMESTAMP
                """, (key, value_str, value_type, description))
            else:
                cursor.execute("""
                    INSERT INTO config (config_key, config_value, value_type)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        config_value = VALUES(config_value),
                        value_type = VALUES(value_type),
                        updated_at = CURRENT_TIMESTAMP
                """, (key, value_str, value_type))

            conn.commit()

            # 캐시 업데이트
            self._cache[key] = value

            return True
        except Exception as e:
            print(f"❌ 설정 저장 실패: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def get_by_category(self, category: str) -> Dict[str, Any]:
        """
        카테고리별 설정 조회

        Args:
            category: 카테고리명 (crawler, collector, network, etc.)

        Returns:
            {key: value} 딕셔너리
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT config_key, config_value, value_type
            FROM config
            WHERE category = %s
        """, (category,))

        rows = cursor.fetchall()
        result = {}

        for key, value, value_type in rows:
            result[key] = self._cast_value(value, value_type)

        cursor.close()
        conn.close()

        return result

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        전체 설정 조회 (카테고리별 그룹화)

        Returns:
            {category: {key: value, ...}, ...}
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT category, config_key, config_value, value_type, description
            FROM config
            ORDER BY category, config_key
        """)

        rows = cursor.fetchall()
        result = {}

        for category, key, value, value_type, description in rows:
            if category not in result:
                result[category] = {}

            result[category][key] = {
                'value': self._cast_value(value, value_type),
                'type': value_type,
                'description': description
            }

        cursor.close()
        conn.close()

        return result

    def reset_to_default(self, key: str) -> bool:
        """설정을 기본값으로 리셋"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE config
                SET config_value = default_value,
                    updated_at = CURRENT_TIMESTAMP
                WHERE config_key = %s
            """, (key,))

            conn.commit()
            self._refresh_cache()
            return True
        except Exception as e:
            print(f"❌ 리셋 실패: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()


# 싱글톤 인스턴스
_config_instance = None

def get_config() -> ConfigManager:
    """ConfigManager 싱글톤 인스턴스 반환"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
