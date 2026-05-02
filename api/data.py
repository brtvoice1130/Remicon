from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import sys
from pathlib import Path

# 현재 파일의 부모 디렉토리 경로 설정
current_dir = Path(__file__).parent
backend_dir = current_dir.parent / "backend"

# 백엔드 경로를 Python path에 추가
sys.path.insert(0, str(backend_dir))

try:
    from db_manager import get_saved_data, delete_data_item, clear_all_data
    print("✅ db_manager import 성공")
except ImportError as e:
    print(f"❌ db_manager import 실패: {e}")
    get_saved_data = None
    delete_data_item = None
    clear_all_data = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # 실제 DB에서 데이터 조회
            if get_saved_data:
                data = get_saved_data()
                response_data = {
                    "status": "success",
                    "data": data
                }
            else:
                response_data = {
                    "status": "error",
                    "message": "DB 연결을 사용할 수 없습니다.",
                    "data": []
                }

            self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            error_response = {
                "status": "error",
                "message": str(e)
            }

            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode())

    def do_DELETE(self):
        try:
            # URL 파싱하여 ID 추출
            parsed_path = urllib.parse.urlparse(self.path)
            path_parts = parsed_path.path.strip('/').split('/')

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            if len(path_parts) > 1 and path_parts[1].isdigit():
                # 개별 항목 삭제 /api/data/{id}
                item_id = int(path_parts[1])

                if delete_data_item:
                    success = delete_data_item(item_id)
                    if success:
                        response_data = {
                            "status": "success",
                            "message": "항목이 삭제되었습니다."
                        }
                    else:
                        response_data = {
                            "status": "error",
                            "message": "삭제할 수 없습니다."
                        }
                else:
                    response_data = {
                        "status": "error",
                        "message": "DB 연결을 사용할 수 없습니다."
                    }
            else:
                # 전체 데이터 삭제 /api/data
                if clear_all_data:
                    success = clear_all_data()
                    if success:
                        response_data = {
                            "status": "success",
                            "message": "모든 데이터가 삭제되었습니다."
                        }
                    else:
                        response_data = {
                            "status": "error",
                            "message": "전체 삭제에 실패했습니다."
                        }
                else:
                    response_data = {
                        "status": "error",
                        "message": "DB 연결을 사용할 수 없습니다."
                    }

            self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            error_response = {
                "status": "error",
                "message": str(e)
            }

            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        # CORS preflight 요청 처리
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()