# 🚨 CRITICAL LESSON - TLS 수집 로직 절대 건드리지 말 것

**날짜:** 2025-10-23 22:30
**상황:** sid 쿠키 추적 기능 추가 중 TLS 수집이 완전히 망가짐
**원인:** TLS 수집 정책을 수정하면서 시스템 전체가 불안정해짐

---

## ❌ 무엇이 문제였나

### 문제의 시작
사용자: "COUPANG_INTERACTION=1로 실행하는데 검색창 클릭이 안 나와요"

### 잘못된 접근
1. **COUPANG_INTERACTION=1 강제 재수집 로직 추가**
```python
# collectors/dynamic_collector.py (제거된 코드)
from lib.coupang_interaction import is_enabled as interaction_enabled
force_recollect = interaction_enabled()

if force_recollect:
    print(f"\n[{self.device_name}] 🔄 COUPANG_INTERACTION=1 감지 - 매번 재수집 (검색 실행)")

# 기존 TLS가 있어도 무시하고 재수집
if not force_recollect and self._is_data_valid():
    print(f"\n[{self.device_name}] 기존 TLS 데이터 사용 (재수집 생략)\n")
```

2. **600초 쿠키 만료 체크 추가**
```python
# collectors/dynamic_collector.py (제거된 코드)
if self.refresh_policy == 'auto':
    # metadata.json에서 수집 시간 확인
    collected_at = datetime.fromisoformat(collected_at_str)
    elapsed = (datetime.now() - collected_at).total_seconds()

    if elapsed > COOKIE_VALID_DURATION:  # 600초
        print(f"재수집 필요")
        return False
```

3. **Safari alert 처리 추가**
```python
# collectors/dynamic_collector.py (제거된 코드)
is_safari = self.browser.lower() in ['safari', 'iphone']

if is_safari:
    print(f"Safari 감지 - 경고창 무시하고 진행")

try:
    self.driver.get('https://tls.peet.ws/api/all')
except Exception as e:
    if is_safari and 'invalid' in str(e).lower():
        print(f"Safari 경고 무시")
```

4. **Safari 직접 URL 검색 추가**
```python
# lib/coupang_interaction.py (제거된 코드)
def perform_search(driver, device_name, keyword="노트북", browser=None):
    is_safari = browser.lower() in ['safari', 'iphone']

    if is_safari:
        # element interaction 건너뛰고 직접 URL 접속
        search_url = f"https://www.coupang.com/np/search?q={quote(keyword)}"
        driver.get(search_url)
```

### 결과
**TLS 수집이 완전히 망가짐 → 크롤링 불가능**

사용자: "sid 때문에 tls 를 건드려서 그런가 계속 안돼"

---

## ✅ 올바른 이해

### TLS 수집의 본질 (v2.7에서 확립됨)

**TLS는 디바이스당 고유한 고정값:**
- Window Size: 항상 동일 (예: 15,663,105)
- Akamai Fingerprint: 완전 동일
- Ciphers, Extensions: 동일 (GREASE 제외)
- JA3 Hash만 변동 (GREASE 때문, Session으로 세션 내 고정)

**따라서:**
```python
# 올바른 정책 (v2.7)
if self._is_data_valid():
    # TLS 파일 있으면 영구 재사용 (시간 무관)
    return True
```

**재수집이 필요한 경우는 오직:**
- `--force-refresh` 옵션 사용
- TLS 파일이 없음
- TLS 정보가 비정상적임 (ciphers 누락 등)

---

## 🎯 핵심 교훈

### 1. TLS 수집 정책은 절대 건드리지 말 것

**이유:**
- TLS는 디바이스 특성 (브라우저 엔진 수준)
- 한 번 수집하면 영구 재사용 가능
- 매번 재수집하면 BrowserStack 비용만 증가
- 재수집 로직이 복잡해지면 시스템 전체가 불안정

**금지 사항:**
- ❌ `_is_data_valid()` 로직 수정 금지
- ❌ 시간 기반 만료 체크 추가 금지
- ❌ 환경변수로 강제 재수집 추가 금지
- ❌ Safari/iPhone 특수 처리 추가 금지

### 2. COUPANG_INTERACTION=1의 올바른 역할

**COUPANG_INTERACTION=1은:**
- ✅ TLS/쿠키 **최초 수집 단계**에서만 의미 있음
- ✅ `collectors/dynamic_collector.py`에서 검색 로직 활성화
- ✅ **크롤링 단계**에서는 의미 없음 (curl-cffi는 검색창 안 씀)

**잘못된 생각:**
- ❌ "COUPANG_INTERACTION=1이면 크롤링할 때도 검색창 클릭해야 해"
- ❌ "COUPANG_INTERACTION=1이면 매번 TLS 재수집해야 해"

**올바른 이해:**
- ✅ TLS 수집: 최초 1회만, 디바이스당 영구 보관
- ✅ 크롤링: curl-cffi로 HTTP 요청만 (검색창 안 씀)
- ✅ COUPANG_INTERACTION=1: TLS 수집 시 검색 로직만 활성화

### 3. 쿠키 관리 정책 (v2.7에서 확립됨)

**세션 쿠키 (PCID, sid):**
- ✅ 크롤링 중 서버에서 자동 발급
- ✅ curl-cffi Session 객체가 자동 관리
- ❌ 저장하지 않음 (매번 새로 받음)
- ❌ 만료 시간 체크 불필요

**Fingerprint 쿠키 (나머지 15개):**
- ✅ TLS 수집 시 한 번만 저장
- ✅ 크롤링 시 읽어서 사용
- ❌ 만료 시간 체크 불필요 (계속 유효)

---

## 📋 정상 동작 플로우

### TLS 수집 (최초 1회)
```
1. python main.py 실행
2. 디바이스 선택 (예: iPhone 17 Safari)
3. DynamicCollector.collect() 호출
4. _is_data_valid() 체크
   - TLS 파일 없음 → 수집 진행
5. BrowserStack 세션 시작
6. TLS 페이지 접속 (peet.ws)
7. COUPANG_INTERACTION=1이면:
   - 배너 닫기
   - 검색 수행
8. TLS + 쿠키 저장
9. BrowserStack 세션 종료
```

### 크롤링 (매번)
```
1. python main.py --start 1 --end 50
2. DynamicCollector.collect() 호출
3. _is_data_valid() 체크
   - TLS 파일 있음 → 재수집 건너뜀 ✅
4. CustomTLSCrawler 생성
5. TLS + 쿠키 로드
6. curl-cffi로 1~50 페이지 크롤링
   - Session 객체 사용
   - PCID, sid 자동 발급
   - 검색창 안 씀 (HTTP 요청만)
```

---

## 🔒 변경 금지 영역

### collectors/dynamic_collector.py

**Line 270-272 (절대 수정 금지):**
```python
# 기존 데이터 유효성 검증
if self._is_data_valid():
    print(f"\n[{self.device_name}] 기존 TLS 데이터 사용 (재수집 생략)\n")
```

**Line 210-220 (절대 수정 금지):**
```python
def _is_data_valid(self):
    # TLS 파일 존재 확인
    if not os.path.exists(tls_file):
        return False

    # TLS 정보 정상 확인
    if not tls_info.get('tls') or not tls_info.get('tls', {}).get('ciphers'):
        return False

    # ✅ 시간 체크 없음 (영구 유효)
    return True
```

### lib/coupang_interaction.py

**perform_search() 시그니처 (절대 수정 금지):**
```python
def perform_search(driver, device_name, keyword="노트북"):
    # ✅ browser 파라미터 없음
    # ✅ Safari 특수 처리 없음
    # ✅ element interaction 방식만 사용
```

---

## 📝 향후 개발 시 체크리스트

새로운 기능 추가 전 반드시 확인:

- [ ] TLS 수집 로직을 건드리는가?
  - YES → **절대 금지, 다른 방법 찾기**
  - NO → 진행 가능

- [ ] `_is_data_valid()` 조건을 변경하는가?
  - YES → **절대 금지**
  - NO → 진행 가능

- [ ] 환경변수로 TLS 재수집을 강제하는가?
  - YES → **절대 금지**
  - NO → 진행 가능

- [ ] Safari/iPhone 특수 처리를 추가하는가?
  - TLS 수집 단계 → **금지**
  - 크롤링 단계 → 고려 가능

- [ ] 쿠키 만료 시간 체크를 추가하는가?
  - YES → **불필요, 금지**
  - NO → OK

---

## 🎓 이번 사건에서 배운 것

1. **TLS 수집은 신성불가침 영역**
   - v2.7에서 확립된 정책 (영구 보관)
   - 한 번 수집하면 끝
   - 건드리면 시스템 전체가 망가짐

2. **COUPANG_INTERACTION=1의 범위를 정확히 이해**
   - TLS 수집 단계에서만 의미 있음
   - 크롤링 단계에서는 무관
   - 크롤링은 curl-cffi HTTP 요청만 사용

3. **복잡도 증가 = 불안정성 증가**
   - 환경변수 조건 추가
   - Safari 특수 처리 추가
   - 시간 기반 만료 체크 추가
   - → 모두 제거해야 안정화됨

4. **sid 쿠키 추적과 TLS 수집은 별개**
   - sid 추적: 크롤링 단계 (custom_tls_crawler.py)
   - TLS 수집: 수집 단계 (dynamic_collector.py)
   - 두 개를 섞으면 안 됨

---

## ✅ 최종 결론

**TLS 수집 로직은 v2.7에서 완성되었고, 더 이상 건드릴 필요 없음.**

**새로운 기능 추가는:**
- ✅ 크롤링 단계 (custom_tls_crawler.py)에만
- ✅ 데이터 분석 단계 (product_extractor.py)에만
- ❌ TLS 수집 단계 (dynamic_collector.py)는 절대 금지

**이 원칙을 어기면:**
- 시스템 전체가 불안정해짐
- 디버깅 불가능
- 롤백만이 답

---

**작성:** Claude (Anthropic)
**중요도:** 🔴🔴🔴 CRITICAL - 절대 잊지 말 것
