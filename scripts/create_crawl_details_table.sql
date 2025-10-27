-- 크롤링 세부 정보 테이블
-- 각 페이지 크롤링 시도의 상세 메트릭 저장

CREATE TABLE IF NOT EXISTS crawl_details (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- 세션 정보
    session_id VARCHAR(50) NOT NULL,

    -- 디바이스 정보
    device_name VARCHAR(100) NOT NULL,
    browser VARCHAR(50) NOT NULL,
    os_version VARCHAR(20) NOT NULL,

    -- 크롤링 정보
    keyword VARCHAR(200) NOT NULL,
    page_number INT NOT NULL,
    worker_id INT,

    -- 결과 상태
    status ENUM('success', 'http2_error', 'akamai_challenge', 'no_products',
                'network_error', 'timeout', 'parsing_error', 'unknown_error') NOT NULL,

    -- 에러 정보
    error_message TEXT,
    error_type VARCHAR(100),

    -- 응답 메트릭
    response_size_bytes INT,
    response_time_ms INT,
    http_status_code INT,

    -- Akamai 차단 감지
    is_akamai_blocked BOOLEAN DEFAULT FALSE,
    akamai_challenge_type VARCHAR(50),  -- 'bm_sc_challenge', 'akamai_page', 'no_products_suspicious'
    bm_sc_cookie VARCHAR(500),          -- Akamai Bot Manager 챌린지 쿠키

    -- 상품 수집 결과
    ranking_products_count INT DEFAULT 0,
    ad_products_count INT DEFAULT 0,
    total_products_count INT DEFAULT 0,

    -- 쿠키 상태
    cookie_source VARCHAR(20),          -- 'DB', '파일', 'none'
    cookie_count INT,
    has_pcid BOOLEAN,
    has_sid BOOLEAN,

    -- 재시도 정보
    attempt_number INT DEFAULT 1,
    max_attempts INT DEFAULT 3,

    -- 시간 정보
    crawled_at TIMESTAMP NOT NULL,

    -- 인덱스
    INDEX idx_session (session_id),
    INDEX idx_device (device_name, browser, os_version),
    INDEX idx_status (status),
    INDEX idx_akamai (is_akamai_blocked),
    INDEX idx_crawled_at (crawled_at)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
