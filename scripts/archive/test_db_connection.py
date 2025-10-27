#!/usr/bin/env python3
"""
MySQL 데이터베이스 연결 테스트
"""

import sys
import os

try:
    import pymysql
    print("✓ pymysql 라이브러리 사용")
except ImportError:
    try:
        import mysql.connector as mysql
        print("✓ mysql-connector-python 라이브러리 사용")
        pymysql = None
    except ImportError:
        print("❌ MySQL 라이브러리가 설치되지 않았습니다.")
        print("\n설치 방법:")
        print("  pip install pymysql")
        print("또는")
        print("  pip install mysql-connector-python")
        sys.exit(1)


def test_connection():
    """MySQL 연결 테스트"""

    # 연결 정보
    config = {
        'host': 'localhost',
        'database': 'tls',
        'user': 'root',
        'password': 'Tech1324!@'
    }

    print("\n" + "="*70)
    print("MySQL 데이터베이스 연결 테스트")
    print("="*70)
    print(f"\n연결 정보:")
    print(f"  Host: {config['host']}")
    print(f"  Database: {config['database']}")
    print(f"  User: {config['user']}")
    print(f"  Password: {'*' * len(config['password'])}")
    print()

    try:
        # pymysql 사용
        if pymysql:
            print("연결 시도 중 (pymysql + unix_socket)...")
            connection = pymysql.connect(
                host=config['host'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                unix_socket='/var/lib/mysql/mysql.sock'  # localhost 연결 시 socket 사용
            )
        else:
            # mysql-connector-python 사용
            print("연결 시도 중 (mysql-connector-python)...")
            import mysql.connector
            connection = mysql.connector.connect(
                host=config['host'],
                user=config['user'],
                password=config['password'],
                database=config['database']
            )

        print("✅ 데이터베이스 연결 성공!\n")

        # 커서 생성
        cursor = connection.cursor()

        # 1. MySQL 버전 확인
        print("="*70)
        print("MySQL 서버 정보")
        print("="*70)
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        if pymysql:
            print(f"MySQL 버전: {version['VERSION()']}")
        else:
            print(f"MySQL 버전: {version[0]}")

        # 2. 현재 데이터베이스 확인
        cursor.execute("SELECT DATABASE()")
        db = cursor.fetchone()
        if pymysql:
            print(f"현재 데이터베이스: {db['DATABASE()']}")
        else:
            print(f"현재 데이터베이스: {db[0]}")

        # 3. 테이블 목록 확인
        print("\n" + "="*70)
        print("테이블 목록")
        print("="*70)
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        if tables:
            print(f"\n총 {len(tables)}개 테이블:")
            for i, table in enumerate(tables, 1):
                if pymysql:
                    table_name = list(table.values())[0]
                else:
                    table_name = table[0]
                print(f"  {i}. {table_name}")
        else:
            print("\n⚠️  테이블이 없습니다 (빈 데이터베이스)")

        # 4. 데이터베이스 문자셋 확인
        print("\n" + "="*70)
        print("문자셋 정보")
        print("="*70)
        cursor.execute("""
            SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
            FROM information_schema.SCHEMATA
            WHERE SCHEMA_NAME = %s
        """, (config['database'],))
        charset_info = cursor.fetchone()
        if charset_info:
            if pymysql:
                print(f"Character Set: {charset_info['DEFAULT_CHARACTER_SET_NAME']}")
                print(f"Collation: {charset_info['DEFAULT_COLLATION_NAME']}")
            else:
                print(f"Character Set: {charset_info[0]}")
                print(f"Collation: {charset_info[1]}")

        # 5. 사용자 권한 확인
        print("\n" + "="*70)
        print("사용자 권한")
        print("="*70)
        cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
        grants = cursor.fetchall()
        print(f"\n{config['user']}@{config['host']} 권한:")
        for grant in grants:
            if pymysql:
                grant_str = list(grant.values())[0]
            else:
                grant_str = grant[0]
            print(f"  • {grant_str}")

        # 연결 종료
        cursor.close()
        connection.close()

        print("\n" + "="*70)
        print("✅ 테스트 완료 - 연결 정상")
        print("="*70)

        return True

    except Exception as e:
        print(f"\n❌ 데이터베이스 연결 실패!")
        print(f"\n에러 메시지:")
        print(f"  {type(e).__name__}: {e}")

        print(f"\n해결 방법:")
        print(f"  1. MySQL 서버가 실행 중인지 확인:")
        print(f"     systemctl status mysqld")
        print(f"  2. 데이터베이스 '{config['database']}'가 존재하는지 확인:")
        print(f"     mysql -u root -p -e 'SHOW DATABASES;'")
        print(f"  3. 사용자 권한 확인:")
        print(f"     mysql -u root -p -e \"SHOW GRANTS FOR '{config['user']}'@'{config['host']}';\"")
        print(f"  4. 비밀번호가 정확한지 확인")

        return False


def create_database_if_not_exists():
    """데이터베이스가 없으면 생성"""

    config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'Tech1324!@'
    }

    try:
        if pymysql:
            connection = pymysql.connect(
                host=config['host'],
                user=config['user'],
                password=config['password'],
                charset='utf8mb4',
                unix_socket='/var/lib/mysql/mysql.sock'
            )
        else:
            import mysql.connector
            connection = mysql.connector.connect(
                host=config['host'],
                user=config['user'],
                password=config['password'],
                unix_socket='/var/lib/mysql/mysql.sock'
            )

        cursor = connection.cursor()

        print("\n데이터베이스 'tls' 생성 시도...")
        cursor.execute("""
            CREATE DATABASE IF NOT EXISTS tls
            CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        """)

        print("✅ 데이터베이스 'tls' 생성 완료 (또는 이미 존재)")

        cursor.close()
        connection.close()

        return True

    except Exception as e:
        print(f"❌ 데이터베이스 생성 실패: {e}")
        return False


if __name__ == '__main__':
    print("\n" + "="*70)
    print("BrowserStack TLS Crawler - MySQL 연결 테스트")
    print("="*70)

    # 연결 테스트
    success = test_connection()

    if not success:
        print("\n데이터베이스가 없는 경우, 자동 생성을 시도합니다...")
        response = input("\n데이터베이스 'tls'를 생성하시겠습니까? (y/N): ").strip().lower()

        if response == 'y':
            if create_database_if_not_exists():
                print("\n다시 연결 테스트를 시도합니다...\n")
                test_connection()

    print()
