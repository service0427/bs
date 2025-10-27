-- 패치노트/변경이력 테이블
-- TLS 최적화 과정의 모든 변경사항을 체계적으로 관리

CREATE TABLE IF NOT EXISTS changelogs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- 버전 정보
    version VARCHAR(20) NOT NULL,               -- v2.14, v2.13 등
    release_date DATE NOT NULL,                 -- 릴리스 날짜

    -- 변경 분류
    category ENUM(
        'feature',      -- 새 기능 추가
        'fix',          -- 버그 수정
        'improvement',  -- 기능 개선
        'analysis',     -- 분석/검증 (TLS 샘플 분석 등)
        'refactor',     -- 코드 리팩토링
        'discovery'     -- 핵심 발견 (차단 패턴 등)
    ) NOT NULL,

    -- 중요도
    impact ENUM('critical', 'major', 'minor') NOT NULL DEFAULT 'minor',

    -- 제목과 설명
    title VARCHAR(200) NOT NULL,                -- 한줄 요약
    description TEXT,                            -- 상세 설명 (마크다운)

    -- 기술 세부사항
    files_changed TEXT,                          -- 변경된 파일 목록 (JSON 배열)
    code_reference VARCHAR(200),                 -- 파일:라인 (예: "custom_tls.py:303-309")

    -- 분류/검색용 태그
    tags VARCHAR(500),                           -- JSON 배열 (예: '["TLS", "cookie", "Galaxy"]')

    -- TLS 관련 메타데이터 (선택)
    tls_extension VARCHAR(100),                  -- 관련 TLS extension (예: "X25519MLKEM768")
    browser_affected VARCHAR(100),               -- 영향받는 브라우저 (예: "iOS Chrome")

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 인덱스
    INDEX idx_version (version),
    INDEX idx_category (category),
    INDEX idx_impact (impact),
    INDEX idx_release_date (release_date),
    INDEX idx_tags (tags(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
