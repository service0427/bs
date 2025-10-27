#!/usr/bin/env python3
"""
기존 fingerprint 파일에서 세션 쿠키 제거 스크립트
PCID, sid 등 세션 쿠키는 크롤링 시마다 새로 발급받아야 함
"""

import os
import json
import glob

# 세션 쿠키 목록
SESSION_COOKIE_NAMES = ['PCID', 'sid', 'sessionid', 'session', 'JSESSIONID']

def cleanup_cookies_file(cookies_file):
    """단일 cookies.json 파일에서 세션 쿠키 제거"""
    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    # 원본 개수
    original_count = len(cookies)

    # 세션 쿠키 찾기
    session_cookies_found = [c['name'] for c in cookies if c['name'] in SESSION_COOKIE_NAMES]

    if not session_cookies_found:
        return None  # 세션 쿠키 없음

    # 세션 쿠키 제외
    filtered_cookies = [
        cookie for cookie in cookies
        if cookie['name'] not in SESSION_COOKIE_NAMES
    ]

    # 파일 저장
    with open(cookies_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_cookies, f, indent=2, ensure_ascii=False)

    return {
        'file': cookies_file,
        'original': original_count,
        'filtered': len(filtered_cookies),
        'removed': session_cookies_found
    }

def main():
    """모든 fingerprint 디렉토리의 cookies.json 파일 정리"""
    base_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'data',
        'fingerprints'
    )

    if not os.path.exists(base_dir):
        print(f"❌ fingerprints 디렉토리가 없습니다: {base_dir}")
        return

    # 모든 cookies.json 파일 찾기
    pattern = os.path.join(base_dir, '*', 'cookies.json')
    cookies_files = glob.glob(pattern)

    if not cookies_files:
        print(f"❌ cookies.json 파일을 찾을 수 없습니다")
        return

    print(f"\n{'='*70}")
    print(f"세션 쿠키 정리 스크립트")
    print(f"{'='*70}\n")
    print(f"대상: {len(cookies_files)}개 디바이스")
    print(f"제거 대상 쿠키: {', '.join(SESSION_COOKIE_NAMES)}\n")

    cleaned_count = 0
    skipped_count = 0

    for cookies_file in sorted(cookies_files):
        device_name = os.path.basename(os.path.dirname(cookies_file))

        result = cleanup_cookies_file(cookies_file)

        if result is None:
            print(f"  ✓ {device_name}: 세션 쿠키 없음 (건너뜀)")
            skipped_count += 1
        else:
            print(f"  🧹 {device_name}: {result['original']} → {result['filtered']}개")
            print(f"     제거: {', '.join(result['removed'])}")
            cleaned_count += 1

    print(f"\n{'='*70}")
    print(f"✅ 완료!")
    print(f"  - 정리됨: {cleaned_count}개")
    print(f"  - 건너뜀: {skipped_count}개")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
