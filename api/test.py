from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
def test():
    return {"status": "API test successful", "message": "Vercel serverless function working"}

@app.get("/api/test")
def test_api():
    return {"status": "API test successful", "path": "/api/test"}

# Vercel 핸들러
def handler(request):
    return app(request)