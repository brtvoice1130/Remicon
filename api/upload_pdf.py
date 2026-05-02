from http.server import BaseHTTPRequestHandler
import json
import os
import tempfile
import sys
from pathlib import Path

# 현재 파일의 부모 디렉토리 경로 설정
current_dir = Path(__file__).parent
backend_dir = current_dir.parent / "backend"

# 백엔드 경로를 Python path에 추가
sys.path.insert(0, str(backend_dir))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 기본적인 응답 설정
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

            # 임시 응답 (기본 기능만)
            response_data = {
                "status": "success",
                "message": "PDF 업로드 API가 정상 작동중입니다",
                "filename": "test.pdf",
                "tables": [
                    {
                        "공급자": "테스트 공급자",
                        "품명": "레미콘",
                        "현장명": "테스트 현장",
                        "물량": "10",
                        "단가": "50000",
                        "공급가액": "500000",
                        "세액": "50000",
                        "합계": "550000"
                    }
                ],
                "saved_count": 1
            }

            self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())

        except Exception as e:
            # 에러 응답
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

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