#!/usr/bin/env python3
"""
DB 통합 테스트
TLS 저장 및 크롤링 결과 저장 검증
"""

import sys
import os
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.db.manager import DBManager


def test_tls_fingerprint_save():
    """TLS Fingerprint 저장 테스트"""
    print("\n" + "="*70)
    print("[1/3] TLS Fingerprint 저장 테스트")
    print("="*70)

    db = DBManager()

    # 샘플 TLS 데이터
    tls_data = {
        'ja3': '771,4865-4866-4867,0-23-65281,29-23-24,0',
        'ja3_hash': 'test_ja3_hash_12345',
        'tls': {
            'ciphers': ['TLS_AES_128_GCM_SHA256', 'TLS_AES_256_GCM_SHA384'],
            'extensions': [
                {'name': 'server_name', 'data': 'example.com'}
            ]
        }
    }

    http2_data = {
        'akamai_fingerprint': '1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p',
        'settings': {
            'HEADER_TABLE_SIZE': 65536,
            'ENABLE_PUSH': 0
        }
    }

    # 저장 (UPSERT)
    try:
        record_id = db.save_tls_fingerprint(
            device_name='Test Device',
            browser='Chrome',
            os_version='14.0',
            tls_data=tls_data,
            http2_data=http2_data,
            test_mode=True
        )

        print(f"✅ 저장 성공 (ID: {record_id})")

        # 조회
        result = db.get_tls_fingerprint('Test Device', 'Chrome', '14.0')

        if result:
            print(f"\n✅ 조회 성공:")
            print(f"  • Device: {result['device_name']}")
            print(f"  • Browser: {result['browser']}")
            print(f"  • OS: {result['os_version']}")
            print(f"  • JA3 Hash: {result['ja3_hash']}")
            print(f"  • Akamai: {result['akamai_fingerprint']}")
            print(f"  • TLS Data Keys: {list(result['tls_data'].keys())}")
            print(f"  • HTTP2 Data Keys: {list(result['http2_data'].keys())}")
            print(f"  • Collected At: {result['collected_at']}")
            print(f"  • Test Mode: {result['test_mode']}")
            return True
        else:
            print("❌ 조회 실패")
            return False

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_variance_sample_save():
    """TLS Variance 샘플 저장 테스트"""
    print("\n" + "="*70)
    print("[2/3] TLS Variance 샘플 저장 테스트")
    print("="*70)

    db = DBManager()

    test_session_id = f"test_variance_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 3개 샘플 저장
    try:
        for i in range(1, 4):
            tls_data = {
                'ja3_hash': f'variance_ja3_hash_{i}',
                'tls': {
                    'ciphers': ['TLS_AES_128_GCM_SHA256'],
                    'grease_value': f'0x{i*0x1A1A:04X}'
                }
            }

            http2_data = {
                'akamai_fingerprint': '1:65536;2:0;4:6291456|15663105|0|m,a,s,p'
            }

            record_id = db.save_variance_sample(
                test_session_id=test_session_id,
                device_name='Test Variance Device',
                browser='Samsung',
                os_version='13.0',
                sample_number=i,
                tls_data=tls_data,
                http2_data=http2_data
            )

            print(f"  ✅ Sample {i} 저장 성공 (ID: {record_id})")

        print(f"\n✅ {test_session_id} 세션 3개 샘플 저장 완료")
        return True

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crawl_result_save():
    """크롤링 결과 저장 테스트"""
    print("\n" + "="*70)
    print("[3/3] 크롤링 결과 저장 테스트")
    print("="*70)

    db = DBManager()

    session_id = f"test_crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    device_config = {
        'device': 'Test iPhone',
        'browser': 'Safari',
        'os_version': '17.0'
    }

    results_summary = {
        'successful_pages': 10,
        'failed_pages': 0,
        'total_ranking': 270,
        'total_ads': 90,
        'pages': [
            {'page': 1, 'ranking_count': 27, 'ad_count': 9},
            {'page': 2, 'ranking_count': 27, 'ad_count': 9}
        ]
    }

    errors = []

    try:
        record_id = db.save_crawl_result(
            session_id=session_id,
            device_config=device_config,
            keyword='테스트키워드',
            pages_start=1,
            pages_end=10,
            results_summary=results_summary,
            duration_seconds=120.5,
            workers=2,
            errors=errors
        )

        print(f"✅ 저장 성공 (ID: {record_id})")

        # 조회
        results = db.get_crawl_results(limit=1, keyword='테스트키워드')

        if results:
            result = results[0]
            print(f"\n✅ 조회 성공:")
            print(f"  • Session ID: {result['session_id']}")
            print(f"  • Device: {result['device_name']}")
            print(f"  • Keyword: {result['keyword']}")
            print(f"  • Pages: {result['pages_start']} ~ {result['pages_end']}")
            print(f"  • Success: {result['pages_successful']} / Failed: {result['pages_failed']}")
            print(f"  • Ranking: {result['total_ranking']} / Ads: {result['total_ads']}")
            print(f"  • Status: {result['status']}")
            print(f"  • Duration: {result['duration_seconds']}s")
            print(f"  • Hour: {result['hour']} / Day: {result['day_of_week']}")
            return True
        else:
            print("❌ 조회 실패")
            return False

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data():
    """테스트 데이터 정리"""
    print("\n" + "="*70)
    print("테스트 데이터 정리")
    print("="*70)

    from lib.db.config import get_db_config
    import pymysql

    config = get_db_config()
    connection = pymysql.connect(**config)
    cursor = connection.cursor()

    try:
        # TLS Fingerprint 테스트 데이터 삭제
        cursor.execute("DELETE FROM tls_fingerprints WHERE test_mode = TRUE")
        tls_deleted = cursor.rowcount

        # Variance 테스트 데이터 삭제
        cursor.execute("DELETE FROM tls_variance_samples WHERE test_session_id LIKE 'test_variance_%'")
        variance_deleted = cursor.rowcount

        # Crawl Result 테스트 데이터 삭제
        cursor.execute("DELETE FROM crawl_results WHERE session_id LIKE 'test_crawl_%'")
        crawl_deleted = cursor.rowcount

        connection.commit()

        print(f"✅ 정리 완료:")
        print(f"  • TLS Fingerprints: {tls_deleted}개 삭제")
        print(f"  • Variance Samples: {variance_deleted}개 삭제")
        print(f"  • Crawl Results: {crawl_deleted}개 삭제")

    except Exception as e:
        print(f"❌ 정리 실패: {e}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()


if __name__ == '__main__':
    print("="*70)
    print("BrowserStack TLS Crawler - DB 통합 테스트")
    print("="*70)

    # 테스트 실행
    test1 = test_tls_fingerprint_save()
    test2 = test_variance_sample_save()
    test3 = test_crawl_result_save()

    # 결과 요약
    print("\n" + "="*70)
    print("테스트 결과 요약")
    print("="*70)

    all_passed = test1 and test2 and test3

    print(f"[1] TLS Fingerprint 저장/조회: {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"[2] Variance 샘플 저장: {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"[3] 크롤링 결과 저장/조회: {'✅ PASS' if test3 else '❌ FAIL'}")

    if all_passed:
        print("\n✅ 모든 테스트 통과!")
    else:
        print("\n❌ 일부 테스트 실패")

    # 테스트 데이터 정리
    cleanup_test_data()

    print("\n" + "="*70)
    print("테스트 완료")
    print("="*70)

    sys.exit(0 if all_passed else 1)
