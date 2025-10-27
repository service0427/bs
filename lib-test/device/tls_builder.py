"""
TLS 설정 빌더 모듈
fingerprint 데이터 로드 및 TLS cipher suite 변환
"""

import os
import json
import sys

# config 모듈 import (lib-test용)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# lib-test 내부 모듈 사용 (상대 경로)
import importlib.util
lib_test_settings = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'settings.py')
spec = importlib.util.spec_from_file_location("settings", lib_test_settings)
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)
get_device_fingerprint_dir = settings.get_device_fingerprint_dir
get_device_identifier = settings.get_device_identifier
get_tls_dir = settings.get_tls_dir


def load_fingerprint_data(device_name, browser, os_version, worker_id=None):
    """
    수집된 fingerprint 데이터 로드

    Args:
        device_name: 디바이스 이름
        browser: 브라우저 이름 (safari, chrome, chromium 등)
        os_version: OS 버전 (예: "13.0", "18.6")
        worker_id: Worker ID (병렬 크롤링용, None이면 원본 사용)
    """
    # 디바이스 + 브라우저 + OS 버전으로 고유 디렉토리 생성
    fingerprint_dir = get_device_fingerprint_dir(device_name, browser, os_version)

    # 파일 경로
    # worker_id가 있으면 패킷용 쿠키 파일 사용
    if worker_id is not None:
        cookies_file = os.path.join(fingerprint_dir, f'cookies_packet_{worker_id}.json')
        original_cookies_file = os.path.join(fingerprint_dir, 'cookies.json')

        # 기존 패킷 파일 삭제 (항상 신선한 원본에서 복사)
        if os.path.exists(cookies_file):
            os.remove(cookies_file)
            print(f"  [Worker {worker_id}] 기존 패킷 쿠키 삭제")

        # 원본에서 새로 복사
        import shutil
        shutil.copy(original_cookies_file, cookies_file)
        print(f"  [Worker {worker_id}] 원본에서 새로 복사 → cookies_packet_{worker_id}.json")
    else:
        cookies_file = os.path.join(fingerprint_dir, 'cookies.json')

    headers_file = os.path.join(fingerprint_dir, 'headers.json')
    metadata_file = os.path.join(fingerprint_dir, 'metadata.json')

    # TLS 파일은 전용 디렉토리에서 로드 (공유)
    tls_dir = get_tls_dir(device_name, browser, os_version)
    tls_file = os.path.join(tls_dir, 'tls_fingerprint.json')

    # TLS 파일 존재 확인
    if not os.path.exists(tls_file):
        raise FileNotFoundError(
            f"\n❌ TLS 정보 파일이 없습니다: {tls_file}\n"
            f"   TLS 정보가 정상적으로 수집되지 않았습니다.\n"
            f"   디바이스를 다시 선택하여 TLS 정보를 재수집하세요.\n"
        )

    # 데이터 로드
    data = {}

    with open(cookies_file, 'r', encoding='utf-8') as f:
        data['cookies'] = json.load(f)

    with open(headers_file, 'r', encoding='utf-8') as f:
        data['headers'] = json.load(f)

    with open(metadata_file, 'r', encoding='utf-8') as f:
        data['metadata'] = json.load(f)

    with open(tls_file, 'r', encoding='utf-8') as f:
        data['tls'] = json.load(f)

    # TLS 정보 검증
    if not data['tls'].get('tls') or not data['tls'].get('tls', {}).get('ciphers'):
        raise ValueError(
            f"\n❌ TLS 정보가 비정상적입니다.\n"
            f"   필수 필드(tls.ciphers)가 없습니다.\n"
            f"   디바이스를 다시 선택하여 TLS 정보를 재수집하세요.\n"
        )

    # 경과 시간 계산 및 표시
    from datetime import datetime
    collected_at_str = data['metadata'].get('collected_at')
    if collected_at_str:
        collected_at = datetime.fromisoformat(collected_at_str)
        elapsed = (datetime.now() - collected_at).total_seconds()
        print(f"\n{'='*60}")
        print(f"🕐 쿠키 경과 시간")
        print(f"{'='*60}")
        print(f"  수집 시각: {collected_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  현재 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  경과 시간: {int(elapsed)}초 ({int(elapsed/60)}분 {int(elapsed%60)}초)")
        print(f"{'='*60}\n")

    return data


def build_cipher_string(tls_info):
    """TLS Cipher Suite 문자열 생성"""
    ciphers = tls_info.get('tls', {}).get('ciphers', [])

    # TLS 암호화 스위트 매핑 테이블 (TLS_* → OpenSSL 포맷)
    cipher_mapping = {
        'TLS_AES_128_GCM_SHA256': 'TLS_AES_128_GCM_SHA256',
        'TLS_AES_256_GCM_SHA384': 'TLS_AES_256_GCM_SHA384',
        'TLS_CHACHA20_POLY1305_SHA256': 'TLS_CHACHA20_POLY1305_SHA256',
        'TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256': 'ECDHE-ECDSA-AES128-GCM-SHA256',
        'TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256': 'ECDHE-RSA-AES128-GCM-SHA256',
        'TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384': 'ECDHE-ECDSA-AES256-GCM-SHA384',
        'TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384': 'ECDHE-RSA-AES256-GCM-SHA384',
        'TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256': 'ECDHE-ECDSA-CHACHA20-POLY1305',
        'TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256': 'ECDHE-RSA-CHACHA20-POLY1305',
        'TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA': 'ECDHE-RSA-AES128-SHA',
        'TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA': 'ECDHE-RSA-AES256-SHA',
        'TLS_RSA_WITH_AES_128_GCM_SHA256': 'AES128-GCM-SHA256',
        'TLS_RSA_WITH_AES_256_GCM_SHA384': 'AES256-GCM-SHA384',
        'TLS_RSA_WITH_AES_128_CBC_SHA': 'AES128-SHA',
        'TLS_RSA_WITH_AES_256_CBC_SHA': 'AES256-SHA',
    }

    openssl_ciphers = []
    for cipher in ciphers:
        # GREASE 값 제외
        if 'GREASE' in cipher or '0x' in cipher:
            continue
        if cipher in cipher_mapping:
            openssl_ciphers.append(cipher_mapping[cipher])

    return ':'.join(openssl_ciphers)


def build_custom_headers(tls_info, base_headers):
    """HTTP/2 헤더 정보를 기반으로 헤더 구성"""
    http2_info = tls_info.get('http2', {})
    sent_frames = http2_info.get('sent_frames', [])

    custom_headers = {}

    for frame in sent_frames:
        if frame.get('frame_type') == 'HEADERS':
            headers = frame.get('headers', [])
            for header in headers:
                if ':' in header and not header.startswith(':'):
                    parts = header.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        custom_headers[key] = value

    final_headers = base_headers.copy()
    final_headers.update(custom_headers)

    return final_headers
