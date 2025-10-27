#!/usr/bin/env python3
"""
패치노트 조회 스크립트
DB에 저장된 변경이력을 검색/필터링하여 조회
"""

import sys
import os
import json
import argparse
from datetime import datetime
import pymysql.cursors

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.db.manager import DBManager


def format_changelog(row):
    """변경이력을 보기 좋게 포맷"""

    impact_emoji = {
        'critical': '🚨',
        'major': '⭐',
        'minor': '📌'
    }

    category_emoji = {
        'feature': '✨',
        'fix': '🐛',
        'improvement': '🔧',
        'analysis': '🔬',
        'refactor': '♻️',
        'discovery': '🎯'
    }

    output = []
    output.append("")
    output.append("=" * 70)
    output.append(f"{impact_emoji.get(row['impact'], '📌')} {row['version']} - {row['release_date']}")
    output.append(f"{category_emoji.get(row['category'], '📝')} [{row['category'].upper()}] {row['title']}")
    output.append("=" * 70)

    # 설명
    if row['description']:
        output.append("")
        output.append(row['description'])

    # 태그
    if row['tags']:
        tags = json.loads(row['tags'])
        output.append("")
        output.append(f"🏷️  태그: {', '.join(tags)}")

    # 변경된 파일
    if row['code_reference']:
        output.append(f"📁 파일: {row['code_reference']}")

    output.append("")

    return '\n'.join(output)


def view_latest(db, limit=10):
    """최신 N개 변경이력 조회"""

    conn = db.get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT * FROM changelogs
        ORDER BY release_date DESC, id DESC
        LIMIT %s
    """, (limit,))

    rows = cursor.fetchall()
    cursor.close()

    print(f"\n📋 최신 {limit}개 변경이력\n")
    for row in rows:
        print(format_changelog(row))


def view_by_version(db, version):
    """특정 버전의 변경이력 조회"""

    conn = db.get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT * FROM changelogs
        WHERE version = %s
        ORDER BY id
    """, (version,))

    rows = cursor.fetchall()
    cursor.close()

    if not rows:
        print(f"\n⚠️  {version} 버전을 찾을 수 없습니다")
        return

    print(f"\n📋 {version} 변경이력 ({len(rows)}개)\n")
    for row in rows:
        print(format_changelog(row))


def view_by_category(db, category):
    """카테고리별 변경이력 조회"""

    conn = db.get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT * FROM changelogs
        WHERE category = %s
        ORDER BY release_date DESC, id DESC
    """, (category,))

    rows = cursor.fetchall()
    cursor.close()

    if not rows:
        print(f"\n⚠️  '{category}' 카테고리가 없습니다")
        return

    print(f"\n📋 [{category.upper()}] 변경이력 ({len(rows)}개)\n")
    for row in rows:
        print(format_changelog(row))


def search_by_tag(db, tag):
    """태그로 검색"""

    conn = db.get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # JSON 배열 내부 검색
    cursor.execute("""
        SELECT * FROM changelogs
        WHERE tags LIKE %s
        ORDER BY release_date DESC, id DESC
    """, (f'%{tag}%',))

    rows = cursor.fetchall()
    cursor.close()

    if not rows:
        print(f"\n⚠️  '{tag}' 태그를 찾을 수 없습니다")
        return

    print(f"\n🔍 태그 '{tag}' 검색 결과 ({len(rows)}개)\n")
    for row in rows:
        print(format_changelog(row))


def view_critical(db):
    """중요 변경사항만 조회"""

    conn = db.get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT * FROM changelogs
        WHERE impact IN ('critical', 'major')
        ORDER BY release_date DESC, id DESC
    """, ())

    rows = cursor.fetchall()
    cursor.close()

    print(f"\n🚨 중요 변경사항 ({len(rows)}개)\n")
    for row in rows:
        print(format_changelog(row))


def view_stats(db):
    """통계 조회"""

    conn = db.get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 전체 통계
    cursor.execute("SELECT COUNT(*) as total FROM changelogs")
    total = cursor.fetchone()['total']

    # 카테고리별 통계
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM changelogs
        GROUP BY category
        ORDER BY count DESC
    """)
    categories = cursor.fetchall()

    # 중요도별 통계
    cursor.execute("""
        SELECT impact, COUNT(*) as count
        FROM changelogs
        GROUP BY impact
        ORDER BY FIELD(impact, 'critical', 'major', 'minor')
    """)
    impacts = cursor.fetchall()

    # 버전별 통계
    cursor.execute("""
        SELECT version, COUNT(*) as count
        FROM changelogs
        GROUP BY version
        ORDER BY version DESC
        LIMIT 10
    """)
    versions = cursor.fetchall()

    cursor.close()

    print("\n📊 변경이력 통계")
    print("=" * 70)
    print(f"\n전체: {total}개")

    print("\n카테고리별:")
    for row in categories:
        print(f"  - {row['category']:12s}: {row['count']:3d}개")

    print("\n중요도별:")
    for row in impacts:
        print(f"  - {row['impact']:8s}: {row['count']:3d}개")

    print("\n최근 버전별:")
    for row in versions:
        print(f"  - {row['version']:10s}: {row['count']:3d}개")

    print("")


def main():
    parser = argparse.ArgumentParser(
        description='패치노트 조회 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 최신 10개 조회
  python view_changelog.py

  # 최신 20개 조회
  python view_changelog.py --latest 20

  # 특정 버전 조회
  python view_changelog.py --version v2.14

  # 카테고리별 조회
  python view_changelog.py --category fix

  # 태그로 검색
  python view_changelog.py --tag TLS

  # 중요 변경사항만
  python view_changelog.py --critical

  # 통계 조회
  python view_changelog.py --stats
        """
    )

    parser.add_argument('--latest', type=int, metavar='N',
                        help='최신 N개 조회 (기본: 10)')
    parser.add_argument('--version', metavar='VERSION',
                        help='특정 버전 조회 (예: v2.14)')
    parser.add_argument('--category', metavar='CATEGORY',
                        choices=['feature', 'fix', 'improvement', 'analysis', 'refactor', 'discovery'],
                        help='카테고리별 조회')
    parser.add_argument('--tag', metavar='TAG',
                        help='태그로 검색 (예: TLS, cookie)')
    parser.add_argument('--critical', action='store_true',
                        help='중요 변경사항만 조회')
    parser.add_argument('--stats', action='store_true',
                        help='통계 조회')

    args = parser.parse_args()

    # DB 연결
    db = DBManager()

    # 명령에 따라 조회
    if args.stats:
        view_stats(db)
    elif args.critical:
        view_critical(db)
    elif args.version:
        view_by_version(db, args.version)
    elif args.category:
        view_by_category(db, args.category)
    elif args.tag:
        search_by_tag(db, args.tag)
    else:
        # 기본: 최신 N개
        limit = args.latest if args.latest else 10
        view_latest(db, limit)


if __name__ == '__main__':
    main()
