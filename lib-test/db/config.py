"""
데이터베이스 설정 모듈
MariaDB/MySQL 연결 설정
"""

import os

# DB 연결 정보
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Tech1324!@',
    'database': 'tls',
    'charset': 'utf8mb4',
    'unix_socket': '/var/lib/mysql/mysql.sock'  # localhost 연결 시 socket 사용
}

# 커넥션 풀 설정
POOL_CONFIG = {
    'pool_name': 'browserstack_pool',
    'pool_size': 5,
    'pool_reset_session': True
}


def get_db_config():
    """
    DB 설정 반환

    Returns:
        dict: DB 연결 정보
    """
    return DB_CONFIG.copy()


def get_connection_string():
    """
    연결 문자열 생성 (로깅용)

    Returns:
        str: 연결 정보 문자열 (비밀번호 마스킹)
    """
    config = get_db_config()
    return (
        f"mysql://{config['user']}:****@{config['host']}"
        f"/{config['database']} (socket: {config.get('unix_socket', 'none')})"
    )
