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

# Google API 키 설정 (환경변수에서 가져오기)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("⚠️ GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
    print("설정 방법: export GOOGLE_API_KEY='your_api_key'")
    client = None
else:
    client = genai.Client(api_key=GOOGLE_API_KEY)
    print("✅ Google AI API 클라이언트 초기화 완료")

def extract_pdf_tables(file_path: str, user_prompt: str = None, debug_mode: bool = False, save_to_db: bool = True, clear_before_save: bool = False) -> List[Dict]:
    """
    최적화된 AI PDF 데이터 추출 시스템
    - 전체 텍스트를 한 번에 처리하여 API 호출 최소화
    - 토큰 사용량 최적화
    """
    print("🤖 Optimized AI-Only PDF Processing Started")

    # API 클라이언트 사전 확인
    if client is None:
        return [{
            "api_error": True,
            "error_type": "api_not_configured",
            "error_message": "Google AI API 클라이언트가 설정되지 않았습니다.",
            "action_required": "GOOGLE_API_KEY 환경변수를 확인해주세요."
        }]

    # 전체 텍스트 추출 (한 번에 모든 페이지 처리)
    all_text = ""
    total_pages = 0

    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"📄 Processing {total_pages} pages as single batch")

        for page_num, page in enumerate(pdf.pages):
            # 페이지 텍스트 추출
            page_text = page.extract_text()
            if page_text:
                all_text += f"\n=== PAGE {page_num + 1} ===\n{page_text}\n"

            # 테이블이 있으면 텍스트 형태로 추가
            tables = page.extract_tables()
            if tables:
                for table_idx, table in enumerate(tables):
                    table_text = f"\n[TABLE {table_idx + 1} on PAGE {page_num + 1}]\n"
                    for row in table:
                        if row:
                            row_text = " | ".join(str(cell) if cell else "" for cell in row)
                            table_text += row_text + "\n"
                    all_text += table_text

    # 텍스트가 너무 길면 청크로 분할 (토큰 제한 고려)
    max_chunk_length = 15000  # 약 3000-4000 토큰 정도
    text_chunks = []

    if len(all_text) > max_chunk_length:
        print(f"📝 텍스트가 길어서 청크로 분할: {len(all_text)} characters")
        # 페이지 기준으로 청크 분할
        pages = all_text.split("=== PAGE")
        current_chunk = ""

        for page in pages[1:]:  # 첫 번째는 빈 문자열
            page_content = "=== PAGE" + page
            if len(current_chunk + page_content) > max_chunk_length:
                if current_chunk:
                    text_chunks.append(current_chunk)
                current_chunk = page_content
            else:
                current_chunk += page_content

        if current_chunk:
            text_chunks.append(current_chunk)
    else:
        text_chunks = [all_text]

    print(f"🔧 처리할 청크 수: {len(text_chunks)}")

    # AI로 청크별 처리 (페이지별이 아닌 청크별)
    ai_extracted_all = []

    for i, chunk in enumerate(text_chunks):
        if chunk.strip():
            print(f"🧠 Processing chunk {i+1}/{len(text_chunks)} with AI...")

            chunk_extracted = extract_with_ai_optimized(chunk, user_prompt)
            if chunk_extracted:
                # API 할당량 소진 확인
                for item in chunk_extracted:
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

                ai_extracted_all.extend(chunk_extracted)
                print(f"✅ Chunk {i+1}: {len(chunk_extracted)} records extracted")

    # 결과 필터링 및 저장
    if ai_extracted_all:
        filtered_results = filter_and_validate_results(ai_extracted_all)
        print(f"🔍 Total extracted: {len(ai_extracted_all)} → {len(filtered_results)} valid records")

        if save_to_db and filtered_results:
            filename = os.path.basename(file_path)
            save_result = save_extracted_data(filename, filtered_results, clear_before_save)

            return [{
                "status": "success_saved",
                "message": save_result.get("message", "데이터가 저장되었습니다."),
                "saved_count": save_result.get("saved_count", 0),
                "filtered_count": save_result.get("filtered_count", 0),
                "filename": filename,
                "db_status": save_result.get("status", "unknown"),
                "optimization_info": {
                    "total_pages": total_pages,
                    "chunks_processed": len(text_chunks),
                    "api_calls": len(text_chunks),
                    "total_text_length": len(all_text)
                }
            }]
        else:
            return filtered_results
    else:
        return [{
            "api_error": False,
            "error_type": "no_data_found",
            "error_message": "PDF에서 유효한 거래 데이터를 찾을 수 없습니다.",
            "suggestion": "다른 PDF 파일을 시도하거나 프롬프트를 조정해주세요."
        }]

def extract_with_ai_optimized(text: str, user_prompt: str = None) -> List[Dict]:
    """
    최적화된 AI 추출 함수 - 토큰 사용량 최소화
    """
    try:
        print("🧠 Using optimized Gemini AI for data extraction...")

        if client is None:
            return [{"api_quota_exceeded": True, "error_message": "AI API 서비스에 연결할 수 없습니다."}]

        # 간결한 프롬프트 사용
        if user_prompt and user_prompt.strip():
            prompt = f"{user_prompt.strip()}\n\n텍스트:\n{text}\n\nJSON만 반환:"
        else:
            prompt = f"""다음 레미콘 거래명세서에서 실제 거래 데이터만 JSON 배열로 추출:

{text}

필수 필드: 출하일, 품명, 물량, 단가, 공급가액, 합계, 공급자, 현장명
제외: 헤더, 합계행, 회사정보
JSON만 반환:"""

        # 토큰 사용량 최적화된 설정
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
            config={
                'temperature': 0.1,
                'max_output_tokens': 8000,  # 토큰 사용량 감소
            }
        )

        if response.text:
            content = response.text.strip()
            return parse_ai_response(content)
        else:
            return [{"api_quota_exceeded": True, "error_message": "AI 응답이 없습니다."}]

    except Exception as e:
        error_msg = str(e).lower()
        if 'quota' in error_msg or 'limit' in error_msg:
            return [{"api_quota_exceeded": True, "error_message": f"API 할당량 소진: {str(e)}"}]
        else:
            print(f"❌ AI 추출 오류: {e}")
            return [{"api_error": True, "error_message": str(e)}]

def parse_ai_response(content: str) -> List[Dict]:
    """AI 응답에서 JSON 추출"""
    try:
        # JSON 블록 찾기
        if content.strip().startswith('['):
            extracted_data = json.loads(content.strip())
        else:
            # ```json 블록 찾기
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # [ 부터 ] 까지 찾기
                start_idx = content.find('[')
                end_idx = content.rfind(']')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx + 1]
                else:
                    return []

            extracted_data = json.loads(json_str)

        if isinstance(extracted_data, list):
            return extracted_data
        else:
            return [extracted_data] if extracted_data else []

    except json.JSONDecodeError as e:
        print(f"JSON 파싱 오류: {e}")
        return []

def filter_and_validate_results(raw_results: List[Dict]) -> List[Dict]:
    """결과 필터링 및 유효성 검사"""
    filtered_results = []

    for result in raw_results:
        if result and isinstance(result, dict):
            # 기본 유효성 검사
            has_product_name = bool(result.get('품명', '').strip())
            has_financial_data = bool(result.get('공급가액') or result.get('금액') or result.get('합계'))
            has_quantity_data = bool(result.get('물량', 0) > 0)
            has_date_data = bool(result.get('출하일', '').strip())

            # 최소한의 유효 데이터가 있으면 포함
            is_valid = has_product_name or has_financial_data or has_quantity_data or has_date_data

            if is_valid:
                filtered_results.append(result)

    return filtered_results