"""
디바이스 선택 모듈
4단계 인터랙티브 선택: Category → Model → Browser → OS Version
"""

import os
import sys
import json

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.mobile_real_devices import (
    get_category_stats,
    get_device_models,
    get_browsers_for_device,
    get_full_config
)
from lib.device.status import get_device_success_status, get_device_model_summary


def select_device():
    """디바이스 선택 인터페이스"""

    print("\n" + "="*60)
    print("BrowserStack TLS Crawler - 디바이스 선택")
    print("="*60 + "\n")

    # 이전 선택 로드 (DB에서)
    from lib.db.manager import DBManager
    db = DBManager()

    last_selection = db.get_last_device_selection()

    # DB 선택 기록을 history 포맷으로 변환
    history = None
    if last_selection:
        history = {
            'version': 3,
            'last_category': last_selection.get('category', ''),
            'last_device_by_category': {
                last_selection.get('category', ''): last_selection.get('device_name', '')
            },
            'devices': {
                last_selection.get('device_name', ''): {
                    'category': last_selection.get('category', ''),
                    'browser_key': last_selection.get('browser', ''),
                    'os_version': last_selection.get('os_version', '')
                }
            }
        }

    # STEP 1: 카테고리 선택
    print("[STEP 1] 기기 카테고리 선택")
    stats = get_category_stats()

    categories = [
        ('galaxy', 'Galaxy', stats['galaxy']),
        ('iphone', 'iPhone', stats['iphone']),
        ('other', 'Other', stats['other'])
    ]

    for idx, (cat_key, name, stat) in enumerate(categories, 1):
        default_mark = ""
        if history and history.get('last_category') == cat_key:
            default_mark = " ← 이전 선택"
        print(f"  {idx}. {name} ({stat['model_count']}개 모델){default_mark}")

    default_idx = None
    if history and history.get('last_category'):
        for idx, (cat_key, _, _) in enumerate(categories):
            if cat_key == history.get('last_category'):
                default_idx = idx
                break

    while True:
        choice = input(f"\n선택 (1-{len(categories)}){' [Enter=이전선택]' if default_idx is not None else ''}: ").strip()

        # 한글 오타 처리
        if choice in ['ㅛ', 'ㅛㅛ']:
            choice = 'y'
        elif choice in ['ㅜ', 'ㅜㅜ']:
            choice = 'n'

        # Enter: 기본값 사용
        if not choice and default_idx is not None:
            choice = str(default_idx + 1)

        if choice.isdigit() and 1 <= int(choice) <= len(categories):
            category = categories[int(choice) - 1][0]
            break
        print("  ⚠️ 올바른 번호를 입력하세요.")

    # STEP 2: 디바이스 모델 선택
    category_display = next(name for cat_key, name, _ in categories if cat_key == category)
    print(f"\n[STEP 2] {category_display} 디바이스 모델 선택")
    models = get_device_models(category)

    # 현재 카테고리의 마지막 선택 디바이스 가져오기
    last_device_in_category = None
    if history and 'last_device_by_category' in history:
        last_device_in_category = history['last_device_by_category'].get(category)

    for idx, model in enumerate(models, 1):
        default_mark = ""
        if last_device_in_category and last_device_in_category == model:
            default_mark = " ← 이전 선택"

        # 디바이스 성공 정보 가져오기
        summary = get_device_model_summary(model)

        # 기본 출력
        star_mark = " ⭐" if summary['has_success'] else ""
        print(f"  {idx}. {model}{star_mark}{default_mark}")

        # 미리보기 정보 (성공 기록이 있으면 표시)
        if summary['summary']:
            date_display = f" ({summary['date_str']})" if summary['date_str'] else ""
            print(f"     └─ {summary['summary']}{date_display}")

    default_idx = None
    if last_device_in_category:
        for idx, model in enumerate(models):
            if model == last_device_in_category:
                default_idx = idx
                break

    while True:
        choice = input(f"\n선택 (1-{len(models)}){' [Enter=이전선택]' if default_idx else ''}: ").strip()

        if choice in ['ㅛ', 'ㅛㅛ']:
            choice = 'y'
        elif choice in ['ㅜ', 'ㅜㅜ']:
            choice = 'n'

        if not choice and default_idx is not None:
            choice = str(default_idx + 1)

        if choice.isdigit() and 1 <= int(choice) <= len(models):
            device_model = models[int(choice) - 1]
            break
        print("  ⚠️ 올바른 번호를 입력하세요.")

    # STEP 3: 브라우저 선택
    print(f"\n[STEP 3] 브라우저 선택")
    browsers = get_browsers_for_device(device_model)

    browser_list = list(browsers.items())

    # 현재 디바이스의 히스토리 가져오기
    device_history = None
    if history and 'devices' in history and device_model in history['devices']:
        device_history = history['devices'][device_model]

    # 디바이스 성공 상태 가져오기 (별 표시용)
    device_status = get_device_success_status()

    # 선택지가 1개면 자동 선택
    if len(browser_list) == 1:
        browser_key, browser_info = browser_list[0]
        browser_name = browser_info['name']
        print(f"  ✓ {browser_name} (자동 선택)")
    else:
        for idx, (browser_key, browser_info) in enumerate(browser_list, 1):
            browser_name = browser_info['name']
            count = len(browser_info['os_versions'])
            default_mark = ""
            # 현재 디바이스의 히스토리만 참조
            if device_history and device_history.get('browser_key') == browser_key:
                default_mark = " ← 이전 선택"

            # 성공 여부 확인 (이 디바이스 + 브라우저 조합)
            star_mark = ""
            for os_ver in browser_info['os_versions']:
                device_key = f"{device_model}_{browser_key}_{os_ver}"
                if device_key in device_status and device_status[device_key].get('success'):
                    star_mark = " ⭐"
                    break

            print(f"  {idx}. {browser_name} ({count}개 버전){star_mark}{default_mark}")

            # User-Agent 표시 (TLS 파일이 있으면)
            try:
                from lib.settings import get_tls_dir
                import os
                import json

                # 첫 번째 OS 버전으로 User-Agent 조회
                if browser_info['os_versions']:
                    first_os_ver = browser_info['os_versions'][0]
                    tls_dir = get_tls_dir(device_model, browser_key, first_os_ver)
                    tls_file = os.path.join(tls_dir, 'tls_fingerprint.json')

                    if os.path.exists(tls_file):
                        with open(tls_file, 'r') as f:
                            tls_data = json.load(f)
                            user_agent = tls_data.get('user_agent', '')

                            if user_agent:
                                # User-Agent 간략 표시 (첫 80자만)
                                ua_short = user_agent[:80] + '...' if len(user_agent) > 80 else user_agent
                                print(f"     └─ UA: {ua_short}")
            except Exception:
                pass  # User-Agent 표시 실패해도 무시

        default_idx = None
        if device_history and device_history.get('browser_key'):
            for idx, (browser_key, _) in enumerate(browser_list):
                if browser_key == device_history.get('browser_key'):
                    default_idx = idx
                    break

        while True:
            choice = input(f"\n선택 (1-{len(browser_list)}){' [Enter=이전선택]' if default_idx is not None else ''}: ").strip()

            if choice in ['ㅛ', 'ㅛㅛ']:
                choice = 'y'
            elif choice in ['ㅜ', 'ㅜㅜ']:
                choice = 'n'

            if not choice and default_idx is not None:
                choice = str(default_idx + 1)

            if choice.isdigit() and 1 <= int(choice) <= len(browser_list):
                browser_key, browser_info = browser_list[int(choice) - 1]
                break
            print("  ⚠️ 올바른 번호를 입력하세요.")

    # STEP 4: OS 버전 선택
    print(f"\n[STEP 4] OS 버전 선택")
    os_versions = browser_info['os_versions']

    # 선택지가 1개면 자동 선택
    if len(os_versions) == 1:
        os_version = os_versions[0]
        print(f"  ✓ OS {os_version} (자동 선택)")
    else:
        for idx, os_ver in enumerate(os_versions, 1):
            default_mark = ""
            # 현재 디바이스의 히스토리만 참조
            if device_history and device_history.get('os_version') == os_ver:
                default_mark = " ← 이전 선택"
            print(f"  {idx}. OS {os_ver}{default_mark}")

        default_idx = None
        if device_history and device_history.get('os_version'):
            for idx, os_ver in enumerate(os_versions):
                if os_ver == device_history.get('os_version'):
                    default_idx = idx
                    break

        while True:
            choice = input(f"\n선택 (1-{len(os_versions)}){' [Enter=이전선택]' if default_idx is not None else ''}: ").strip()

            if choice in ['ㅛ', 'ㅛㅛ']:
                choice = 'y'
            elif choice in ['ㅜ', 'ㅜㅜ']:
                choice = 'n'

            if not choice and default_idx is not None:
                choice = str(default_idx + 1)

            if choice.isdigit() and 1 <= int(choice) <= len(os_versions):
                os_version = os_versions[int(choice) - 1]
                break
            print("  ⚠️ 올바른 번호를 입력하세요.")

    # 선택된 디바이스 정보
    selected_device = get_full_config(device_model, browser_key, os_version)

    if not selected_device:
        print("\n❌ 디바이스를 찾을 수 없습니다.")
        return None

    # 선택 저장 (v3 포맷: 카테고리별 + 디바이스별 히스토리)
    if history is None:
        history = {
            'version': 3,
            'last_category': None,
            'last_device_by_category': {},
            'devices': {}
        }

    # 전역 히스토리 업데이트
    history['last_category'] = category

    # 카테고리별 마지막 디바이스 업데이트
    if 'last_device_by_category' not in history:
        history['last_device_by_category'] = {}
    history['last_device_by_category'][category] = device_model

    # 디바이스별 히스토리 업데이트
    if 'devices' not in history:
        history['devices'] = {}
    history['devices'][device_model] = {
        'category': category,
        'browser_key': browser_key,
        'os_version': os_version
    }

    # DB에 선택 기록 저장
    db.save_device_selection(
        device_name=device_model,
        browser=browser_key,
        os_version=os_version,
        category=category
    )

    # 최종 선택 출력
    print("\n" + "="*60)
    print("선택된 디바이스")
    print("="*60)
    print(f"  디바이스: {selected_device['device']}")
    print(f"  OS: {selected_device['os']} {selected_device['os_version']}")
    print(f"  브라우저: {selected_device['browser']}")
    if selected_device.get('browser_version'):
        print(f"  브라우저 버전: {selected_device['browser_version']}")
    print(f"  Real Mobile: {selected_device.get('real_mobile', True)}")
    print("="*60 + "\n")

    return selected_device
