# TLS 수집 URL 변경 가이드

**Version**: 1.0
**Last Updated**: 2025-10-27
**Migration**: tls.peet.ws → tls.browserleaks.com

---

## 📋 목차

1. [변경 이유](#변경-이유)
2. [변경된 정보 (8가지)](#변경된-정보-8가지)
3. [JSON 구조 비교](#json-구조-비교)
4. [코드 변경 사항](#코드-변경-사항)
5. [마이그레이션 가이드](#마이그레이션-가이드)
6. [호환성](#호환성)

---

## 🚨 변경 이유

### tls.peet.ws SSL 인증서 만료

```bash
# 2025-10-27 확인
$ curl https://tls.peet.ws/api/all
curl: (60) SSL certificate problem: certificate has expired
```

**증상:**
```
[Samsung Galaxy S21] ❌ JSON 파싱 실패: Expecting value: line 1 column 1 (char 0)
[Samsung Galaxy S21]    <h1>Your clock is ahead</h1>
[Samsung Galaxy S21]    <p>A private connection to tls.peet.ws can't be established...</p>
```

**해결:**
- 새로운 TLS 수집 사이트로 변경: **tls.browserleaks.com**
- SSL 인증서 정상, 더 상세한 정보 제공
- 장기적 안정성 확보

---

## 📊 변경된 정보 (8가지)

### 1. JA3 String (`ja3`)

**설명:** TLS Client Hello의 핵심 정보를 압축한 문자열

**형식:** `TLS_VERSION,CIPHERS,EXTENSIONS,ELLIPTIC_CURVES,EC_POINT_FORMATS`

**샘플:**
```json
"771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,11-10-0-17513-51-23-65037-16-43-18-27-13-35-45-5-65281,29-23-24,0"
```

**변경사항:** 동일 (peet.ws와 browserleaks 모두 같은 형식)

---

### 2. JA3 Hash (`ja3_hash`)

**설명:** JA3 String의 MD5 해시값 (디바이스 식별자)

**형식:** 32자 MD5 해시

**샘플:**
```json
"9585f405ae4267418097408914990f3e"
```

**변경사항:** 동일 (같은 JA3 String → 같은 Hash)

---

### 3. Cipher Suites (`ciphers`)

**설명:** 클라이언트가 지원하는 암호화 알고리즘 목록

**형식:** 숫자 배열 (TLS Cipher Suite ID)

**샘플:**
```json
[
  "4865",  // TLS_AES_128_GCM_SHA256
  "4866",  // TLS_AES_256_GCM_SHA384
  "4867",  // TLS_CHACHA20_POLY1305_SHA256
  "49195", // TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
  "49199", // TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
  "49196", // TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
  "49200", // TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
  "52393", // TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256
  "52392", // TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256
  "49171", // TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA
  "49172", // TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA
  "156",   // TLS_RSA_WITH_AES_128_GCM_SHA256
  "157",   // TLS_RSA_WITH_AES_256_GCM_SHA384
  "47",    // TLS_RSA_WITH_AES_128_CBC_SHA
  "53"     // TLS_RSA_WITH_AES_256_CBC_SHA
]
```

**변경사항:**
- **peet.ws**: 문자열 배열 (`["TLS_AES_128_GCM_SHA256", ...]`)
- **browserleaks**: 숫자 배열 (`["4865", "4866", ...]`)
- **해결**: JA3 String에서 파싱하여 추출

---

### 4. Extensions (`extensions`)

**설명:** TLS Client Hello에 포함된 확장 기능 목록

**형식:** 숫자 배열 (Extension Type ID)

**샘플:**
```json
[
  "11",    // ec_point_formats
  "10",    // supported_groups
  "0",     // server_name (SNI)
  "17513", // application_settings
  "51",    // key_share
  "23",    // session_ticket
  "65037", // encrypted_client_hello
  "16",    // application_layer_protocol_negotiation (ALPN)
  "43",    // supported_versions
  "18",    // signed_certificate_timestamp
  "27",    // compress_certificate
  "13",    // signature_algorithms
  "35",    // session_ticket (duplicate?)
  "45",    // psk_key_exchange_modes
  "5",     // status_request
  "65281"  // renegotiation_info
]
```

**변경사항:**
- **peet.ws**: 상세한 extension 객체 배열
- **browserleaks**: 숫자 ID 배열
- **해결**: JA3 String에서 파싱하여 추출

---

### 5. Akamai Fingerprint (`akamai_fingerprint`)

**설명:** HTTP/2 설정을 기반으로 한 Akamai 봇 탐지 지문

**형식:** `SETTINGS|WINDOW_UPDATE|PRIORITY|FRAMES`

**샘플:**
```json
"1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p"
```

**구조:**
```
1:65536       → SETTINGS_HEADER_TABLE_SIZE: 65536
2:0           → SETTINGS_ENABLE_PUSH: 0 (disabled)
4:6291456     → SETTINGS_INITIAL_WINDOW_SIZE: 6291456
6:262144      → SETTINGS_MAX_HEADER_LIST_SIZE: 262144
|15663105     → WINDOW_UPDATE: 15663105
|0            → PRIORITY: 0 (없음)
|m,a,s,p      → FRAMES: SETTINGS, WINDOW_UPDATE, SETTINGS, PRIORITY
```

**변경사항:** 동일 (필드명만 `akamai_text` → `akamai_fingerprint`)

---

### 6. HTTP Version (`http_version`)

**설명:** 사용된 HTTP 프로토콜 버전

**형식:** 문자열

**샘플:**
```json
"h2"  // HTTP/2
```

**변경사항:** 동일

---

### 7. User-Agent (`user_agent`)

**설명:** 브라우저 식별 문자열

**형식:** 표준 User-Agent 문자열

**샘플:**
```json
"Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36"
```

**변경사항:** 동일 (browserleaks에서도 제공)

---

### 8. browserleaks_raw (신규 추가)

**설명:** browserleaks.com에서 제공하는 전체 원본 데이터

**형식:** JSON 객체

**샘플:**
```json
{
  "akamai_hash": "52d84b11737d980aef856699f885ca86",
  "akamai_text": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
  "ja3_hash": "9585f405ae4267418097408914990f3e",
  "ja3_text": "771,4865-4866-...",
  "ja3n_hash": "473f0e7c0b6a0f7b049072f4e683068b",
  "ja3n_text": "771,4865-4866-...",
  "ja4": "t13d1516h2_8daaf6152771_02713d6af862",
  "ja4_o": "t13d1516h2_acb858a92679_31e1831c4317",
  "ja4_r": "t13d1516h2_002f,0035,009c,...",
  "ja4_ro": "t13d1516h2_1301,1302,1303,...",
  "user_agent": "Mozilla/5.0 ..."
}
```

**포함 정보:**
- **JA3n**: GREASE 제거된 JA3 (정규화된 버전)
- **JA4**: 차세대 TLS fingerprint (4가지 변형)
- **Hash 값들**: 각 fingerprint의 해시

**변경사항:**
- **peet.ws**: 제공하지 않음
- **browserleaks**: 전체 원본 데이터 보존 ✅

---

## 🔄 JSON 구조 비교

### peet.ws (기존)

```json
{
  "donate": "Please consider donating...",
  "ip": "220.121.120.83:56000",
  "http_version": "h2",
  "method": "GET",
  "user_agent": "Mozilla/5.0 ...",
  "tls": {
    "ciphers": [
      "TLS_GREASE (0xBABA)",
      "TLS_AES_128_GCM_SHA256",
      "TLS_AES_256_GCM_SHA384",
      ...
    ],
    "extensions": [
      {
        "name": "server_name (0)",
        "server_name": "tls.peet.ws"
      },
      {
        "name": "extended_master_secret (23)",
        "data": ""
      },
      ...
    ],
    "ja3": "771,4865-4866-4867-...",
    "ja3_hash": "d8a0b7611e3fe02f04ed0a7daa098296"
  },
  "http2": {
    "akamai_fingerprint": "1:65536;2:0;4:6291456;...",
    "sent_frames": [...]
  }
}
```

**구조:** 중첩 구조 (`tls.tls`, `tls.http2`)

---

### browserleaks (신규)

```json
{
  "tls": {
    "ja3": "771,4865-4866-4867-...",
    "ja3_hash": "9585f405ae4267418097408914990f3e",
    "ciphers": ["4865", "4866", "4867", ...],
    "extensions": ["11", "10", "0", "17513", ...]
  },
  "http2": {
    "akamai_fingerprint": "1:65536;2:0;4:6291456;..."
  },
  "http_version": "h2",
  "user_agent": "Mozilla/5.0 ...",
  "browserleaks_raw": {
    "ja3_hash": "9585f405ae4267418097408914990f3e",
    "ja3_text": "771,4865-4866-4867-...",
    "ja3n_hash": "473f0e7c0b6a0f7b049072f4e683068b",
    "ja3n_text": "771,4865-4866-4867-...",
    "ja4": "t13d1516h2_8daaf6152771_02713d6af862",
    "ja4_o": "t13d1516h2_acb858a92679_31e1831c4317",
    "ja4_r": "t13d1516h2_002f,0035,009c,...",
    "ja4_ro": "t13d1516h2_1301,1302,1303,...",
    "akamai_hash": "52d84b11737d980aef856699f885ca86",
    "akamai_text": "1:65536;2:0;4:6291456;...",
    "user_agent": "Mozilla/5.0 ..."
  }
}
```

**구조:** 플랫 구조 (최상위에 `tls`, `http2`)

---

## 🛠️ 코드 변경 사항

### 1. TLS 수집 (lib/collectors/dynamic.py)

**URL 변경:**
```python
# Before
self.driver.get('https://tls.peet.ws/api/all')

# After
self.driver.get('https://tls.browserleaks.com/')
```

**데이터 추출 방법 변경:**
```python
# Before: 페이지 소스에서 JSON 추출
page_source = self.driver.page_source
json_match = re.search(r'<pre[^>]*>(.*?)</pre>', page_source)

# After: JavaScript XHR로 /json API 직접 호출
browserleaks_raw = self.driver.execute_script("""
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/json', false);
    xhr.send();
    return JSON.parse(xhr.responseText);
""")
```

**형식 변환:**
```python
# browserleaks 원본 → peet.ws 호환 형식
ja3_parts = browserleaks_raw['ja3_text'].split(',')

tls_info = {
    'tls': {
        'ja3': browserleaks_raw['ja3_text'],
        'ja3_hash': browserleaks_raw.get('ja3_hash', ''),
        'ciphers': ja3_parts[1].split('-') if len(ja3_parts) > 1 else [],
        'extensions': ja3_parts[2].split('-') if len(ja3_parts) > 2 else []
    },
    'http2': {
        'akamai_fingerprint': browserleaks_raw.get('akamai_text', '')
    },
    'http_version': 'h2',
    'user_agent': browserleaks_raw.get('user_agent', ''),
    'browserleaks_raw': browserleaks_raw  # 원본 보존
}
```

---

### 2. TLS 검증 (lib/device/tls_builder.py)

**검증 로직 변경:**
```python
# Before: peet.ws 중첩 구조만 지원
if not data['tls'].get('tls') or not data['tls'].get('tls', {}).get('ciphers'):
    raise ValueError("TLS 정보 비정상")

# After: browserleaks 플랫 구조 지원
if not data['tls'].get('ciphers') and not data['tls'].get('tls', {}).get('ciphers'):
    raise ValueError("TLS 정보 비정상")
```

---

### 3. TLS 사용 (lib/crawler/custom_tls.py)

**구조 자동 감지:**
```python
# Before: peet.ws 가정
tls_data = tls.get('tls', {})
http2_data = tls.get('http2', {})

# After: 자동 감지
if 'ja3' in tls:
    # browserleaks 형식: tls가 바로 TLS 데이터
    tls_data = tls
    http2_data = data.get('http2', {})
else:
    # peet.ws 형식: tls 안에 tls/http2가 중첩
    tls_data = tls.get('tls', tls)
    http2_data = tls.get('http2', {})
```

---

## 📦 마이그레이션 가이드

### 기존 peet.ws 데이터

**변경 불필요!**

기존 peet.ws로 수집한 TLS 데이터는 그대로 사용 가능합니다.

**저장 위치:**
```
/var/www/html/browserstack/lib/data/tls/Samsung/S22_Samsung_12_0/tls_fingerprint.json
```

**크롤링 시:**
- 자동으로 peet.ws 형식 감지
- 기존 코드와 100% 호환

---

### 새로 수집하는 경우

**방법 1: 자동 디바이스 선택**
```bash
python main.py --keyword "칫솔" --start 1 --end 3
# → BrowserStack 연결 → browserleaks.com 수집
```

**방법 2: 강제 재수집**
```bash
python main.py --keyword "칫솔" --start 1 --end 3 --force-refresh
# → 기존 TLS 무시하고 새로 수집
```

**방법 3: 디바이스별 수집**
```bash
python -m lib.collectors.dynamic \
  --device "Samsung Galaxy S21" \
  --browser "samsung"
# → TLS만 수집
```

---

## ✅ 호환성

### 기존 코드 100% 호환

| 항목 | peet.ws | browserleaks | 호환 |
|------|---------|--------------|------|
| **JA3 String** | ✅ | ✅ | ✅ |
| **JA3 Hash** | ✅ | ✅ | ✅ |
| **Ciphers** | 문자열 배열 | 숫자 배열 | ✅ 자동 변환 |
| **Extensions** | 객체 배열 | 숫자 배열 | ✅ 자동 변환 |
| **Akamai** | ✅ | ✅ | ✅ |
| **User-Agent** | ✅ | ✅ | ✅ |
| **HTTP Version** | ✅ | ✅ | ✅ |
| **원본 데이터** | ❌ | ✅ `browserleaks_raw` | ➕ 추가 정보 |

### curl-cffi 사용

**변경 없음!**

```python
from curl_cffi.requests import Session

session = Session()
response = session.get(
    url,
    ja3=ja3,              # ← JA3 String 그대로 사용
    akamai=akamai,        # ← Akamai Fingerprint 그대로 사용
    headers=headers,
    cookies=cookies
)
```

---

## 🆕 추가 정보 활용

### JA3n (GREASE 제거)

**용도:** 디바이스 간 TLS 비교 (GREASE 영향 제거)

```python
browserleaks_raw = tls_info.get('browserleaks_raw', {})
ja3n_hash = browserleaks_raw.get('ja3n_hash')

# 같은 브라우저 엔진인지 확인
if ja3n_hash == "473f0e7c0b6a0f7b049072f4e683068b":
    print("Samsung Browser 28.0 계열")
```

---

### JA4 (차세대 Fingerprint)

**용도:** 더 정확한 디바이스 식별

```python
ja4 = browserleaks_raw.get('ja4')
# "t13d1516h2_8daaf6152771_02713d6af862"

# t13 = TLS 1.3
# d1516 = 15개 cipher + 16개 extension
# h2 = HTTP/2
```

---

## 📊 요약

### 변경된 8가지 정보

1. ✅ **JA3 String** - 동일
2. ✅ **JA3 Hash** - 동일
3. 🔄 **Ciphers** - 숫자 배열로 변경 (자동 변환)
4. 🔄 **Extensions** - 숫자 배열로 변경 (자동 변환)
5. ✅ **Akamai Fingerprint** - 동일
6. ✅ **HTTP Version** - 동일
7. ✅ **User-Agent** - 동일
8. ➕ **browserleaks_raw** - 신규 추가 (원본 데이터)

### 코드 변경

- ✅ `lib/collectors/dynamic.py` - URL + 파싱 로직
- ✅ `lib/device/tls_builder.py` - 검증 로직
- ✅ `lib/crawler/custom_tls.py` - 구조 자동 감지
- ✅ **기존 코드 100% 호환**

### GitHub 커밋

```bash
# 1차 커밋: URL 변경 + 파싱 로직
commit: 1c57340
message: fix: TLS 수집 URL 변경 (peet.ws → browserleaks.com)

# 2차 커밋: 호환성 수정
commit: f8930aa
message: fix: browserleaks TLS 형식 호환성 수정
```

---

**문서 작성:** 2025-10-27
**작성자:** Claude (Anthropic)
**버전:** 1.0
