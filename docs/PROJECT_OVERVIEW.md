# BrowserStack TLS Crawler - 프로젝트 전체 정리

**Version**: 2.14
**Last Updated**: 2025-10-27
**작성자**: Claude (Anthropic)

---

## 🎯 프로젝트 목표

**대규모 쿠팡 크롤링 시 차단 우회 전략 수립**

### 핵심 질문
1. **IP 기반 차단인가?** → IP 변경으로 해결 가능
2. **TLS 기반 차단인가?** → 특정 디바이스 회피 필요
3. **둘 다인가?** → IP + TLS 조합 전략 필요

### 최종 목표
- 100,000 페이지 크롤링 달성
- 차단 없이 안정적인 데이터 수집
- 자동화된 로테이션 시스템

---

## 📊 현재까지 발견한 사실

### 1. IP 기반 Rate Limiting (확인됨 ✅)

**테스트 결과:**
```
동일 IP (220.121.120.83) + 동일 디바이스:
  페이지 1-10: 100% 성공 (10/10)
  페이지 11+: 점진적 실패 증가

결론: 쿠팡은 IP 주소로 Rate Limit 적용
```

**증거:**
- iPhone 14 Pro (iOS 16): 10/10 성공
- Samsung Galaxy S21 Plus: 10/10 성공
- 동일 디바이스 재시도 시 차단 증가

### 2. TLS 차단 여부 (미확인 ❓)

**가설:**
- 일부 TLS fingerprint는 봇으로 인식될 가능성
- Android Chrome은 X25519MLKEM768 extension으로 차단 확인
- Samsung Browser, iPhone Safari는 통과 확인

**검증 필요:**
- 동일 IP에서 13개 디바이스 순차 테스트
- 특정 TLS만 차단되는지 확인

### 3. X25519MLKEM768 Extension (확인됨 ✅)

**차단 패턴:**
```
Android Chrome (모든 버전):
  → X25519MLKEM768 (포스트 양자 암호화)
  → 2페이지부터 HTTP/2 INTERNAL_ERROR
  → 봇 탐지 신호로 인식

Samsung Browser, iPhone Safari:
  → X25519MLKEM768 없음
  → 정상 크롤링 가능
```

**결론:** X25519MLKEM768 없는 디바이스만 사용

---

## 🏗️ 시스템 구조

### 1. TLS 수집 시스템

**BrowserStack Real Device 사용:**
```
lib/collectors/dynamic.py
  ↓
BrowserStack API
  ↓
Real Device (클라우드 실기기)
  ↓
TLS Fingerprint 수집
  - JA3 String (GREASE 포함)
  - Akamai Fingerprint (HTTP/2)
  - User-Agent
  - 쿠키 (PCID, sid, _abck)
  ↓
DB 저장 (tls_fingerprints, cookies)
```

**수집 항목:**
```json
{
  "tls": {
    "ja3": "771,4865-4866-...,11-23-51-...,29-23-24,0",
    "ja3_hash": "d8a0b7611e3fe02f04ed0a7daa098296",
    "ciphers": [4865, 4866, ...],
    "extensions": [11, 23, 51, ...]
  },
  "http2": {
    "akamai_fingerprint": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
    "version": "h2"
  },
  "cookies": {
    "PCID": "17613977311388401171189...",
    "sid": "8bcf825c38f04089954b26845aba163c...",
    "_abck": "5DF4B8E6B0B7EB035F9CD55A3BF069C7~-1~..."
  }
}
```

### 2. 크롤링 시스템

**curl-cffi 기반:**
```
lib/custom_tls_crawler.py
  ↓
curl-cffi Session 객체
  ↓
JA3 String 적용
Akamai Fingerprint 적용
쿠키 적용
  ↓
쿠팡 검색 크롤링
  ↓
HTML 파싱 (상품 정보)
  ↓
DB 저장 (crawl_results, products)
```

**Session 재사용 (중요!):**
```python
# ✅ 올바른 방식
class CustomTLSCrawler:
    def __init__(self):
        self.session = Session()  # 한 번만 생성

    def crawl_pages(self, start, end):
        for page in range(start, end + 1):
            response = self.session.get(url, ja3=ja3, ...)
            # GREASE 일관성 유지
```

### 3. 데이터베이스 구조

**9개 테이블:**
```
1. tls_fingerprints  - TLS 지문 (append-only)
2. cookies           - 쿠키 (lifecycle tracking)
3. crawl_results     - 크롤링 세션 요약
4. crawl_details     - 페이지별 상세
5. products          - 상품 데이터
6. tls_variance_samples - TLS variance 테스트
7. device_selections - 마지막 선택 디바이스
8. changelogs        - 변경 이력
9. config            - 런타임 설정
```

**TLS + 쿠키 조합:**
```sql
-- 특정 디바이스의 최신 TLS
SELECT * FROM tls_fingerprints
WHERE device_name = 'Samsung Galaxy S22'
  AND browser = 'samsung'
ORDER BY collected_at DESC LIMIT 1;

-- 해당 TLS의 쿠키
SELECT * FROM cookies
WHERE fingerprint_id = ?
  AND is_expired = 0
ORDER BY collected_at DESC LIMIT 1;
```

---

## 🔄 차단 검증 로직 (구현 예정)

### Phase 1: 동일 IP에서 모든 TLS 테스트

**시나리오:**
```
IP A (220.121.120.83)에서:

페이지 1-10: Device A (iPhone 14 Pro) + TLS_A
  → 결과: 10/10 성공 ✅

페이지 11-20: Device B (Samsung S22) + TLS_B
  → 결과: 5/10 성공 (차단 시작)

페이지 21-30: Device C (iPhone 15) + TLS_C
  → 결과: 2/10 성공 (차단 심화)

페이지 31-40: Device D (Samsung S23) + TLS_D
  → 결과: 0/10 성공 (완전 차단)
```

**판단:**
- 페이지 11부터 차단 시작
- 디바이스 변경해도 차단 지속
- **→ IP 기반 Rate Limit 확인** ✅

### Phase 2: VPN으로 IP 변경 (별도 검증 예정)

**시나리오:**
```
IP B (61.80.38.75)로 전환 후:

페이지 41-50: Device A (iPhone 14 Pro) + TLS_A (재사용)
  → 결과: ?/10 성공
```

**예상 결과:**

**Case 1: IP 차단만 있는 경우**
```
IP B + TLS_A → 10/10 성공 ✅
IP B + TLS_B → 10/10 성공 ✅
IP B + TLS_C → 10/10 성공 ✅

결론: IP만 변경하면 모든 TLS 정상 작동
전략: IP 로테이션 (20개 VPN)
```

**Case 2: 특정 TLS 차단도 있는 경우**
```
IP B + TLS_A → 10/10 성공 ✅
IP B + TLS_B → 0/10 성공 ❌ (TLS_B 차단)
IP B + TLS_C → 10/10 성공 ✅

결론: TLS_B가 차단됨 (봇 인식)
전략: TLS_B 회피 + IP 로테이션
```

**Case 3: IP + TLS 조합 차단**
```
IP A + TLS_A → 차단
IP B + TLS_A → 정상 ✅
IP B + TLS_A (재사용) → 차단 (IP B도 Rate Limit)
IP C + TLS_B → 정상 ✅

결론: IP와 TLS 조합으로 관리
전략: IP × TLS 매트릭스 로테이션
```

### Phase 3: 차단 감지 및 자동 대응

**차단 감지 로직:**
```python
def is_blocked(response):
    """
    차단 여부 판단

    Returns:
        bool: True = 차단됨, False = 정상
    """
    # 1. Response Size 체크
    if len(response.content) < 3000:  # 3KB 미만
        return True

    # 2. HTTP/2 에러 체크
    if "INTERNAL_ERROR" in response.text:
        return True

    # 3. 상품 개수 체크
    product_count = parse_products(response.text)
    if product_count == 0:
        return True

    return False
```

**자동 대응 전략:**
```python
def crawl_with_rotation(keyword, start, end):
    """
    차단 발생 시 자동 로테이션
    """
    current_ip = "A"
    devices = load_devices_from_db()  # 13개

    for page in range(start, end + 1):
        for device_idx, device in enumerate(devices):
            tls, cookies = get_tls_cookies(device)
            response = crawl(page, tls, cookies)

            if is_blocked(response):
                # 다음 디바이스로 재시도
                print(f"❌ 차단 감지: {device['name']}")
                continue
            else:
                # 성공
                print(f"✅ 성공: {device['name']}")
                save_result(page, device, response)
                break
        else:
            # 모든 디바이스 실패 → IP 문제
            print(f"⚠️  페이지 {page}: 모든 TLS 차단 → IP 문제")

            # VPN으로 IP 변경 (별도 구현)
            switch_vpn(next_vpn_id)
            current_ip = get_current_ip()

            # 처음 디바이스로 재시도
            device = devices[0]
            tls, cookies = get_tls_cookies(device)
            response = crawl(page, tls, cookies)

            if is_blocked(response):
                print(f"❌ IP 변경 후에도 차단 → TLS 문제 의심")
            else:
                print(f"✅ IP 변경 후 성공 → IP Rate Limit 확인")
```

---

## 📋 검증된 디바이스 (13개)

**현재 사용 가능:**

### iPhone Safari (6개)
1. iPhone 14 Pro (iOS 16) - ✅ 10/10 성공 검증
2. iPhone 14 Pro (iOS 17)
3. iPhone 15 (iOS 17)
4. iPhone 15 (iOS 18)
5. iPhone 16 Pro Max (iOS 18)
6. iPhone 17 (iOS 18)

### Samsung Browser (7개)
1. Samsung Galaxy S21 Plus (Android 11.0) - ✅ 10/10 성공 검증
2. Samsung Galaxy S22 (Android 12.0)
3. Samsung Galaxy S22 Plus (Android 12.0)
4. Samsung Galaxy S22 Ultra (Android 12.0)
5. Samsung Galaxy S23 Ultra (Android 13.0)
6. Samsung Galaxy A52 (Android 11.0)
7. Samsung Galaxy M52 (Android 11.0)

**필터링 기준:**
- X25519MLKEM768 extension 없음 ✅
- Android Chrome 제외 ❌

**저장 위치:**
```
/tmp/rotation_config.json
→ 13개 디바이스 정보 + 테스트 결과
```

---

## 🔧 구현된 기능

### 1. TLS 수집 (✅ 완료)

**기능:**
- BrowserStack Real Device 자동 연결
- TLS + 쿠키 + HTTP/2 정보 수집
- IP 확인 (Step 0에 추가됨)
- DB 자동 저장

**실행 방법:**
```bash
python -m lib.collectors.dynamic \
  --device "Samsung Galaxy S22" \
  --browser "samsung"
```

### 2. 크롤링 (✅ 완료)

**기능:**
- curl-cffi JA3 TLS 적용
- Session 객체 재사용 (GREASE 일관성)
- 다중 페이지 크롤링
- Checkpoint 시스템 (중단 재개)

**실행 방법:**
```bash
python main.py \
  --keyword "칫솔" \
  --start 1 --end 10 \
  --device-name "Samsung Galaxy S22" \
  --browser "samsung"
```

### 3. 디바이스 선택 (✅ 완료)

**기능:**
- 대화형 디바이스 선택
- 카테고리별 필터링 (Galaxy, iPhone 등)
- DB에서 TLS 존재 여부 확인
- 마지막 선택 기억

**실행 방법:**
```bash
python main.py --keyword "칫솔"
# → 대화형 선택 시작
```

### 4. Config 관리 (✅ 완료)

**기능:**
- 런타임 설정 변경 (코드 수정 없음)
- cookie_expiry, retry 설정 등
- DB config 테이블 관리

**실행 방법:**
```bash
python -c "
from lib.db.config_manager import get_config
config = get_config()
config.set('cookie_expiry', 43200)  # 12시간
"
```

---

## 🚧 구현 필요 기능

### 1. 차단 감지 로직 (우선순위 1)

**목적:** Response가 차단된 건지 정상인지 자동 판단

**구현 위치:** `lib/utils/block_detector.py`

**기능:**
```python
def is_blocked(response, page_num):
    """
    차단 여부 판단

    체크 항목:
    1. Response Size < 3KB
    2. HTTP/2 INTERNAL_ERROR
    3. 상품 개수 = 0
    4. 특정 차단 페이지 패턴

    Returns:
        dict: {
            'is_blocked': bool,
            'reason': str,
            'confidence': float  # 0.0 ~ 1.0
        }
    """
```

### 2. TLS 로테이션 시스템 (우선순위 2)

**목적:** DB에서 다음 사용할 TLS 자동 선택

**구현 위치:** `lib/rotation/tls_rotator.py`

**기능:**
```python
class TLSRotator:
    def __init__(self):
        self.devices = load_rotation_config()
        self.current_index = 0

    def get_next_device(self):
        """다음 디바이스 TLS + 쿠키 반환"""
        device = self.devices[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.devices)

        tls = get_latest_tls(device)
        cookies = get_latest_cookies(device)

        return {
            'device': device,
            'tls': tls,
            'cookies': cookies
        }

    def mark_blocked(self, device):
        """특정 디바이스를 차단 목록에 추가"""
        # DB에 차단 기록
        # 다음 로테이션 시 건너뛰기
```

### 3. IP vs TLS 검증 자동화 (우선순위 3)

**목적:** 차단 원인이 IP인지 TLS인지 자동 판단

**구현 위치:** `scripts/verify_block_cause.py`

**워크플로우:**
```bash
python scripts/verify_block_cause.py \
  --keyword "칫솔" \
  --start 1 --end 50 \
  --vpn-enabled  # VPN 검증 후 활성화

출력:
=== 차단 원인 분석 ===
IP A (220.121.120.83):
  - Device A: 10/10 성공 (페이지 1-10)
  - Device B: 5/10 성공 (페이지 11-20)
  - Device C: 0/10 성공 (페이지 21-30)

결론: 페이지 11부터 IP Rate Limit 발생

IP B (61.80.38.75):
  - Device A: 10/10 성공 (페이지 31-40)
  - Device B: 10/10 성공 (페이지 41-50)

✅ 결론: IP 차단만 존재, TLS 차단 없음
전략: IP 로테이션으로 무제한 크롤링 가능
```

### 4. 차단 결과 DB 저장 (우선순위 4)

**목적:** 어떤 디바이스가 언제 차단되었는지 기록

**DB 테이블:** `block_history`

**스키마:**
```sql
CREATE TABLE block_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_name VARCHAR(100),
    browser VARCHAR(50),
    os_version VARCHAR(20),
    ip_address VARCHAR(50),
    page_number INT,
    blocked_at DATETIME,
    block_reason VARCHAR(255),
    response_size INT,
    retry_success BOOLEAN
);
```

**활용:**
```sql
-- 가장 많이 차단된 디바이스
SELECT device_name, COUNT(*) as block_count
FROM block_history
GROUP BY device_name
ORDER BY block_count DESC;

-- 특정 IP의 차단 패턴
SELECT page_number, COUNT(*) as blocks
FROM block_history
WHERE ip_address = '220.121.120.83'
GROUP BY page_number;
```

---

## 📊 예상 시나리오

### 시나리오 A: IP 차단만 존재 (가장 가능성 높음)

**현상:**
```
IP A:
  - 모든 디바이스: 페이지 1-10 성공
  - 페이지 11부터 점진적 차단

IP B:
  - 모든 디바이스: 페이지 1-10 성공 다시 가능
```

**전략:**
```
20개 VPN × 10페이지 = 200페이지
반복 가능 → 10,000+ 페이지
```

### 시나리오 B: TLS 차단도 존재

**현상:**
```
IP A:
  - Device A, C, E: 정상
  - Device B, D: 2페이지부터 차단

IP B:
  - Device A, C, E: 정상
  - Device B, D: 여전히 차단 (TLS 문제)
```

**전략:**
```
안전한 디바이스만 사용 (A, C, E)
20개 VPN × 3개 디바이스 × 10페이지 = 600페이지
```

### 시나리오 C: IP + TLS 조합 관리

**현상:**
```
IP A + Device A: 10페이지 성공
IP A + Device B: 10페이지 성공
IP B + Device A: 10페이지 성공
IP B + Device B: 10페이지 성공

하지만:
IP A (재사용): 차단
```

**전략:**
```
IP × Device 매트릭스:
20개 VPN × 13개 디바이스 = 260개 조합
각 조합당 10페이지 = 2,600페이지
```

---

## 🎯 다음 단계

### 즉시 구현 (VPN 없이 가능)

1. **차단 감지 로직**
   ```bash
   # 현재 크롤링에 차단 감지 추가
   python main.py --keyword "칫솔" --start 1 --end 20
   → 차단된 페이지 자동 식별
   ```

2. **TLS 로테이션 시스템**
   ```bash
   # 차단 시 자동으로 다음 디바이스 시도
   python main.py --keyword "칫솔" --start 1 --end 50 --auto-rotate
   → 13개 디바이스 순환 사용
   ```

3. **차단 패턴 분석**
   ```bash
   # 동일 IP에서 13개 디바이스 순차 테스트
   python scripts/test_all_devices.py --keyword "칫솔" --pages-per-device 10
   → IP Rate Limit 발생 시점 확인
   → 특정 TLS 차단 여부 확인
   ```

### VPN 검증 후 구현

4. **VPN 통합**
   ```bash
   # VMware에서 검증 완료 후
   python main.py --vpn-rotation --vpn-count 20
   → IP 자동 로테이션
   ```

5. **대규모 크롤링**
   ```bash
   # 최종 목표 달성
   python main.py --keyword "칫솔" --start 1 --end 10000
   → 차단 감지 + TLS 로테이션 + IP 로테이션
   → 100,000 페이지 목표
   ```

---

## 📞 참고 문서

- **CLAUDE.md** - 프로젝트 핵심 가이드
- **TLS_BLOCKING.md** - X25519MLKEM768 차단 패턴
- **SESSION_STRATEGY.md** - GREASE 일관성
- **DATABASE.md** - DB 스키마 및 쿼리
- **FINGERPRINT_ROTATION.md** - 디바이스 로테이션 전략

---

**작성 완료**: 2025-10-27
**다음 업데이트**: 차단 감지 로직 구현 완료 시
