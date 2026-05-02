import sys
import os
from pathlib import Path

# 현재 파일의 부모 디렉토리 경로 설정
current_dir = Path(__file__).parent
backend_dir = current_dir.parent / "backend"

# 백엔드 경로를 Python path에 추가
sys.path.insert(0, str(backend_dir))

print(f"Current directory: {current_dir}")
print(f"Backend directory: {backend_dir}")
print(f"Backend exists: {backend_dir.exists()}")

try:
    # 환경변수 로드
    from dotenv import load_dotenv
    env_path = current_dir.parent / ".env"
    load_dotenv(env_path)
    print(f"Environment file loaded from: {env_path}")

    # FastAPI 앱 import
    from main import app
    print("FastAPI app imported successfully")

    # Vercel 핸들러 함수
    def handler(request, response):
        return app(request, response)

    # Vercel용 앱 export
    app = app

except Exception as e:
    print(f"Error importing FastAPI app: {e}")
    import traceback
    traceback.print_exc()

    # 기본 응답을 위한 간단한 앱
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/")
    def read_root():
        return {"error": "FastAPI import failed", "message": str(e)}

    @app.get("/api/test")
    def test():
        return {"status": "API test successful"}