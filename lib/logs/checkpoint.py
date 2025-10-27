"""
체크포인트 관리 모듈
크롤링 중 차단 시 재개를 위한 체크포인트 저장/로드
"""

import os
import json
from datetime import datetime
from lib.settings import get_device_fingerprint_dir


class Checkpoint:
    """체크포인트 관리 클래스"""

    def __init__(self, keyword, device_name, browser, start_page, end_page):
        """
        Args:
            keyword: 검색 키워드
            device_name: 디바이스 이름
            browser: 브라우저 이름
            start_page: 시작 페이지
            end_page: 종료 페이지
        """
        self.keyword = keyword
        self.device_name = device_name
        self.browser = browser
        self.start_page = start_page
        self.end_page = end_page

        # 체크포인트 디렉토리 (lib/logs/ → lib/ → 프로젝트 루트)
        self.checkpoint_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data',
            'checkpoints'
        )
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        # 체크포인트 파일명
        safe_keyword = keyword.replace(' ', '_').replace('/', '_')
        safe_device = device_name.replace(' ', '_').replace('/', '_')
        self.checkpoint_file = os.path.join(
            self.checkpoint_dir,
            f"{safe_keyword}_{safe_device}_{browser}.json"
        )

        # 데이터 구조
        self.data = {
            'keyword': keyword,
            'device': device_name,
            'browser': browser,
            'start_page': start_page,
            'end_page': end_page,
            'completed_pages': [],
            'results': {},
            'last_updated': None,
            'cookies_collected_at': None
        }

    def load(self):
        """체크포인트 로드"""
        if not os.path.exists(self.checkpoint_file):
            return False

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            print(f"⚠️ 체크포인트 로드 실패: {e}")
            return False

    def save(self):
        """체크포인트 저장"""
        self.data['last_updated'] = datetime.now().isoformat()

        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠️ 체크포인트 저장 실패: {e}")
            return False

    def add_result(self, page, result):
        """
        페이지 결과 추가

        Args:
            page: 페이지 번호
            result: 크롤링 결과 dict
        """
        if page not in self.data['completed_pages']:
            self.data['completed_pages'].append(page)
            self.data['completed_pages'].sort()

        # 결과 저장 (성공한 경우만)
        if result.get('success'):
            self.data['results'][str(page)] = {
                'ranking': len(result.get('ranking', [])),
                'ads': len(result.get('ads', [])),
                'total': result.get('total', 0),
                'timestamp': datetime.now().isoformat()
            }

        self.save()

    def get_completed_pages(self):
        """완료된 페이지 목록 반환"""
        return self.data.get('completed_pages', [])

    def get_last_success_page(self):
        """마지막 성공 페이지 번호 반환"""
        completed = self.data.get('completed_pages', [])
        return max(completed) if completed else 0

    def get_next_page(self):
        """다음 크롤링할 페이지 번호 반환"""
        last = self.get_last_success_page()
        return last + 1 if last > 0 else self.start_page

    def is_completed(self):
        """모든 페이지 완료 여부"""
        completed = set(self.data.get('completed_pages', []))
        required = set(range(self.start_page, self.end_page + 1))
        return required.issubset(completed)

    def get_remaining_pages(self):
        """남은 페이지 목록 반환"""
        completed = set(self.data.get('completed_pages', []))
        required = set(range(self.start_page, self.end_page + 1))
        remaining = sorted(required - completed)
        return remaining

    def clear(self):
        """체크포인트 삭제"""
        if os.path.exists(self.checkpoint_file):
            try:
                os.remove(self.checkpoint_file)
                print(f"✓ 체크포인트 삭제됨: {self.checkpoint_file}")
                return True
            except Exception as e:
                print(f"⚠️ 체크포인트 삭제 실패: {e}")
                return False
        return True

    def get_summary(self):
        """체크포인트 요약 반환"""
        completed = len(self.data.get('completed_pages', []))
        total = self.end_page - self.start_page + 1
        last_updated = self.data.get('last_updated', 'N/A')

        return {
            'completed': completed,
            'total': total,
            'progress': f"{completed}/{total}",
            'percentage': f"{(completed/total*100):.1f}%" if total > 0 else "0%",
            'last_updated': last_updated,
            'remaining': self.get_remaining_pages()
        }

    def update_cookies_timestamp(self):
        """쿠키 수집 시간 업데이트"""
        self.data['cookies_collected_at'] = datetime.now().isoformat()
        self.save()

    def __str__(self):
        """체크포인트 정보 출력"""
        summary = self.get_summary()
        return f"Checkpoint({self.keyword}): {summary['progress']} ({summary['percentage']})"
