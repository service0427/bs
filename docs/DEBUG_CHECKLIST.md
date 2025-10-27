# 2페이지 차단 디버깅 체크리스트

## ✅ 문제 해결 완료! (2025-10-23)

**실제 원인**: curl-cffi Session 쿠키 관리 충돌
- 매 페이지 `cookies=cookie_dict` 전달 → Session 자동 저장 쿠키 무시
- 2페이지에 PCID가 전달되지 않음

**해결책**: 쿠키 전달 전략 변경
- 1페이지: `cookies=cookie_dict` 전달 (fingerprint 쿠키 초기화)
- 2페이지 이후: `cookies` 파라미터 제거 (Session 자동 관리)

**검증**: 8페이지까지 연속 크롤링 성공 ✅

---

## 과거 디버깅 기록

### 이전 상황
- ✅ 1페이지: 성공
- ❌ 2페이지: 차단
- 📅 오늘 변경 사항: 검색 기능 추가, 쿠키 재수집 로직 제거

---

## 🔍 TEST 1: 검색 기능 비활성화 (가장 의심됨)

### 가설
쿠키 수집 시 "아이폰" 검색 → 크롤링 시 다른 키워드 사용 → 쿠키 불일치

### 수정
```bash
vi /var/www/html/browserstack/collectors/dynamic_collector.py
```

**Line 416-434 주석 처리:**
```python
# 변경 전
# 5-1. 실제 사용자처럼 행동 (배너 제거 + 검색)
from lib.coupang_interaction import close_banners, perform_search
...

# 변경 후
"""
# 5-1. 실제 사용자처럼 행동 (배너 제거 + 검색) - 디버깅용 비활성화
from lib.coupang_interaction import close_banners, perform_search
...
"""

# 이 줄 추가 (line 416)
print(f"\n[{self.device_name}] [디버깅] 검색 기능 비활성화 (메인 페이지만)")
```

### 테스트
```bash
# 1. 쿠키 재수집 (검색 없이)
python main.py --keyword "갤럭시" --start 1 --end 1 --force-refresh

# 2. 2페이지까지 크롤링
python main.py --keyword "갤럭시" --start 1 --end 2
```

### 확인할 로그
```
[디버깅] 검색 기능 비활성화 (메인 페이지만)  ← 이 메시지 나오는지
```

### 결과
- [x] 2페이지 실패 → 다음 테스트 (검색 기능은 원인 아님)

---

## 🔍 TEST 2: 세션 쿠키 전달 확인

### 가설
1페이지에서 받은 PCID, sid 쿠키가 2페이지에 전달되지 않음

### 수정
```bash
vi /var/www/html/browserstack/lib/custom_tls_crawler.py
```

**Line 128-134 수정 (디버깅 출력 추가):**
```python
# 이전 페이지에서 받은 세션 쿠키 추가 (2페이지부터)
if self.session_cookies:
    cookie_dict.update(self.session_cookies)
    print(f"  ✓ 쿠키: {len(cookie_dict)}개 (Fingerprint + 세션 쿠키)")
    print(f"      세션 쿠키: {', '.join(self.session_cookies.keys())}")

    # [디버깅] 추가
    print(f"\n[디버깅] 세션 쿠키 상세:")
    for name in ['PCID', 'sid']:
        if name in cookie_dict:
            print(f"  - {name}: {cookie_dict[name][:30]}...")
        else:
            print(f"  - {name}: ❌ 없음!")
    print()
else:
    print(f"  ✓ 쿠키: {len(cookie_dict)}개 (Fingerprint, 세션 쿠키 없음)")
    print(f"      첫 요청 - 서버가 새 세션 쿠키 발급 예정")

    # [디버깅] 추가
    print(f"\n[디버깅] self.session_cookies가 비어있음!")
    print()
```

**Line 305-320 수정 (쿠키 수신 확인 강화):**
```python
# 응답에서 세션 쿠키 추출 (PCID, sid 등)
session_cookie_names = ['PCID', 'sid', 'sessionid', 'session', 'JSESSIONID']
received_cookies = []
for cookie_name in session_cookie_names:
    if cookie_name in response.cookies:
        self.session_cookies[cookie_name] = response.cookies[cookie_name]
        received_cookies.append(cookie_name)

if received_cookies:
    print(f"  ✓ 세션 쿠키 수신: {', '.join(received_cookies)}")
    # [디버깅] 추가
    print(f"[디버깅] 수신된 세션 쿠키 상세:")
    for name in received_cookies:
        print(f"  - {name}: {self.session_cookies[name][:30]}...")
else:
    print(f"  ⚠️  세션 쿠키 미수신")
```

### 테스트
```bash
python main.py --keyword "갤럭시" --start 1 --end 2
```

### 확인할 로그
```
# 1페이지
[디버깅] self.session_cookies가 비어있음!
  ✓ 세션 쿠키 수신: PCID, sid
[디버깅] 수신된 세션 쿠키 상세:
  - PCID: 17612167309709420355083...
  - sid: 2a4a73a336ff470ebda41bae0e...

# 2페이지
[디버깅] 세션 쿠키 상세:
  - PCID: 17612167309709420355083...  ← 1페이지와 동일해야 함
  - sid: 2a4a73a336ff470ebda41bae0e...  ← 1페이지와 동일해야 함
```

### 결과
- [x] **원인 발견: curl-cffi Session 쿠키 관리 충돌**
  - 매 페이지 `cookies=cookie_dict` 전달 → Session 자동 저장 쿠키 무시
  - 2페이지에 PCID가 전달되지 않음

**수정 완료 (custom_tls_crawler.py):**
```python
# Line 303-309: 쿠키 전달 전략 변경
if page == 1:
    request_params['cookies'] = cookie_dict  # 첫 페이지만 전달
else:
    # 2페이지 이후: cookies 파라미터 제거
    # Session이 자동으로 Set-Cookie 적용
    pass
```

**검증 결과**: 8페이지까지 성공 ✅

---

## 🔍 TEST 3: Referer 헤더 확인

### 가설
2페이지 요청 시 Referer가 1페이지 URL이어야 하는데 잘못됨

### 수정
```bash
vi /var/www/html/browserstack/lib/custom_tls_crawler.py
```

**Line 247-258 수정 (디버깅 출력 추가):**
```python
# Referer 설정 (모든 페이지)
if page == 1:
    # 1페이지: 메인 페이지에서 검색한 것처럼
    headers['Referer'] = 'https://www.coupang.com/'
    headers['Sec-Fetch-Site'] = 'same-origin'
    print(f"  [디버깅] Referer: https://www.coupang.com/ (메인 페이지)")
else:
    # 2페이지 이상: 이전 페이지 URL
    prev_url = f"https://www.coupang.com/np/search?q={quote(keyword)}&page={page-1}"
    headers['Referer'] = prev_url
    headers['Sec-Fetch-Site'] = 'same-origin'
    print(f"  [디버깅] Referer: {prev_url}")
    print(f"  [디버깅] 현재 페이지: {page}")
```

### 테스트
```bash
python main.py --keyword "갤럭시" --start 1 --end 2
```

### 확인할 로그
```
# 2페이지
[디버깅] Referer: https://www.coupang.com/np/search?q=갤럭시&page=1
[디버깅] 현재 페이지: 2
```

### 결과
- [ ] Referer 정상 → 다음 테스트
- [ ] Referer 이상 → **원인: Referer 헤더**

---

## 🔍 TEST 4: User-Agent 일치 확인

### 가설
쿠키 수집 시와 크롤링 시 User-Agent가 다름

### 수정
```bash
vi /var/www/html/browserstack/lib/custom_tls_crawler.py
```

**Line 115 다음에 추가:**
```python
headers = data.get('headers', {})
tls = data.get('tls', {})

# [디버깅] User-Agent 확인
print(f"[디버깅] User-Agent: {headers.get('User-Agent', 'N/A')[:100]}")
```

**쿠키 수집 시 User-Agent도 확인:**
```bash
vi /var/www/html/browserstack/collectors/dynamic_collector.py
```

**Line 444 다음에 추가:**
```python
# 6. 헤더 구성
headers = self._build_headers(user_agent)

# [디버깅] User-Agent 확인
print(f"[디버깅] 수집 시 User-Agent: {user_agent[:100]}")
```

### 테스트
```bash
# 1. 쿠키 재수집
python main.py --keyword "갤럭시" --start 1 --end 1 --force-refresh

# 2. 크롤링
python main.py --keyword "갤럭시" --start 1 --end 2
```

### 확인할 로그
```
# 쿠키 수집 시
[디버깅] 수집 시 User-Agent: Mozilla/5.0 (Linux; Android 10.0; SM-A115F) ...

# 크롤링 시 (1페이지, 2페이지 모두)
[디버깅] User-Agent: Mozilla/5.0 (Linux; Android 10.0; SM-A115F) ...
```

### 결과
- [ ] User-Agent 동일 → 다음 테스트
- [ ] User-Agent 다름 → **원인: User-Agent 불일치**

---

## 🔍 TEST 5: 재수집 로직 복원

### 가설
2페이지 차단 시 쿠키를 재수집하지 않아서 계속 차단됨

### 수정
```bash
vi /var/www/html/browserstack/main.py
```

**Line 218-233 전체 교체:**
```python
# 변경 전 (단순 1회 실행)
if num_workers == 1:
    # 단일 worker 모드 (체크포인트 활성화)
    crawler = CustomTLSCrawler(device_name, browser, device_config=device_config)
    result = crawler.crawl_pages(...)

    if isinstance(result, dict):
        all_results = result.get('results', [])
    else:
        all_results = result

# 변경 후 (재시도 루프 추가)
if num_workers == 1:
    # 단일 worker 모드 (체크포인트 + 재시도)
    max_retries = 3
    retry_count = 0
    all_results = []

    while retry_count < max_retries:
        crawler = CustomTLSCrawler(device_name, browser, device_config=device_config)
        result = crawler.crawl_pages(
            keyword=keyword,
            start_page=start_page,
            end_page=end_page,
            use_checkpoint=True
        )

        if isinstance(result, dict):
            all_results.extend(result.get('results', []))

            # 성공하거나 재시도 불필요하면 종료
            if result.get('success') or not result.get('need_refresh'):
                break

            # 차단 감지 - 쿠키 재수집
            retry_count += 1
            last_page = result.get('last_page', start_page)

            print(f"\n{'='*70}")
            print(f"🔄 재시도 {retry_count}/{max_retries}: 쿠키 재수집 후 페이지 {last_page}부터 재개")
            print("="*70)

            if retry_count >= max_retries:
                print(f"\n⚠️ 최대 재시도 횟수 도달 - 중단")
                break

            # 쿠키 재수집
            print(f"\n{'='*70}")
            print("BrowserStack 재접속 - 새로운 쿠키 수집")
            print("="*70)
            if not collect_fingerprint(device_config, refresh_policy='force'):
                print(f"\n❌ 쿠키 재수집 실패 - 중단")
                break

            print(f"\n✓ 새로운 쿠키 수집 완료 - 크롤링 재개\n")
        else:
            all_results = result
            break
```

### 테스트
```bash
python main.py --keyword "갤럭시" --start 1 --end 2
```

### 확인할 로그
```
# 2페이지 차단 시
🔄 재시도 1/3: 쿠키 재수집 후 페이지 2부터 재개
BrowserStack 재접속 - 새로운 쿠키 수집
✓ 새로운 쿠키 수집 완료 - 크롤링 재개
```

### 결과
- [ ] 재수집 후 2페이지 성공 → **원인: 쿠키 만료**
- [ ] 재수집 후에도 실패 → 다른 원인

---

## 🔍 TEST 6: TLS 정보 확인 (오늘 변경)

### 가설
TLS 디렉토리 구조 변경 후 잘못된 TLS 정보 사용

### 확인
```bash
# 현재 사용 중인 TLS 파일 확인
ls -la /var/www/html/browserstack/data/tls/Samsung/

# 디바이스 정보 확인
cat /var/www/html/browserstack/data/fingerprints/Samsung_Galaxy_*/metadata.json | grep -A 3 "browser"
```

### 수정
```bash
vi /var/www/html/browserstack/lib/custom_tls_crawler.py
```

**Line 113 다음에 추가:**
```python
data = load_fingerprint_data(self.device_name, self.browser, self.os_version, worker_id=self.worker_id)
cookies = data.get('cookies', [])
headers = data.get('headers', {})
tls = data.get('tls', {})

# [디버깅] TLS 파일 경로 확인
from config import get_tls_dir
tls_dir = get_tls_dir(self.device_name, self.browser, self.os_version)
print(f"[디버깅] TLS 디렉토리: {tls_dir}")
print(f"[디버깅] JA3 Hash: {tls.get('tls', {}).get('ja3_hash', 'N/A')}")
```

### 결과
- [ ] TLS 경로 정상
- [ ] TLS 경로 이상 → **원인: TLS 구조 변경**

---

## 📊 결과 보고 양식

각 테스트 후 다음 형식으로 결과를 보고해주세요:

```
TEST N 결과:
- 수정 완료: ✅ / ❌
- 테스트 실행: ✅ / ❌
- 1페이지: 성공 / 실패
- 2페이지: 성공 / 실패
- 특이 로그: (있으면 복사)
```

---

**마지막 업데이트:** 2025-10-23
**디버깅 시작 시간:** (기록)
