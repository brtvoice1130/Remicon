from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from pathlib import Path

# 현재 파일의 부모 디렉토리 경로 설정
current_dir = Path(__file__).parent
backend_dir = current_dir.parent / "backend"

# 백엔드 경로를 Python path에 추가
sys.path.insert(0, str(backend_dir))

try:
    from db_manager import get_statistics
    print("✅ db_manager import 성공 (statistics)")
except ImportError as e:
    print(f"❌ db_manager import 실패: {e}")
    get_statistics = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # 실제 DB에서 통계 조회
            if get_statistics:
                statistics = get_statistics()
                response_data = {
                    "status": "success",
                    "statistics": statistics,
                    "message": "Statistics API working",
                    "path": self.path,
                    "debug": {
                        "supabase_url_configured": bool(os.getenv("SUPABASE_URL")),
                        "google_api_configured": bool(os.getenv("GOOGLE_API_KEY"))
                    }
                }
            else:
                response_data = {
                    "status": "success",
                    "statistics": {
                        "total_records": 0,
                        "total_files": 0,
                        "total_amount": 0,
                        "supabase_configured": False
                    },
                    "message": "Statistics API working (DB 연결 없음)",
                    "path": self.path,
                    "debug": {
                        "supabase_url_configured": bool(os.getenv("SUPABASE_URL")),
                        "google_api_configured": bool(os.getenv("GOOGLE_API_KEY"))
                    }
                }

            self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            error_response = {
                "status": "error",
                "message": str(e),
                "statistics": {
                    "total_records": 0,
                    "total_files": 0,
                    "total_amount": 0
                }
            }

            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        # CORS preflight 요청 처리
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()