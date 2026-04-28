import pdfplumber
from typing import List, Dict
import pytesseract
from PIL import Image
import io
import json
import re
import os
import google.generativeai as genai

# Google API 키 설정
GOOGLE_API_KEY = "AIzaSyDkADnwq-uIfqjpozVH8NbGxO8aDWSxuZo"
genai.configure(api_key=GOOGLE_API_KEY)

def extract_pdf_tables(file_path: str, user_prompt: str = None) -> List[Dict]:
    """
    AI 우선 PDF 데이터 추출 시스템
    Google Gemini AI가 메인으로 모든 텍스트를 분석하고 구조화된 데이터를 추출합니다.
    """
    print("🤖 AI-First PDF Processing Started")

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

    # AI로 페이지별 텍스트 처리 (응답 길이 제한 해결)
    ai_extracted_all = []
    if page_texts:
        print(f"🧠 Processing {total_pages} pages individually with AI")

        for i, page_text in enumerate(page_texts):
            if page_text.strip():
                print(f"📄 Processing page {i+1} with AI...")
                page_extracted = extract_with_ai(page_text, user_prompt)
                if page_extracted:
                    # API 할당량 소진 확인
                    if any(item.get('api_quota_exceeded') for item in page_extracted):
                        print("❌ API 할당량 소진으로 작업 중단")
                        return page_extracted  # 에러 정보 반환

                    ai_extracted_all.extend(page_extracted)
                    print(f"✅ Page {i+1}: {len(page_extracted)} records")

        # AI 추출 성공 기준을 유연하게 조정 (API 할당량 고려)
        if len(ai_extracted_all) >= 15:  # 완전한 추출 (모든 페이지 AI 처리)
            print(f"✅ AI extracted {len(ai_extracted_all)} total structured records (완전)")
            return ai_extracted_all
        elif len(ai_extracted_all) >= 3 and any(r.get('품명') and r.get('공급가액') for r in ai_extracted_all):
            # 일부 페이지라도 완전한 데이터가 있으면 성공으로 처리
            print(f"✅ AI extracted {len(ai_extracted_all)} records (부분 성공 - API 할당량 제한)")
            return ai_extracted_all
        else:
            print(f"❌ AI processing: Only {len(ai_extracted_all)} incomplete records, falling back to traditional extraction")

    # AI 실패시 강력한 백업: 전통적 테이블 추출
    print("🔄 Fallback: Using traditional multi-page table extraction")
    traditional_results = []

    with pdfplumber.open(file_path) as pdf:
        supplier_info = ""
        site_info = ""

        for page_num, page in enumerate(pdf.pages):
            print(f"📄 Fallback processing page {page_num + 1}")

            # 전통적 테이블 추출
            tables = page.extract_tables()
            if tables:
                for table_idx, table in enumerate(tables):
                    if table and len(table) > 1:
                        headers = table[0]

                        # 공급자/현장 정보 추출
                        page_supplier = extract_supplier_info(table, headers)
                        if page_supplier:
                            supplier_info = page_supplier

                        page_site = extract_site_info(table, headers)
                        if page_site:
                            site_info = page_site

                        # 데이터 행 처리
                        for row_idx, row in enumerate(table[1:]):
                            if row and any(cell for cell in row if cell):
                                row_dict = {}
                                for i in range(min(len(headers), len(row))):
                                    if headers[i]:
                                        row_dict[headers[i]] = row[i] if row[i] else ""

                                # 필터링 및 검증
                                if not is_summary_row(row_dict) and has_meaningful_data(row_dict):
                                    if supplier_info:
                                        row_dict['공급자'] = supplier_info
                                    if site_info:
                                        row_dict['현장명'] = site_info

                                    print(f"📋 Page {page_num + 1} - Valid record: {supplier_info} - {row_dict.get('품목', 'N/A')}")
                                    traditional_results.append(row_dict)

    print(f"🔄 Traditional extraction: {len(traditional_results)} records")

    # 전통적 추출도 실패시 최종 백업
    if not traditional_results:
        print("⚠️ Final fallback: Manual text parsing")
        traditional_results = parse_text_manually(all_text) if all_text else []

    if not traditional_results:
        traditional_results.append({
            "공급자": "추출 실패",
            "품명": "모든 방법 실패",
            "현장명": "확인 필요",
            "물량": 0, "단가": 0, "공급가액": 0, "세액": 0, "합계": 0
        })

    print(f"Total extracted records: {len(traditional_results)}")
    return traditional_results


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


def extract_with_ai(text: str, user_prompt: str = None) -> List[Dict]:
    """
    Google Gemini AI를 사용하여 텍스트에서 구조화된 견적서/청구서 데이터를 추출합니다.
    """
    try:
        print("Using Google Gemini AI for data extraction...")

        # Gemini 모델 초기화 (최신 모델)
        model = genai.GenerativeModel('gemini-flash-latest')

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
이 페이지의 레미콘 거래 데이터를 JSON 배열로 추출하세요.

{text}

⚠️ 중요한 구분 규칙:
- 공급자(판매자): 에스피레미콘, 유진기업, 쌍용레미콘 등 (실제 레미콘을 공급하는 회사)
- 현장명(구매자): 포스코이앤씨, 공사명 등 (레미콘을 공급받는 곳)
- 포스코이앤씨는 절대 공급자가 아님 (현장명으로 분류)

추출 지침:
- 실제 거래 행만 추출 (헤더/소계/합계 제외)
- 레미콘 품목이 있는 행만 추출
- 빈 값은 ""으로 표시
- 숫자에서 쉼표 제거

JSON 형식:
[{{"현장명":"포스코이앤씨 관련 현장명","공급자":"실제 레미콘 공급업체","품명":"레미콘(일반)","규격":"25-35-180","단위":"M3","물량":69,"단가":102000,"공급가액":7038000,"세액":703800,"합계":7741800,"출하일":"2026-03-16","비고":""}}]

JSON만 반환하세요."""

        # Gemini API 호출 - 대용량 JSON 응답을 위한 토큰 증가
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=16000,  # 21개 레코드의 완전한 JSON을 위해 대폭 증가
            )
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
                    if not isinstance(extracted_data, list):
                        extracted_data = [extracted_data]

                    print(f"✅ Gemini AI extracted {len(extracted_data)} items")

                    # 데이터 품질 확인
                    valid_records = [r for r in extracted_data if r.get('공급자') and r.get('품명')]
                    print(f"Valid records with 공급자 and 품명: {len(valid_records)}")

                    if len(extracted_data) >= 1:  # 페이지별로 1개 이상이면 성공
                        return extracted_data
                    else:
                        print(f"❌ No valid records ({len(extracted_data)}), falling back")
                        return parse_text_manually(text)
                else:
                    print("❌ No valid JSON found in response")
                    return parse_text_manually(text)

            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing error: {e}")
                if 'json_str' in locals():
                    print(f"Problematic JSON (first 500 chars): {json_str[:500]}")
                return parse_text_manually(text)
        else:
            print("No response from Gemini AI")
            return parse_text_manually(text)

    except Exception as e:
        error_msg = str(e)
        print(f"Gemini AI extraction error: {e}")

        # API 할당량 소진 감지
        if "429" in error_msg and "quota" in error_msg.lower():
            print("❌ API 할당량 소진 감지됨")
            # 특별한 에러 객체 반환 (fallback 하지 않음)
            return [{"api_quota_exceeded": True, "error_message": "API 할당량이 소진되어 작업을 진행할 수 없습니다."}]

        return parse_text_manually(text)


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
