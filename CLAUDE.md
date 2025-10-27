# Claude Development Guide - BrowserStack TLS Crawler
# Claude 개발 가이드 - BrowserStack TLS 크롤러

**Version**: 2.13
**Last Updated**: 2025-10-25

---

## 🎯 Quick Start

```bash
# 1. 크롤링 실행 (디바이스 자동 선택)
python main.py --keyword "칫솔" --start 1 --end 3

# 2. 새 디바이스 TLS 수집
python -m lib.collectors.dynamic --device "Samsung Galaxy S23" --browser "android"

# 3. TLS variance 테스트
python scripts/test_tls_variance.py --device "Samsung Galaxy Tab S8" --iterations 5
```

---

## 🚨 Critical Rules (읽지 않으면 실패!)

### 1️⃣ **반드시 통과하는 브라우저만 사용**

✅ **사용 가능 (검증됨)**:
- **Samsung Browser** (Galaxy 시리즈) - 1순위 추천 ⭐
- **iPhone Safari** (iOS 16/17/18)
- **iPhone Chrome** (iOS 26)

❌ **절대 사용 금지 (차단됨)**:
- **Android Chrome** (모든 Galaxy/Pixel 디바이스)

**이유**: X25519MLKEM768 포스트 양자 암호화 extension 탐지
→ 상세: [docs/TLS_BLOCKING.md](docs/TLS_BLOCKING.md)

### 2️⃣ **Session 객체 필수 사용**

```python
# ✅ 올바른 방식
from curl_cffi.requests import Session

class CustomTLSCrawler:
    def __init__(self):
        self.session = Session()  # ← 페이지 1~N까지 재사용

    def crawl_pages(self, start, end):
        for page in range(start, end + 1):
            # 같은 Session = GREASE 일관성 = 정상 브라우저
            response = self.session.get(url, ja3=ja3, ...)
```

❌ **잘못된 방식**: 매 페이지 새 Session 생성 = GREASE 변동 = 봇 신호!

**이유**: GREASE는 세션 내에서 고정되어야 함
→ 상세: [docs/SESSION_STRATEGY.md](docs/SESSION_STRATEGY.md)

### 3️⃣ **JA3 문자열만 전달 (Hash 계산 불필요)**

```python
# ✅ curl-cffi가 자동 처리
ja3_string = "771,4865-4866-4867-...,11-23-51-...,29-23-24,0"
response = session.get(url, ja3=ja3_string, ...)  # 끝!
```

❌ **하지 않아도 되는 일**: JA3 Hash 계산, Cipher 직접 설정, TLS handshake 구성

**이유**: curl-cffi가 내부적으로 모두 처리
→ 상세: [docs/TLS_IMPLEMENTATION.md](docs/TLS_IMPLEMENTATION.md)

---

## 📚 Documentation Structure

이 문서는 핵심 요약입니다. 상세한 내용은 아래 문서를 참조하세요:

### Core Guides (필수 읽기)

1. **[TLS_BLOCKING.md](docs/TLS_BLOCKING.md)** - 차단 패턴 분석
   - X25519MLKEM768 탐지 원리
   - 브라우저별 차단 테스트 결과
   - 화이트리스트 디바이스

2. **[SESSION_STRATEGY.md](docs/SESSION_STRATEGY.md)** - 세션 유지 전략
   - PCID/sid 쿠키 관리
   - Session 객체 사용법
   - 다중 페이지 크롤링 성공 사례

3. **[FINGERPRINT_ROTATION.md](docs/FINGERPRINT_ROTATION.md)** - 기기 차단 우회 전략 ⭐ NEW!
   - TLS Fingerprint 로테이션 시스템
   - 동일 IP, 다양한 디바이스로 인식
   - 자동 Health Tracking & Cooldown
   - 쿠팡/네이버 타겟별 전략

4. **[TLS_IMPLEMENTATION.md](docs/TLS_IMPLEMENTATION.md)** - TLS 구현 상세
   - JA3 vs Akamai fingerprint
   - extra_fp 8가지 옵션
   - TLS Extensions 불변성

### Reference Guides (참조용)

5. **[CRAWLING_GUIDE.md](docs/CRAWLING_GUIDE.md)** - 실행 방법
   - 명령어 옵션
   - 디바이스 선택 플로우
   - 문제 해결 가이드

6. **[DATABASE.md](docs/DATABASE.md)** - 데이터베이스 설계
   - 9개 테이블 스키마 (config, fingerprint_health 추가)
   - 쿼리 패턴 20+ 예시
   - 데이터 흐름

7. **[VERSION_HISTORY.md](docs/VERSION_HISTORY.md)** - 변경 이력
   - v1.0 ~ v2.13
   - 주요 발견 및 수정 사항

---

## 🏗️ Project Structure

```
/var/www/html/browserstack/
├── CLAUDE.md                    # ← 이 파일 (핵심 요약)
├── main.py                      # 메인 실행 파일
├── lib/
│   ├── custom_tls_crawler.py    # JA3 기반 크롤러
│   ├── device_selector.py       # 디바이스 선택기
│   └── db/manager.py            # DB 관리
├── docs/                        # 📚 상세 문서
│   ├── TLS_BLOCKING.md
│   ├── SESSION_STRATEGY.md
│   ├── TLS_IMPLEMENTATION.md
│   ├── CRAWLING_GUIDE.md
│   ├── DATABASE.md
│   └── VERSION_HISTORY.md
├── scripts/
│   ├── test_random_devices.py
│   ├── test_akamai_cross.py
│   └── test_tls_variance.py
└── data/
    ├── fingerprints/            # TLS + 쿠키
    └── search_history/          # 크롤링 결과
```

---

## 💡 Key Concepts

### TLS Fingerprint = JA3 + Akamai

```python
# TLS fingerprint 수집 (BrowserStack 실기기)
tls_data = collect_from_browserstack()

# JA3 문자열 (변동: GREASE)
ja3 = tls_data['tls']['ja3']
# "771,4865-4866-...,11-23-51-...,29-23-24,0"

# Akamai fingerprint (안정: 고정값)
akamai = tls_data['http2']['akamai_fingerprint']
# "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p"

# 크롤링 시 사용
response = session.get(url, ja3=ja3, akamai=akamai, ...)
```

### Session = TLS 연결 + GREASE + 쿠키

```python
# Session 객체 = 실제 브라우저 세션
session = Session()

# 페이지 1: GREASE 랜덤 생성 + 첫 TLS handshake
r1 = session.get("page1", ja3=ja3, cookies=initial_cookies)

# 페이지 2~N: 같은 GREASE + TLS 연결 재사용
r2 = session.get("page2", ja3=ja3)  # cookies 자동 관리
r3 = session.get("page3", ja3=ja3)
```

### Database = 8 Tables

```sql
-- TLS 지문 (append-only)
tls_fingerprints  -- tls_data + http2_data (JSON)

-- 쿠키 (lifecycle tracking)
cookies           -- cookie_data (JSON)

-- 크롤링 결과 (session-based)
crawl_results     -- 세션 요약
crawl_details     -- 페이지별 상세
products          -- 상품 데이터

-- 분석용
tls_variance_samples  -- TLS variance test
device_selections     -- 마지막 선택
changelogs            -- 변경 이력
```

---

## 🔥 Common Mistakes (자주 하는 실수)

### ❌ Mistake 1: Android Chrome 사용
```python
device_config = {
    'device': 'Samsung Galaxy S23',
    'browser': 'android',  # ← Chrome! 차단됨!
}
```

✅ **해결**: Samsung Browser 사용
```python
device_config = {
    'device': 'Samsung Galaxy S23',
    'browser': 'samsung',  # ← Samsung Browser ✅
}
```

### ❌ Mistake 2: 매 페이지 새 Session
```python
for page in range(1, 11):
    session = Session()  # ← 매번 새 Session! GREASE 변동!
    response = session.get(url, ja3=ja3)
```

✅ **해결**: Session 재사용
```python
session = Session()  # ← 한 번만 생성
for page in range(1, 11):
    response = session.get(url, ja3=ja3)  # ← 재사용
```

### ❌ Mistake 3: JA3 Hash 직접 계산
```python
import hashlib
ja3_hash = hashlib.md5(ja3_string.encode()).hexdigest()  # ← 불필요!
response = session.get(url, ja3=ja3_hash)  # ← 틀림!
```

✅ **해결**: JA3 문자열만 전달
```python
ja3_string = "771,4865-4866-..."  # ← 문자열만
response = session.get(url, ja3=ja3_string)  # ← 정답!
```

---

## 📊 Quick Reference

### 명령어

```bash
# 기본 크롤링
python main.py --keyword "검색어" --start 1 --end 10

# 특정 페이지만
python main.py --keyword "검색어" --page 5

# 강제 TLS 재수집
python main.py --keyword "검색어" --force-refresh
```

### Config 관리 (런타임 설정 변경)

**터미널에서 즉시 설정 변경 (코드 수정 없음!):**

```bash
# 1. 전체 설정 보기
python -c "
from lib.db.config_manager import get_config
config = get_config()
for category, configs in config.get_all().items():
    print(f'[{category}]')
    for k, m in configs.items(): print(f'  {k}: {m[\"value\"]} - {m[\"description\"]}')
"

# 2. 특정 설정 변경
python -c "
from lib.db.config_manager import get_config
config = get_config()
config.set('cookie_expiry', 43200, description='12시간으로 단축')
print(f'✅ cookie_expiry = {config.get(\"cookie_expiry\")}초')
"

# 3. 카테고리별 조회
python -c "
from lib.db.config_manager import get_config
config = get_config()
configs = config.get_by_category('crawler')
for k, v in configs.items(): print(f'{k}: {v}')
"

# 4. 기본값 복원
python -c "
from lib.db.config_manager import get_config
config = get_config()
config.reset_to_default('cookie_expiry')
print('✅ 기본값 복원 완료')
"
```

**💡 주요 설정:**
- `cookie_expiry`: 쿠키 유효 시간 (기본: 86400초 = 24시간)
- `crawler_max_retries`: HTTP2 에러 재시도 횟수 (기본: 3회)
- `crawler_retry_delay`: 재시도 대기 시간 (기본: 3초)
- `max_workers`: 최대 병렬 Worker (기본: 20)
- `page_delay_min/max`: 페이지 간 딜레이 (기본: 2-5초)

→ 전체 설정: `python -c "from lib.db.config_manager import get_config; get_config().get_all()"`

### 터미널에서 빠른 DB 조회 (임시 스크립트 불필요!)

**원라이너로 바로 조회 가능:**

```bash
# 1. 최근 TLS 수집 내역
python -c "
import sys; sys.path.insert(0, '.')
from lib.db.manager import DBManager
db = DBManager()
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute('SELECT device_name, browser, os_version, DATE_FORMAT(collected_at, \"%Y-%m-%d %H:%i\") FROM tls_fingerprints ORDER BY collected_at DESC LIMIT 5')
for row in cursor.fetchall(): print(f'{row[0]:30} {row[1]:10} {row[2]:6} {row[3]}')
cursor.close(); conn.close()
"

# 2. 최근 크롤링 세션 통계
python -c "
import sys; sys.path.insert(0, '.')
from lib.db.manager import DBManager
db = DBManager()
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute('SELECT keyword, device_name, pages_successful, pages_failed, status, DATE_FORMAT(created_at, \"%m-%d %H:%i\") FROM crawl_results ORDER BY created_at DESC LIMIT 5')
for row in cursor.fetchall(): print(f'{row[0]:12} {row[1]:25} OK:{row[2]:2} Fail:{row[3]:2} [{row[4]:8}] {row[5]}')
cursor.close(); conn.close()
"

# 3. 테이블 구조 확인
python -c "
import sys; sys.path.insert(0, '.')
from lib.db.manager import DBManager
db = DBManager()
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute('DESCRIBE crawl_results')  # 또는 다른 테이블명
for row in cursor.fetchall(): print(f'{row[0]:20} {row[1]:20}')
cursor.close(); conn.close()
"
```

**💡 팁**:
- `!` 문자는 Bash에서 히스토리 확장으로 인식되므로 `"%m-%d"` 형식으로 이스케이프
- 긴 쿼리는 여러 줄로 나눠서 사용 가능
- 임시 파일 없이 바로 데이터 확인 가능

### 스크립트로 DB 쿼리 (복잡한 분석용)

```python
from lib.db.manager import DBManager

db = DBManager()

# 최신 TLS 가져오기
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("""
    SELECT tls_data, http2_data
    FROM tls_fingerprints
    WHERE device_name = %s AND browser = %s
    ORDER BY collected_at DESC LIMIT 1
""", ('Samsung Galaxy S23', 'samsung'))
```

→ 더 많은 쿼리: [docs/DATABASE.md](docs/DATABASE.md)

### 디바이스 선택

```
STEP 1: Category
  → Galaxy ⭐ (Samsung Browser 사용)

STEP 2: Device Model
  → S23 Ultra ⭐ (성공 기록 확인)

STEP 3: Browser
  → Samsung Browser ⭐ (절대 Chrome 아님!)

STEP 4: OS Version
  → 13.0 (최신 권장)
```

→ 상세: [docs/CRAWLING_GUIDE.md](docs/CRAWLING_GUIDE.md)

---

## 🆘 Troubleshooting

### 문제 1: 2페이지부터 차단 (HTTP/2 INTERNAL_ERROR)

**원인**: Android Chrome 사용 (X25519MLKEM768 탐지)

**해결**:
1. Samsung Browser 사용
2. 또는 iPhone Safari 사용

→ 상세: [docs/TLS_BLOCKING.md](docs/TLS_BLOCKING.md)

### 문제 2: 페이지마다 GREASE 값 다름

**원인**: Session 객체 재사용 안 함

**해결**:
```python
# ✅ 올바른 방식
self.session = Session()  # __init__에서 한 번만
```

→ 상세: [docs/SESSION_STRATEGY.md](docs/SESSION_STRATEGY.md)

### 문제 3: DB 쿼리 방법 모름

**해결**: [docs/DATABASE.md](docs/DATABASE.md) 참조
- Query Patterns 섹션에 20+ 예시

---

## 📞 Support

- **Issues**: GitHub Issues (준비 중)
- **Documentation**: 이 파일 + `docs/` 폴더
- **Version**: v2.13 (2025-10-25)

---

**마지막 업데이트**: 2025-10-25
**작성자**: Claude (Anthropic)
