#!/usr/bin/env python3
"""
Fingerprint Pool Manager - TLS Fingerprint 로테이션 시스템
목적: 동일 IP에서 다양한 디바이스로 인식되게 하여 기기 차단 회피
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import random
import json
from lib.db.manager import DBManager


class FingerprintPool:
    """
    TLS Fingerprint 풀 관리자

    기능:
    1. 사용 가능한 fingerprint 목록 관리
    2. 순환 알고리즘 (Round-Robin, Random, Weighted)
    3. Health Tracking (성공/실패율)
    4. 자동 차단 감지 및 Cooldown
    5. 쿠팡 전용: Chrome 차단 시 Safari/Samsung 자동 전환

    Usage:
        pool = FingerprintPool(target='coupang')
        fp = pool.get_next()  # 다음 사용할 fingerprint
        pool.report_success(fp['id'])  # 성공 보고
        pool.report_failure(fp['id'], error_type='http2_error')  # 실패 보고
    """

    def __init__(self, target='coupang', strategy='weighted'):
        """
        Args:
            target: 타겟 사이트 (coupang, naver)
            strategy: 선택 전략
                - 'round_robin': 순환
                - 'random': 랜덤
                - 'weighted': 가중치 (성공률 기반)
        """
        self.db = DBManager()
        self.target = target
        self.strategy = strategy
        self._current_index = 0  # Round-Robin용
        self._ensure_tables()

    def _ensure_tables(self):
        """fingerprint_health 테이블 생성"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fingerprint_health (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                tls_fingerprint_id BIGINT NOT NULL,
                device_name VARCHAR(100) NOT NULL,
                browser VARCHAR(50) NOT NULL,
                target_site VARCHAR(50) NOT NULL,

                -- 통계
                total_requests INT DEFAULT 0,
                successful_requests INT DEFAULT 0,
                failed_requests INT DEFAULT 0,
                success_rate DECIMAL(5,2) DEFAULT 0.00,

                -- 에러 카운트
                http2_errors INT DEFAULT 0,
                akamai_challenges INT DEFAULT 0,
                timeout_errors INT DEFAULT 0,
                other_errors INT DEFAULT 0,

                -- 상태
                status ENUM('active', 'cooldown', 'banned') DEFAULT 'active',
                cooldown_until DATETIME NULL,
                last_used_at DATETIME NULL,
                last_success_at DATETIME NULL,
                last_failure_at DATETIME NULL,

                -- 메타
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                UNIQUE KEY uk_fp_target (tls_fingerprint_id, target_site),
                INDEX idx_target_status (target_site, status),
                INDEX idx_device (device_name, browser),
                INDEX idx_success_rate (success_rate DESC),
                FOREIGN KEY (tls_fingerprint_id) REFERENCES tls_fingerprints(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        conn.commit()
        cursor.close()
        conn.close()

    def _init_health_record(self, fp_id: int, device_name: str, browser: str) -> int:
        """health 레코드 초기화"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO fingerprint_health
                (tls_fingerprint_id, device_name, browser, target_site)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                updated_at = CURRENT_TIMESTAMP
        """, (fp_id, device_name, browser, self.target))

        conn.commit()

        # 생성된 ID 가져오기
        cursor.execute("""
            SELECT id FROM fingerprint_health
            WHERE tls_fingerprint_id = %s AND target_site = %s
        """, (fp_id, self.target))

        health_id = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return health_id

    def get_available_pool(self, exclude_android_chrome=True) -> List[Dict]:
        """
        사용 가능한 fingerprint 풀 조회

        Args:
            exclude_android_chrome: Android Chrome 제외 (쿠팡 차단)

        Returns:
            [{'id', 'device_name', 'browser', 'tls_data', 'http2_data', ...}, ...]
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # TLS fingerprint + Health 정보 조인
        query = """
            SELECT
                tf.id,
                tf.device_name,
                tf.browser,
                tf.os_version,
                tf.tls_data,
                tf.http2_data,
                tf.ja3_hash,
                tf.akamai_fingerprint,
                COALESCE(fh.status, 'active') as status,
                COALESCE(fh.success_rate, 0) as success_rate,
                COALESCE(fh.total_requests, 0) as total_requests,
                fh.cooldown_until
            FROM tls_fingerprints tf
            LEFT JOIN fingerprint_health fh
                ON tf.id = fh.tls_fingerprint_id
                AND fh.target_site = %s
            WHERE 1=1
        """

        params = [self.target]

        # Android Chrome 제외 (쿠팡 전용)
        if exclude_android_chrome and self.target == 'coupang':
            query += " AND NOT (tf.browser = 'android')"

        # Active + Cooldown 만료된 것만
        query += """
            AND (
                fh.status IS NULL
                OR fh.status = 'active'
                OR (fh.status = 'cooldown' AND fh.cooldown_until < NOW())
            )
        """

        # 성공률 순으로 정렬 (weighted 전략용)
        query += " ORDER BY success_rate DESC, total_requests ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        pool = []
        for row in rows:
            fp = {
                'id': row[0],
                'device_name': row[1],
                'browser': row[2],
                'os_version': row[3],
                'tls_data': json.loads(row[4]) if row[4] else {},
                'http2_data': json.loads(row[5]) if row[5] else {},
                'ja3_hash': row[6],
                'akamai_fingerprint': row[7],
                'status': row[8],
                'success_rate': float(row[9]) if row[9] else 0.0,
                'total_requests': row[10] or 0,
                'cooldown_until': row[11]
            }

            # Health 레코드 없으면 초기화
            if fp['status'] is None:
                self._init_health_record(fp['id'], fp['device_name'], fp['browser'])
                fp['status'] = 'active'

            pool.append(fp)

        cursor.close()
        conn.close()

        return pool

    def get_next(self, exclude_android_chrome=True) -> Optional[Dict]:
        """
        다음 사용할 fingerprint 선택

        전략:
        - round_robin: 순환
        - random: 랜덤
        - weighted: 성공률 가중치
        """
        pool = self.get_available_pool(exclude_android_chrome=exclude_android_chrome)

        if not pool:
            print("⚠️ 사용 가능한 fingerprint 없음!")
            return None

        if self.strategy == 'round_robin':
            # 순환
            fp = pool[self._current_index % len(pool)]
            self._current_index += 1
            return fp

        elif self.strategy == 'random':
            # 랜덤
            return random.choice(pool)

        elif self.strategy == 'weighted':
            # 가중치 (성공률 기반)
            # 새로운 fingerprint (total_requests=0) 우선 테스트
            untested = [fp for fp in pool if fp['total_requests'] == 0]
            if untested:
                return random.choice(untested)

            # 성공률 기반 가중치
            weights = []
            for fp in pool:
                # 성공률 + 보너스 (최근 사용 안 한 것 우대)
                weight = fp['success_rate'] + 10  # 최소 10
                weights.append(weight)

            return random.choices(pool, weights=weights)[0]

        else:
            return pool[0]

    def report_success(self, fp_id: int):
        """성공 보고"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE fingerprint_health
            SET
                total_requests = total_requests + 1,
                successful_requests = successful_requests + 1,
                success_rate = (successful_requests + 1) * 100.0 / (total_requests + 1),
                last_used_at = NOW(),
                last_success_at = NOW(),
                status = 'active',  -- Cooldown 해제
                cooldown_until = NULL
            WHERE tls_fingerprint_id = %s AND target_site = %s
        """, (fp_id, self.target))

        conn.commit()
        cursor.close()
        conn.close()

    def report_failure(self, fp_id: int, error_type='other'):
        """
        실패 보고 및 자동 Cooldown

        Args:
            error_type: http2_error, akamai_challenge, timeout, other
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # 에러 타입별 카운트 증가
        error_column = {
            'http2_error': 'http2_errors',
            'akamai_challenge': 'akamai_challenges',
            'timeout': 'timeout_errors',
            'other': 'other_errors'
        }.get(error_type, 'other_errors')

        # 실패 기록
        cursor.execute(f"""
            UPDATE fingerprint_health
            SET
                total_requests = total_requests + 1,
                failed_requests = failed_requests + 1,
                success_rate = successful_requests * 100.0 / (total_requests + 1),
                {error_column} = {error_column} + 1,
                last_used_at = NOW(),
                last_failure_at = NOW()
            WHERE tls_fingerprint_id = %s AND target_site = %s
        """, (fp_id, self.target))

        # 연속 실패 확인 (최근 3회)
        cursor.execute("""
            SELECT
                failed_requests,
                successful_requests,
                http2_errors,
                akamai_challenges
            FROM fingerprint_health
            WHERE tls_fingerprint_id = %s AND target_site = %s
        """, (fp_id, self.target))

        row = cursor.fetchone()
        if row:
            failed, successful, http2_err, akamai_err = row

            # Cooldown 조건
            should_cooldown = False
            cooldown_minutes = 30  # 기본 30분

            # HTTP2 에러 3회 이상 → 즉시 Cooldown
            if http2_err >= 3:
                should_cooldown = True
                cooldown_minutes = 60  # 1시간

            # Akamai Challenge 5회 이상 → Cooldown
            elif akamai_err >= 5:
                should_cooldown = True
                cooldown_minutes = 120  # 2시간

            # 성공률 20% 미만이고 총 10회 이상 사용 → Cooldown
            elif successful > 0 and (successful / (failed + successful)) < 0.2 and (failed + successful) >= 10:
                should_cooldown = True
                cooldown_minutes = 30

            if should_cooldown:
                cursor.execute("""
                    UPDATE fingerprint_health
                    SET
                        status = 'cooldown',
                        cooldown_until = DATE_ADD(NOW(), INTERVAL %s MINUTE)
                    WHERE tls_fingerprint_id = %s AND target_site = %s
                """, (cooldown_minutes, fp_id, self.target))

                print(f"⏸️  Fingerprint #{fp_id} → Cooldown ({cooldown_minutes}분)")

        conn.commit()
        cursor.close()
        conn.close()

    def get_stats(self) -> Dict:
        """풀 통계"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'cooldown' THEN 1 ELSE 0 END) as cooldown,
                SUM(CASE WHEN status = 'banned' THEN 1 ELSE 0 END) as banned,
                AVG(success_rate) as avg_success_rate,
                SUM(total_requests) as total_requests
            FROM fingerprint_health
            WHERE target_site = %s
        """, (self.target,))

        row = cursor.fetchone()

        stats = {
            'total': row[0] or 0,
            'active': row[1] or 0,
            'cooldown': row[2] or 0,
            'banned': row[3] or 0,
            'avg_success_rate': float(row[4]) if row[4] else 0.0,
            'total_requests': row[5] or 0
        }

        cursor.close()
        conn.close()

        return stats

    def reset_cooldown(self, fp_id: int):
        """수동 Cooldown 해제"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE fingerprint_health
            SET
                status = 'active',
                cooldown_until = NULL
            WHERE tls_fingerprint_id = %s AND target_site = %s
        """, (fp_id, self.target))

        conn.commit()
        cursor.close()
        conn.close()

        print(f"✅ Fingerprint #{fp_id} Cooldown 해제")


# 싱글톤 풀 인스턴스
_pools = {}

def get_pool(target='coupang', strategy='weighted') -> FingerprintPool:
    """싱글톤 풀 인스턴스 반환"""
    key = f"{target}_{strategy}"
    if key not in _pools:
        _pools[key] = FingerprintPool(target=target, strategy=strategy)
    return _pools[key]
