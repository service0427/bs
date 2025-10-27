#!/usr/bin/env python3
"""
DB 상태 확인
테이블 목록 및 레코드 수 확인
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
from lib.db.config import get_db_config


def check_database_status():
    """데이터베이스 상태 확인"""
    config = get_db_config()
    connection = pymysql.connect(**config)
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    print("="*70)
    print("BrowserStack TLS Crawler - DB 상태 확인")
    print("="*70)

    # 1. 테이블 목록
    print("\n[1] 테이블 목록:")
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    for table in tables:
        table_name = list(table.values())[0]
        print(f"  • {table_name}")

    # 2. 각 테이블의 레코드 수
    print("\n[2] 레코드 수:")

    for table in tables:
        table_name = list(table.values())[0]
        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        count = cursor.fetchone()['count']
        print(f"  • {table_name}: {count} rows")

    # 3. tls_fingerprints 최근 5개
    print("\n[3] TLS Fingerprints (최근 5개):")
    cursor.execute("""
        SELECT
            device_name, browser, os_version,
            ja3_hash, akamai_fingerprint,
            collected_at, test_mode
        FROM tls_fingerprints
        ORDER BY created_at DESC
        LIMIT 5
    """)

    tls_records = cursor.fetchall()
    if tls_records:
        for record in tls_records:
            print(f"\n  [{record['device_name']} / {record['browser']} / {record['os_version']}]")
            print(f"    JA3: {record['ja3_hash']}")
            print(f"    Akamai: {record['akamai_fingerprint']}")
            print(f"    Collected: {record['collected_at']}")
            print(f"    Test Mode: {record['test_mode']}")
    else:
        print("  (레코드 없음)")

    # 4. crawl_results 최근 5개
    print("\n[4] Crawl Results (최근 5개):")
    cursor.execute("""
        SELECT
            session_id, device_name, browser, keyword,
            pages_successful, pages_failed,
            total_ranking, total_ads,
            status, duration_seconds,
            created_at
        FROM crawl_results
        ORDER BY created_at DESC
        LIMIT 5
    """)

    crawl_records = cursor.fetchall()
    if crawl_records:
        for record in crawl_records:
            print(f"\n  [{record['session_id']}]")
            print(f"    Device: {record['device_name']} / {record['browser']}")
            print(f"    Keyword: {record['keyword']}")
            print(f"    Pages: {record['pages_successful']} success / {record['pages_failed']} failed")
            print(f"    Results: {record['total_ranking']} ranking / {record['total_ads']} ads")
            print(f"    Status: {record['status']} ({record['duration_seconds']}s)")
            print(f"    Created: {record['created_at']}")
    else:
        print("  (레코드 없음)")

    # 5. variance_samples 샘플 수
    print("\n[5] TLS Variance Samples:")
    cursor.execute("""
        SELECT
            test_session_id,
            COUNT(*) as sample_count,
            device_name, browser, os_version
        FROM tls_variance_samples
        GROUP BY test_session_id, device_name, browser, os_version
        ORDER BY MIN(created_at) DESC
        LIMIT 5
    """)

    variance_records = cursor.fetchall()
    if variance_records:
        for record in variance_records:
            print(f"\n  [{record['test_session_id']}]")
            print(f"    Device: {record['device_name']} / {record['browser']} / {record['os_version']}")
            print(f"    Samples: {record['sample_count']}개")
    else:
        print("  (레코드 없음)")

    cursor.close()
    connection.close()

    print("\n" + "="*70)
    print("확인 완료")
    print("="*70)


if __name__ == '__main__':
    check_database_status()
