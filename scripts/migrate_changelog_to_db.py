#!/usr/bin/env python3
"""
CLAUDE.md의 버전 히스토리를 DB로 마이그레이션
"""

import sys
import os
import re
import json
from datetime import datetime

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.db.manager import DBManager


def parse_changelog_from_claude_md():
    """
    CLAUDE.md에서 버전 히스토리 파싱

    Returns:
        list: 변경이력 목록
    """
    claude_md = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'CLAUDE.md'
    )

    with open(claude_md, 'r', encoding='utf-8') as f:
        content = f.read()

    # "## 📝 버전 히스토리" 섹션 찾기
    version_section = re.search(r'## 📝 버전 히스토리\n\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if not version_section:
        print("⚠️  버전 히스토리 섹션을 찾을 수 없습니다")
        return []

    changelog_text = version_section.group(1)

    # 버전별로 분리 (### v2.XX 패턴)
    version_blocks = re.findall(
        r'### (v[\d.]+) \(([\d-]+)\)\n(.*?)(?=\n###|\Z)',
        changelog_text,
        re.DOTALL
    )

    changelogs = []

    for version, date_str, content_block in version_blocks:
        # 날짜 파싱 (2025-10-24 형식)
        release_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # 주요 변경사항 파싱
        lines = content_block.strip().split('\n')

        # 첫 줄은 보통 요약 (예: "**최적화: TLS 영구 보관**")
        first_line = lines[0] if lines else ""

        # 카테고리 추출
        category_map = {
            '기능 추가': 'feature',
            '개선': 'improvement',
            '수정': 'fix',
            '분석': 'analysis',
            '리팩토링': 'refactor',
            '발견': 'discovery',
            '최적화': 'improvement',
            '검증': 'analysis',
        }

        category = 'improvement'  # 기본값
        for keyword, cat in category_map.items():
            if keyword in first_line:
                category = cat
                break

        # 중요도 판단
        impact = 'minor'
        if '🚨' in content_block or 'CRITICAL' in content_block or '긴급' in content_block:
            impact = 'critical'
        elif '🎉' in content_block or '핵심' in content_block or '완전' in content_block:
            impact = 'major'

        # 제목 추출 (**: 사이의 텍스트)
        title_match = re.search(r'\*\*([^*]+)\*\*', first_line)
        title = title_match.group(1) if title_match else first_line[:100]

        # 태그 추출 (TLS, 쿠키, Galaxy 등)
        tags = []
        tag_keywords = ['TLS', 'cookie', 'Session', 'Galaxy', 'iPhone', 'GREASE',
                        'JA3', 'Akamai', 'ECH', 'ALPS', 'X25519MLKEM768', 'DB']
        for keyword in tag_keywords:
            if keyword.lower() in content_block.lower():
                tags.append(keyword)

        # 파일 변경 추출 (예: "custom_tls.py:303-309")
        file_refs = re.findall(r'`([a-z_/]+\.py):(\d+(?:-\d+)?)`', content_block)
        code_reference = ', '.join([f"{f}:{l}" for f, l in file_refs[:3]]) if file_refs else None

        changelogs.append({
            'version': version,
            'release_date': release_date,
            'category': category,
            'impact': impact,
            'title': title,
            'description': content_block.strip(),
            'files_changed': json.dumps([f for f, _ in file_refs]) if file_refs else None,
            'code_reference': code_reference,
            'tags': json.dumps(tags, ensure_ascii=False) if tags else None,
        })

    return changelogs


def create_changelog_table(db):
    """changelog 테이블 생성"""

    sql_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'create_changelog_table.sql'
    )

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    # 주석 제거하고 실행
    statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

    conn = db.get_connection()
    cursor = conn.cursor()

    for statement in statements:
        if statement:
            cursor.execute(statement)

    conn.commit()
    cursor.close()

    print("✅ changelogs 테이블 생성 완료")


def migrate_changelogs(db, changelogs):
    """변경이력을 DB에 저장"""

    conn = db.get_connection()
    cursor = conn.cursor()

    for changelog in changelogs:
        cursor.execute("""
            INSERT INTO changelogs (
                version, release_date, category, impact,
                title, description, files_changed, code_reference, tags
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            changelog['version'],
            changelog['release_date'],
            changelog['category'],
            changelog['impact'],
            changelog['title'],
            changelog['description'],
            changelog['files_changed'],
            changelog['code_reference'],
            changelog['tags']
        ))

    conn.commit()
    cursor.close()

    print(f"✅ {len(changelogs)}개 변경이력 DB 저장 완료")


def main():
    print("=" * 60)
    print("CLAUDE.md 버전 히스토리 → DB 마이그레이션")
    print("=" * 60)
    print()

    # 1. DB 연결
    db = DBManager()
    print("✅ DB 연결 완료")

    # 2. 테이블 생성
    create_changelog_table(db)

    # 3. CLAUDE.md 파싱
    print("\n📖 CLAUDE.md 파싱 중...")
    changelogs = parse_changelog_from_claude_md()
    print(f"   → {len(changelogs)}개 버전 히스토리 발견")

    if not changelogs:
        print("⚠️  변경이력이 없습니다")
        return

    # 4. DB에 저장
    print("\n💾 DB 저장 중...")
    migrate_changelogs(db, changelogs)

    print("\n" + "=" * 60)
    print("✅ 마이그레이션 완료!")
    print("=" * 60)


if __name__ == '__main__':
    main()
