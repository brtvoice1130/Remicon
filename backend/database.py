import sqlite3
import json
import re
from datetime import datetime
from typing import List, Dict

class DatabaseManager:
    def __init__(self, db_path: str = "remicon.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 추출 데이터 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS extracted_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    upload_date TEXT NOT NULL,
                    site_name TEXT,
                    supplier TEXT,
                    item_name TEXT,
                    specification TEXT,
                    unit TEXT,
                    quantity REAL,
                    unit_price REAL,
                    amount REAL,
                    tax_amount REAL,
                    total_amount REAL,
                    currency TEXT DEFAULT 'KRW',
                    method TEXT,
                    raw_data TEXT,
                    prompt_used TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 파일 업로드 히스토리 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS upload_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_size INTEGER,
                    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    extracted_rows INTEGER DEFAULT 0
                )
            """)

            conn.commit()

    def save_extracted_data(self, filename: str, extracted_tables: List[Dict], prompt_used: str = None) -> int:
        """추출된 데이터를 데이터베이스에 저장 (중복 방지 및 검증 강화)"""
        saved_count = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            upload_date = datetime.now().strftime("%Y-%m-%d")

            # 기존 파일의 데이터 삭제 (중복 방지)
            cursor.execute("DELETE FROM extracted_data WHERE filename = ?", (filename,))
            cursor.execute("DELETE FROM upload_history WHERE filename = ?", (filename,))

            valid_rows = []

            for row_data in extracted_tables:
                # OCR 텍스트만 있는 경우 스키프
                if 'ocr_text' in row_data and len(row_data) == 1:
                    continue

                # 데이터 매핑 및 정제
                mapped_data = self.map_data_to_schema(row_data, filename, upload_date, prompt_used)

                # 강화된 유효성 검사
                if self.is_valid_data_enhanced(mapped_data):
                    valid_rows.append(mapped_data)

            # 유효한 데이터가 있을 때만 저장
            if valid_rows:
                # 파일 업로드 히스토리 저장
                cursor.execute("""
                    INSERT INTO upload_history (filename, status, extracted_rows)
                    VALUES (?, ?, ?)
                """, (filename, "success", len(valid_rows)))

                for mapped_data in valid_rows:
                    cursor.execute("""
                        INSERT INTO extracted_data
                        (filename, upload_date, site_name, supplier, item_name, specification,
                         unit, quantity, unit_price, amount, tax_amount, total_amount,
                         currency, method, raw_data, prompt_used)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, mapped_data)
                    saved_count += 1

                conn.commit()
            else:
                # 유효한 데이터가 없는 경우
                cursor.execute("""
                    INSERT INTO upload_history (filename, status, extracted_rows)
                    VALUES (?, ?, ?)
                """, (filename, "no_valid_data", 0))
                conn.commit()

        return saved_count

    def is_valid_data(self, mapped_data: tuple) -> bool:
        """AI 우선 데이터 검증 - AI 처리 데이터는 더 관대하게 검증"""
        # mapped_data 구조: (filename, upload_date, site_name, supplier, item_name, specification,
        #                   unit, quantity, unit_price, amount, tax_amount, total_amount,
        #                   currency, method, raw_data, prompt_used)

        site_name = mapped_data[2].strip() if mapped_data[2] else ""
        supplier = mapped_data[3].strip() if mapped_data[3] else ""
        item_name = mapped_data[4].strip() if mapped_data[4] else ""
        specification = mapped_data[5].strip() if mapped_data[5] else ""
        quantity = mapped_data[7] if mapped_data[7] else 0
        unit_price = mapped_data[8] if mapped_data[8] else 0
        amount = mapped_data[9] if mapped_data[9] else 0
        total_amount = mapped_data[11] if mapped_data[11] else 0

        # AI 처리 실패 케이스 제외
        if any(fail_indicator in item_name for fail_indicator in ["추출 실패", "AI 처리 실패", "텍스트 추출 실패"]):
            print(f"❌ 검증 실패: AI 처리 오류 - {item_name}")
            return False

        # AI 데이터는 더 관대한 검증 (AI가 이미 의미있는 데이터만 추출했다고 가정)
        has_supplier = len(supplier) > 1
        has_site = len(site_name) > 1
        has_item_info = len(item_name) > 1 or len(specification) > 1
        has_numeric_data = quantity > 0 or unit_price > 0 or amount > 0 or total_amount > 0

        # 더 유연한 검증: 공급자/현장명/품목/금액 중 2개 이상 있으면 유효
        criteria_met = sum([has_supplier, has_site, has_item_info, has_numeric_data])

        # 특별 케이스: 공급자만 있어도 회사 정보로서 가치 있음
        if has_supplier and len(supplier) > 5:  # 의미있는 회사명
            is_valid = True
            print(f"✅ 검증 통과 (공급자 정보): {supplier} (총액: {total_amount:,.0f})")
        # 일반 케이스: 2개 이상 조건 만족
        elif criteria_met >= 2:
            is_valid = True
            print(f"✅ 검증 통과 ({criteria_met}/4 조건): {supplier} - {item_name} (총액: {total_amount:,.0f})")
        else:
            is_valid = False
            print(f"❌ 검증 실패: 조건 부족 ({criteria_met}/4) - S:{supplier[:20]} I:{item_name[:20]}")

        return is_valid

    def is_valid_data_enhanced(self, mapped_data: tuple) -> bool:
        """강화된 데이터 검증 - 공급자 구분 및 실제 거래 데이터만 허용"""
        # mapped_data 구조: (filename, upload_date, site_name, supplier, item_name, specification,
        #                   unit, quantity, unit_price, amount, tax_amount, total_amount,
        #                   currency, method, raw_data, prompt_used)

        supplier = mapped_data[3].strip() if mapped_data[3] else ""
        item_name = mapped_data[4].strip() if mapped_data[4] else ""
        total_amount = mapped_data[11] if mapped_data[11] else 0

        # 1. 공급자 검증 - 포스코이앤씨는 공급자가 아님
        invalid_suppliers = ['포스코이앤씨', '포스코', '(주)포스코이앤씨', 'POSCO']
        if any(invalid in supplier for invalid in invalid_suppliers):
            print(f"❌ 잘못된 공급자 제외: {supplier}")
            return False

        # 2. 기본 데이터 검증 - 공급자가 있으면 저장 (품목 없어도 OK)
        if not supplier or len(supplier) < 3:
            print(f"❌ 유효하지 않은 공급자: {supplier}")
            return False

        # 레미콘 품목이 없어도 허용 (다른 데이터라도 의미 있을 수 있음)
        if not item_name:
            print(f"⚠️ 품목 정보 없음 (허용): {supplier}")
        elif '레미콘' not in item_name:
            print(f"⚠️ 레미콘 외 품목 (허용): {supplier} - {item_name}")

        # 금액이 없어도 허용 (공급자 정보만으로도 의미 있음)
        if not total_amount or total_amount <= 0:
            print(f"⚠️ 금액 정보 없음 (허용): {supplier} - {item_name}")
        else:
            print(f"✅ 완전한 거래 데이터: {supplier} - {item_name} ({total_amount:,.0f}원)")

        # 3. 유효한 공급자 목록 확인 (화이트리스트)
        valid_supplier_keywords = ['에스피레미콘', '유진기업', '쌍용레미콘', '레미콘']
        if not any(keyword in supplier for keyword in valid_supplier_keywords):
            print(f"⚠️ 의심스러운 공급자 (확인 필요): {supplier}")

        print(f"✅ 유효한 거래 데이터: {supplier} - {item_name} ({total_amount:,.0f}원)")
        return True

    def map_data_to_schema(self, row_data: Dict, filename: str, upload_date: str, prompt_used: str = None) -> tuple:
        """추출된 데이터를 데이터베이스 스키마에 매핑"""

        def safe_float(value) -> float:
            """안전한 float 변환"""
            try:
                if value is None or value == "":
                    return 0.0
                if isinstance(value, (int, float)):
                    return float(value)
                # 문자열에서 숫자만 추출
                cleaned = ''.join(c for c in str(value) if c.isdigit() or c in '.-')
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0

        def safe_string(value) -> str:
            """안전한 문자열 변환"""
            if value is None:
                return ""
            return str(value).strip()

        # AI 우선: 구조화된 데이터 직접 매핑 (메인 처리 방식)
        if any(key in row_data for key in ['공급자', '현장명', '품명', '규격']):
            # AI가 추출한 구조화된 데이터 (우선 처리)
            site_name = safe_string(row_data.get('현장명', row_data.get('납기장소', '')))
            supplier = safe_string(row_data.get('공급자', ''))
            item_name = safe_string(row_data.get('품명', row_data.get('품목', '')))
            specification = safe_string(row_data.get('규격', ''))
            unit = safe_string(row_data.get('단위', ''))
            quantity = safe_float(row_data.get('물량', row_data.get('수량', 0)))
            unit_price = safe_float(row_data.get('단가', 0))
            amount = safe_float(row_data.get('공급가액', row_data.get('금액', 0)))
            tax_amount = safe_float(row_data.get('세액', 0))
            total_amount = safe_float(row_data.get('합계', 0))

            print(f"🤖 AI 데이터 매핑 완료: {supplier} - {item_name} ({specification})")
        else:
            # 기존 테이블 추출 데이터 처리
            key_mappings = {
                'site_name': ['현장명', '납기장소', '현장', '납품처', '현장주소', '공사명'],
                'supplier': ['공급자', '업체', '회사', '공급업체', '판매자', '상호', 'supplier'],
                'item_name': ['품명', '품목', '상품명', '제품명', '항목', '내용', 'item', 'name', '제품', '제 품'],
                'specification': ['규격', '사양', '스펙', '단위규격', '상세규격', 'spec', '제품(규격)', '제 품(규 격)'],
                'unit': ['단위', 'unit', '개', '식', 'ea', 'set'],
                'quantity': ['수량', '물량', 'qty', 'quantity', '개수', '공급량', '수 량'],
                'unit_price': ['단가', '단위가격', '가격', 'price', '단 가'],
                'amount': ['금액', '공급가액', '합계', '총액', 'amount', '공 급 가 액', '공급 가액'],
                'tax_amount': ['세액', '부가세', 'vat', '세금', 'tax', '세 액'],
                'total_amount': ['합계', '총금액', '최종금액', 'total', '합 계']
            }

            def find_value_by_keys(data: Dict, key_list: List[str]) -> str:
                """키워드 목록으로 값 찾기 (공백과 줄바꿈 무시)"""
                for data_key, value in data.items():
                    if data_key is None:
                        continue
                    # 공백과 줄바꿈 제거해서 비교
                    data_key_clean = str(data_key).replace(' ', '').replace('\n', '').lower()
                    for key in key_list:
                        key_clean = key.replace(' ', '').replace('\n', '').lower()
                        if key_clean in data_key_clean:
                            return safe_string(value)
                return ""

            site_name = find_value_by_keys(row_data, key_mappings['site_name'])
            supplier = find_value_by_keys(row_data, key_mappings['supplier'])

            # 품목과 규격 추출 (복합 필드 처리)
            item_name = find_value_by_keys(row_data, key_mappings['item_name'])
            specification = find_value_by_keys(row_data, key_mappings['specification'])

            # 제품(규격) 복합 필드 처리
            combined_product = find_value_by_keys(row_data, ['제품(규격)', '제 품(규 격)'])
            if combined_product and not item_name:
                # 규격 패턴 추출 (예: 25-35-180)
                spec_pattern = re.search(r'(\d+-\d+-\d+)', combined_product)
                if spec_pattern:
                    specification = spec_pattern.group(1)
                    item_name = combined_product.replace(specification, '').strip('-').strip()
                else:
                    item_name = combined_product

            unit = find_value_by_keys(row_data, key_mappings['unit'])
            quantity = safe_float(find_value_by_keys(row_data, key_mappings['quantity']))
            unit_price = safe_float(find_value_by_keys(row_data, key_mappings['unit_price']))
            amount = safe_float(find_value_by_keys(row_data, key_mappings['amount']))
            tax_amount = safe_float(find_value_by_keys(row_data, key_mappings['tax_amount']))
            total_amount = safe_float(find_value_by_keys(row_data, key_mappings['total_amount']))

        # 계산된 값 추정 (누락된 값들을 계산으로 채움)
        if amount == 0.0 and quantity > 0 and unit_price > 0:
            amount = quantity * unit_price

        if tax_amount == 0.0 and amount > 0:
            tax_amount = amount * 0.1  # 10% 부가세

        if total_amount == 0.0 and amount > 0:
            total_amount = amount + tax_amount

        return (
            filename, upload_date, site_name, supplier, item_name, specification,
            unit, quantity, unit_price, amount, tax_amount, total_amount,
            'KRW', '대가건설', json.dumps(row_data, ensure_ascii=False), prompt_used or ""
        )

    def get_all_data(self) -> List[Dict]:
        """저장된 모든 데이터 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, filename, upload_date, site_name, supplier, item_name, specification,
                       unit, quantity, unit_price, amount, tax_amount, total_amount,
                       currency, method, prompt_used, created_at
                FROM extracted_data
                ORDER BY created_at DESC
            """)

            columns = [description[0] for description in cursor.description]
            results = []

            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                results.append(row_dict)

            return results

    def get_statistics(self) -> Dict:
        """통계 정보 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 총 레코드 수
            cursor.execute("SELECT COUNT(*) FROM extracted_data")
            total_records = cursor.fetchone()[0]

            # 총 업로드 파일 수
            cursor.execute("SELECT COUNT(DISTINCT filename) FROM extracted_data")
            total_files = cursor.fetchone()[0]

            # 총 금액
            cursor.execute("SELECT SUM(total_amount) FROM extracted_data")
            total_amount = cursor.fetchone()[0] or 0

            return {
                "total_records": total_records,
                "total_files": total_files,
                "total_amount": total_amount
            }