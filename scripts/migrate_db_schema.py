#!/usr/bin/env python3
"""
DB 스키마 마이그레이션
v2.13 → v2.14: TLS 누적 저장, 디바이스 선택 기록 추가
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from lib.db.config import get_db_config


def migrate():
    """DB 스키마 마이그레이션 실행"""

    config = get_db_config()
    connection = pymysql.connect(**config)
    cursor = connection.cursor()

    print("="*70)
    print("DB 스키마 마이그레이션 v2.13 → v2.14")
    print("="*70)

    try:
        # 1. tls_fingerprints 테이블 수정
        print("\n[1/3] tls_fingerprints 테이블 수정...")

        # UNIQUE KEY 제거 (누적 저장 위해)
        try:
            cursor.execute("ALTER TABLE tls_fingerprints DROP INDEX unique_device")
            print("  ✅ UNIQUE KEY 제거 완료")
        except Exception as e:
            print(f"  ⚠️  UNIQUE KEY 제거 실패 (이미 제거됨?): {e}")

        # test_mode 컬럼 제거
        try:
            cursor.execute("ALTER TABLE tls_fingerprints DROP COLUMN test_mode")
            print("  ✅ test_mode 컬럼 제거 완료")
        except Exception as e:
            print(f"  ⚠️  test_mode 컬럼 제거 실패 (이미 제거됨?): {e}")

        # is_valid 컬럼 제거 (불필요)
        try:
            cursor.execute("ALTER TABLE tls_fingerprints DROP COLUMN is_valid")
            print("  ✅ is_valid 컬럼 제거 완료")
        except Exception as e:
            print(f"  ⚠️  is_valid 컬럼 제거 실패 (이미 제거됨?): {e}")

        # 2. 디바이스 선택 기록 테이블 추가
        print("\n[2/3] device_selections 테이블 생성...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_selections (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,

                -- 디바이스 정보
                device_name VARCHAR(100) NOT NULL COMMENT '디바이스 이름',
                browser VARCHAR(50) NOT NULL COMMENT '브라우저',
                os_version VARCHAR(20) NOT NULL COMMENT 'OS 버전',

                -- 선택 정보
                category VARCHAR(50) COMMENT '카테고리 (Galaxy, iPhone, etc.)',

                -- 메타데이터
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '선택 시각',

                -- 인덱스
                KEY idx_device (device_name, browser, os_version),
                KEY idx_selected (selected_at)

            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='디바이스 선택 기록 (마지막 선택 추적)'
        """)

        print("  ✅ device_selections 테이블 생성 완료")

        # 3. 기존 last_selection.json 데이터 마이그레이션
        print("\n[3/3] 기존 선택 기록 마이그레이션...")

        import json
        last_selection_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'last_selection.json'
        )

        if os.path.exists(last_selection_file):
            with open(last_selection_file, 'r') as f:
                data = json.load(f)

            # 마지막 카테고리와 디바이스 찾기
            last_category = data.get('last_category', '')
            last_device_name = data.get('last_device_by_category', {}).get(last_category, '')

            if last_device_name and last_device_name in data.get('devices', {}):
                device_info = data['devices'][last_device_name]
                browser = device_info.get('browser_key', '')
                os_version = device_info.get('os_version', '')
                category = device_info.get('category', '')

                cursor.execute("""
                    INSERT INTO device_selections (
                        device_name, browser, os_version, category
                    ) VALUES (%s, %s, %s, %s)
                """, (last_device_name, browser, os_version, category))

                print(f"  ✅ 기존 선택 기록 마이그레이션 완료:")
                print(f"     {last_device_name} / {browser} / {os_version}")
            else:
                print("  ⚠️  유효한 선택 기록 없음")
        else:
            print("  ⚠️  기존 선택 기록 없음")

        connection.commit()

        # 테이블 확인
        print("\n" + "="*70)
        print("마이그레이션 완료 - 테이블 목록")
        print("="*70)

        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  • {table_name}: {count} rows")

        print("\n✅ 마이그레이션 성공!")
        return True

    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        connection.rollback()
        return False

    finally:
        cursor.close()
        connection.close()


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
