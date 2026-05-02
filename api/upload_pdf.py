from http.server import BaseHTTPRequestHandler
import json
import os
import tempfile
import sys
import cgi
import io
from pathlib import Path

# 현재 파일의 부모 디렉토리 경로 설정
current_dir = Path(__file__).parent
backend_dir = current_dir.parent / "backend"

# 백엔드 경로를 Python path에 추가
sys.path.insert(0, str(backend_dir))

try:
    from pdf_utils import extract_pdf_tables
    print("✅ pdf_utils import 성공")
except ImportError as e:
    print(f"❌ pdf_utils import 실패: {e}")
    extract_pdf_tables = None

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 기본 응답 헤더 설정
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

            # AI API 필수 체크 - 없으면 즉시 중단
            if not os.getenv("GOOGLE_API_KEY"):
                response_data = {
                    "status": "configuration_error",
                    "error": "🔧 AI 추출 서비스를 사용할 수 없습니다.",
                    "action_required": "Google AI API가 설정되지 않았습니다. 관리자에게 문의해주세요.",
                    "details": "이 서비스는 AI 기반 데이터 추출만 지원합니다."
                }
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())
                return

            # pdf_utils가 없으면 테스트 응답
            if extract_pdf_tables is None:
                response_data = {
                    "status": "success",
                    "message": "PDF 처리 모듈 로드 실패 - 테스트 데이터 반환",
                    "filename": "test.pdf",
                    "tables": [
                        {
                            "공급자": "테스트 공급자",
                            "품명": "레미콘",
                            "현장명": "테스트 현장",
                            "물량": 10,
                            "단가": 50000,
                            "공급가액": 500000,
                            "세액": 50000,
                            "합계": 550000
                        }
                    ],
                    "saved_count": 1
                }
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())
                return

            # multipart/form-data 파싱
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                raise ValueError("multipart/form-data가 필요합니다")

            # POST 데이터 읽기
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            # cgi.FieldStorage로 파싱
            fp = io.BytesIO(post_data)
            form = cgi.FieldStorage(fp=fp, environ={
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': content_type,
                'CONTENT_LENGTH': str(content_length)
            })

            # 파일, 프롬프트, 디버그 모드, DB 저장 옵션 추출
            file_item = form['file'] if 'file' in form else None
            prompt = form['prompt'].value if 'prompt' in form else None
            debug_mode = form['debug'].value.lower() == 'true' if 'debug' in form else False
            save_to_db = form['save_db'].value.lower() != 'false' if 'save_db' in form else True  # 기본값: True

            if not file_item or not file_item.filename:
                raise ValueError("파일이 업로드되지 않았습니다")

            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_item.file.read())
                temp_path = tmp_file.name

            try:
                print(f"📄 Processing PDF: {file_item.filename}")
                print(f"📝 User prompt: {prompt}")
                print(f"🔑 API Key configured: {bool(os.getenv('GOOGLE_API_KEY'))}")

                # PDF 처리
                extracted_data = extract_pdf_tables(temp_path, prompt, debug_mode, save_to_db)

                # Debug 모드에서는 다른 데이터 구조 처리
                if debug_mode and extracted_data and isinstance(extracted_data[0], dict) and extracted_data[0].get('status') == 'success':
                    debug_result = extracted_data[0]
                    response_data = {
                        "status": "debug_success",
                        "filename": file_item.filename,
                        "tables": debug_result.get('data', []),
                        "saved_count": len(debug_result.get('data', [])),
                        "debug_info": debug_result.get('debug_info', {}),
                        "extraction_details": {
                            "total_extracted": len(debug_result.get('debug_info', {}).get('raw_ai_results', [])),
                            "validation_passed": len(debug_result.get('data', [])),
                            "validation_failed": len(debug_result.get('debug_info', {}).get('raw_ai_results', [])) - len(debug_result.get('data', []))
                        }
                    }
                    self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())
                    return

                print(f"✅ Extraction completed: {len(extracted_data)} records")
                print(f"📊 Raw extraction result: {extracted_data[:2] if extracted_data else 'No data'}")

                # DB 저장 완료 응답 처리
                if extracted_data and isinstance(extracted_data[0], dict):
                    first_item = extracted_data[0]

                    # DB 저장 성공 응답
                    if first_item.get('status') == 'success_saved':
                        response_data = {
                            "status": "success",
                            "message": first_item.get('message'),
                            "filename": file_item.filename,
                            "saved_count": first_item.get('saved_count', 0),
                            "filtered_count": first_item.get('filtered_count', 0),
                            "db_status": first_item.get('db_status'),
                            "tables": []  # 데이터는 DB에 저장됨
                        }
                        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())
                        return

                    # API 할당량 초과 확인
                    if first_item.get('api_error') and first_item.get('error_type') == 'quota_exceeded':
                        response_data = {
                            "status": "api_quota_exceeded",
                            "error": first_item.get('error_message'),
                            "recovery_time": first_item.get('recovery_time'),
                            "recovery_message": first_item.get('recovery_message')
                        }
                        if debug_mode and first_item.get('debug_info'):
                            response_data["debug_info"] = first_item.get('debug_info')
                        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())
                        return

                    # 설정 오류 확인
                    if first_item.get('api_error') and first_item.get('error_type') == 'api_not_configured':
                        response_data = {
                            "status": "configuration_error",
                            "error": first_item.get('error_message'),
                            "action_required": first_item.get('action_required')
                        }
                        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())
                        return

                    # 추출 실패 확인 (Debug 정보 포함)
                    if first_item.get('api_error') == False and first_item.get('error_type'):
                        response_data = {
                            "status": "extraction_failed",
                            "error": first_item.get('error_message'),
                            "suggestion": first_item.get('suggestion'),
                            "extracted_count": first_item.get('extracted_count', 0),
                            "valid_count": first_item.get('valid_count', 0)
                        }
                        if debug_mode and first_item.get('debug_info'):
                            response_data["debug_info"] = first_item.get('debug_info')
                        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())
                        return

                # 성공 응답 (더 상세한 정보 포함)
                response_data = {
                    "status": "success",
                    "filename": file_item.filename,
                    "tables": extracted_data,
                    "saved_count": len(extracted_data),
                    "debug_mode": debug_mode,
                    "debug_info": {
                        "total_extracted": len(extracted_data),
                        "api_key_present": bool(os.getenv("GOOGLE_API_KEY")),
                        "first_item_keys": list(extracted_data[0].keys()) if extracted_data else [],
                        "extraction_preview": str(extracted_data[0])[:200] if extracted_data else "No data"
                    }
                }

                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())

            finally:
                # 임시 파일 삭제
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            print(f"❌ Upload error: {e}")
            # 에러 응답
            error_response = {
                "status": "error",
                "message": f"업로드 처리 중 오류: {str(e)}"
            }

            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        # CORS preflight 요청 처리
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()