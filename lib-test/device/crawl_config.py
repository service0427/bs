"""
크롤링 설정 모듈
키워드 입력, Worker 수 설정, 타임아웃 입력 처리
"""

import sys
import select
import random


# 랜덤 검색어 목록 (100개)
RANDOM_KEYWORDS = [
    # 전자제품 (20개)
    '아이폰', '갤럭시', '맥북', '아이패드', '에어팟',
    '노트북', '무선이어폰', '마우스', '키보드', '모니터',
    '삼성TV', 'LG세탁기', '냉장고', '에어컨', '공기청정기',
    '선풍기', '청소기', '로봇청소기', '스탠드', '전기포트',

    # 패션/의류 (20개)
    '운동화', '스니커즈', '구두', '샌들', '슬리퍼',
    '가방', '백팩', '크로스백', '지갑', '벨트',
    '패딩', '점퍼', '코트', '티셔츠', '청바지',
    '운동복', '레깅스', '양말', '모자', '선글라스',

    # 뷰티/화장품 (15개)
    '립스틱', '쿠션', '스킨케어', '마스크팩', '선크림',
    '샴푸', '린스', '바디워시', '향수', '핸드크림',
    '클렌징폼', '토너', '세럼', '크림', '립밤',

    # 식품 (15개)
    '과자', '초콜릿', '커피', '차', '라면',
    '통조림', '견과류', '건강식품', '비타민', '홍삼',
    '쌀', '김', '참치', '스팸', '치즈',

    # 생활용품 (15개)
    '휴지', '물티슈', '세제', '섬유유연제', '샤워타월',
    '칫솔', '치약', '비누', '수건', '베개',
    '이불', '매트리스', '커튼', '슬리퍼', '옷걸이',

    # 주방용품 (10개)
    '프라이팬', '냄비', '식칼', '도마', '믹서기',
    '전자레인지', '에어프라이어', '밥솥', '정수기', '컵',

    # 스포츠/레저 (5개)
    '요가매트', '덤벨', '런닝화', '자전거', '텐트'
]


def input_with_timeout(prompt, timeout):
    """
    타임아웃을 가진 입력 함수

    Args:
        prompt: 입력 프롬프트
        timeout: 타임아웃 시간(초)

    Returns:
        str: 입력값 또는 None (타임아웃 시)
    """
    print(prompt, end='', flush=True)

    # select를 사용한 타임아웃 입력 (Linux/Mac)
    ready, _, _ = select.select([sys.stdin], [], [], timeout)

    if ready:
        return sys.stdin.readline().strip()
    else:
        print(f"\n⏱️  {timeout}초 타임아웃 - 기본값 사용")
        return None


def get_crawl_config(keyword=None, num_workers=None):
    """
    크롤링 설정 입력 (키워드, Worker 수)

    Args:
        keyword: 검색 키워드 (None이면 인터랙티브)
        num_workers: Worker 수 (None이면 인터랙티브)

    Returns:
        dict: {'keyword': str, 'num_workers': int}
    """
    print("\n" + "="*70)
    print("크롤링 설정")
    print("="*70)

    # 검색어 입력 (5초 타임아웃)
    if keyword is None:
        keyword_input = input_with_timeout("\n검색 키워드 입력 (Enter = 랜덤, 5초 타임아웃): ", 5)

        # 타임아웃 또는 Enter (빈 문자열)
        if keyword_input is None or not keyword_input:
            keyword = random.choice(RANDOM_KEYWORDS)
            print(f"  → 랜덤 키워드 선택: {keyword}")
        else:
            keyword = keyword_input
            print(f"  → 키워드: {keyword}")
    else:
        print(f"\n검색 키워드: {keyword}")

    # 워커 수 입력 (5초 타임아웃)
    if num_workers is None:
        worker_input = input_with_timeout("\n병렬 Worker 수 (1-20, Enter = 1, 5초 타임아웃): ", 5)

        # 타임아웃 또는 Enter (빈 문자열)
        if worker_input is None or not worker_input:
            num_workers = 1
            if worker_input is not None:  # Enter를 눌렀을 때
                print(f"  → 기본값 선택: 1개")
        else:
            # 한글 오타 처리
            if worker_input in ['ㅛ', 'ㅛㅛ']:
                worker_input = '1'
            elif worker_input in ['ㅜ', 'ㅜㅜ']:
                worker_input = '1'

            if worker_input.isdigit():
                num_workers = int(worker_input)
                if num_workers < 1:
                    print(f"  ⚠️ 1 미만입니다. 기본값 1 사용")
                    num_workers = 1
                elif num_workers > 20:
                    print(f"  ⚠️ 20 초과입니다. 20개로 제한합니다.")
                    num_workers = 20
            else:
                print(f"  ⚠️ 숫자가 아닙니다. 기본값 1 사용")
                num_workers = 1
    else:
        if num_workers > 20:
            print(f"\n⚠️ Worker 수가 20개를 초과합니다. 20개로 제한합니다.")
            num_workers = 20

    print(f"\n✓ Worker 수: {num_workers}개")
    print("="*70)

    return {
        'keyword': keyword,
        'num_workers': num_workers
    }
