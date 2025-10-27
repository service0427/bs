"""
쿠팡 상호작용 모듈 (배너 제거 + 검색)

쿠키 수집 시 선택적으로 사용 가능:
- 배너 닫기: FULL_BANNER, bottom_sheet_nudge_banner 쿠키 획득
- 검색 수행: 실제 사용자처럼 검색하여 추가 쿠키 획득

⚠️ 주의: 이 모듈은 선택적 사용입니다.
         리얼 브라우저에서 차단되면 검색이 의미 없으므로
         차단 여부를 확인하기 위한 테스트 용도로 사용됩니다.
"""

import time


def close_banners(driver, device_name):
    """
    쿠팡 배너 닫기 (fullBanner, bottomSheetBudge)

    Args:
        driver: Selenium WebDriver
        device_name: 디바이스 이름 (로그용)

    Returns:
        dict: {
            'full_banner_closed': bool,
            'bottom_banner_closed': bool,
            'full_banner_cookie': bool,
            'bottom_banner_cookie': bool
        }
    """
    print(f"[{device_name}] 배너 대기 중 (최대 20초)...")
    time.sleep(20)  # 배너가 뜰 때까지 충분히 대기

    result = {
        'full_banner_closed': False,
        'bottom_banner_closed': False,
        'full_banner_cookie': False,
        'bottom_banner_cookie': False
    }

    try:
        # 1. fullBanner 닫기
        print(f"[{device_name}] fullBanner 확인 중...")
        full_banner_script = """
        var fullBanner = document.getElementById('fullBanner');
        if (fullBanner) {
            var closeBtn = fullBanner.querySelector('.close-banner-icon-button');
            if (closeBtn) {
                closeBtn.click();
                return 'closed';
            }
        }
        return 'not_found';
        """
        banner_result = driver.execute_script(full_banner_script)

        if banner_result == 'closed':
            print(f"[{device_name}] fullBanner 닫기 클릭 완료")
            time.sleep(3)  # 쿠키 생성 대기
            result['full_banner_closed'] = True

            # FULL_BANNER 쿠키 확인
            cookies = driver.get_cookies()
            result['full_banner_cookie'] = any(c['name'] == 'FULL_BANNER' for c in cookies)
            if result['full_banner_cookie']:
                print(f"[{device_name}] ✓ FULL_BANNER 쿠키 생성 확인")
            else:
                print(f"[{device_name}] ⚠️  FULL_BANNER 쿠키 미생성")
        else:
            print(f"[{device_name}] fullBanner 없음")

        # 2. bottom sheet nudge banner 닫기
        print(f"[{device_name}] bottom sheet banner 확인 중...")
        bottom_banner_script = """
        var closeBtn = document.getElementById('bottomSheetBudgeCloseButton');
        if (closeBtn) {
            closeBtn.click();
            return 'closed';
        }
        return 'not_found';
        """
        bottom_result = driver.execute_script(bottom_banner_script)

        if bottom_result == 'closed':
            print(f"[{device_name}] bottom sheet banner 닫기 클릭 완료")
            time.sleep(3)  # 쿠키 생성 대기
            result['bottom_banner_closed'] = True

            # bottom_sheet_nudge_banner 쿠키 확인
            cookies = driver.get_cookies()
            result['bottom_banner_cookie'] = any(c['name'] == 'bottom_sheet_nudge_banner' for c in cookies)
            if result['bottom_banner_cookie']:
                print(f"[{device_name}] ✓ bottom_sheet_nudge_banner 쿠키 생성 확인")
            else:
                print(f"[{device_name}] ⚠️  bottom_sheet_nudge_banner 쿠키 미생성")
        else:
            print(f"[{device_name}] bottom sheet banner 없음")

        # 최종 쿠키 상태 확인
        cookies = driver.get_cookies()
        cookie_names = [c['name'] for c in cookies]
        has_full = 'FULL_BANNER' in cookie_names
        has_bottom = 'bottom_sheet_nudge_banner' in cookie_names

        print(f"[{device_name}] 배너 쿠키 최종 확인:")
        print(f"  - FULL_BANNER: {'✓' if has_full else '✗'}")
        print(f"  - bottom_sheet_nudge_banner: {'✓' if has_bottom else '✗'}")

        return result

    except Exception as e:
        print(f"[{device_name}] ⚠️  배너 닫기 중 에러: {e}")
        return result


def perform_search(driver, device_name, keyword="노트북"):
    """
    쿠팡 검색 수행 (Selenium 네이티브 API 사용)

    Args:
        driver: Selenium WebDriver
        device_name: 디바이스 이름 (로그용)
        keyword: 검색 키워드 (기본: "노트북")

    Returns:
        dict: {
            'success': bool,
            'method': str,  # 'selenium_input', 'direct_url'
            'search_page': bool  # 검색 결과 페이지 도달 여부
        }
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    print(f"\n[{device_name}] [자연스러운 탐색] 검색 시작...")
    print(f"[{device_name}] 키워드: \"{keyword}\"\n")

    result = {
        'success': False,
        'method': None,
        'search_page': False
    }

    try:
        # Step 2: 검색창 찾기 및 클릭
        search_input = None
        selectors = [
            (By.CSS_SELECTOR, 'input[name="q"]'),
            (By.CSS_SELECTOR, '.headerSearchKeyword'),
            (By.CSS_SELECTOR, 'input[type="search"]'),
            (By.ID, 'headerSearchKeyword'),
            (By.CSS_SELECTOR, 'input.search-input'),
        ]

        print(f"[{device_name}] [Step 2] 검색창 찾기...")

        # 모바일에서는 검색 아이콘/버튼을 먼저 클릭해야 검색창이 활성화됨
        search_button_selectors = [
            (By.CSS_SELECTOR, '.search-btn'),
            (By.CSS_SELECTOR, '.btn-search'),
            (By.CSS_SELECTOR, 'button[aria-label*="검색"]'),
            (By.CSS_SELECTOR, '.header-search-button'),
            (By.ID, 'searchButton'),
        ]

        print(f"[{device_name}] 모바일 검색 버튼 찾기 시도...")
        search_button_clicked = False
        for by, selector in search_button_selectors:
            try:
                search_btn = driver.find_element(by, selector)
                if search_btn.is_displayed():
                    print(f"[{device_name}] ✓ 검색 버튼 발견: {selector}")
                    search_btn.click()
                    time.sleep(1)
                    search_button_clicked = True
                    print(f"[{device_name}] ✅ 검색 버튼 클릭 완료")
                    break
            except (NoSuchElementException, Exception):
                continue

        # 검색창 찾기
        for by, selector in selectors:
            try:
                # clickable 상태 확인
                search_input = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((by, selector))
                )
                print(f"[{device_name}] ✓ 검색창 발견 (클릭 가능): {selector}")
                break
            except (TimeoutException, NoSuchElementException):
                # presence만 확인
                try:
                    search_input = WebDriverWait(driver, 1).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    print(f"[{device_name}] ✓ 검색창 발견 (존재만): {selector}")
                    break
                except:
                    continue

        if search_input:
            # 검색창 활성화 (여러 방법 시도)
            activated = False

            # 방법 1: JavaScript로 포커스
            try:
                print(f"[{device_name}] 검색창 활성화 시도 (JavaScript)...")
                driver.execute_script("arguments[0].focus();", search_input)
                driver.execute_script("arguments[0].click();", search_input)
                time.sleep(0.5)
                activated = True
                print(f"[{device_name}] ✅ 검색창 활성화 (JavaScript)")
            except Exception as e:
                print(f"[{device_name}] JavaScript 활성화 실패: {e}")

            # 방법 2: Selenium 네이티브 클릭
            if not activated:
                try:
                    print(f"[{device_name}] 검색창 클릭 (Selenium)...")
                    search_input.click()
                    time.sleep(0.5)
                    activated = True
                    print(f"[{device_name}] ✅ 검색창 활성화 (Selenium)")
                except Exception as e:
                    print(f"[{device_name}] Selenium 클릭 실패: {e}")

            # 방법 3: ActionChains로 클릭
            if not activated:
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    print(f"[{device_name}] 검색창 클릭 (ActionChains)...")
                    ActionChains(driver).move_to_element(search_input).click().perform()
                    time.sleep(0.5)
                    activated = True
                    print(f"[{device_name}] ✅ 검색창 활성화 (ActionChains)")
                except Exception as e:
                    print(f"[{device_name}] ActionChains 실패: {e}")

            if not activated:
                print(f"[{device_name}] ⚠️  검색창 활성화 실패 - JavaScript로 직접 입력 시도")

            # Step 3: 검색어 입력 (자연스럽게, 한 글자씩)
            print(f"\n[{device_name}] [Step 3] 검색어 입력: \"{keyword}\"")

            import random
            input_success = False

            # 방법 1: Selenium 네이티브 방식 (activated=True일 때만)
            if activated:
                try:
                    # 기존 텍스트 제거 (Ctrl+A로 전체 선택 후 삭제)
                    search_input.send_keys(Keys.CONTROL + 'a')
                    time.sleep(0.2)
                    search_input.send_keys(Keys.DELETE)
                    time.sleep(0.3)

                    # 자연스러운 타이핑 (한 글자씩, 랜덤 딜레이)
                    for i, char in enumerate(keyword, 1):
                        search_input.send_keys(char)
                        # 100~200ms 랜덤 딜레이 (사람처럼)
                        delay = 0.1 + random.random() * 0.1
                        time.sleep(delay)

                        # 중간 진행 상황 출력 (3글자마다)
                        if i % 3 == 0 or i == len(keyword):
                            print(f"[{device_name}]   진행: {keyword[:i]}... ({i}/{len(keyword)}자)")

                    input_success = True
                    time.sleep(0.5)
                    print(f"[{device_name}] ✅ 검색어 입력 완료\n")
                except Exception as e:
                    print(f"[{device_name}] Selenium 입력 실패: {e}")

            # 방법 2: JavaScript로 직접 값 설정 (activated=False이거나 방법1 실패)
            if not input_success:
                try:
                    print(f"[{device_name}] JavaScript로 직접 입력 시도...")
                    # 값 설정
                    driver.execute_script(f"""
                        arguments[0].value = '{keyword}';
                        arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                        arguments[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                    """, search_input)
                    time.sleep(0.5)
                    input_success = True
                    print(f"[{device_name}] ✅ 검색어 입력 완료 (JavaScript)\n")
                except Exception as e:
                    print(f"[{device_name}] JavaScript 입력 실패: {e}")

            if not input_success:
                raise Exception("검색어 입력 실패 (모든 방법 시도함)")

            # 현재 URL 저장 (검색 전)
            url_before = driver.current_url
            print(f"[{device_name}] 검색 전 URL: {url_before[:50]}...")

            # Step 4: Enter 키로 검색 실행
            print(f"[{device_name}] [Step 4] 검색 실행 (Enter)...")
            search_executed = False

            # 방법 1: Selenium Enter 키
            if activated:
                try:
                    search_input.send_keys(Keys.RETURN)
                    time.sleep(1)
                    search_executed = True
                    print(f"[{device_name}] ✓ Enter 키 입력 완료 (Selenium)")
                except Exception as e:
                    print(f"[{device_name}] Selenium Enter 실패: {e}")

            # 방법 2: JavaScript Enter 이벤트
            if not search_executed:
                try:
                    print(f"[{device_name}] JavaScript Enter 이벤트 발생...")
                    driver.execute_script("""
                        var event = new KeyboardEvent('keydown', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true
                        });
                        arguments[0].dispatchEvent(event);
                    """, search_input)
                    time.sleep(1)
                    search_executed = True
                    print(f"[{device_name}] ✓ Enter 이벤트 발생 완료 (JavaScript)")
                except Exception as e:
                    print(f"[{device_name}] JavaScript Enter 실패: {e}")

            # 방법 3: Form Submit
            if not search_executed:
                try:
                    print(f"[{device_name}] Form Submit 시도...")
                    driver.execute_script("""
                        var form = arguments[0].closest('form');
                        if (form) {
                            form.submit();
                        }
                    """, search_input)
                    time.sleep(1)
                    search_executed = True
                    print(f"[{device_name}] ✓ Form Submit 완료 (JavaScript)")
                except Exception as e:
                    print(f"[{device_name}] Form Submit 실패: {e}")

            if not search_executed:
                raise Exception("검색 실행 실패 (모든 방법 시도함)")

            # 검색 결과 페이지 로드 대기
            print(f"[{device_name}] [Step 5] 검색 결과 대기...")
            try:
                # URL 변경 대기 (최대 20초)
                WebDriverWait(driver, 20).until(
                    lambda d: d.current_url != url_before
                )
                url_after = driver.current_url
                print(f"[{device_name}] ✓ URL 변경 감지: {url_after[:80]}...")

                # traceId 확인
                if 'traceId' in url_after:
                    print(f"[{device_name}] ✓ traceId 파라미터 확인됨 (검색 성공)")
                else:
                    print(f"[{device_name}] ⚠️  traceId 없음 (검색 실패 가능성)")

                # DOM 로드 완료 대기 (추가 3초)
                print(f"[{device_name}] DOM 로드 완료 대기 중...")
                time.sleep(3)
                print(f"[{device_name}] ✅ 자연스러운 탐색 완료")

                result['success'] = True
                result['method'] = 'selenium_input'
            except TimeoutException:
                print(f"[{device_name}] ⚠️  URL 변경 타임아웃 (검색 실패)")
                # URL이 안 바뀌어도 페이지 소스 확인
                time.sleep(3)

        else:
            # 검색창 못 찾음 - 직접 URL로 이동
            print(f"[{device_name}] ⚠️  검색창을 찾지 못함")
            print(f"[{device_name}] → 검색 URL로 직접 이동")
            from urllib.parse import quote
            search_url = f"https://www.coupang.com/np/search?q={quote(keyword)}&channel=user"
            driver.get(search_url)
            print(f"[{device_name}] 검색 URL 접속: {search_url}")
            time.sleep(15)
            result['success'] = True
            result['method'] = 'direct_url'

        # 검색 페이지 도달 확인
        current_url = driver.current_url
        html = driver.page_source

        result['search_page'] = (
            'search-product' in html or
            '검색결과' in html or
            'traceId' in current_url or
            '/np/search' in current_url
        )

        if result['search_page']:
            print(f"[{device_name}] ✅ 검색 페이지 도달 성공")
            print(f"[{device_name}]    최종 URL: {current_url[:100]}...")
        else:
            print(f"[{device_name}] ❌ 검색 페이지 확인 실패")
            print(f"[{device_name}]    현재 URL: {current_url[:100]}...")

        return result

    except Exception as e:
        print(f"[{device_name}] ❌ 검색 중 에러: {e}")
        import traceback
        traceback.print_exc()
        return result


def is_enabled():
    """
    상호작용 기능 활성화 여부 확인

    환경변수 COUPANG_INTERACTION=1 로 활성화

    Returns:
        bool: 활성화 여부
    """
    import os
    return os.environ.get('COUPANG_INTERACTION', '0') == '1'
