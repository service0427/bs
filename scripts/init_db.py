#!/usr/bin/env python3
"""
데이터베이스 초기화 스크립트
테이블 생성 및 초기 설정
"""

import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
from lib.db.config import get_db_config, get_connection_string


def create_tables():
    """테이블 생성"""

    config = get_db_config()

    print("="*70)
    print("BrowserStack TLS Crawler - 데이터베이스 초기화")
    print("="*70)
    print(f"\n연결 정보: {get_connection_string()}\n")

    try:
        # DB 연결
        connection = pymysql.connect(**config)
        cursor = connection.cursor()

        print("✅ 데이터베이스 연결 성공\n")

        # 1. tls_fingerprints 테이블
        print("[1/3] tls_fingerprints 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tls_fingerprints (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,

                -- 디바이스 식별
                device_name VARCHAR(100) NOT NULL COMMENT '디바이스 이름',
                browser VARCHAR(50) NOT NULL COMMENT '브라우저',
                os_version VARCHAR(20) NOT NULL COMMENT 'OS 버전',

                -- TLS 데이터 (JSON 통으로)
                tls_data JSON NOT NULL COMMENT 'TLS 전체 데이터',
                http2_data JSON NOT NULL COMMENT 'HTTP/2 전체 데이터',

                -- 빠른 조회용 인덱스 필드
                ja3_hash VARCHAR(64) COMMENT 'JA3 Hash',
                akamai_fingerprint VARCHAR(100) COMMENT 'Akamai Fingerprint',
                peetprint_hash VARCHAR(64) COMMENT 'Peetprint Hash',

                -- 메타데이터
                collected_at DATETIME NOT NULL COMMENT '수집 시각',
                is_valid BOOLEAN DEFAULT TRUE COMMENT '유효 여부',
                test_mode BOOLEAN DEFAULT FALSE COMMENT '테스트 수집 여부',

                -- 통계
                cipher_count INT COMMENT 'Cipher 개수',
                extension_count INT COMMENT 'Extension 개수',

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                -- 인덱스
                UNIQUE KEY unique_device (device_name, browser, os_version),
                KEY idx_ja3_hash (ja3_hash),
                KEY idx_akamai (akamai_fingerprint),
                KEY idx_collected (collected_at),
                KEY idx_valid (is_valid)

            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='TLS Fingerprint 데이터 (디바이스당 1개)'
        """)
        print("✅ tls_fingerprints 테이블 생성 완료")

        # 2. tls_variance_samples 테이블
        print("\n[2/3] tls_variance_samples 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tls_variance_samples (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,

                -- 테스트 세션 식별
                test_session_id VARCHAR(50) NOT NULL COMMENT '테스트 세션 ID',
                device_name VARCHAR(100) NOT NULL COMMENT '디바이스 이름',
                browser VARCHAR(50) NOT NULL COMMENT '브라우저',
                os_version VARCHAR(20) NOT NULL COMMENT 'OS 버전',

                -- 샘플 정보
                sample_number INT NOT NULL COMMENT '샘플 번호',

                -- TLS 데이터 (JSON 통으로)
                tls_data JSON NOT NULL COMMENT 'TLS 전체 데이터',
                http2_data JSON NOT NULL COMMENT 'HTTP/2 전체 데이터',

                -- 빠른 조회용
                ja3_hash VARCHAR(64) COMMENT 'JA3 Hash',
                akamai_fingerprint VARCHAR(100) COMMENT 'Akamai Fingerprint',

                collected_at DATETIME NOT NULL COMMENT '수집 시각',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- 인덱스
                KEY idx_test_session (test_session_id),
                KEY idx_device (device_name, browser, os_version),
                KEY idx_sample (sample_number)

            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='TLS 변동성 테스트 샘플'
        """)
        print("✅ tls_variance_samples 테이블 생성 완료")

        # 3. crawl_results 테이블
        print("\n[3/3] crawl_results 테이블 생성 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_results (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,

                -- 세션 정보
                session_id VARCHAR(50) NOT NULL COMMENT '크롤링 세션 ID',

                -- 디바이스 정보
                device_name VARCHAR(100) NOT NULL COMMENT '디바이스 이름',
                browser VARCHAR(50) NOT NULL COMMENT '브라우저',
                os_version VARCHAR(20) NOT NULL COMMENT 'OS 버전',

                -- 크롤링 설정
                keyword VARCHAR(200) NOT NULL COMMENT '검색 키워드',
                pages_start INT NOT NULL COMMENT '시작 페이지',
                pages_end INT NOT NULL COMMENT '종료 페이지',
                workers INT DEFAULT 1 COMMENT 'Worker 수',

                -- 결과
                pages_successful INT DEFAULT 0 COMMENT '성공 페이지 수',
                pages_failed INT DEFAULT 0 COMMENT '실패 페이지 수',
                total_ranking INT DEFAULT 0 COMMENT '전체 랭킹 상품 수',
                total_ads INT DEFAULT 0 COMMENT '전체 광고 수',

                -- 상태
                status ENUM('success', 'partial', 'failed') DEFAULT 'success' COMMENT '크롤링 상태',

                -- 통계
                duration_seconds FLOAT COMMENT '소요 시간 (초)',

                -- 시간 정보 (통계용)
                hour TINYINT COMMENT '시간 (0-23)',
                day_of_week VARCHAR(10) COMMENT '요일',

                -- 전체 결과 (JSON)
                full_results JSON COMMENT '전체 상세 결과',
                errors JSON COMMENT '에러 목록',

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- 인덱스
                KEY idx_session (session_id),
                KEY idx_device (device_name, browser, os_version),
                KEY idx_keyword (keyword),
                KEY idx_status (status),
                KEY idx_hour (hour),
                KEY idx_created (created_at)

            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='크롤링 결과 (search_history → DB)'
        """)
        print("✅ crawl_results 테이블 생성 완료")

        # 테이블 목록 확인
        print("\n" + "="*70)
        print("생성된 테이블 목록")
        print("="*70)

        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        for table in tables:
            table_name = table[0]

            # 레코드 수 확인
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]

            print(f"  • {table_name}: {count} rows")

        # 테이블 상세 정보
        print("\n" + "="*70)
        print("테이블 상세 정보")
        print("="*70)

        for table_name in ['tls_fingerprints', 'tls_variance_samples', 'crawl_results']:
            cursor.execute(f"""
                SELECT
                    TABLE_NAME,
                    ENGINE,
                    TABLE_ROWS,
                    DATA_LENGTH,
                    INDEX_LENGTH,
                    TABLE_COMMENT
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = '{config['database']}'
                AND TABLE_NAME = '{table_name}'
            """)

            info = cursor.fetchone()
            if info:
                print(f"\n[{info[0]}]")
                print(f"  Engine: {info[1]}")
                print(f"  Rows: {info[2]}")
                print(f"  Data Size: {info[3]:,} bytes")
                print(f"  Index Size: {info[4]:,} bytes")
                print(f"  Comment: {info[5]}")

        connection.commit()
        cursor.close()
        connection.close()

        print("\n" + "="*70)
        print("✅ 데이터베이스 초기화 완료!")
        print("="*70)

        return True

    except Exception as e:
        print(f"\n❌ 데이터베이스 초기화 실패!")
        print(f"\n에러: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = create_tables()
    sys.exit(0 if success else 1)
