-- 상품 정보 테이블
-- 크롤링으로 수집된 모든 상품 데이터 저장 (랭킹 + 광고)

CREATE TABLE IF NOT EXISTS products (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- 세션 정보
    session_id VARCHAR(50) NOT NULL,

    -- 디바이스 정보
    device_name VARCHAR(100) NOT NULL,
    browser VARCHAR(50) NOT NULL,
    os_version VARCHAR(20) NOT NULL,

    -- 검색 정보
    keyword VARCHAR(200) NOT NULL,
    page_number INT NOT NULL,

    -- 상품 타입
    product_type ENUM('ranking', 'ad') NOT NULL,

    -- 상품 정보
    product_name VARCHAR(500),
    product_price VARCHAR(100),
    product_url VARCHAR(1000),
    product_image_url VARCHAR(1000),

    -- 위치 정보
    rank_position INT,           -- 랭킹 상품 순위 (1~27)
    ad_slot VARCHAR(50),         -- 광고 슬롯 (예: "검색결과최상단_1")

    -- 광고 세부 정보
    ad_type VARCHAR(50),         -- 광고 타입 (검색결과최상단, 검색결과중간, 등)
    ad_position INT,             -- 광고 내 순서

    -- 수집 시각
    collected_at TIMESTAMP NOT NULL,

    -- 인덱스
    INDEX idx_session (session_id),
    INDEX idx_device (device_name, browser, os_version),
    INDEX idx_keyword (keyword),
    INDEX idx_type (product_type),
    INDEX idx_collected_at (collected_at)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
