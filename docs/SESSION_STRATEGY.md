# Session Strategy - 세션 유지 전략

**Status**: ✅ 완료 (Completed)
**Last Updated**: 2025-10-25

---

## 🔐 세션 유지 메커니즘 (2025-10-24 검증 완료)

### 📌 핵심 원칙

**쿠팡이 "같은 사용자"로 인식하려면 3가지 요소가 모두 필요:**

1. ✅ **TLS Fingerprint 일관성** (가장 중요!)
2. ✅ **PCID/sid 쿠키 유지**
3. ✅ **쿠키 수명 관리** (24시간 이내)

### 🎯 필수 요소 상세

#### 1. TLS Fingerprint (1순위 - 봇 판별)

**통과 조건:**
```python
✅ Android Chrome이 아니면 모두 통과!

안드로이드 삼성브라우저 → ✅
아이폰 크롬 → ✅
아이폰 사파리 → ✅
```

**차단 조건:**
```python
❌ Android + Chrome 조합만 차단
   - 자동화 도구들이 가장 많이 사용하는 fingerprint
   - curl-cffi, Playwright 기본 타겟
   - Akamai가 "봇 도구 표준 시그니처"로 분류
```

**검증 방법:**
```bash
# X25519MLKEM768 확인
jq '.tls.tls.extensions[] | select(.name | contains("supported_groups")) | .supported_groups[]' \
   /var/www/html/browserstack/data/tls/iPhone/14_Pro_Chromium_26/tls_fingerprint.json

# iOS Chrome 결과: "X25519MLKEM768 (4588)" → ❌ 차단
# iPhone Safari 결과: 없음 → ✅ 통과
# Galaxy Samsung Browser 결과: 없음 → ✅ 통과

# ECH/ALPS 확인 (참고용, 차단 조건 아님)
jq '.tls.tls.extensions[] | select(.name | contains("Encrypted") or contains("application_settings")) | .name' \
   /var/www/html/browserstack/data/tls/Samsung/S21_Plus_Samsung_11_0/tls_fingerprint.json

# Galaxy 결과: ECH + ALPS 있음 → ✅ 통과! (X25519MLKEM768 없으므로)
```

#### 2. PCID/sid 쿠키 (2순위 - 세션 식별)

**PCID (Primary Client ID):**
```python
목적: 사용자 고유 식별자
수명: 수 시간 (서버 정책에 따름)
발급: 쿠팡 메인 페이지 첫 방문 시
예시: "17612920160076583595169..."

유지 방법:
  - BrowserStack에서 수집한 원본 유지
  - curl-cffi Session 객체로 자동 관리
  - 절대 삭제/변경하지 말 것
```

**sid (Session ID):**
```python
목적: 세션 고유 식별자
수명: PCID와 동일 (쌍으로 관리)
발급: /n-api/recommend/feeds API 호출 시
예시: "f81aa0d44aca4065bd5add99c597474a21129158..."

특징:
  - PCID와 페어로 작동
  - 둘 중 하나라도 없으면 세션 무효
  - 서버가 자동 검증
```

**검증 결과 (2025-10-24):**
```
테스트: iPhone 14 Pro Safari
PCID: 17612920160076583595169... (일관)
sid:  f81aa0d44aca4065bd5add99c597474a21129158... (일관)

1페이지 첫 방문 → PCID/sid 동일 ✅
2페이지 방문     → PCID/sid 동일 ✅
1페이지 재방문   → PCID/sid 동일 ✅

결과:
  - 랭킹 상품: 고정 (0~1개 실시간 변동)
  - 광고 슬롯: 36개 고정 (위치 일치)
  - 광고 내용: 6개 로테이션 (16.7%)

→ 쿠팡이 "같은 사용자"로 인식 확인!
```

#### 3. 쿠키 수명 (3순위 - 시간 제약)

**임계값 (실제 테스트 결과):**
```
0~24시간: ✅ 쿠키 유효 (다중 크롤링 안정)
24시간+:  ⚠️  쿠키 만료 (재수집 필요)

시스템 설정: 24시간 (86400초)
권장: 쿠키 수집 후 24시간 이내 사용
```

**증거:**
```
성공 (12분 14초):
  1페이지 ✅ 2페이지 ✅ 재방문 ✅

실패 (14분 41초):
  1페이지 ❌ HTTP/2 INTERNAL_ERROR (curl 92)
  → 세션 완전 만료
```

### 🔄 Session 객체 필수 사용

**올바른 방식:**
```python
from curl_cffi.requests import Session

class CustomTLSCrawler:
    def __init__(self, device_name, browser):
        self.session = Session()  # ✅ 필수!

    def crawl_page(self, page):
        if page == 1:
            # 첫 페이지: fingerprint 쿠키 전달
            response = self.session.get(url, ja3=ja3, cookies=cookie_dict)
        else:
            # 2페이지 이상: Session이 자동 관리
            response = self.session.get(url, ja3=ja3)  # cookies 생략!
```

**Session 사용 이유:**
1. ✅ **TLS 연결 재사용** - 페이지 1~N까지 같은 연결
2. ✅ **GREASE 일관성** - 세션 내 동일한 GREASE 값
3. ✅ **쿠키 자동 관리** - Set-Cookie 자동 저장/전달
4. ✅ **PCID/sid 유지** - 서버 발급 쿠키 자동 전달

### 🧪 검증된 시나리오

#### ✅ 성공 사례 1: iPhone Safari + Session 유지

```
디바이스: iPhone 14 Pro
브라우저: Safari (iOS 16)
쿠키 나이: 14초 (신선)

[TLS Fingerprint]
  JA3 Hash: 773906b0efdefa24a7f2b8eb6985bf37
  Akamai:   4:2097152;3:100|10485760|0|m,s,p,a
  X25519MLKEM768: ❌ 없음 (중요!)
  ECH:      ❌ 없음
  ALPS:     ❌ 없음

[세션 쿠키]
  PCID: 17612985632383195209466... (모든 페이지 동일)
  sid:  da8ff7233462422eb9ceb5a3b4a08473aebd2d03... (모든 페이지 동일)

[크롤링 결과]
  페이지 1: ✅ 성공 (1.5MB, 27개 랭킹 상품)
  페이지 2: ✅ 성공 (565KB, 27개 랭킹 상품)
  페이지 10: ✅ 성공 (10페이지 연속 통과)

[세션 일관성]
  랭킹 상품: 27개 고정 (±1개 실시간 변동)
  광고 슬롯: 36개 고정 (위치 일치)
  광고 내용: 9개 로테이션 (같은 사용자 인식)
```

#### ✅ 성공 사례 2: Galaxy Samsung Browser + Session 유지 (신규!)

```
디바이스: Samsung Galaxy S21 Plus
브라우저: Samsung Browser (Android 11)
쿠키 나이: 15초 (신선)

[TLS Fingerprint]
  JA3 Hash: 0e1e6b5d069be378004eb6230976c0a5
  Akamai:   1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p
  X25519MLKEM768: ❌ 없음 (중요!)
  ECH:      ✅ 있음! (65037)
  ALPS:     ✅ 있음! (17513)

[세션 쿠키]
  PCID: 17612990192677161297832... (모든 페이지 동일)
  sid:  9b82f8de442f4301898c8d291d22cfa4ce511429... (2페이지에서 새로 발급)

[크롤링 결과]
  페이지 1: ✅ 성공 (1.2MB, 27개 랭킹 상품)
  페이지 2: ✅ 성공 (641KB, 27개 랭킹 상품)
  페이지 10: ✅ 성공 (10페이지 연속 통과)

[핵심 발견]
  ✅ ECH + ALPS가 있어도 통과!
  ✅ X25519MLKEM768 없으면 통과!
  ✅ brotli 압축, Chrome Akamai 패턴 사용
  → ECH/ALPS는 차단 조건이 아님을 증명!
```

#### ❌ 실패 사례: iOS Chrome + X25519MLKEM768

```
디바이스: iPhone 14 Pro
브라우저: Chrome (iOS 26)
쿠키 나이: 14초 (신선)

[TLS Fingerprint]
  JA3 Hash: ecdf4f49dd59effc439639da29186671
  Akamai:   2:0;4:2097152;3:100;9:1|10485760|0|m,s,p,a
  X25519MLKEM768: ✅ 있음! (4588) ← 봇 신호!
  ECH:      ❌ 없음 (iOS WebKit 강제)
  ALPS:     ❌ 없음 (iOS WebKit 강제)

[세션 쿠키]
  PCID: 17612981950231962865253... (유지됨)
  sid:  8f468fccd8de4c79b61d4127af152a8e90f3287c... (유지됨)

[크롤링 결과]
  페이지 1: ✅ 성공 (1.3MB)
  페이지 2: ❌ 차단 (1,177 bytes - Akamai Challenge)
            bm_sc: 1~1~558262553 (챌린지 쿠키 발급)

[차단 이유]
  PCID/sid는 유효하지만,
  X25519MLKEM768 (4588) 존재 = "자동화 도구"로 판별됨
  → 2페이지부터 엄격 검증 실패
  → ECH/ALPS는 무관 (없어도 차단!)
```

### 📊 브라우저별 TLS 비교 (차단 vs 통과)

| 디바이스 | 브라우저 | X25519MLKEM768 | ECH | ALPS | 결과 | 검증일시 |
|----------|----------|----------------|-----|------|------|--------|
| **iPhone 14 Pro** | **Chrome (iOS 26)** | ✅ 있음 | ❌ | ❌ | ❌ **차단** | 2025-10-24 18:29 |
| **iPhone 14 Pro** | **Safari (iOS 16)** | ❌ 없음 | ❌ | ❌ | ✅ 통과 | 2025-10-24 18:35 |
| **iPhone 14 Pro** | **Safari (iOS 26)** | ❌ 없음 | ❌ | ❌ | ✅ 통과 | 2025-10-24 19:00 |
| **Galaxy S21 Plus** | **Samsung Browser** | ❌ 없음 | ✅ | ✅ | ✅ **통과!** | 2025-10-24 18:42 |
| **Galaxy S21 Plus** | **Chrome** | ✅ 있음 | ✅ | ✅ | ❌ **차단** | 2025-10-24 19:14 |

**핵심 발견:**
- ❌ **X25519MLKEM768 (4588) = 차단의 유일한 원인**
- ✅ **ECH/ALPS는 무관** (Galaxy Samsung Browser가 ECH+ALPS 있어도 통과)
- ✅ **Samsung Browser = 안전** (X25519MLKEM768 미지원)
- ⚠️ **브라우저 선택이 중요, 디바이스 아님** (같은 Galaxy S21 Plus에서 Samsung Browser ✅, Chrome ❌)

### 🎯 세션 유지 체크리스트

**크롤링 시작 전:**
```
□ TLS Fingerprint 검증 (가장 중요!)
  └─ X25519MLKEM768 (4588) 없는지 확인 ← 유일한 차단 조건!
  └─ iPhone Safari 또는 Galaxy Samsung Browser 사용
  └─ Chromium 기반 브라우저 절대 사용 금지

□ 쿠키 준비
  └─ PCID 있는지 확인
  └─ sid 있는지 확인
  └─ 수집 시각 확인 (13분 이내)

□ Session 객체 사용
  └─ curl_cffi.requests.Session() 생성
  └─ 첫 페이지만 cookies 전달
  └─ 이후 Session 자동 관리
```

**크롤링 중:**
```
□ PCID/sid 일관성 모니터링
  └─ 각 페이지 응답 후 Session.cookies 확인
  └─ PCID/sid 값이 변경되지 않는지 체크

□ 응답 크기 검증
  └─ 정상: 500KB~2MB
  └─ 차단: 1KB~2KB (Akamai Challenge)

□ 시간 제한 준수
  └─ 수집 후 10분 이내 크롤링 완료
  └─ 페이지당 2~3초 딜레이
```

### 🔧 차단 우회 연구 (2025-10-24 검증 완료)

**시도 1: ECH/ALPS Extension 제거 - ❌ 실패**
```python
# 시도: curl-cffi setopt으로 Extension 비활성화
from curl_cffi.curl import CurlOpt

session = Session()
curl_handle = session.curl
curl_handle.setopt(CurlOpt.SSL_ENABLE_ALPS, 0)  # ALPS 비활성화
curl_handle.setopt(CurlOpt.ECH, 0)              # ECH 비활성화

response = session.get(url, ja3=ja3_galaxy)

# 결과: 여전히 387 bytes 차단 응답
# 이유: JA3 파라미터가 setopt보다 우선순위 높음
# JA3 문자열에 이미 extension ID 포함:
# "771,ciphers,51-13-17613-10-65037-...,curves,points"
#              ^^^^^^^     ^^^^^^^
#              ALPS        ECH
```

**시도 2: Session 내 JA3 변경 - ❌ 불가 (TLS 프로토콜 제약)**
```python
# 실험: 동일 Session에서 Galaxy → Safari JA3 변경 시도
session = Session()
r1 = session.get(url, ja3=ja3_galaxy)   # 1차: Galaxy JA3
r2 = session.get(url, ja3=ja3_safari)   # 2차: Safari JA3

# 결과: "This extension(65281) can not be toggled"
# 이유: TLS Handshake는 연결당 1회만
# Extensions는 ClientHello 시점에 고정, 이후 변경 불가

# TLS 연결 구조:
# ClientHello (Extensions 포함) ← 1회만!
#   ↓
# ServerHello, Certificate, Finished
#   ↓
# HTTP/2 Stream 1: GET /page1  ← 동일 TLS 재사용
# HTTP/2 Stream 2: GET /page2  ← 동일 TLS 재사용
```

**시도 3: JA3 문자열 파싱 및 수정 - 🔬 이론적 가능 (미구현)**
```python
# Galaxy JA3에서 ECH(65037), ALPS(17613) ID 제거
def remove_extensions(ja3_string, ext_ids_to_remove):
    version, ciphers, extensions, curves, points = ja3_string.split(',')
    ext_list = extensions.split('-')
    ext_list = [e for e in ext_list if int(e) not in ext_ids_to_remove]
    return f"{version},{ciphers},{'-'.join(ext_list)},{curves},{points}"

ja3_modified = remove_extensions(ja3_galaxy, [17613, 65037])

# 문제점:
# 1. Extension 순서 변경으로 부자연스러움
# 2. Extension 개수 감소 (17개 → 15개)
# 3. Akamai가 "비정상 Chrome"으로 판별 가능성
# 4. 다른 Chrome 특성(Window Size 등)은 그대로
```

**시도 4: 대체 도구 고려**
```bash
# Playwright with Firefox
# → Firefox도 ECH 지원하므로 동일 문제 가능성

# Selenium + undetected-chromedriver
# → JavaScript 실행 가능 (bm_* 센서 우회)
# → 하지만 속도 느림 (10배↓)
# → DevTools Protocol 탐지 위험

# mitmproxy + 실기기
# → 완벽한 TLS (실기기가 직접 협상)
# → 복잡한 설정, BrowserStack 불가
```

**검증된 결론 (2025-10-24):**
- ✅ **Galaxy Samsung Browser = 통과!** (X25519MLKEM768 없음)
- ✅ **iPhone Safari = 통과!** (X25519MLKEM768 없음)
- ❌ **iOS Chrome = 차단** (X25519MLKEM768 있음)
- ❌ **모든 Chromium 브라우저 = 차단** (X25519MLKEM768 지원)
- 📌 **핵심 발견**: ECH/ALPS는 차단 조건이 아님
- 💡 **차단 원인**: X25519MLKEM768 (4588) 포스트 양자 암호화

**왜 일부 브라우저만 성공하는가:**
```
iPhone Safari / Galaxy Samsung Browser:
  ❌ X25519MLKEM768 없음 (미지원) ← 핵심!
  → 정확한 모방 = 정상 브라우저로 인식

iOS Chrome / Chromium 브라우저:
  ✅ X25519MLKEM768 있음 (Chrome 124+) ← 봇 신호!
  → 정확한 모방 = 자동화 도구로 판별
```

**TLS 모방의 역설:**
> "최신 보안 기술(포스트 양자 암호화)을 지원하는 브라우저일수록 차단당한다. 실제 모바일 브라우저는 아직 미지원하기 때문."

**ECH/ALPS의 진실:**
```
검증 결과:
  Galaxy Samsung Browser: ECH ✅ + ALPS ✅ + X25519MLKEM768 ❌ → ✅ 통과
  iOS Chrome:             ECH ❌ + ALPS ❌ + X25519MLKEM768 ✅ → ❌ 차단

결론: ECH/ALPS는 차단 조건이 아님!
```

---

**참고 문서:**
- [TLS_BLOCKING.md](TLS_BLOCKING.md) - 차단 패턴 상세 분석
- [DATABASE.md](DATABASE.md) - 쿠키 및 세션 데이터 저장 구조
- [CLAUDE.md](../CLAUDE.md) - 전체 개발 가이드
