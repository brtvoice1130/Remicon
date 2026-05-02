from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        response = {
            "status": "API test successful",
            "message": "Vercel serverless function working"
        }

        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        self.do_GET()