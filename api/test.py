from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response_data = {
            "status": "API test successful",
            "message": "Vercel serverless function working",
            "path": self.path,
            "method": "GET"
        }

        self.wfile.write(json.dumps(response_data).encode())
        return

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response_data = {
            "status": "API test successful",
            "path": self.path,
            "method": "POST"
        }

        self.wfile.write(json.dumps(response_data).encode())
        return