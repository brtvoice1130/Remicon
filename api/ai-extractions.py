from http.server import BaseHTTPRequestHandler
import json
import urllib.parse

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # URL 경로 분석
            path = self.path

            if '/ai-extractions/' in path and '/test/' not in path:
                # 개별 추출 결과 조회
                response_data = {
                    "status": "success",
                    "data": {
                        "filename": "test.pdf",
                        "prompt": "테스트 프롬프트",
                        "extraction_time": "2026-05-02T12:00:00Z",
                        "ai_results": [],
                        "analysis": {
                            "total_extracted": 0,
                            "complete_records": 0,
                            "empty_records": 0,
                            "suppliers": []
                        }
                    }
                }
            else:
                # 전체 추출 목록 조회
                response_data = {
                    "status": "success",
                    "extractions": []
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

    def do_POST(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.end_headers()

            # AI 추출 테스트 응답
            response_data = {
                "status": "success",
                "filename": "test.pdf",
                "prompt": "테스트 프롬프트",
                "ai_results": [
                    {
                        "공급자": "테스트 공급자",
                        "품명": "레미콘",
                        "현장명": "테스트 현장",
                        "물량": "10",
                        "단가": 50000,
                        "공급가액": 500000,
                        "세액": 50000,
                        "합계": 550000
                    }
                ],
                "analysis": {
                    "total_extracted": 1,
                    "complete_records": 1,
                    "empty_records": 0,
                    "suppliers": ["테스트 공급자"]
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
                "message": str(e)
            }

            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()