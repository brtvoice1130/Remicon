from http.server import BaseHTTPRequestHandler
import json
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            response_data = {
                "status": "success",
                "statistics": {
                    "total_records": 0,
                    "total_files": 0,
                    "total_amount": 0
                },
                "message": "Statistics API working",
                "path": self.path,
                "debug": {
                    "supabase_url_configured": bool(os.getenv("SUPABASE_DB_URL")),
                    "google_api_configured": bool(os.getenv("GOOGLE_API_KEY"))
                }
            }

            self.wfile.write(json.dumps(response_data).encode())
            return

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                "status": "error",
                "error": str(e),
                "path": self.path
            }

            self.wfile.write(json.dumps(error_response).encode())
            return