# Database Design Documentation
# 데이터베이스 설계 문서

**Last Updated**: 2025-10-25
**Database**: `browserstack` (MariaDB/MySQL)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Table Schemas](#table-schemas)
3. [Table Relationships](#table-relationships)
4. [Data Flow](#data-flow)
5. [Query Patterns](#query-patterns)
6. [Indexing Strategy](#indexing-strategy)
7. [Usage Examples](#usage-examples)

---

## Overview
## 개요

The `browserstack` database stores all data related to TLS fingerprinting, cookie management, and web crawling results from BrowserStack real devices.

`browserstack` 데이터베이스는 BrowserStack 실기기에서 수집한 TLS 지문, 쿠키 관리, 웹 크롤링 결과를 저장합니다.

**Database Philosophy**:
- **Append-Only for TLS/Cookies**: Never delete old fingerprints - track variance over time
- **Session-Based Tracking**: All crawl operations linked by `session_id`
- **Rich Metadata**: Capture detailed error types, timings, and Akamai detection
- **Analysis-Ready**: Optimized for retrospective analysis and debugging

**데이터베이스 철학**:
- **TLS/쿠키는 추가만**: 오래된 지문을 삭제하지 않음 - 시간에 따른 변동성 추적
- **세션 기반 추적**: 모든 크롤링 작업을 `session_id`로 연결
- **풍부한 메타데이터**: 상세한 에러 타입, 타이밍, Akamai 탐지 정보 저장
- **분석 준비**: 회고적 분석 및 디버깅에 최적화

---

## Table Schemas
## 테이블 스키마

### 1. `tls_fingerprints` - TLS 지문 저장소

**Purpose**: Store TLS fingerprints collected from real devices (append-only)

**목적**: 실기기에서 수집한 TLS 지문 저장 (추가 전용)

```sql
CREATE TABLE tls_fingerprints (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_name         VARCHAR(100) NOT NULL,
  browser             VARCHAR(50) NOT NULL,
  os_version          VARCHAR(20) NOT NULL,

  -- Full TLS/HTTP2 data (JSON)
  tls_data            LONGTEXT NOT NULL,      -- TLS extension, ciphers, ja3, etc.
  http2_data          LONGTEXT NOT NULL,      -- Akamai fingerprint, sent_frames, etc.

  -- Quick lookup fields (extracted from JSON)
  ja3_hash            VARCHAR(64),
  akamai_fingerprint  VARCHAR(100),
  peetprint_hash      VARCHAR(64),

  -- Statistics
  cipher_count        INT,
  extension_count     INT,

  -- Timestamps
  collected_at        DATETIME NOT NULL,      -- When BrowserStack collected this
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  -- Indexes
  INDEX idx_device (device_name, browser, os_version),
  INDEX idx_ja3 (ja3_hash),
  INDEX idx_akamai (akamai_fingerprint),
  INDEX idx_collected (collected_at)
);
```

**Key Fields**:
- `tls_data`: Full TLS fingerprint from https://tls.peet.ws/api/all
  - Contains: ciphers, extensions, ja3, ja3_hash, ja4, peetprint, etc.
- `http2_data`: HTTP/2 fingerprint
  - Contains: akamai_fingerprint, akamai_fingerprint_hash, sent_frames
- `ja3_hash`: Quick lookup (varies per session due to GREASE)
- `akamai_fingerprint`: Quick lookup (stable across sessions)

**주요 필드**:
- `tls_data`: https://tls.peet.ws/api/all 에서 가져온 전체 TLS 지문
  - 포함 내용: ciphers, extensions, ja3, ja3_hash, ja4, peetprint 등
- `http2_data`: HTTP/2 지문
  - 포함 내용: akamai_fingerprint, akamai_fingerprint_hash, sent_frames
- `ja3_hash`: 빠른 조회용 (GREASE로 인해 세션마다 변동)
- `akamai_fingerprint`: 빠른 조회용 (세션 간 안정적)

**Important**: This table is **append-only**. Never UPDATE or DELETE records.
**중요**: 이 테이블은 **추가 전용**입니다. 레코드를 UPDATE나 DELETE하지 마세요.

---

### 2. `cookies` - 쿠키 저장소

**Purpose**: Store cookies collected from Coupang (append-only with lifecycle tracking)

**목적**: 쿠팡에서 수집한 쿠키 저장 (추가 전용, 생명주기 추적)

```sql
CREATE TABLE cookies (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_name       VARCHAR(100) NOT NULL,
  browser           VARCHAR(50) NOT NULL,
  os_version        VARCHAR(20) NOT NULL,

  -- Cookie metadata
  cookie_type       ENUM('original', 'updated') NOT NULL,  -- original: from BrowserStack, updated: from crawl
  cookie_data       LONGTEXT NOT NULL,                     -- JSON array of cookies

  -- Session context
  session_id        VARCHAR(50),                           -- Which crawl session used this
  page_number       INT,                                   -- Which page updated this

  -- Lifecycle tracking
  collected_at      TIMESTAMP NOT NULL,
  is_valid          BOOLEAN DEFAULT TRUE,
  last_used_at      TIMESTAMP,
  use_count         INT DEFAULT 0,
  success_pages     INT DEFAULT 0,
  failed_pages      INT DEFAULT 0,

  created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  -- Indexes
  INDEX idx_device (device_name, browser, os_version),
  INDEX idx_type (cookie_type),
  INDEX idx_collected (collected_at),
  INDEX idx_session (session_id),
  INDEX idx_valid (is_valid)
);
```

**Key Fields**:
- `cookie_type`:
  - `original`: Initial cookies from BrowserStack dynamic collection
  - `updated`: Cookies updated during multi-page crawling (Set-Cookie)
- `cookie_data`: JSON array with cookies (PCID, sid, _abck, etc.)
- `is_valid`: Tracks if cookies are still working
- `success_pages` / `failed_pages`: Performance tracking

**주요 필드**:
- `cookie_type`:
  - `original`: BrowserStack 동적 수집에서 가져온 초기 쿠키
  - `updated`: 다중 페이지 크롤링 중 업데이트된 쿠키 (Set-Cookie)
- `cookie_data`: 쿠키 배열 JSON (PCID, sid, _abck 등)
- `is_valid`: 쿠키가 여전히 작동하는지 추적
- `success_pages` / `failed_pages`: 성능 추적

**Lifecycle**:
1. Initial collection → `cookie_type = 'original'`
2. Crawl updates cookies → New record with `cookie_type = 'updated'`
3. Track success/failure → Update `is_valid`, `success_pages`, `failed_pages`

**생명주기**:
1. 초기 수집 → `cookie_type = 'original'`
2. 크롤링 중 쿠키 업데이트 → `cookie_type = 'updated'`로 새 레코드
3. 성공/실패 추적 → `is_valid`, `success_pages`, `failed_pages` 업데이트

---

### 3. `products` - 상품 데이터

**Purpose**: Store all products (ranking + ads) from Coupang search results

**목적**: 쿠팡 검색 결과의 모든 상품 (랭킹 + 광고) 저장

```sql
CREATE TABLE products (
  id                 BIGINT AUTO_INCREMENT PRIMARY KEY,

  -- Session context
  session_id         VARCHAR(50) NOT NULL,
  device_name        VARCHAR(100) NOT NULL,
  browser            VARCHAR(50) NOT NULL,
  os_version         VARCHAR(20) NOT NULL,

  -- Search context
  keyword            VARCHAR(200) NOT NULL,
  page_number        INT NOT NULL,

  -- Product classification
  product_type       ENUM('ranking', 'ad') NOT NULL,

  -- Product details
  product_name       VARCHAR(500),
  product_price      VARCHAR(100),
  product_url        VARCHAR(1000),
  product_image_url  VARCHAR(1000),

  -- Ranking products
  rank_position      INT,                    -- 1, 2, 3, ...

  -- Ad products
  ad_slot            VARCHAR(50),            -- "row_1_col_1", "bottom_1", etc.
  ad_type            VARCHAR(50),            -- "SPONSORED", "ROCKET", etc.
  ad_position        INT,                    -- Order within same slot type

  collected_at       TIMESTAMP NOT NULL,

  -- Indexes
  INDEX idx_session (session_id),
  INDEX idx_device (device_name, browser, os_version),
  INDEX idx_keyword (keyword),
  INDEX idx_type (product_type),
  INDEX idx_collected (collected_at)
);
```

**Key Fields**:
- `product_type`: Distinguishes ranking vs. ad products
- `rank_position`: For ranking products (1-based)
- `ad_slot`: Grid position for ads (e.g., "row_1_col_1")
- `ad_type`: SPONSORED, ROCKET, etc.

**주요 필드**:
- `product_type`: 랭킹 vs. 광고 상품 구분
- `rank_position`: 랭킹 상품의 순위 (1부터 시작)
- `ad_slot`: 광고의 그리드 위치 (예: "row_1_col_1")
- `ad_type`: SPONSORED, ROCKET 등

**Query Pattern**:
```sql
-- Get all ranking products for a session
SELECT * FROM products
WHERE session_id = '20251025_123456'
  AND product_type = 'ranking'
ORDER BY page_number, rank_position;

-- Ad distribution analysis
SELECT ad_slot, COUNT(*) as count
FROM products
WHERE product_type = 'ad'
GROUP BY ad_slot;
```

---

### 4. `crawl_details` - 크롤링 상세 정보

**Purpose**: Record every crawl attempt (success or failure) with detailed metrics

**목적**: 모든 크롤링 시도 (성공/실패)를 상세한 지표와 함께 기록

```sql
CREATE TABLE crawl_details (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,

  -- Session context
  session_id              VARCHAR(50) NOT NULL,
  device_name             VARCHAR(100) NOT NULL,
  browser                 VARCHAR(50) NOT NULL,
  os_version              VARCHAR(20) NOT NULL,

  -- Crawl target
  keyword                 VARCHAR(200) NOT NULL,
  page_number             INT NOT NULL,
  worker_id               INT,                    -- For parallel crawling

  -- Outcome
  status                  ENUM(
                            'success',
                            'http2_error',
                            'akamai_challenge',
                            'no_products',
                            'network_error',
                            'timeout',
                            'parsing_error',
                            'unknown_error'
                          ) NOT NULL,
  error_message           TEXT,
  error_type              VARCHAR(100),

  -- HTTP metrics
  response_size_bytes     INT,
  response_time_ms        INT,
  http_status_code        INT,

  -- Akamai detection
  is_akamai_blocked       BOOLEAN,
  akamai_challenge_type   VARCHAR(50),           -- 'bm_sc_challenge', 'akamai_page', etc.
  bm_sc_cookie            VARCHAR(500),          -- Challenge cookie if blocked

  -- Product counts (for success)
  ranking_products_count  INT,
  ad_products_count       INT,
  total_products_count    INT,

  -- Cookie context
  cookie_source           VARCHAR(20),           -- 'original', 'updated', 'session'
  cookie_count            INT,
  has_pcid                BOOLEAN,
  has_sid                 BOOLEAN,

  -- Retry tracking
  attempt_number          INT,
  max_attempts            INT,

  crawled_at              TIMESTAMP NOT NULL,

  -- Indexes
  INDEX idx_session (session_id),
  INDEX idx_device (device_name, browser, os_version),
  INDEX idx_status (status),
  INDEX idx_akamai (is_akamai_blocked),
  INDEX idx_crawled (crawled_at)
);
```

**Key Fields**:
- `status`: Precise error categorization (8 types)
- `is_akamai_blocked`: Quick filter for Akamai blocks
- `akamai_challenge_type`: Specific Akamai challenge detected
- `response_size_bytes`: Detect blocks (< 5KB typically)
- `attempt_number` / `max_attempts`: Retry tracking

**주요 필드**:
- `status`: 정밀한 에러 분류 (8가지 타입)
- `is_akamai_blocked`: Akamai 차단 빠른 필터
- `akamai_challenge_type`: 감지된 특정 Akamai 챌린지
- `response_size_bytes`: 차단 감지 (일반적으로 < 5KB)
- `attempt_number` / `max_attempts`: 재시도 추적

**Analysis Queries**:
```sql
-- Akamai block rate by device
SELECT device_name, browser,
       COUNT(*) as total_attempts,
       SUM(is_akamai_blocked) as blocked,
       ROUND(100.0 * SUM(is_akamai_blocked) / COUNT(*), 2) as block_rate
FROM crawl_details
GROUP BY device_name, browser
ORDER BY block_rate DESC;

-- Success rate by hour
SELECT HOUR(crawled_at) as hour,
       COUNT(*) as total,
       SUM(status = 'success') as success,
       ROUND(100.0 * SUM(status = 'success') / COUNT(*), 2) as success_rate
FROM crawl_details
GROUP BY hour
ORDER BY hour;
```

---

### 5. `crawl_results` - 크롤링 세션 요약

**Purpose**: Aggregate results for each complete crawl session

**목적**: 각 크롤링 세션의 전체 결과 집계

```sql
CREATE TABLE crawl_results (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,

  -- Session identification
  session_id        VARCHAR(50) NOT NULL UNIQUE,
  device_name       VARCHAR(100) NOT NULL,
  browser           VARCHAR(50) NOT NULL,
  os_version        VARCHAR(20) NOT NULL,

  -- Crawl parameters
  keyword           VARCHAR(200) NOT NULL,
  pages_start       INT NOT NULL,
  pages_end         INT NOT NULL,
  workers           INT,                    -- Parallel workers used

  -- Outcome summary
  pages_successful  INT,
  pages_failed      INT,
  total_ranking     INT,
  total_ads         INT,
  status            ENUM('success', 'partial', 'failed'),

  -- Performance
  duration_seconds  FLOAT,

  -- Time analysis
  hour              TINYINT,                -- 0-23
  day_of_week       VARCHAR(10),            -- Monday, Tuesday, ...

  -- Detailed data (JSON)
  full_results      LONGTEXT,               -- Complete crawl results
  errors            LONGTEXT,               -- Array of error details

  created_at        TIMESTAMP,

  -- Indexes
  INDEX idx_session (session_id),
  INDEX idx_device (device_name, browser, os_version),
  INDEX idx_keyword (keyword),
  INDEX idx_status (status),
  INDEX idx_hour (hour),
  INDEX idx_created (created_at)
);
```

**Key Fields**:
- `status`:
  - `success`: All pages crawled successfully
  - `partial`: Some pages failed
  - `failed`: All pages failed
- `hour` / `day_of_week`: Time-based analysis (best crawl times)
- `full_results`: Complete JSON for detailed analysis
- `errors`: Array of all errors encountered

**주요 필드**:
- `status`:
  - `success`: 모든 페이지 크롤링 성공
  - `partial`: 일부 페이지 실패
  - `failed`: 모든 페이지 실패
- `hour` / `day_of_week`: 시간대 분석 (최적 크롤링 시간)
- `full_results`: 상세 분석용 완전한 JSON
- `errors`: 발생한 모든 에러 배열

---

### 6. `device_selections` - 디바이스 선택 이력

**Purpose**: Track last selected device for default value in selector

**목적**: 선택기의 기본값으로 사용할 마지막 선택 디바이스 추적

```sql
CREATE TABLE device_selections (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_name   VARCHAR(100) NOT NULL,
  browser       VARCHAR(50) NOT NULL,
  os_version    VARCHAR(20) NOT NULL,
  category      VARCHAR(50),            -- Galaxy, iPhone, etc.
  selected_at   TIMESTAMP,

  INDEX idx_device (device_name),
  INDEX idx_selected (selected_at)
);
```

**Usage**: Keep only latest N selections for quick lookup.

**사용법**: 빠른 조회를 위해 최근 N개 선택만 유지.

---

### 7. `changelogs` - 변경 이력

**Purpose**: Document all significant changes, discoveries, and fixes

**목적**: 모든 중요한 변경사항, 발견, 수정 사항 문서화

```sql
CREATE TABLE changelogs (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  version         VARCHAR(20) NOT NULL,
  release_date    DATE NOT NULL,
  category        ENUM('feature', 'fix', 'improvement', 'analysis', 'refactor', 'discovery') NOT NULL,
  impact          ENUM('critical', 'major', 'minor') NOT NULL,

  -- Content
  title           VARCHAR(200) NOT NULL,
  description     TEXT,
  files_changed   TEXT,                   -- JSON array of file paths
  code_reference  VARCHAR(200),           -- File:line reference

  -- Metadata
  tags            VARCHAR(500),           -- Comma-separated tags
  tls_extension   VARCHAR(100),           -- If related to TLS (ECH, ALPS, etc.)
  browser_affected VARCHAR(100),          -- Which browsers affected

  created_at      TIMESTAMP,

  -- Indexes
  INDEX idx_version (version),
  INDEX idx_date (release_date),
  INDEX idx_category (category),
  INDEX idx_impact (impact),
  INDEX idx_tags (tags)
);
```

**Example Entry**:
```sql
INSERT INTO changelogs VALUES (
  NULL, 'v2.10', '2025-10-24', 'discovery', 'critical',
  'X25519MLKEM768 identified as sole blocking factor',
  'Confirmed that X25519MLKEM768 extension (4588) is the only reason for Akamai blocking. ECH and ALPS are irrelevant.',
  '["CLAUDE.md"]',
  'CLAUDE.md:125-150',
  'tls,akamai,blocking,x25519mlkem768',
  'X25519MLKEM768',
  'Chromium 124+',
  NOW()
);
```

---

### 8. `tls_variance_samples` - TLS 변동성 샘플

**Purpose**: Store multiple TLS collections from same device for variance analysis

**목적**: 변동성 분석을 위해 동일 디바이스의 여러 TLS 수집 저장

```sql
CREATE TABLE tls_variance_samples (
  id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
  test_session_id    VARCHAR(50) NOT NULL,
  device_name        VARCHAR(100) NOT NULL,
  browser            VARCHAR(50) NOT NULL,
  os_version         VARCHAR(20) NOT NULL,
  sample_number      INT NOT NULL,           -- 1, 2, 3, ...

  -- Full fingerprints
  tls_data           LONGTEXT NOT NULL,
  http2_data         LONGTEXT NOT NULL,

  -- Quick lookup
  ja3_hash           VARCHAR(64),
  akamai_fingerprint VARCHAR(100),

  collected_at       DATETIME NOT NULL,
  created_at         TIMESTAMP,

  -- Indexes
  INDEX idx_test_session (test_session_id),
  INDEX idx_device (device_name, browser, os_version),
  INDEX idx_sample_number (sample_number)
);
```

**Usage**: Compare multiple samples to identify what varies (GREASE) vs. what's stable (Akamai).

**사용법**: 여러 샘플을 비교하여 변동되는 것(GREASE)과 안정적인 것(Akamai)을 식별.

---

## Table Relationships
## 테이블 관계

```
┌─────────────────────┐
│  tls_fingerprints   │  (Append-only)
│  - Device TLS data  │
│  - Collected once   │
└──────────┬──────────┘
           │
           │ Referenced by device_name + browser + os_version
           │
           ▼
┌─────────────────────┐
│      cookies        │  (Append-only with lifecycle)
│  - Original cookies │
│  - Updated cookies  │
└──────────┬──────────┘
           │
           │ Used in crawl sessions
           │
           ▼
┌─────────────────────┐         ┌──────────────────┐
│  crawl_results      │◄────────┤ crawl_details    │
│  - Session summary  │ 1:N     │ - Per-page data  │
│  - Aggregate stats  │         │ - Error details  │
└──────────┬──────────┘         └────────┬─────────┘
           │                              │
           │ session_id                   │ session_id
           │                              │
           ▼                              ▼
┌─────────────────────┐         ┌──────────────────┐
│     products        │         │ (Same session)   │
│  - Ranking items    │         │                  │
│  - Ad items         │         │                  │
└─────────────────────┘         └──────────────────┘

┌─────────────────────┐
│ device_selections   │  (Independent - UI state)
│  - Last selected    │
└─────────────────────┘

┌─────────────────────┐
│    changelogs       │  (Independent - documentation)
│  - Version history  │
└─────────────────────┘

┌─────────────────────┐
│tls_variance_samples │  (Independent - analysis)
│  - Variance tests   │
└─────────────────────┘
```

**Key Relationships**:
1. `tls_fingerprints` + `cookies` → Collected once per device
2. `crawl_results` (1) → `crawl_details` (N) → `products` (N)
3. All linked by `session_id` (format: `YYYYMMDD_HHMMSS`)

**주요 관계**:
1. `tls_fingerprints` + `cookies` → 디바이스당 1회 수집
2. `crawl_results` (1) → `crawl_details` (N) → `products` (N)
3. 모두 `session_id`로 연결 (형식: `YYYYMMDD_HHMMSS`)

---

## Data Flow
## 데이터 흐름

### 1. Initial Device Setup (Once per device)
### 1. 초기 디바이스 설정 (디바이스당 1회)

```
┌─────────────────┐
│ BrowserStack    │
│ Real Device     │
└────────┬────────┘
         │
         │ (1) Navigate to tls.peet.ws
         │ (2) Collect cookies from coupang.com
         │
         ▼
┌─────────────────┐
│DynamicCollector │
└────────┬────────┘
         │
         ├─────► tls_fingerprints (INSERT - append only)
         │         - tls_data (full JSON)
         │         - http2_data (Akamai fingerprint)
         │         - ja3_hash, akamai_fingerprint (extracted)
         │
         └─────► cookies (INSERT - original)
                   - cookie_data (PCID, sid, _abck, etc.)
                   - cookie_type = 'original'
```

### 2. Crawl Session (Multi-page)
### 2. 크롤링 세션 (다중 페이지)

```
┌─────────────────┐
│   main.py       │  Generate session_id
│   --keyword X   │  (e.g., "20251025_123456")
│   --start 1     │
│   --end 10      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│CustomTLSCrawler │  Load TLS + Cookies
└────────┬────────┘
         │
         │ For each page (1-10):
         │
         ├─────► crawl_details (INSERT per attempt)
         │         - session_id, page_number
         │         - status (success/http2_error/akamai_challenge/...)
         │         - response_size_bytes, response_time_ms
         │         - is_akamai_blocked, akamai_challenge_type
         │         - ranking_products_count, ad_products_count
         │         - attempt_number, max_attempts
         │
         ├─────► products (INSERT batch per successful page)
         │         - session_id, page_number
         │         - product_type (ranking/ad)
         │         - rank_position (for ranking)
         │         - ad_slot, ad_type (for ads)
         │
         └─────► cookies (INSERT if Set-Cookie received)
                   - cookie_type = 'updated'
                   - session_id, page_number
```

### 3. Session Summary
### 3. 세션 요약

```
┌─────────────────┐
│   main.py       │  After all pages complete
└────────┬────────┘
         │
         │ Aggregate results
         │
         ▼
┌─────────────────┐
│ crawl_results   │  (INSERT once per session)
│                 │
│ SELECT from crawl_details WHERE session_id = X
│   → pages_successful = COUNT(status = 'success')
│   → pages_failed = COUNT(status != 'success')
│
│ SELECT from products WHERE session_id = X
│   → total_ranking = COUNT(product_type = 'ranking')
│   → total_ads = COUNT(product_type = 'ad')
│
│ status = CASE
│   WHEN pages_failed = 0 THEN 'success'
│   WHEN pages_successful = 0 THEN 'failed'
│   ELSE 'partial'
│ END
└─────────────────┘
```

---

## Query Patterns
## 쿼리 패턴

### Common Queries
### 일반적인 쿼리

#### 1. Get Latest TLS Fingerprint
#### 1. 최신 TLS 지문 가져오기

```sql
SELECT tls_data, http2_data, akamai_fingerprint
FROM tls_fingerprints
WHERE device_name = 'Samsung Galaxy S23 Ultra'
  AND browser = 'android'
  AND os_version = '13.0'
ORDER BY collected_at DESC
LIMIT 1;
```

#### 2. Get Valid Cookies
#### 2. 유효한 쿠키 가져오기

```sql
SELECT cookie_data
FROM cookies
WHERE device_name = 'iPhone 15'
  AND browser = 'iphone'
  AND os_version = '17'
  AND is_valid = TRUE
ORDER BY collected_at DESC
LIMIT 1;
```

#### 3. Session Success Analysis
#### 3. 세션 성공 분석

```sql
SELECT
  session_id,
  device_name,
  keyword,
  pages_successful,
  pages_failed,
  total_ranking,
  total_ads,
  status,
  duration_seconds
FROM crawl_results
WHERE DATE(created_at) = CURDATE()
ORDER BY created_at DESC;
```

#### 4. Akamai Block Rate by Device
#### 4. 디바이스별 Akamai 차단율

```sql
SELECT
  device_name,
  browser,
  os_version,
  COUNT(*) as total_attempts,
  SUM(is_akamai_blocked) as blocked_count,
  ROUND(100.0 * SUM(is_akamai_blocked) / COUNT(*), 2) as block_rate_pct
FROM crawl_details
GROUP BY device_name, browser, os_version
HAVING COUNT(*) >= 10  -- Minimum sample size
ORDER BY block_rate_pct ASC;  -- Best devices first
```

#### 5. Device Performance Comparison
#### 5. 디바이스 성능 비교

```sql
SELECT
  device_name,
  browser,
  COUNT(DISTINCT session_id) as sessions,
  AVG(pages_successful) as avg_success_pages,
  AVG(total_ranking) as avg_ranking_products,
  AVG(total_ads) as avg_ad_products,
  AVG(duration_seconds) as avg_duration
FROM crawl_results
WHERE status IN ('success', 'partial')
GROUP BY device_name, browser
ORDER BY avg_success_pages DESC;
```

#### 6. TLS Variance Analysis
#### 6. TLS 변동성 분석

```sql
-- Check if JA3 varies but Akamai is stable
SELECT
  test_session_id,
  COUNT(DISTINCT ja3_hash) as unique_ja3,
  COUNT(DISTINCT akamai_fingerprint) as unique_akamai,
  GROUP_CONCAT(DISTINCT ja3_hash) as all_ja3_hashes,
  MAX(akamai_fingerprint) as akamai_fp
FROM tls_variance_samples
GROUP BY test_session_id;
```

#### 7. Hourly Success Rate
#### 7. 시간대별 성공률

```sql
SELECT
  hour,
  COUNT(*) as total_sessions,
  SUM(status = 'success') as success_count,
  ROUND(100.0 * SUM(status = 'success') / COUNT(*), 2) as success_rate
FROM crawl_results
GROUP BY hour
ORDER BY hour;
```

#### 8. Product Distribution Analysis
#### 8. 상품 분포 분석

```sql
-- Average products per page by device
SELECT
  d.device_name,
  d.browser,
  AVG(d.ranking_products_count) as avg_ranking_per_page,
  AVG(d.ad_products_count) as avg_ads_per_page,
  AVG(d.total_products_count) as avg_total_per_page
FROM crawl_details d
WHERE d.status = 'success'
GROUP BY d.device_name, d.browser;
```

---

## Indexing Strategy
## 인덱싱 전략

### Primary Indexes (Already Applied)
### 주요 인덱스 (이미 적용됨)

1. **Device Lookups**: `(device_name, browser, os_version)`
   - Used in: All tables
   - Purpose: Fast device-specific queries

2. **Session Tracking**: `(session_id)`
   - Used in: crawl_results, crawl_details, products
   - Purpose: Link all session data

3. **Time-Based**: `(collected_at)`, `(crawled_at)`, `(created_at)`
   - Used in: All tables
   - Purpose: Time-range queries, latest data

4. **Status Filtering**: `(status)`, `(is_akamai_blocked)`, `(is_valid)`
   - Purpose: Filter success/failure, detect blocks

5. **Fingerprint Lookups**: `(ja3_hash)`, `(akamai_fingerprint)`
   - Purpose: Find devices with specific fingerprints

### Composite Index Recommendations
### 복합 인덱스 권장사항

```sql
-- If frequently querying by device + time range
CREATE INDEX idx_device_time ON crawl_details (device_name, browser, os_version, crawled_at);

-- If analyzing Akamai blocks by time
CREATE INDEX idx_akamai_time ON crawl_details (is_akamai_blocked, crawled_at);

-- If analyzing products by keyword + time
CREATE INDEX idx_keyword_time ON products (keyword, collected_at);
```

---

## Usage Examples
## 사용 예시

### Python Usage with DBManager
### DBManager를 사용한 Python 사용법

```python
from lib.db.manager import DBManager

db = DBManager()

# 1. Save TLS Fingerprint
tls_id = db.save_tls_fingerprint(
    device_name="Samsung Galaxy S23 Ultra",
    browser="android",
    os_version="13.0",
    tls_data=tls_info['tls'],        # Full TLS dict
    http2_data=tls_info['http2'],    # Full HTTP/2 dict
    collected_at=datetime.now()
)

# 2. Save Cookie
cookie_id = db.save_cookie(
    device_name="Samsung Galaxy S23 Ultra",
    browser="android",
    os_version="13.0",
    cookie_type="original",
    cookie_data=cookie_list,          # List of cookie dicts
    collected_at=datetime.now()
)

# 3. Save Products (Batch)
db.save_products_batch(
    session_id="20251025_123456",
    device_name="Samsung Galaxy S23 Ultra",
    browser="android",
    os_version="13.0",
    keyword="칫솔",
    page_number=1,
    products_list=extracted_products,  # List of product dicts
    collected_at=datetime.now()
)

# 4. Save Crawl Detail
db.save_crawl_detail(
    session_id="20251025_123456",
    device_name="Samsung Galaxy S23 Ultra",
    browser="android",
    os_version="13.0",
    keyword="칫솔",
    page_number=1,
    status="success",
    detail_data={
        'response_size_bytes': 512000,
        'response_time_ms': 1200,
        'http_status_code': 200,
        'is_akamai_blocked': False,
        'ranking_products_count': 27,
        'ad_products_count': 36,
        'total_products_count': 63,
        'cookie_count': 15,
        'has_pcid': True,
        'has_sid': True
    },
    crawled_at=datetime.now()
)
```

### Direct SQL Queries
### 직접 SQL 쿼리

```python
import pymysql
import json

conn = pymysql.connect(
    host='localhost',
    user='browserstack_user',
    password='your_password',
    database='browserstack',
    charset='utf8mb4'
)

cursor = conn.cursor()

# Get latest TLS for device
cursor.execute("""
    SELECT tls_data, http2_data
    FROM tls_fingerprints
    WHERE device_name = %s AND browser = %s AND os_version = %s
    ORDER BY collected_at DESC
    LIMIT 1
""", ('Samsung Galaxy S23 Ultra', 'android', '13.0'))

row = cursor.fetchone()
if row:
    tls_data = json.loads(row[0])
    http2_data = json.loads(row[1])

    akamai_fp = http2_data['akamai_fingerprint']
    ja3 = tls_data['ja3']

cursor.close()
conn.close()
```

---

## Best Practices
## 모범 사례

### 1. Data Retention
### 1. 데이터 보존

- **TLS/Cookies**: Never delete - track variance over time
- **Products**: Keep at least 30 days for analysis
- **Crawl Details**: Keep at least 90 days for debugging
- **Crawl Results**: Keep indefinitely (small size)

- **TLS/쿠키**: 절대 삭제하지 않음 - 시간에 따른 변동성 추적
- **상품**: 분석을 위해 최소 30일 보관
- **크롤링 상세정보**: 디버깅을 위해 최소 90일 보관
- **크롤링 결과**: 무기한 보관 (작은 크기)

### 2. Session ID Format
### 2. 세션 ID 형식

Always use: `YYYYMMDD_HHMMSS` (e.g., `20251025_143022`)

항상 사용: `YYYYMMDD_HHMMSS` (예: `20251025_143022`)

```python
session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
```

### 3. Error Handling
### 3. 에러 처리

Always save `crawl_details` even on failure - crucial for debugging!

실패 시에도 항상 `crawl_details` 저장 - 디버깅에 중요!

```python
try:
    result = crawler.crawl_page(page)
    db.save_crawl_detail(status='success', ...)
except Exception as e:
    db.save_crawl_detail(
        status='unknown_error',
        error_message=str(e),
        error_type=type(e).__name__,
        ...
    )
```

### 4. JSON Storage
### 4. JSON 저장

Always use `ensure_ascii=False` for Korean text:

한글 텍스트를 위해 항상 `ensure_ascii=False` 사용:

```python
json.dumps(data, ensure_ascii=False)
```

### 5. Batch Inserts
### 5. 배치 삽입

Use `executemany()` for products (much faster):

상품에는 `executemany()` 사용 (훨씬 빠름):

```python
cursor.executemany("""
    INSERT INTO products (...) VALUES (...)
""", values_list)
```

---

## Schema Migrations
## 스키마 마이그레이션

When adding new columns, always provide defaults:

새 컬럼 추가 시 항상 기본값 제공:

```sql
ALTER TABLE crawl_details
ADD COLUMN new_field VARCHAR(100) DEFAULT NULL;

-- Add index if needed
CREATE INDEX idx_new_field ON crawl_details (new_field);
```

---

## Troubleshooting
## 문제 해결

### Check Table Sizes
### 테이블 크기 확인

```sql
SELECT
  table_name,
  ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb,
  table_rows
FROM information_schema.TABLES
WHERE table_schema = 'browserstack'
ORDER BY (data_length + index_length) DESC;
```

### Find Slow Queries
### 느린 쿼리 찾기

```sql
-- Enable slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;  -- 2 seconds

-- Check slow queries
SELECT * FROM mysql.slow_log
ORDER BY query_time DESC
LIMIT 10;
```

### Check Index Usage
### 인덱스 사용 확인

```sql
EXPLAIN SELECT * FROM crawl_details
WHERE device_name = 'Samsung Galaxy S23 Ultra'
  AND browser = 'android';
```

---

## Changelog
## 변경 이력

- **2025-10-25**: Initial documentation
  - Documented all 8 tables
  - Added query patterns and examples
  - Added best practices

---

**Last Updated**: 2025-10-25
**Maintained By**: Claude (Anthropic)
**Referenced In**: CLAUDE.md
