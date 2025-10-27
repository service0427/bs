"""
광고 위치 분석 모듈 (검증 전용)

목적: 광고 로테이션 검증
- DOM 상품 순서 추적
- 광고 슬롯 위치 파악
- 랭킹 vs 광고 비교
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs


class AdPositionAnalyzer:
    """광고 위치 분석기 (검증용)"""

    @staticmethod
    def analyze_html(html):
        """
        HTML에서 상품 리스트와 광고 위치 분석

        Args:
            html: 쿠팡 검색 페이지 HTML

        Returns:
            dict: {
                'products': [상품 리스트 (position 포함)],
                'ranking_products': [랭킹 상품만],
                'ad_products': [광고 상품만],
                'ad_positions': [광고 위치 리스트],
                'total_count': 전체 상품 수,
                'ranking_count': 랭킹 상품 수,
                'ad_count': 광고 수
            }
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 상품 리스트 컨테이너 찾기
        product_list = soup.select_one('#productList, #product-list')
        if not product_list:
            return {
                'products': [],
                'ranking_products': [],
                'ad_products': [],
                'ad_positions': [],
                'total_count': 0,
                'ranking_count': 0,
                'ad_count': 0
            }

        # 모든 상품 링크 찾기
        links = product_list.select('a[href*="/products/"]')

        all_products = []
        ranking_products = []
        ad_products = []
        ad_positions = []

        position = 0  # DOM 순서

        for link in links:
            href = link.get('href', '')

            # /vp/products/ 형식만
            if '/vp/products/' not in href:
                continue

            # product_id 추출
            product_id_match = re.search(r'/vp/products/(\d+)', href)
            if not product_id_match:
                continue

            product_id = product_id_match.group(1)

            # URL 파라미터 파싱
            parsed = urlparse(href)
            params = parse_qs(parsed.query)

            item_id = params.get('itemId', [''])[0]
            vendor_item_id = params.get('vendorItemId', [''])[0]

            # 고유 키: product_id + item_id + vendor_item_id
            unique_key = f"{product_id}_{item_id}_{vendor_item_id}"

            # rank 파라미터 확인
            has_rank = 'rank' in params
            rank = None

            if has_rank:
                try:
                    rank = int(params['rank'][0])
                except (ValueError, IndexError):
                    pass

            # AdMark 클래스 확인
            product_card = link.find_parent('li') or link.find_parent('div')
            has_ad_mark = False

            if product_card:
                ad_mark = product_card.select('[class*="AdMark"]')
                has_ad_mark = len(ad_mark) > 0

            # 상품명, 가격 추출
            name_el = None
            price_el = None

            if product_card:
                name_el = (product_card.select_one('.name') or
                          product_card.select_one('[class*="name"]') or
                          link)
                price_el = (product_card.select_one('.price-value') or
                           product_card.select_one('[class*="price"]'))

            # 상품 데이터
            product_data = {
                'position': position,  # DOM 순서 (0부터 시작)
                'productId': product_id,
                'itemId': item_id,
                'vendorItemId': vendor_item_id,
                'uniqueKey': unique_key,
                'name': name_el.get_text(strip=True) if name_el else '',
                'price': price_el.get_text(strip=True) if price_el else '',
                'url': href,
                'rank': rank,
                'hasRank': has_rank,
                'hasAdMark': has_ad_mark,
                'isAd': not (has_rank and rank is not None and not has_ad_mark)
            }

            all_products.append(product_data)

            # 순수 랭킹 상품 (rank 있고 + AdMark 없음)
            if has_rank and rank is not None and not has_ad_mark:
                ranking_products.append(product_data)
            else:
                ad_products.append(product_data)
                ad_positions.append(position)

            position += 1

        return {
            'products': all_products,
            'ranking_products': ranking_products,
            'ad_products': ad_products,
            'ad_positions': ad_positions,
            'total_count': len(all_products),
            'ranking_count': len(ranking_products),
            'ad_count': len(ad_products)
        }

    @staticmethod
    def compare_results(result1, result2, label1="Visit 1", label2="Visit 2"):
        """
        두 크롤링 결과 비교

        Args:
            result1: 첫 번째 방문 결과
            result2: 두 번째 방문 결과
            label1: 첫 번째 라벨
            label2: 두 번째 라벨

        Returns:
            dict: 비교 결과
        """
        # 랭킹 상품 uniqueKey 추출
        ranking_keys_1 = {p['uniqueKey'] for p in result1['ranking_products']}
        ranking_keys_2 = {p['uniqueKey'] for p in result2['ranking_products']}

        # 광고 uniqueKey 추출
        ad_keys_1 = {p['uniqueKey'] for p in result1['ad_products']}
        ad_keys_2 = {p['uniqueKey'] for p in result2['ad_products']}

        # 광고 위치 비교
        ad_positions_1 = result1['ad_positions']
        ad_positions_2 = result2['ad_positions']

        # 랭킹 상품 일치 확인
        ranking_same = ranking_keys_1 == ranking_keys_2
        ranking_added = ranking_keys_2 - ranking_keys_1
        ranking_removed = ranking_keys_1 - ranking_keys_2

        # 광고 슬롯 위치 일치 확인
        positions_same = ad_positions_1 == ad_positions_2

        # 광고 내용 변경 확인
        ad_same = ad_keys_1 == ad_keys_2
        ad_changed = len(ad_keys_1.symmetric_difference(ad_keys_2))
        ad_change_rate = (ad_changed / len(ad_keys_1) * 100) if len(ad_keys_1) > 0 else 0

        return {
            'ranking': {
                'same': ranking_same,
                'count_v1': len(ranking_keys_1),
                'count_v2': len(ranking_keys_2),
                'added': list(ranking_added),
                'removed': list(ranking_removed)
            },
            'ad_positions': {
                'same': positions_same,
                'positions_v1': ad_positions_1,
                'positions_v2': ad_positions_2,
                'count_v1': len(ad_positions_1),
                'count_v2': len(ad_positions_2)
            },
            'ad_content': {
                'same': ad_same,
                'changed_count': ad_changed,
                'change_rate': ad_change_rate,
                'total_v1': len(ad_keys_1),
                'total_v2': len(ad_keys_2)
            }
        }

    @staticmethod
    def print_comparison(comparison, label1="Visit 1", label2="Visit 2"):
        """비교 결과 출력"""
        print("\n" + "="*80)
        print(f"광고 로테이션 검증 결과: {label1} vs {label2}")
        print("="*80)

        # 1. 랭킹 상품 비교
        ranking = comparison['ranking']
        print("\n[1] 랭킹 상품 일관성")
        print(f"  {label1}: {ranking['count_v1']}개")
        print(f"  {label2}: {ranking['count_v2']}개")

        if ranking['same']:
            print(f"  결과: ✅ 완전 동일 (랭킹 상품 리스트 일치)")
        else:
            print(f"  결과: ❌ 불일치")
            if ranking['added']:
                print(f"    추가: {len(ranking['added'])}개")
            if ranking['removed']:
                print(f"    제거: {len(ranking['removed'])}개")

        # 2. 광고 슬롯 위치 비교
        positions = comparison['ad_positions']
        print("\n[2] 광고 슬롯 위치")
        print(f"  {label1}: {positions['count_v1']}개 광고 슬롯")
        print(f"  {label2}: {positions['count_v2']}개 광고 슬롯")

        if positions['same']:
            print(f"  결과: ✅ 광고 위치 동일")
            print(f"    위치: {positions['positions_v1'][:5]}..." if len(positions['positions_v1']) > 5 else f"    위치: {positions['positions_v1']}")
        else:
            print(f"  결과: ⚠️ 광고 위치 변경됨")
            print(f"    {label1} 위치: {positions['positions_v1'][:10]}...")
            print(f"    {label2} 위치: {positions['positions_v2'][:10]}...")

        # 3. 광고 내용 로테이션
        ad_content = comparison['ad_content']
        print("\n[3] 광고 내용 로테이션")
        print(f"  {label1}: {ad_content['total_v1']}개 광고")
        print(f"  {label2}: {ad_content['total_v2']}개 광고")

        if ad_content['same']:
            print(f"  결과: ⚠️ 광고 내용 동일 (로테이션 없음)")
        else:
            print(f"  결과: ✅ 광고 로테이션 작동")
            print(f"    변경: {ad_content['changed_count']}개 ({ad_content['change_rate']:.1f}%)")

        print("\n" + "="*80)

        # 종합 판정
        print("\n[종합 판정]")
        all_passed = True

        if not ranking['same']:
            print("  ❌ 랭킹 상품이 변경됨 (비정상)")
            all_passed = False
        else:
            print("  ✅ 랭킹 상품 일치")

        if not positions['same']:
            print("  ⚠️ 광고 슬롯 위치 변경됨 (확인 필요)")
            all_passed = False
        else:
            print("  ✅ 광고 슬롯 위치 일치")

        if ad_content['same']:
            print("  ⚠️ 광고 로테이션 없음 (확인 필요)")
        else:
            print("  ✅ 광고 로테이션 정상 작동")

        if all_passed:
            print("\n  ✅ 전체 검증 통과: Session 유지 정상 작동")
        else:
            print("\n  ❌ 일부 항목 불일치: 추가 확인 필요")

        print("="*80)

        return comparison
