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

            # 환경변수 체크
            if not os.getenv("GOOGLE_API_KEY"):
                response_data = {
                    "status": "configuration_error",
                    "error": "Google AI API 키가 설정되지 않았습니다.",
                    "action_required": "관리자에게 문의하여 GOOGLE_API_KEY를 설정해주세요."
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

            # 파일과 프롬프트 추출
            file_item = form['file'] if 'file' in form else None
            prompt = form['prompt'].value if 'prompt' in form else None

            if not file_item or not file_item.filename:
                raise ValueError("파일이 업로드되지 않았습니다")

            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_item.file.read())
                temp_path = tmp_file.name

            try:
                print(f"📄 Processing PDF: {file_item.filename}")

                # PDF 처리
                extracted_data = extract_pdf_tables(temp_path, prompt)

                print(f"✅ Extraction completed: {len(extracted_data)} records")

                # API 에러 처리
                if extracted_data and isinstance(extracted_data[0], dict):
                    first_item = extracted_data[0]

                    # API 할당량 초과 확인
                    if first_item.get('api_error') and first_item.get('error_type') == 'quota_exceeded':
                        response_data = {
                            "status": "api_quota_exceeded",
                            "error": first_item.get('error_message'),
                            "recovery_time": first_item.get('recovery_time'),
                            "recovery_message": first_item.get('recovery_message')
                        }
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

                    # 추출 실패 확인
                    if first_item.get('api_error') == False and first_item.get('error_type'):
                        response_data = {
                            "status": "extraction_failed",
                            "error": first_item.get('error_message'),
                            "suggestion": first_item.get('suggestion')
                        }
                        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())
                        return

                # 성공 응답
                response_data = {
                    "status": "success",
                    "filename": file_item.filename,
                    "tables": extracted_data,
                    "saved_count": len(extracted_data)
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