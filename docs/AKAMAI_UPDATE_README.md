# Akamai 쿠키 업데이트 기능 (테스트용)

⚠️ **주의:** 이 기능은 원본 보호 원칙을 위반하는 **테스트용** 기능입니다.

---

## 📋 개요

### 목적
크롤링 중 서버에서 갱신된 Akamai 쿠키를 원본 `cookies.json`에 실시간 반영하여 상태 변화를 모니터링

### 업데이트 대상 쿠키 (9개)
```
_abck       # Akamai Bot Manager (핵심!)
bm_sz       # Session 정보
bm_sv       # Session 검증
bm_mi       # Machine ID
bm_s        # Session 상태
bm_ss       # Session 서명
bm_so       # Session 옵션
bm_lso      # Last Session
ak_bmsc     # Akamai 메타데이터
```

---

## 🚀 사용 방법

### 1️⃣ 현재 상태 확인
```bash
python test_akamai_update.py status "Samsung Galaxy S21 Ultra"
```

**출력 예시:**
```
======================================================================
Akamai 쿠키 상태 조회
======================================================================
디바이스: Samsung Galaxy S21 Ultra
활성화: ❌ OFF (환경변수 AKAMAI_UPDATE=1 필요)
======================================================================

발견된 Akamai 쿠키: 9개

  ✓ _abck
    값: 12345ABC...
  ✓ bm_sz
    값: 67890DEF...
  ...
```

---

### 2️⃣ 업데이트 활성화하고 크롤링

#### 리얼 모드 (원본 업데이트 O)
```bash
# 환경변수로 활성화
AKAMAI_UPDATE=1 python main.py --keyword "아이폰"
```

**출력:**
```
[STEP 3] curl-cffi JA3 TLS 요청
  ✓ 세션 쿠키 수신: PCID, sid
  🔄 Akamai 쿠키 업데이트: _abck, bm_sz, bm_sv (3개)  ← 새로 추가됨!
  ✓ 응답 수신
```

#### 패킷 모드 (원본 업데이트 X)
```bash
# Worker는 업데이트 안 함 (충돌 방지)
AKAMAI_UPDATE=1 python main.py --keyword "아이폰" --workers 3
```

**Worker들은 업데이트하지 않음:**
```
[Worker 1] 패킷 모드 - Akamai 업데이트 생략
[Worker 2] 패킷 모드 - Akamai 업데이트 생략
[Worker 3] 패킷 모드 - Akamai 업데이트 생략
```

---

### 3️⃣ 업데이트 후 상태 확인
```bash
python test_akamai_update.py status "Samsung Galaxy S21 Ultra"
```

**변경된 쿠키 값 확인:**
```
  ✓ _abck
    값: NEW_VALUE_ABC...  ← 변경됨!
```

---

## 🔒 안전 장치

### 1. 환경변수 필수
```bash
# 비활성화 (기본)
python main.py --keyword "테스트"

# 활성화 (명시적)
AKAMAI_UPDATE=1 python main.py --keyword "테스트"
```

### 2. 패킷 모드 자동 차단
```python
# custom_tls_crawler.py:271-277
if is_enabled():
    result = update_akamai_cookies(device_name, response.cookies, worker_id)
    # worker_id가 있으면 (패킷 모드) 업데이트 안 함
```

### 3. 파일 락 (동시 쓰기 방지)
```python
# akamai_updater.py:86-95
fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
# 최대 5초 대기, 타임아웃 시 실패
```

---

## ⚠️ 주의사항

### 원본 보호 원칙 위반
```
원본 cookies.json (읽기 전용) ← 원칙
  ↓
Akamai 쿠키 쓰기 ← 위반!
```

### 리스크
1. **차단 쿠키로 원본 오염 가능**
   - 크롤링 실패 시 차단된 Akamai 쿠키가 원본에 저장됨
   - 해결: 차단 감지 시 즉시 재수집

2. **5분 주기 갱신과 충돌**
   - DynamicCollector가 5분마다 완전 재수집
   - 실시간 업데이트와 주기 갱신이 섞임

3. **병렬 안전성 보장 안 됨** (패킷 모드)
   - Worker들은 업데이트 차단됨
   - 리얼 모드만 업데이트

---

## 🗑️ 기능 제거 방법

### 1단계: 환경변수 제거
```bash
# AKAMAI_UPDATE=1 제거 (더 이상 사용 안 함)
python main.py --keyword "테스트"  # 비활성화 상태
```

### 2단계: 코드 제거 (완전 삭제 시)
```bash
# 1. 모듈 삭제
rm lib/akamai_updater.py

# 2. custom_tls_crawler.py에서 호출 부분 제거 (line 271-277)
# [테스트용] Akamai 쿠키 업데이트 부분 삭제

# 3. 테스트 스크립트 삭제
rm test_akamai_update.py
rm AKAMAI_UPDATE_README.md
```

---

## 📊 Before vs After

### Before (기본)
```
원본 쿠키 (5분 주기 갱신)
  → 패킷 복사
  → 크롤링
  → 원본 변경 없음 ✅
```

### After (업데이트 활성화)
```
원본 쿠키 (5분 주기 갱신)
  → 리얼 크롤링
  → 응답에서 Akamai 쿠키 추출
  → 원본 업데이트 ⚠️
  → 다음 요청에 반영
```

---

## 🎯 테스트 시나리오

### 시나리오 1: 정상 업데이트
```bash
# 1. 초기 상태
python test_akamai_update.py status "Samsung Galaxy S21 Ultra"
# _abck: OLD_VALUE

# 2. 크롤링 (업데이트 활성화)
AKAMAI_UPDATE=1 python main.py --keyword "아이폰"
# 🔄 Akamai 쿠키 업데이트: _abck, bm_sz (2개)

# 3. 업데이트 확인
python test_akamai_update.py status "Samsung Galaxy S21 Ultra"
# _abck: NEW_VALUE ✅
```

### 시나리오 2: 패킷 모드 (업데이트 안 됨)
```bash
AKAMAI_UPDATE=1 python main.py --keyword "아이폰" --workers 3
# Worker들은 업데이트 안 함 (원본 보호)
```

### 시나리오 3: 차단 발생
```bash
AKAMAI_UPDATE=1 python main.py --keyword "아이폰"
# 차단됨 → 오염된 Akamai 쿠키가 원본에 저장됨 ⚠️
# 해결: 즉시 재수집 (DynamicCollector)
```

---

## 📝 결론

### 사용 권장 상황
- ✅ **리얼 모드 테스트** (단일 크롤링)
- ✅ **Akamai 쿠키 변화 모니터링**
- ✅ **짧은 테스트 세션**

### 사용 비권장 상황
- ❌ **병렬 크롤링** (Worker들은 업데이트 안 됨)
- ❌ **장기 운영** (원본 오염 리스크)
- ❌ **프로덕션 환경** (안정성 우선)

---

**마지막 업데이트:** 2025-10-22 18:40
**작성자:** Claude (Anthropic)
**상태:** 🧪 실험 기능 (Experimental)
