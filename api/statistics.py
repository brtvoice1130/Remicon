import os
import sys
from pathlib import Path

# 환경변수와 경로 설정
current_dir = Path(__file__).parent
backend_dir = current_dir.parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
@app.get("/statistics/")
def get_statistics():
    try:
        # 환경변수 로드
        from dotenv import load_dotenv
        env_path = current_dir.parent / ".env"
        load_dotenv(env_path)

        # 데이터베이스 연결 테스트
        from database import DatabaseManager
        db = DatabaseManager()
        stats = db.get_statistics()

        return JSONResponse({
            "status": "success",
            "statistics": stats
        })

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "debug": {
                "backend_dir_exists": backend_dir.exists(),
                "env_file_exists": (current_dir.parent / ".env").exists(),
                "supabase_url": os.getenv("SUPABASE_DB_URL", "Not found")[:50] + "..." if os.getenv("SUPABASE_DB_URL") else "Not found"
            }
        }, status_code=500)

# Vercel 핸들러
def handler(request):
    return app(request)