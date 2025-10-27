# BrowserStack TLS Crawler

BrowserStack 실기기에서 TLS fingerprint와 쿠키를 수집하여 curl-cffi JA3 방식으로 쿠팡을 크롤링하는 시스템

## ✨ 주요 특징

- ✅ **JA3 TLS Fingerprint**: 실제 디바이스의 TLS 그대로 재현
- ✅ **BoringSSL 사용**: curl-cffi의 BoringSSL로 완벽한 호환
- ✅ **자동 쿠키 관리**: 5분 유효성 검증 + 자동 재수집
- ✅ **인터랙티브 선택**: 4단계 디바이스 선택 UI
- ✅ **상품 자동 분류**: 랭킹 vs 광고 상품 구분

## 🚀 빠른 시작

### 설치

```bash
# Python 3.9+ 필요
cd /var/www/html/browserstack
source venv/bin/activate

# curl-cffi 최신 버전 (JA3 지원)
pip install --upgrade curl-cffi
```

### 기본 실행

```bash
# 1페이지 크롤링
python main.py --keyword "아이폰"

# 다중 페이지 크롤링
python main.py --keyword "아이폰" --start 1 --end 3
```

첫 실행 시:
1. 디바이스 선택 (4단계)
2. TLS + 쿠키 자동 수집
3. 크롤링 시작

## 📋 사용법

### 명령어

```bash
# 기본 (1페이지)
python main.py --keyword "아이폰"

# 다중 페이지
python main.py --keyword "갤럭시" --start 1 --end 5

# 단일 페이지 지정
python main.py --keyword "맥북" --page 2
```

### 옵션

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--keyword`, `-k` | 검색 키워드 | `--keyword "아이폰"` |
| `--start`, `-s` | 시작 페이지 | `--start 1` |
| `--end`, `-e` | 종료 페이지 | `--end 3` |
| `--page`, `-p` | 단일 페이지 | `--page 2` |

## 🔧 핵심 개념

### 1. JA3 TLS Fingerprint 방식

**수집된 fingerprint를 그대로 사용합니다:**

```python
response = requests.get(
    url,
    ja3=ja3,                # TLS fingerprint
    akamai=akamai,          # HTTP/2 fingerprint
    extra_fp=extra_fp,      # 추가 설정
    headers=headers,
    cookies=cookies
)
```

**장점:**
- ✅ 실제 디바이스 TLS 완벽 재현
- ✅ GREASE, cipher 순서 그대로
- ✅ HTTP/2 에러 없음
- ✅ 수동 변환 불필요

### 2. 쿠키 관리

- **유효 시간:** 5분 (300초)
- **전략:** 원본 쿠키 사용 (수정 금지)
- **자동 재수집:** 만료 시 자동으로 재수집
- **필수 쿠키:** `_abck`, `PCID`, `sid`

### 3. 4단계 디바이스 선택

```
1. Category (Galaxy / iPhone / Other)
   └─ 2. Device Model (Samsung Galaxy S22 Ultra 등)
       └─ 3. Browser (Samsung Browser, Chrome 등)
           └─ 4. OS Version (Android 12, iOS 16 등)
```

이전 선택값이 기본값으로 표시됩니다.

## 📁 프로젝트 구조

```
/var/www/html/browserstack/
├── main.py                      # 메인 실행 파일
├── lib/                         # 핵심 모듈
│   ├── device_selector.py       # 디바이스 선택
│   ├── tls_builder.py           # TLS 로드/검증
│   └── custom_tls_crawler.py    # JA3 크롤러
├── collectors/
│   └── dynamic_collector.py     # BrowserStack 데이터 수집
├── data/
│   ├── fingerprints/            # 유효한 데이터만
│   │   ├── Samsung_Galaxy_S21_Ultra/
│   │   │   ├── cookies.json
│   │   │   ├── headers.json
│   │   │   ├── metadata.json
│   │   │   └── tls_fingerprint.json
│   │   └── ...
│   └── fingerprints_backup/     # 백업
├── product_extractor.py         # 상품 추출
└── config.py                    # 설정
```

## 📊 실행 결과

```
✅ 성공 사례: Samsung Galaxy S21 Ultra + JA3

[크롤링 결과]
  - 검색 키워드: 아이폰
  - 크롤링 페이지: 1 ~ 1 (1/1개 성공)
  - 총 랭킹 상품: 32개
  - 총 광고 상품: 22개

[적용된 TLS Fingerprint]
  - JA3: 771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171...
  - JA3 Hash: aa369a5a417c59d0f846c41f849417f2
  - Akamai: 1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p
  - Signature Algorithms: 8개
  - HTTP/2 Priority: weight=256, exclusive=1
```

## 🛠️ 기술 스택

- **Python:** 3.9+
- **curl-cffi:** 0.13.0+ (JA3 지원)
- **Selenium:** 4.x
- **BrowserStack:** Real Device Testing
- **BeautifulSoup4:** HTML 파싱

## 📝 데이터 구조

### fingerprints/{device_name}/

```
├── cookies.json           # Selenium 쿠키 리스트
├── headers.json           # HTTP 헤더
├── metadata.json          # 수집 시간, 유효성 정보
└── tls_fingerprint.json   # TLS + HTTP/2 fingerprint
```

### tls_fingerprint.json 구조

```json
{
  "tls": {
    "ja3": "771,4865-4866-...",
    "ja3_hash": "aa369a5a417c59d0f846c41f849417f2",
    "ciphers": [...],
    "extensions": [...]
  },
  "http2": {
    "akamai_fingerprint": "1:65536;2:0;4:6291456;...",
    "sent_frames": [...]
  }
}
```

## ⚙️ 환경 변수

```bash
export BROWSERSTACK_USERNAME="your_username"
export BROWSERSTACK_ACCESS_KEY="your_access_key"
```

또는 `.env` 파일:

```env
BROWSERSTACK_USERNAME=your_username
BROWSERSTACK_ACCESS_KEY=your_access_key
```

## 🔍 트러블슈팅

### TLS 정보 수집 실패

**증상:** `TLS 정보 파일이 없습니다` 에러

**원인:** iPhone/Safari에서 TLS 페이지 파싱 실패

**해결:**
1. Samsung 디바이스 선택
2. 디바이스 재선택

### HTTP/2 프로토콜 에러

**증상:** `HTTP/2 stream was not closed cleanly`

**해결:** 이미 `ja3 + akamai + extra_fp` 방식으로 해결됨

### 쿠키 만료

**증상:** 5분 경과 후 크롤링 실패

**해결:** 자동으로 재수집됨 (수동 개입 불필요)

## ⚠️ 주의사항

### ✅ 해야 할 것
- JA3 방식 사용
- 원본 쿠키 유지
- TLS 검증 로직 유지

### ❌ 하지 말아야 할 것
- 수동 cipher 변환 (`cipher_mapping`)
- impersonate 방식 사용 (테스트만)
- 쿠키 업데이트 (Set-Cookie)
- TLS 검증 생략

자세한 내용은 `CLAUDE.md` 참조

## 📚 참고 문서

- **CLAUDE.md:** 개발자 가이드 (필수 정책)
- **curl-cffi 문서:** https://curl-cffi.readthedocs.io/en/stable/impersonate/customize.html
- **BrowserStack 문서:** https://www.browserstack.com/docs/automate/selenium

## 📄 라이선스

Private Project

---

**마지막 업데이트:** 2025-10-27
**버전:** 2.14 (IP/TLS 차단 검증 시스템)

## 📦 최신 업데이트 (v2.14)

- ✅ IP 기반 Rate Limiting 확인
- ✅ X25519MLKEM768 차단 패턴 분석
- ✅ 13개 검증된 디바이스 필터링
- ✅ IP 확인 기능 추가 (Step 0)
- ✅ 프로젝트 전체 정리 (PROJECT_OVERVIEW.md)
- ⏳ 차단 감지 및 로테이션 시스템 (구현 중)

자세한 내용: [PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
