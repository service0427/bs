# lib 폴더 구조

BrowserStack TLS Crawler의 핵심 라이브러리 모듈들입니다.

## 📁 폴더 구조

```
lib/
├── db/                     # 데이터베이스 관련 (2개)
├── device/                 # 디바이스/설정 관련 (5개)
├── crawler/                # 크롤링 관련 (2개)
├── logs/                   # 로깅/히스토리 (4개)
└── utils/                  # 분석/유틸리티 (2개)
```

## 📦 모듈 상세

### 🗄️ db/ - 데이터베이스
- `db_config.py` - MariaDB 연결 설정
- `db_manager.py` - TLS/크롤링 결과 저장/조회

### 📱 device/ - 디바이스 설정
- `device_selector.py` - 4단계 인터랙티브 디바이스 선택
- `device_status.py` - 디바이스 성공 기록 추적 (⭐ 표시)
- `tls_builder.py` - TLS Fingerprint 로드/검증
- `crawl_config.py` - 크롤링 설정 입력
- `fingerprint_manager.py` - TLS/쿠키 데이터 수집 추상화

### 🕷️ crawler/ - 크롤링
- `custom_tls_crawler.py` - JA3 기반 커스텀 TLS 크롤러 (핵심)
- `coupang_interaction.py` - 쿠팡 배너 제거 등 인터랙션

### 📝 logs/ - 로깅/히스토리
- `logger.py` - TeeLogger (콘솔 + 파일)
- `unified_logger.py` - 통합 크롤링 로그 (.jsonl)
- `search_history.py` - 검색 히스토리 관리 (레거시)
- `checkpoint.py` - 체크포인트 기능

### 🛠️ utils/ - 유틸리티
- `ad_position_analyzer.py` - 광고 위치 분석
- `akamai_updater.py` - Akamai 쿠키 업데이트 (테스트용)

## 📚 사용 예시

```python
# DB 사용
from lib.db.db_manager import DBManager
db = DBManager()
db.save_tls_fingerprint(...)

# 디바이스 선택
from lib.device.device_selector import select_device
device_config = select_device()

# 크롤링
from lib.crawler.custom_tls_crawler import CustomTLSCrawler
crawler = CustomTLSCrawler(device_name, browser)
crawler.crawl_pages(keyword, 1, 10)

# 로깅
from lib.logs.unified_logger import UnifiedLogger
logger = UnifiedLogger()
logger.log_crawl_attempt(...)
```

## 🔄 버전 히스토리

### v2.14 (2025-10-25)
- **폴더 이름 변경**: `lib/logging/` → `lib/logs/`
  - Python 표준 라이브러리 `logging` 충돌 해결
  - `AttributeError: module 'logging' has no attribute 'getLogger'` 에러 해결
- **import 경로 업데이트**: `lib.logging` → `lib.logs`

### v2.13 (2025-10-25)
- **lib 폴더 정리**: 용도별로 5개 하위 폴더로 분류
  - db/ - 데이터베이스 관련
  - device/ - 디바이스/설정 관련
  - crawler/ - 크롤링 관련
  - logs/ - 로깅/히스토리
  - utils/ - 분석/유틸리티
- **import 경로 업데이트**: 모든 파일의 import 경로 자동 수정
- **목적**: 코드 가독성 향상, 모듈 책임 명확화

---

**마지막 업데이트:** 2025-10-25
