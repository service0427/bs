# Scripts 디렉토리

BrowserStack TLS Crawler 프로젝트의 유틸리티 스크립트 모음입니다.

## 📁 파일 목록

### TLS 분석 및 수집

#### `collect_tls_samples.py`
**목적:** BrowserStack 실기기에서 TLS fingerprint 샘플을 다중 수집

**사용법:**
```bash
python scripts/collect_tls_samples.py
```

**기능:**
- 인터랙티브 디바이스 선택
- 동일 디바이스에서 N회 반복 수집
- peet.ws에서 TLS fingerprint 수집
- `data/tls_samples/{device}_{timestamp}/` 디렉토리에 저장
- GREASE 값 변동 분석용

**예시 출력:**
```
data/tls_samples/Samsung_Galaxy_S23_Ultra_20251023_160532/
├── sample_001.json
├── sample_002.json
├── sample_003.json
...
└── sample_010.json
```

---

#### `collect_daily_tls.py`
**목적:** 일일 TLS fingerprint 자동 수집 (크론탭 실행용)

**사용법:**
```bash
# 수동 실행
python scripts/collect_daily_tls.py

# 크론탭 (매일 오전 3시)
0 3 * * * cd /var/www/html/browserstack && python scripts/collect_daily_tls.py
```

**기능:**
- 전체 디바이스 목록에서 TLS 수집
- 기존 TLS가 있으면 스킵
- 에러 시 계속 진행 (로그 출력)
- 일일 배치 작업용

---

#### `analyze_tls_samples.py`
**목적:** 수집된 TLS 샘플 통계 분석

**사용법:**
```bash
python scripts/analyze_tls_samples.py
```

**기능:**
- 샘플 디렉토리 선택
- JA3 Hash 변동 분석 (GREASE 영향)
- Window Size 일관성 확인
- Akamai Fingerprint 동일성 검증
- Extension 순서 분석

**출력 예시:**
```
[분석 결과]
샘플 수: 10개
JA3 Hash: 10개 (모두 다름) → GREASE 영향
Window Size: 1개 (15663105) → 완전 동일
Akamai FP: 1개 → 완전 동일
Extension 순서: GREASE 제외 시 동일
```

---

### 쿠키 관리

#### `cleanup_session_cookies.py`
**목적:** fingerprint 파일에서 세션 쿠키 제거

**사용법:**
```bash
python scripts/cleanup_session_cookies.py
```

**기능:**
- `data/fingerprints/` 전체 스캔
- PCID, sid 등 세션 쿠키 자동 제거
- 백업 생성 (`cookies.json.backup`)
- 제거 전/후 쿠키 수 출력

**제거 대상 쿠키:**
- `PCID`: 쿠팡 세션 ID
- `sid`: 세션 ID
- `sessionid`: 일반 세션 ID
- `session`: 일반 세션
- `JSESSIONID`: Java 세션 ID

**출력 예시:**
```
[Samsung Galaxy S23 Ultra]
  백업: cookies.json.backup
  제거 전: 17개
  제거 후: 15개 (PCID, sid 제거)
```

---

### 데이터 뷰어

#### `view_history.py`
**목적:** 검색 히스토리 조회 및 분석

**사용법:**
```bash
# 전체 히스토리 (최근 20개)
python scripts/view_history.py

# 최근 N개
python scripts/view_history.py --limit 50

# 특정 키워드 검색
python scripts/view_history.py --keyword "아이폰"

# 특정 디바이스 필터
python scripts/view_history.py --device "Samsung Galaxy S23 Ultra"

# 성공만 보기
python scripts/view_history.py --success-only

# 실패만 보기
python scripts/view_history.py --failure-only
```

**기능:**
- `data/search_history.jsonl` 파일 읽기
- 키워드, 디바이스, 성공/실패 필터
- 페이지별 상세 정보 출력
- 크롤링 소요 시간 표시

**출력 예시:**
```
[1] 2025-10-23 15:30:42
    키워드: 아이폰
    디바이스: iPhone 17 (Safari, iOS 18.6)
    Worker: 1개 (단일)
    페이지: 1~3 (3/3 성공)
    랭킹: 90개, 광고: 30개
    소요시간: 45초
    정책: auto
```

---

## 🎯 권장 워크플로우

### 1. 새 디바이스 TLS 수집
```bash
# Step 1: TLS 샘플 수집 (10개)
python scripts/collect_tls_samples.py

# Step 2: 통계 분석
python scripts/analyze_tls_samples.py

# Step 3: 문제 없으면 메인 크롤링
python main.py --keyword "테스트" --force-refresh
```

### 2. 세션 쿠키 정리 (v2.7 이후 불필요)
```bash
# v2.7 이전 데이터만 정리
python scripts/cleanup_session_cookies.py
```

### 3. 크롤링 히스토리 분석
```bash
# 최근 실패 케이스 확인
python scripts/view_history.py --failure-only --limit 10
```

---

## 📝 참고사항

### TLS 샘플 수집 주기
- **GREASE 분석**: 10~20개 샘플로 충분
- **Window Size 검증**: 5개 샘플로 충분
- **일일 수집**: 불필요 (TLS는 디바이스당 고정)

### 세션 쿠키 정책 (v2.7)
- **수집 안 함**: 크롤링 중 서버에서 자동 발급
- **저장 안 함**: cookies.json에 포함 X
- **cleanup 불필요**: 새로 수집된 데이터는 이미 세션 쿠키 제외

### 히스토리 보관 정책
- **형식**: JSONL (JSON Lines, 1줄 = 1 레코드)
- **크기 제한**: 없음 (무제한 추가)
- **정리**: 수동 (필요 시 오래된 데이터 삭제)

---

## 🔧 유지보수

### 스크립트 의존성
```bash
# 필요한 패키지
pip install selenium curl-cffi
```

### BrowserStack Local 필요
- `collect_tls_samples.py`
- `collect_daily_tls.py`

**확인:**
```bash
ps aux | grep BrowserStackLocal
```

---

**마지막 업데이트:** 2025-10-23
**작성자:** Claude (Anthropic)
