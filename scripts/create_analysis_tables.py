#!/usr/bin/env python3
"""
분석용 테이블 생성 스크립트
products, crawl_details 테이블 생성
"""

import os
import sys

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.db.manager import DBManager

def create_tables():
    """분석용 테이블 생성"""

    db = DBManager()
    connection = db.get_connection()
    cursor = connection.cursor()

    # SQL 파일 경로
    script_dir = os.path.dirname(os.path.abspath(__file__))
    products_sql = os.path.join(script_dir, 'create_products_table.sql')
    crawl_details_sql = os.path.join(script_dir, 'create_crawl_details_table.sql')

    try:
        # products 테이블 생성
        print("📦 products 테이블 생성 중...")
        with open(products_sql, 'r', encoding='utf-8') as f:
            sql = f.read()
            cursor.execute(sql)
        print("✅ products 테이블 생성 완료")

        # crawl_details 테이블 생성
        print("📊 crawl_details 테이블 생성 중...")
        with open(crawl_details_sql, 'r', encoding='utf-8') as f:
            sql = f.read()
            cursor.execute(sql)
        print("✅ crawl_details 테이블 생성 완료")

        connection.commit()
        print("\n🎉 모든 분석용 테이블 생성 완료!")

    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    create_tables()
