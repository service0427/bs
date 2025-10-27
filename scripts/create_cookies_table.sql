-- 쿠키 관리 테이블
-- BrowserStack에서 수집한 원본 쿠키와 크롤링 중 업데이트된 쿠키를 별도 관리

CREATE TABLE IF NOT EXISTS cookies (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- 디바이스 정보
    device_name VARCHAR(100) NOT NULL,
    browser VARCHAR(50) NOT NULL,
    os_version VARCHAR(20) NOT NULL,

    -- 쿠키 타입
    cookie_type ENUM('original', 'updated') NOT NULL DEFAULT 'original',
    -- original: BrowserStack에서 최초 수집한 원본
    -- updated: 크롤링 중 Set-Cookie로 업데이트된 쿠키

    -- 쿠키 데이터 (JSON)
    cookie_data JSON NOT NULL,
    -- 예: [{"name": "PCID", "value": "17612...", "domain": ".coupang.com", ...}, ...]

    -- 메타데이터
    collected_at TIMESTAMP NOT NULL,           -- 수집/업데이트 시각
    session_id VARCHAR(50),                     -- 크롤링 세션 ID (updated 타입만)
    page_number INT,                            -- 업데이트된 페이지 번호 (updated 타입만)

    -- 쿠키 유효성 검증
    is_valid BOOLEAN DEFAULT TRUE,              -- 차단 여부 (False = 차단됨)
    last_used_at TIMESTAMP,                     -- 마지막 사용 시각
    use_count INT DEFAULT 0,                    -- 사용 횟수

    -- 성능 메트릭
    success_pages INT DEFAULT 0,                -- 성공한 페이지 수
    failed_pages INT DEFAULT 0,                 -- 실패한 페이지 수

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- 인덱스
    INDEX idx_device (device_name, browser, os_version),
    INDEX idx_cookie_type (cookie_type),
    INDEX idx_valid (is_valid),
    INDEX idx_collected_at (collected_at),
    INDEX idx_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 원본 쿠키는 디바이스당 최신 1개만 유지 (자동 정리용 인덱스)
CREATE INDEX idx_original_latest ON cookies (device_name, browser, os_version, cookie_type, collected_at DESC);
