#!/usr/bin/env python3
"""간단한 DB 연결 테스트"""

import pymysql

# 연결 정보
config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Tech1324!@',  # Python 문자열은 이스케이프 문제 없음
    'charset': 'utf8mb4'
}

print("="*70)
print("MariaDB 연결 테스트")
print("="*70)
print(f"Host: {config['host']}")
print(f"User: {config['user']}")
print(f"Password: {'*' * len(config['password'])}")
print()

try:
    # 데이터베이스 지정 없이 연결 (서버 연결만 테스트)
    print("연결 시도 중...")
    connection = pymysql.connect(
        host=config['host'],
        user=config['user'],
        password=config['password'],
        charset=config['charset'],
        # MariaDB localhost 연결 시 unix_socket 사용 (PHP와 동일)
        unix_socket='/var/lib/mysql/mysql.sock'
    )

    print("✅ 서버 연결 성공!\n")

    cursor = connection.cursor()

    # 데이터베이스 목록 확인
    print("데이터베이스 목록:")
    cursor.execute("SHOW DATABASES")
    databases = cursor.fetchall()

    for db in databases:
        db_name = db[0]
        if db_name == 'tls':
            print(f"  • {db_name} ✅ (존재)")
        else:
            print(f"  • {db_name}")

    # tls 데이터베이스 확인
    cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = 'tls'")
    tls_exists = cursor.fetchone()

    print()
    if tls_exists:
        print("✅ 'tls' 데이터베이스 존재")

        # tls 데이터베이스로 전환
        cursor.execute("USE tls")

        # 테이블 확인
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        print(f"\n테이블 개수: {len(tables)}")
        if tables:
            for table in tables:
                print(f"  • {table[0]}")
        else:
            print("  (테이블 없음 - 비어있음)")
    else:
        print("⚠️  'tls' 데이터베이스가 없습니다")
        print("\n생성하시겠습니까? (y/N): ", end='')

        # 자동으로 생성
        print("y")
        cursor.execute("""
            CREATE DATABASE tls
            CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        """)
        print("✅ 데이터베이스 'tls' 생성 완료")

    cursor.close()
    connection.close()

    print("\n" + "="*70)
    print("✅ 연결 테스트 성공!")
    print("="*70)

except pymysql.err.OperationalError as e:
    print(f"❌ 연결 실패!")
    print(f"\n에러 코드: {e.args[0]}")
    print(f"에러 메시지: {e.args[1]}")

    if e.args[0] == 1045:
        print("\n💡 비밀번호가 틀렸습니다.")
        print("   config에 설정된 비밀번호를 확인해주세요.")
    elif e.args[0] == 2003:
        print("\n💡 MySQL/MariaDB 서버에 연결할 수 없습니다.")
        print("   서버가 실행 중인지 확인하세요: systemctl status mariadb")

except Exception as e:
    print(f"❌ 예상치 못한 에러: {e}")
    import traceback
    traceback.print_exc()
