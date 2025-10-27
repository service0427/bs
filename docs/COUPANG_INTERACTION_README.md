# 쿠팡 상호작용 모드 (배너 제거 + 검색)

## 📋 개요

쿠키 수집 시 선택적으로 배너 제거 및 검색을 수행하는 모드입니다.

**목적:**
- 리얼 디바이스에서 차단 여부를 확인
- 추가 쿠키 획득 (`FULL_BANNER`, `bottom_sheet_nudge_banner`)
- 실제 사용자처럼 행동하여 차단 회피

**⚠️ 주의:**
- 기본적으로 **비활성화**되어 있습니다
- 쿠키 수집 시간이 약 40초 증가합니다 (배너 대기 20초 + 검색 대기 20초)
- 리얼 디바이스에서만 의미가 있습니다

---

## 🚀 사용 방법

### 1️⃣ 기본 모드 (비활성화)

```bash
python main.py --keyword "아이폰"
```

**수행 단계:**
1. TLS 정보 수집
2. 쿠팡 메인 페이지 접속
3. 필수 쿠키 대기 (_abck, PCID, sid)
4. 쿠키 저장

---

### 2️⃣ 상호작용 모드 (활성화)

```bash
COUPANG_INTERACTION=1 python main.py --keyword "아이폰"
```

**수행 단계:**
1. TLS 정보 수집
2. 쿠팡 메인 페이지 접속
3. 필수 쿠키 대기 (_abck, PCID, sid)
4. **[추가] 배너 닫기**
   - fullBanner 닫기 → `FULL_BANNER` 쿠키 획득
   - bottom sheet banner 닫기 → `bottom_sheet_nudge_banner` 쿠키 획득
5. **[추가] 검색 수행**
   - 검색창에 "노트북" 입력
   - 검색 결과 페이지 도달
6. 쿠키 재수집 (추가 쿠키 포함)
7. 쿠키 저장

**출력 예시:**
```
[iPhone 17 Pro] ========================================
[iPhone 17 Pro] 추가 상호작용 모드 활성화 (COUPANG_INTERACTION=1)
[iPhone 17 Pro] ========================================
[iPhone 17 Pro] 배너 대기 중 (최대 20초)...
[iPhone 17 Pro] fullBanner 확인 중...
[iPhone 17 Pro] fullBanner 닫기 클릭 완료
[iPhone 17 Pro] ✓ FULL_BANNER 쿠키 생성 확인
[iPhone 17 Pro] bottom sheet banner 확인 중...
[iPhone 17 Pro] bottom sheet banner 닫기 클릭 완료
[iPhone 17 Pro] ✓ bottom_sheet_nudge_banner 쿠키 생성 확인
[iPhone 17 Pro] 배너 쿠키 최종 확인:
  - FULL_BANNER: ✓
  - bottom_sheet_nudge_banner: ✓
[iPhone 17 Pro] 검색 시도 중... (키워드: 노트북)
[iPhone 17 Pro] 검색 스크립트 결과: form_submitted
[iPhone 17 Pro] 검색 결과 로드 대기 (20초)...
[iPhone 17 Pro] ✅ 검색 페이지 도달 성공
[iPhone 17 Pro] 상호작용 후 쿠키 재수집: 19개
[iPhone 17 Pro] ========================================
```

---

## 📊 비교

| 항목 | 기본 모드 | 상호작용 모드 |
|------|----------|--------------|
| 소요 시간 | 약 30초 | 약 70초 |
| 쿠키 수 | 약 15개 | 약 19개 |
| FULL_BANNER | ✗ | ✓ |
| bottom_sheet_nudge_banner | ✗ | ✓ |
| 검색 수행 | ✗ | ✓ |
| 차단 확인 | 불가 | 가능 |

---

## 🎯 사용 시나리오

### 시나리오 1: 빠른 쿠키 수집 (운영 환경)
```bash
# 기본 모드 사용
python main.py --keyword "아이폰" --start 1 --end 20
```
- 배너/검색 없이 빠르게 수집
- 운영 환경에서 사용

### 시나리오 2: 차단 여부 확인 (테스트 환경)
```bash
# 상호작용 모드 사용
COUPANG_INTERACTION=1 python main.py --keyword "아이폰"
```
- 실제 사용자처럼 행동
- 리얼 브라우저에서 차단되는지 확인
- 차단되면 쿠키 재수집 또는 디바이스 변경

### 시나리오 3: 새 디바이스 테스트
```bash
# 상호작용 모드로 첫 쿠키 수집
COUPANG_INTERACTION=1 python main.py --keyword "아이폰" --force-refresh

# 정상이면 기본 모드로 대량 크롤링
python main.py --keyword "아이폰" --start 1 --end 100 --workers 5
```

---

## 🔍 획득 가능한 쿠키

### 기본 모드 (약 15개)
- `_abck` (Akamai 필수)
- `PCID` (세션 필수)
- `sid` (세션 필수)
- `bm_sz`, `bm_sv`, `ak_bmsc` (Akamai)
- 기타 일반 쿠키

### 상호작용 모드 (약 19개)
기본 모드 쿠키 + 추가:
- `FULL_BANNER` (배너 닫기)
- `bottom_sheet_nudge_banner` (배너 닫기)
- 검색 관련 쿠키 (검색 수행)

---

## 🛠️ 모듈 구조

```
lib/
  └── coupang_interaction.py
      ├── close_banners()      # 배너 닫기
      ├── perform_search()     # 검색 수행
      └── is_enabled()         # 활성화 여부 확인

collectors/
  └── dynamic_collector.py
      └── collect()            # 상호작용 모듈 호출
```

---

## 📝 구현 세부사항

### 배너 닫기 (`close_banners`)
```python
# fullBanner
fullBanner = document.getElementById('fullBanner')
closeBtn = fullBanner.querySelector('.close-banner-icon-button')
closeBtn.click()

# bottom sheet banner
closeBtn = document.getElementById('bottomSheetBudgeCloseButton')
closeBtn.click()
```

### 검색 수행 (`perform_search`)
```python
# 검색창 찾기
searchInput = document.querySelector('input[name="q"]')

# 값 입력
searchInput.value = '노트북'

# 폼 제출
form = searchInput.closest('form')
form.submit()
```

---

## ⚠️ 주의사항

1. **환경변수 제어**: `COUPANG_INTERACTION=1`로만 활성화
2. **시간 증가**: 쿠키 수집 시간이 약 40초 증가
3. **선택적 사용**: 기본적으로 비활성화 권장
4. **차단 확인용**: 차단 여부 확인이 주 목적
5. **배너 없을 수도**: 배너가 이미 닫혔거나 없으면 쿠키 미생성

---

## 🔄 제거 방법

필요 없으면 쉽게 제거 가능:

```bash
# 1. 환경변수 제거 (비활성화)
python main.py --keyword "아이폰"  # COUPANG_INTERACTION 없이

# 2. 완전 삭제 (선택)
rm lib/coupang_interaction.py
rm COUPANG_INTERACTION_README.md

# 3. dynamic_collector.py 수정
# line 432-451 제거 (선택)
```

---

**마지막 업데이트:** 2025-10-22
**버전:** 1.0
**작성자:** Claude (Anthropic)
