import pdfplumber
from typing import List, Dict
import pytesseract
from PIL import Image
import io
import json
import re
import os
import google.genai as genai
from db_manager import save_extracted_data

# Gemini API 키 설정 (환경변수에서 가져오기)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️ GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    print("설정 방법: export GEMINI_API_KEY='your_api_key'")
    client = None
else:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("✅ Gemini API 클라이언트 초기화 완료")

def extract_pdf_tables(file_path: str, user_prompt: str = None, debug_mode: bool = False, save_to_db: bool = True, clear_before_save: bool = False) -> List[Dict]:
    """
    AI 전용 PDF 데이터 추출 시스템
    Google Gemini AI만 사용하여 PDF를 분석하고 구조화된 데이터를 추출합니다.
    API 제한 시 작업을 중단하고 사용자에게 안내합니다.
    """
    print("🤖 AI-Only PDF Processing Started")

    # API 클라이언트 사전 확인
    if client is None:
        return [{
            "api_error": True,
            "error_type": "api_not_configured",
            "error_message": "Google AI API 클라이언트가 설정되지 않았습니다.",
            "action_required": "GOOGLE_API_KEY 환경변수를 확인해주세요."
        }]

    # 모든 페이지의 텍스트 추출
    all_text = ""
    page_texts = []

    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"📄 Processing {total_pages} pages with AI")

        for page_num, page in enumerate(pdf.pages):
            print(f"📃 Extracting text from page {page_num + 1}")

            # 페이지 텍스트 추출
            page_text = page.extract_text()
            if page_text:
                page_texts.append(f"=== PAGE {page_num + 1} ===\n{page_text}")
                all_text += f"\n=== PAGE {page_num + 1} ===\n{page_text}\n"

            # 테이블이 있으면 텍스트 형태로 추가 추출
            tables = page.extract_tables()
            if tables:
                for table_idx, table in enumerate(tables):
                    table_text = f"\n[TABLE {table_idx + 1} on PAGE {page_num + 1}]\n"
                    for row in table:
                        if row:
                            row_text = " | ".join(str(cell) if cell else "" for cell in row)
                            table_text += row_text + "\n"
                    all_text += table_text

            # OCR 보조 (이미지 기반 표가 있을 수 있음)
            try:
                pil_img = page.to_image(resolution=300).original
                ocr_text = pytesseract.image_to_string(pil_img, lang="kor+eng")
                if ocr_text.strip():
                    all_text += f"\n[OCR TEXT PAGE {page_num + 1}]\n{ocr_text}\n"
            except Exception as e:
                print(f"OCR failed for page {page_num + 1}: {e}")

    # 디버깅 정보 수집
    debug_info = {
        "pdf_info": {
            "total_pages": total_pages,
            "text_length": len(all_text),
            "has_tables": bool([page for page in pdf.pages for table in page.extract_tables() if table])
        },
        "extraction_steps": [],
        "raw_ai_results": [],
        "validation_results": [],
        "text_preview": all_text[:500] + "..." if len(all_text) > 500 else all_text
    } if debug_mode else None

    # AI로 최적화된 텍스트 처리 (API 호출 최소화)
    ai_extracted_all = []

    # 전체 텍스트를 청크로 분할하여 처리 (페이지별이 아닌 청크별)
    max_chunk_length = 12000  # 토큰 제한 고려

    if len(all_text) > max_chunk_length:
        print(f"🔧 텍스트가 길어서 청크로 분할: {len(all_text)} characters")
        # 페이지 기준으로 청크 분할
        text_chunks = []
        current_chunk = ""

        for page_text in page_texts:
            if len(current_chunk + page_text) > max_chunk_length:
                if current_chunk:
                    text_chunks.append(current_chunk)
                current_chunk = page_text
            else:
                current_chunk += page_text

        if current_chunk:
            text_chunks.append(current_chunk)
    else:
        text_chunks = [all_text]

    print(f"🧠 Processing {len(text_chunks)} chunks with AI (instead of {total_pages} individual pages)")

    for i, chunk in enumerate(text_chunks):
        if chunk.strip():
            print(f"📄 Processing chunk {i+1}/{len(text_chunks)} with AI...")
            if debug_mode:
                debug_info["extraction_steps"].append(f"Processing chunk {i+1} (text length: {len(chunk)})")

            page_extracted = extract_with_ai(chunk, user_prompt)
            if page_extracted:
                    # API 할당량 소진 즉시 감지 및 중단
                    for item in page_extracted:
                        if item.get('api_quota_exceeded'):
                            print("🚫 API 할당량 소진됨 - 작업 즉시 중단")
                            return [{
                                "api_error": True,
                                "error_type": "quota_exceeded",
                                "error_message": "API 사용량 제한으로 프로그램 이용이 제한됩니다.",
                                "recovery_time": "매일 오전 9시 (한국시간)",
                                "recovery_message": "오전 9시 이후에 다시 이용해주세요.",
                                "current_status": "현재 API 할당량이 소진된 상태입니다."
                            }]

                    if debug_mode:
                        debug_info["raw_ai_results"].extend(page_extracted)
                        debug_info["extraction_steps"].append(f"Page {i+1}: extracted {len(page_extracted)} raw records")

                    ai_extracted_all.extend(page_extracted)
                    print(f"✅ Page {i+1}: {len(page_extracted)} records")

        # AI 추출 결과 필터링 및 유효성 검사
        filtered_results = []
        validation_details = []

        for i, result in enumerate(ai_extracted_all):
            if result and isinstance(result, dict):
                # 유효성 검사
                has_product_name = bool(result.get('품명', '').strip())
                has_financial_data = bool(result.get('공급가액') or result.get('금액') or result.get('합계'))
                has_quantity_data = bool(result.get('물량', 0) > 0)
                has_date_data = bool(result.get('출하일', '').strip())

                # 검증 결과 저장
                validation_result = {
                    "index": i,
                    "has_product_name": has_product_name,
                    "has_financial_data": has_financial_data,
                    "has_quantity_data": has_quantity_data,
                    "has_date_data": has_date_data,
                    "data_preview": {k: v for k, v in list(result.items())[:5]}  # 처음 5개 필드만
                }

                # 더 관대한 유효성 검사: 최소 1개 필드만 있어도 유효 (빈 문자열이나 0이 아닌 경우)
                has_supplier = bool(result.get('공급자', '').strip())
                has_customer = bool(result.get('현장명', '').strip())

                # 유효한 필드 개수 계산
                valid_fields = sum([
                    has_product_name,
                    has_financial_data,
                    has_quantity_data,
                    has_date_data,
                    has_supplier,
                    has_customer
                ])

                # 최소 1개 필드라도 있으면 유효 (매우 관대한 기준)
                is_valid = valid_fields >= 1

                print(f"  검증: 품명={has_product_name}, 금액={has_financial_data}, 수량={has_quantity_data}, 날짜={has_date_data}, 공급자={has_supplier}, 현장={has_customer}, 유효필드={valid_fields}")
                validation_result["is_valid"] = is_valid

                if debug_mode:
                    validation_details.append(validation_result)

                if is_valid:
                    filtered_results.append(result)

        if debug_mode:
            debug_info["validation_results"] = validation_details
            debug_info["extraction_steps"].append(f"Validation complete: {len(filtered_results)}/{len(ai_extracted_all)} records passed")

        print(f"🔍 AI 추출 완료: {len(ai_extracted_all)}개 → {len(filtered_results)}개 (유효한 거래 데이터)")

        if filtered_results:
            print(f"✅ AI가 {len(filtered_results)}개의 유효한 거래 데이터를 추출했습니다")

            # DB 저장 옵션이 활성화된 경우
            if save_to_db:
                # 파일명 추출 (전체 경로에서 파일명만)
                import os
                filename = os.path.basename(file_path)

                # DB에 저장
                save_result = save_extracted_data(filename, filtered_results, clear_before_save)

                if debug_mode:
                    return [{
                        "status": "success",
                        "data": filtered_results,
                        "debug_info": debug_info,
                        "db_save_result": save_result
                    }]
                else:
                    # 저장 결과만 반환 (데이터는 DB에 있으므로 불필요)
                    return [{
                        "status": "success_saved",
                        "message": save_result.get("message", "데이터가 저장되었습니다."),
                        "saved_count": save_result.get("saved_count", 0),
                        "filtered_count": save_result.get("filtered_count", 0),
                        "filename": filename,
                        "db_status": save_result.get("status", "unknown")
                    }]
            else:
                # DB 저장하지 않고 데이터 반환
                if debug_mode:
                    return [{
                        "status": "success",
                        "data": filtered_results,
                        "debug_info": debug_info
                    }]
                return filtered_results
        else:
            print("❌ AI가 유효한 거래 데이터를 찾지 못했습니다")
            error_result = {
                "api_error": False,
                "error_type": "no_valid_data",
                "error_message": "PDF에서 유효한 거래 데이터를 찾을 수 없습니다.",
                "suggestion": "다른 PDF 파일을 시도하거나 프롬프트를 수정해보세요.",
                "extracted_count": len(ai_extracted_all),
                "valid_count": len(filtered_results)
            }
            if debug_mode:
                error_result["debug_info"] = debug_info
            return [error_result]
    else:
        print("❌ PDF에서 텍스트를 추출할 수 없습니다")
        return [{
            "api_error": False,
            "error_type": "no_text_extracted",
            "error_message": "PDF에서 텍스트를 읽을 수 없습니다.",
            "suggestion": "PDF 파일이 올바른지 확인하고 다시 시도해주세요.",
            "possible_causes": ["스캔된 이미지 PDF", "암호화된 PDF", "손상된 파일"]
        }]


def extract_supplier_info(table: List[List[str]], headers: List[str]) -> str:
    """테이블에서 공급자 정보 추출"""
    supplier_keywords = ['상호', '회사명', '법인명', '공급자', '업체명']

    for row in table:
        if row:
            for i, cell in enumerate(row):
                if cell:
                    cell_str = str(cell).strip()
                    # 상호 키워드를 찾으면 다음 셀에서 회사명 추출
                    if any(keyword in cell_str for keyword in supplier_keywords):
                        if i + 1 < len(row) and row[i + 1]:
                            company_name = str(row[i + 1]).strip()
                            # 괄호 안의 내용이나 기타 불필요한 정보 제거
                            if '(' in company_name:
                                company_name = company_name.split('(')[0].strip()
                            if company_name and len(company_name) > 1:
                                print(f"Found supplier: {company_name}")
                                return company_name

                    # 직접적으로 회사명이 있는 경우 (주식회사, 주식회사, 회사 등)
                    if any(pattern in cell_str for pattern in ['(주)', '주식회사', '회사', '기업', '㈜']):
                        if len(cell_str) > 5:  # 너무 짧은 것은 제외
                            print(f"Found company name directly: {cell_str}")
                            return cell_str

    return ""


def extract_site_info(table: List[List[str]], headers: List[str]) -> str:
    """테이블에서 현장 정보 추출"""
    site_keywords = ['현장', '납기장소', '공사명', '현장명', '프로젝트', '공사', '납품처', '비고']

    for row in table:
        if row:
            for i, cell in enumerate(row):
                if cell:
                    cell_str = str(cell).strip()
                    # 현장 키워드를 찾으면 다음 셀에서 현장명 추출
                    if any(keyword in cell_str for keyword in site_keywords):
                        if i + 1 < len(row) and row[i + 1]:
                            site_name = str(row[i + 1]).strip()
                            if site_name and len(site_name) > 2:
                                print(f"Found site info: {site_name}")
                                return site_name

                    # 비고 컬럼에서 현장 정보 찾기
                    if '지구' in cell_str or '현장' in cell_str or 'BL' in cell_str or '공사' in cell_str:
                        if len(cell_str) > 3:
                            print(f"Found site info in description: {cell_str}")
                            return cell_str

    return ""


def is_summary_row(row_dict: Dict) -> bool:
    """소계, 합계 행인지 확인"""
    summary_keywords = ['소계', '합계', '총계', '품목집계', '월계', '일계']

    # '계'는 단독으로만 체크 (회사명에 '계'가 들어갈 수 있음)
    standalone_keywords = ['계']

    for key, value in row_dict.items():
        if value and isinstance(value, str):
            value_str = str(value).strip()

            # 명확한 집계 키워드 확인
            if any(keyword in value_str for keyword in summary_keywords):
                return True

            # '계'는 단독으로 있거나 앞뒤에 공백이 있을 때만
            for keyword in standalone_keywords:
                if value_str == keyword or f' {keyword} ' in value_str or value_str.startswith(f'{keyword} ') or value_str.endswith(f' {keyword}'):
                    return True

    return False


def is_actual_transaction(row_dict: Dict) -> bool:
    """실제 거래 데이터인지 확인 (헤더, 합계, 메타데이터 제외)"""
    # 명확하게 제외할 헤더나 메타데이터 키워드
    exclusion_keywords = ['등록번호', '사업장', '대표', '업태', '종목', '전화', '주소', '팩스']

    # 합계/소계 키워드
    summary_keywords = ['합계', '소계', '총계', '품목집계', '월계', '일계']

    for key, value in row_dict.items():
        if value and isinstance(value, str):
            value_str = str(value).strip()

            # 명확한 제외 키워드가 있으면 제외
            if any(keyword in value_str for keyword in exclusion_keywords):
                return False

            # 합계 행인지 확인
            if any(keyword in value_str for keyword in summary_keywords):
                return False

    # 거래 데이터 조건을 더 유연하게: 품명 또는 수량/금액이 있으면 유효
    has_item = False
    has_financial_data = False

    for key, value in row_dict.items():
        if value:
            value_str = str(value).strip()

            # 레미콘 품명 확인 (더 유연하게)
            if '레미콘' in value_str:
                has_item = True

            # 금액이나 수량 데이터 확인
            if (re.search(r'\d{1,3}(?:,\d{3})*', value_str) and  # 숫자 패턴
                (len(re.findall(r'\d', value_str)) >= 3)):  # 최소 3자리 숫자
                has_financial_data = True

    # 품명과 금액/수량 중 하나라도 있으면 유효한 거래로 판단
    return has_item or has_financial_data


def has_meaningful_data(row_dict: Dict) -> bool:
    """의미있는 데이터가 있는 행인지 확인"""
    # 숫자 데이터가 있는지 확인 (더 포괄적으로)
    numeric_fields = ['수량', '단가', '공급가액', '세액', '합계', '물량', '공급량', '가격', '금액', '원']
    data_fields = ['품목', '품명', '제품', '출하일별', '거래', '규격', '상호', '법인명', '회사', '업체', '공급자']

    has_numeric = False
    has_data = False

    for key, value in row_dict.items():
        if value and str(value).strip():
            key_str = str(key).replace('\n', '').replace(' ', '').lower() if key else ''
            value_str = str(value).strip()

            # 숫자가 포함된 필드 확인 (키 이름과 값 모두 확인)
            if any(field in key_str for field in numeric_fields) or any(c.isdigit() for c in value_str if len(value_str) > 0):
                if any(c.isdigit() for c in value_str):
                    has_numeric = True

            # 데이터 필드 확인 (더 유연하게)
            if any(field in key_str for field in data_fields):
                if len(value_str) > 1:
                    has_data = True

            # 날짜 패턴 확인 (출하일 등)
            if '-' in value_str and len(value_str) >= 8:  # 2026-03-16 형식
                has_data = True

            # 회사명/공급자명 패턴 확인 (주식회사, 기업 등)
            if any(pattern in value_str for pattern in ['(주)', '주식회사', '회사', '기업', '㈜']) and len(value_str) > 3:
                has_data = True

            # 숫자 패턴이 포함된 값 확인 (금액, 수량 등)
            if re.search(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?', value_str):
                has_numeric = True

    # 최소한 데이터 필드나 숫자 필드 중 하나는 있어야 함
    return has_numeric or has_data


def flatten_transaction_data(data: Dict) -> List[Dict]:
    """
    AI가 반환하는 다양한 nested JSON 구조를 flat한 거래 레코드 배열로 변환
    """
    flat_records = []

    def extract_nested_value(obj, keys):
        """nested 객체에서 값을 안전하게 추출"""
        if not isinstance(obj, dict):
            return ''

        for key in keys:
            if key in obj:
                value = obj[key]
                if isinstance(value, dict):
                    # nested된 경우 company_name 등을 찾기
                    return value.get('company_name', '') or value.get('name', '') or str(value)
                return str(value) if value else ''
        return ''

    # 다양한 레벨에서 공급자 정보 추출 (Gemini 응답 형태 추가)
    supplier = (
        extract_nested_value(data, ['supplier']) or
        extract_nested_value(data.get('header', {}), ['supplier']) or
        extract_nested_value(data.get('supplier_info', {}), ['company_name', 'name']) or
        data.get('공급자', '') or
        data.get('공급자명', '')  # Gemini 응답 형태
    )

    # 현장명/고객 정보 추출 (Gemini 응답 형태 추가)
    customer = (
        extract_nested_value(data, ['customer', 'receiver', 'buyer']) or
        extract_nested_value(data.get('header', {}), ['customer']) or
        data.get('현장명', '') or
        data.get('delivery_site', '') or
        data.get('project_name', '')
    )

    print(f"Extracted - Supplier: '{supplier}', Customer: '{customer}'")

    # transactions 배열 찾기 (다양한 위치에서, Gemini 응답 형태 추가)
    transactions = (
        data.get('transactions', []) or
        data.get('transaction_list', []) or
        data.get('items', []) or
        data.get('records', []) or
        data.get('거래데이터', []) or  # Gemini 응답 형태
        data.get('거래내역', [])     # 추가 가능한 형태
    )

    # transactions가 없으면 데이터 자체가 거래 레코드인지 확인 (Gemini 형태 추가)
    if not transactions:
        if (data.get('item', '') or data.get('품명', '') or data.get('품목', '') or  # Gemini: 품목
            data.get('date', '') or data.get('출하일', '') or  # Gemini: 출하일
            data.get('amount', '') or data.get('공급가액', '') or data.get('합계', '')):  # Gemini: 공급가액, 합계
            transactions = [data]
        # header 안에 있을 수도 있음
        elif data.get('header', {}).get('transactions', []):
            transactions = data['header']['transactions']

    print(f"Found {len(transactions)} potential transactions")

    for i, transaction in enumerate(transactions):
        if isinstance(transaction, dict):
            print(f"Transaction {i+1}: {list(transaction.keys())}")

            # 🔍 DEBUG: AI가 반환한 모든 필드와 값 출력
            print(f"  전체 데이터: {transaction}")

            # 공급가액 관련 필드 특별 확인
            supply_related_keys = [k for k in transaction.keys() if '가액' in str(k) or '금액' in str(k) or '원' in str(k) or 'amount' in str(k).lower()]
            if supply_related_keys:
                print(f"  💰 공급가액 관련 가능 필드들: {supply_related_keys}")
                for key in supply_related_keys:
                    print(f"    - {key}: {transaction[key]}")

            # 숫자 필드 안전하게 처리
            def safe_int(value):
                if not value:
                    return 0
                try:
                    return int(str(value).replace(',', '').replace('.', ''))
                except:
                    return 0

            def safe_float(value):
                if not value:
                    return 0.0
                try:
                    return float(str(value).replace(',', ''))
                except:
                    return 0.0

            # 필드명 통일 (더 포괄적으로 매핑)
            record = {
                '현장명': (transaction.get('현장명', '') or
                         transaction.get('customer', '') or
                         transaction.get('buyer', '') or
                         transaction.get('site', '') or
                         customer or '포스코이앤씨 관련'),
                '공급자': (transaction.get('공급자', '') or
                         transaction.get('공급자명', '') or  # Gemini 응답
                         transaction.get('supplier', '') or
                         transaction.get('company', '') or
                         supplier or '미확인'),
                '품명': (transaction.get('품명', '') or
                        transaction.get('품목', '') or  # Gemini 응답
                        transaction.get('item', '') or
                        transaction.get('product', '') or
                        transaction.get('product_name', '') or
                        transaction.get('material', '')),
                '규격': (transaction.get('규격', '') or
                        transaction.get('specification', '') or
                        transaction.get('spec', '') or
                        transaction.get('grade', '') or
                        transaction.get('standard', '')),
                '단위': (transaction.get('단위', '') or
                        transaction.get('unit', '') or 'M3'),
                '물량': safe_float(transaction.get('물량', 0) or
                                 transaction.get('공급량', 0) or  # Gemini 응답
                                 transaction.get('quantity', 0) or
                                 transaction.get('volume', 0) or
                                 transaction.get('amount_delivered', 0) or
                                 transaction.get('qty', 0)),
                '단가': safe_int(transaction.get('단가', 0) or
                               transaction.get('unit_price', 0) or
                               transaction.get('price', 0) or
                               transaction.get('rate', 0)),
                '공급가액': safe_int(transaction.get('공급가액', 0) or
                                   transaction.get('amount', 0) or
                                   transaction.get('supply_amount', 0) or
                                   transaction.get('subtotal', 0) or
                                   transaction.get('net_amount', 0)),
                '세액': safe_int(transaction.get('세액', 0) or
                               transaction.get('tax', 0) or
                               transaction.get('tax_amount', 0) or
                               transaction.get('vat', 0)),
                '합계': safe_int(transaction.get('합계', 0) or
                               transaction.get('total', 0) or
                               transaction.get('grand_total', 0) or
                               transaction.get('total_amount', 0)),
                '출하일': (transaction.get('출하일', '') or
                         transaction.get('date', '') or
                         transaction.get('delivery_date', '') or
                         transaction.get('ship_date', '') or
                         transaction.get('supply_date', '')),
                '비고': (transaction.get('비고', '') or
                        transaction.get('note', '') or
                        transaction.get('remarks', '') or
                        transaction.get('memo', ''))
            }

            print(f"  품명: '{record['품명']}', 물량: {record['물량']}, 공급가액: {record['공급가액']}")

            # 더 관대한 유효성 검사 - 최소 1개 필드만 있어도 유효
            has_product = bool(record['품명'].strip()) if record['품명'] else False
            has_quantity = record['물량'] > 0
            has_amount = record['공급가액'] > 0 or record['합계'] > 0
            has_date = bool(record['출하일'].strip()) if record['출하일'] else False
            has_supplier = bool(record['공급자'].strip()) if record['공급자'] else False
            has_customer = bool(record['현장명'].strip()) if record['현장명'] else False

            # 유효한 필드 개수 계산
            valid_fields_count = sum([has_product, has_quantity, has_amount, has_date, has_supplier, has_customer])

            # 최소 1개 필드라도 있으면 추가 (매우 관대한 기준)
            if valid_fields_count >= 1:
                flat_records.append(record)
                print(f"  ✅ 거래 데이터 추가: 유효필드={valid_fields_count}개 (품명={has_product}, 수량={has_quantity}, 금액={has_amount}, 날짜={has_date}, 공급자={has_supplier}, 현장={has_customer})")
            else:
                print(f"  ❌ 거래 데이터 건너뜀: 모든 필드가 비어있음")

    return flat_records


def extract_with_ai(text: str, user_prompt: str = None) -> List[Dict]:
    """
    Google Gemini AI를 사용하여 텍스트에서 구조화된 견적서/청구서 데이터를 추출합니다.
    """
    try:
        print("🤖 Google Gemini AI를 사용하여 데이터 추출 중...")

        # API 클라이언트 확인
        if client is None:
            print("❌ Google AI 클라이언트가 초기화되지 않았습니다.")
            return [{"api_quota_exceeded": True, "error_message": "AI API 서비스에 연결할 수 없습니다. API 키를 확인해주세요."}]

        # 사용자 정의 프롬프트가 있으면 사용, 없으면 기본 프롬프트 사용
        if user_prompt and user_prompt.strip():
            prompt = f"""
{user_prompt.strip()}

텍스트:
{text}

JSON만 반환:
"""
        else:
            prompt = f"""
다음 건설/레미콘 거래명세서/세금계산서에서 유효한 거래 데이터만을 JSON 배열로 추출하세요.

{text}

🎯 선별적 추출 원칙:
- 실제 거래 내역만 추출 (헤더, 합계, 메타데이터 제외)
- 최소한 다음 중 2개 이상이 있는 행만 추출:
  * 금액 데이터 (공급가액 또는 합계)
  * 수량 데이터 (물량)
  * 날짜 정보 (출하일)
  * 품명 정보
- 의미있는 거래 데이터만 포함

📋 필수 추출 필드:
- 출하일: 납품/출하 날짜 (YYYY-MM-DD 형식 선호)
- 품명: 구체적인 품목명 (일반적인 단어는 제외)
- 규격: 사양/등급 정보
- 물량: 공급 수량 (양수만)
- 단위: 수량 단위
- 단가: 단위당 가격 (양수만)
- 공급가액: 공급 금액 (양수만)
- 세액: 부가세 (0 이상)
- 합계: 총 금액 (양수만)

🔍 품질 기준:
- 공급가액이나 합계 중 하나는 반드시 0보다 큰 값
- 물량이 있으면 반드시 0보다 큰 값
- 명확하지 않은 데이터는 제외
- 테스트/샘플 데이터는 제외

⚠️ 제외 항목:
- 컬럼 제목 행
- 소계/합계 행
- 회사 정보
- 불완전한 데이터 행

🏢 회사 정보:
- 공급자: 문서 상단의 공급하는 회사명 찾기
- 현장명: 납품지/구매처 정보

⚠️ 제외 항목:
- 컬럼 제목 행 (NO, 품목, 단가 등)
- 합계/소계 행
- 회사 정보/주소 등

JSON 형식 예시:
[
  {{
    "출하일": "2026-03-16",
    "품명": "레미콘(일반)",
    "규격": "25-35-180",
    "물량": 69.000,
    "단위": "M3",
    "단가": 102000,
    "공급가액": 7038000,
    "세액": 703800,
    "합계": 7741800,
    "공급자": "(주)에스피레미콘",
    "현장명": "포스코이앤씨",
    "비고": ""
  }}
]

숫자 필드는 쉼표 없이 숫자만 반환하세요. 실제 거래 데이터만 JSON 배열로 반환하세요."""

        # Gemini API 호출 - 토큰 사용량 최적화
        response = client.models.generate_content(
            model='gemini-1.5-flash',  # 안정적인 모델 사용 (experimental 버전 제외)
            contents=prompt,
            config={
                'temperature': 0.1,
                'max_output_tokens': 2048,  # 할당량 절약을 위해 대폭 감소
            }
        )

        if response.text:
            content = response.text.strip()
            print(f"Gemini response: {content[:200]}...")

            # JSON 부분만 추출 (강화된 파싱)
            try:
                json_str = ""
                print(f"Full response length: {len(content)}")
                print(f"Response preview: {content[:300]}...")

                # AI 응답이 JSON 배열로 시작하는지 확인
                if content.strip().startswith('['):
                    print("Response starts with JSON array")
                    # 전체 응답이 JSON 배열인 경우
                    try:
                        extracted_data = json.loads(content.strip())
                        if isinstance(extracted_data, list):
                            print(f"✅ Direct JSON parsing successful: {len(extracted_data)} items")
                            if len(extracted_data) >= 10:
                                return extracted_data
                    except json.JSONDecodeError as e:
                        print(f"Direct parsing failed: {e}")
                        # JSON이 불완전할 수 있으므로 부분 추출 시도
                        pass

                # 1. ```json 블록 찾기
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                    print(f"Found JSON block, length: {len(json_str)}")

                # 2. 첫 번째 [ 부터 마지막 ] 까지 찾기 (가장 일반적)
                elif '[' in content:
                    start_idx = content.find('[')
                    # 가능한 모든 ] 위치 확인
                    end_positions = [i for i, char in enumerate(content) if char == ']']

                    for end_idx in reversed(end_positions):  # 뒤에서부터 시도
                        if end_idx > start_idx:
                            candidate_json = content[start_idx:end_idx + 1]
                            try:
                                test_data = json.loads(candidate_json)
                                if isinstance(test_data, list) and len(test_data) > 0:
                                    json_str = candidate_json
                                    print(f"Found valid JSON array, length: {len(json_str)}, items: {len(test_data)}")
                                    break
                            except json.JSONDecodeError:
                                continue

                # 3. 중첩 구조 처리
                if not json_str and 'remicon_transactions' in content.lower():
                    try:
                        full_json = json.loads(content)
                        if 'remicon_transactions' in full_json:
                            json_str = json.dumps(full_json['remicon_transactions'])
                            print(f"Extracted from nested structure")
                    except:
                        pass

                # JSON 파싱 및 검증
                if json_str:
                    extracted_data = json.loads(json_str)

                    # Nested 구조를 flat 구조로 변환
                    flat_records = []

                    if isinstance(extracted_data, list):
                        for item in extracted_data:
                            flat_records.extend(flatten_transaction_data(item))
                    else:
                        flat_records = flatten_transaction_data(extracted_data)

                    print(f"✅ Gemini AI extracted {len(flat_records)} transaction records")

                    # 매우 관대한 유효성 검사 - 거의 모든 데이터 허용
                    valid_records = []
                    for r in flat_records:
                        # 모든 가능한 필드 확인
                        has_product_name = bool(r.get('품명', '').strip())
                        has_financial_data = bool(r.get('공급가액') or r.get('금액') or r.get('합계'))
                        has_quantity_data = bool(r.get('물량', 0) > 0)
                        has_date_data = bool(r.get('출하일', '').strip())
                        has_supplier = bool(r.get('공급자', '').strip())
                        has_customer = bool(r.get('현장명', '').strip())

                        # 유효한 필드 개수 계산
                        valid_field_count = sum([
                            has_product_name,
                            has_financial_data,
                            has_quantity_data,
                            has_date_data,
                            has_supplier,
                            has_customer
                        ])

                        # 최소 1개 필드만 있어도 유효 (매우 관대한 기준)
                        is_valid = valid_field_count >= 1

                        if is_valid:
                            valid_records.append(r)
                            print(f"  ✅ 레코드 추가: 유효필드={valid_field_count}개 - 품명:{has_product_name}, 금액:{has_financial_data}, 수량:{has_quantity_data}, 날짜:{has_date_data}, 공급자:{has_supplier}, 현장:{has_customer}")
                        else:
                            print(f"  ❌ 레코드 제외: 모든 필드가 비어있음")

                    print(f"Valid transaction records: {len(valid_records)} (including records without product names)")

                    if len(valid_records) >= 1:  # 페이지별로 1개 이상이면 성공
                        return valid_records
                    else:
                        print(f"❌ AI가 유효한 거래 데이터를 찾지 못했습니다 ({len(valid_records)})")
                        return [{"api_quota_exceeded": True, "error_message": "AI가 이 PDF에서 유효한 거래 데이터를 찾을 수 없습니다. 다른 PDF 파일을 시도해보세요."}]
                else:
                    print("❌ AI 응답에서 유효한 JSON을 찾을 수 없습니다")
                    return [{"api_quota_exceeded": True, "error_message": "AI가 데이터를 올바르게 처리하지 못했습니다. 다른 PDF를 시도해보거나 잠시 후 다시 시도해주세요."}]

            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing error: {e}")
                if 'json_str' in locals():
                    print(f"Problematic JSON (first 500 chars): {json_str[:500]}")
                return [{"api_quota_exceeded": True, "error_message": "AI 응답 데이터 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}]
        else:
            print("No response from Gemini AI")
            return [{"api_quota_exceeded": True, "error_message": "AI 서비스로부터 응답을 받을 수 없습니다. 네트워크 연결을 확인하거나 잠시 후 다시 시도해주세요."}]

    except Exception as e:
        error_msg = str(e)
        print(f"Gemini AI extraction error: {e}")

        # API 할당량 소진 감지
        if "429" in error_msg and "quota" in error_msg.lower():
            print("❌ API 할당량 소진 감지됨")
            # 특별한 에러 객체 반환 (fallback 하지 않음)
            return [{"api_quota_exceeded": True, "error_message": "API 할당량이 소진되어 작업을 진행할 수 없습니다."}]

        return [{"api_quota_exceeded": True, "error_message": f"AI 서비스 오류: {error_msg}. 잠시 후 다시 시도해주세요."}]


def parse_text_manually(text: str) -> List[Dict]:
    """
    AI가 실패했을 때 수동으로 텍스트를 파싱합니다.
    """
    print("Attempting manual text parsing...")

    lines = text.split('\n')
    results = []

    # 간단한 패턴 매칭으로 데이터 추출 시도
    current_item = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 금액 패턴 찾기
        amount_pattern = r'(\d{1,3}(?:,\d{3})*)'
        amounts = re.findall(amount_pattern, line)

        # 품명 패턴 (한글/영문 제품명)
        if re.search(r'[가-힣]{2,}', line) and not re.search(r'(주식회사|회사|대표)', line):
            if '품명' not in current_item:
                current_item['품명'] = line

        # 공급자 패턴
        if re.search(r'(주식회사|회사|대표|상호)', line):
            current_item['공급자'] = line

        # 수량 패턴
        if re.search(r'\d+\s*(개|식|ea|set|EA|SET)', line):
            unit_match = re.search(r'(\d+)\s*(개|식|ea|set|EA|SET)', line)
            if unit_match:
                current_item['물량'] = int(unit_match.group(1))
                current_item['단위'] = unit_match.group(2)

        # 금액이 포함된 라인
        if amounts and len(amounts) >= 2:
            current_item['단가'] = int(amounts[0].replace(',', '')) if amounts[0] else 0
            current_item['공급가액'] = int(amounts[1].replace(',', '')) if amounts[1] else 0
            if len(amounts) >= 3:
                current_item['세액'] = int(amounts[2].replace(',', '')) if amounts[2] else 0
            if len(amounts) >= 4:
                current_item['합계'] = int(amounts[3].replace(',', '')) if amounts[3] else 0

    # 현재 아이템이 유효하면 결과에 추가
    if current_item and ('품명' in current_item or '공급자' in current_item):
        # 기본값 설정
        defaults = {
            '공급자': '',
            '품명': '',
            '규격': '',
            '단위': '',
            '물량': 0,
            '단가': 0,
            '공급가액': 0,
            '세액': 0,
            '합계': 0
        }
        defaults.update(current_item)
        results.append(defaults)

    # 수동 파싱도 실패하면 원본 텍스트를 하나의 항목으로
    if not results:
        results.append({
            '공급자': '',
            '품명': '텍스트 추출 실패',
            '규격': text[:100] + '...' if len(text) > 100 else text,
            '단위': '',
            '물량': 0,
            '단가': 0,
            '공급가액': 0,
            '세액': 0,
            '합계': 0
        })

    print(f"Manual parsing extracted {len(results)} items")
    return results
