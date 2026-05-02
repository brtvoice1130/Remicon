from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response_data = {
            "message": "Hello from Vercel Python!",
            "path": self.path,
            "method": "GET",
            "status": "success"
        }

        self.wfile.write(json.dumps(response_data).encode())
        return

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response_data = {
            "message": "Hello from Vercel Python!",
            "path": self.path,
            "method": "POST",
            "status": "success"
        }

        self.wfile.write(json.dumps(response_data).encode())
        return