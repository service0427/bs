"""
BrowserStack TLS 크롤러 설정
v2.14 - DB 중심 아키텍처
"""

import os

# ==========================================
# BrowserStack 인증
# ==========================================
BROWSERSTACK_USERNAME = os.environ.get('BROWSERSTACK_USERNAME', 'bsuser_wHW2oU')
BROWSERSTACK_ACCESS_KEY = os.environ.get('BROWSERSTACK_ACCESS_KEY', 'fuymXXoQNhshiN5BsZhp')
BROWSERSTACK_HUB = 'https://hub-cloud.browserstack.com/wd/hub'

# BrowserStack 프로젝트 설정
BROWSERSTACK_PROJECT_NAME = 'Coupang TLS Crawler'
BROWSERSTACK_BUILD_NAME = 'TLS Collection'

# ==========================================
# 디렉토리 경로
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
FINGERPRINTS_DIR = os.path.join(DATA_DIR, 'fingerprints')  # 레거시 (일부 파일에서 사용)
TLS_DIR = os.path.join(DATA_DIR, 'tls')

# ==========================================
# 크롤링 설정
# ==========================================
COOKIE_VALID_DURATION = 600  # 10분 (레거시, v2.14에서 미사용)

CRAWL_CONFIG = {
    'timeout': 30,
    'max_workers': 5,
    'delay_between_requests': 0.5,
    'allow_redirects': True
}

# ==========================================
# 대상 URL
# ==========================================
TARGET_URLS = {
    'main': 'https://www.coupang.com/',
    'search': 'https://www.coupang.com/np/search?q={keyword}&page={page}'
}

# ==========================================
# 헬퍼 함수
# ==========================================

def ensure_directories():
    """필요한 디렉토리 생성"""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FINGERPRINTS_DIR, exist_ok=True)
    os.makedirs(TLS_DIR, exist_ok=True)


def get_device_identifier(device_name, browser, os_version):
    """
    디바이스 + 브라우저 + OS 버전으로 고유 식별자 생성 (레거시)

    Args:
        device_name: 디바이스 이름
        browser: 브라우저 이름
        os_version: OS 버전

    Returns:
        str: 안전한 식별자
    """
    identifier = f"{device_name}_{browser}_{os_version}"
    safe_identifier = identifier.replace(' ', '_').replace('/', '_').replace('.', '_')
    return safe_identifier


def get_device_fingerprint_dir(device_name, browser=None, os_version=None):
    """
    디바이스 fingerprint 디렉토리 반환 (레거시)

    v2.14에서는 get_tls_dir() 사용 권장

    Args:
        device_name: 디바이스 이름
        browser: 브라우저 이름 (옵션)
        os_version: OS 버전 (옵션)

    Returns:
        str: fingerprint 디렉토리 경로
    """
    if browser and os_version:
        identifier = get_device_identifier(device_name, browser, os_version)
    else:
        identifier = device_name.replace(' ', '_').replace('/', '_').replace('.', '_')

    return os.path.join(FINGERPRINTS_DIR, identifier)


def get_tls_category(device_name):
    """
    디바이스명에서 카테고리 추출

    Args:
        device_name: "Samsung Galaxy S25", "iPhone 17" 등

    Returns:
        str: "Samsung", "iPhone", "Google" 등
    """
    device_lower = device_name.lower()

    if 'samsung' in device_lower or 'galaxy' in device_lower:
        return 'Samsung'
    elif 'iphone' in device_lower:
        return 'iPhone'
    elif 'google' in device_lower or 'pixel' in device_lower:
        return 'Google'
    elif 'xiaomi' in device_lower:
        return 'Xiaomi'
    elif 'oneplus' in device_lower:
        return 'OnePlus'
    elif 'oppo' in device_lower:
        return 'Oppo'
    elif 'vivo' in device_lower:
        return 'Vivo'
    else:
        return 'Other'


def normalize_device_for_tls(device_name):
    """
    디바이스명 정규화 (TLS 디렉토리용)

    "Samsung Galaxy S25" → "S25"
    "iPhone 17 Pro Max" → "17_Pro_Max"
    "Google Pixel 8 Pro" → "Pixel_8_Pro"

    Args:
        device_name: 디바이스 이름

    Returns:
        str: 정규화된 모델명
    """
    if 'Samsung Galaxy' in device_name:
        model = device_name.replace('Samsung Galaxy ', '')
    elif 'iPhone' in device_name:
        model = device_name.replace('iPhone ', '')
    elif 'Google Pixel' in device_name:
        model = device_name.replace('Google ', '')
    else:
        model = device_name

    return model.replace(' ', '_')


def normalize_browser_for_tls(browser):
    """
    브라우저명 단축 (TLS 디렉토리용)

    "samsung" → "Samsung"
    "chrome" → "Chrome"
    "safari" → "Safari"
    "android" → "Android"

    Args:
        browser: 브라우저 키 (mobile_real_devices.py의 browser_key)

    Returns:
        str: 단축된 브라우저명
    """
    browser_lower = browser.lower()

    mapping = {
        'samsung': 'Samsung',
        'chrome': 'Chrome',
        'safari': 'Safari',
        'iphone': 'Safari',  # iPhone = Safari
        'android': 'Android',
        'chromium': 'Chromium',
        'firefox': 'Firefox',
        'ipad': 'Safari'
    }

    return mapping.get(browser_lower, browser.capitalize())


def get_tls_dir(device_name, browser, os_version=None):
    """
    TLS 전용 디렉토리 경로 반환

    구조: data/tls/{category}/{model_browser_version}/

    예시:
    - Samsung Galaxy S25, samsung, 13.0
      → data/tls/Samsung/S25_Samsung_13_0/

    - iPhone 17, safari, 18.6
      → data/tls/iPhone/17_Safari_18_6/

    Args:
        device_name: 디바이스 이름
        browser: 브라우저 키 (samsung, chrome, safari 등)
        os_version: OS 버전 (None이면 생략)

    Returns:
        str: TLS 디렉토리 경로
    """
    category = get_tls_category(device_name)
    model = normalize_device_for_tls(device_name)
    browser_short = normalize_browser_for_tls(browser)

    # 식별자 생성
    if os_version:
        os_safe = os_version.replace('.', '_').replace('/', '_')
        identifier = f"{model}_{browser_short}_{os_safe}"
    else:
        identifier = f"{model}_{browser_short}"

    # 카테고리 디렉토리 생성
    category_dir = os.path.join(TLS_DIR, category)
    os.makedirs(category_dir, exist_ok=True)

    # TLS 디렉토리 반환
    tls_path = os.path.join(category_dir, identifier)
    os.makedirs(tls_path, exist_ok=True)

    return tls_path
