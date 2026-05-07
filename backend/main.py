from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import sqlite3
import json
import traceback
from datetime import datetime
from typing import Optional, List, Dict
from dotenv import load_dotenv

# 최상위 .env 파일 로드
load_dotenv(dotenv_path="../.env")

from database import DatabaseManager
from pdf_utils import extract_pdf_tables

app = FastAPI()

# AI 추출 결과 임시 저장소
ai_extraction_results = {}

# CORS 설정 (프론트엔드 개발 편의)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 데이터베이스 매니저 초기화 (테스트용 임시 우회)
try:
    db = DatabaseManager()
    print("✅ 데이터베이스 연결 성공")
except Exception as e:
    print(f"⚠️ 데이터베이스 연결 실패, 테스트 모드로 실행: {e}")
    db = None

@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "message": "Remicon API Server is running",
        "database": "connected" if db else "test_mode",
        "ai_api": "configured" if os.getenv("GOOGLE_API_KEY") else "not_configured"
    }

@app.post("/upload_pdf/")
async def upload_pdf(
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(None)
):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as f:
        f.write(await file.read())

    # PDF 표 데이터 추출 (Google Gemini AI 전용)
    try:
        # DB가 없으면 메모리에만 저장, 디버그 모드로 AI 원시 데이터 확인
        save_to_db = db is not None
        tables = extract_pdf_tables(file_location, user_prompt=prompt, debug_mode=True, save_to_db=save_to_db)

        # API 에러 감지 및 처리
        if tables and len(tables) > 0 and tables[0].get('api_error'):
            error_info = tables[0]

            if error_info.get('error_type') == 'quota_exceeded':
                return JSONResponse({
                    "filename": file.filename,
                    "prompt": prompt,
                    "status": "api_quota_exceeded",
                    "error": error_info.get('error_message', 'API 할당량이 소진되었습니다.'),
                    "error_type": "quota_exceeded",
                    "recovery_time": error_info.get('recovery_time', '매일 오전 9시'),
                    "recovery_message": error_info.get('recovery_message', '오전 9시 이후에 다시 이용해주세요.'),
                    "current_status": error_info.get('current_status', 'API 할당량 소진')
                }, status_code=429)
            elif error_info.get('error_type') == 'api_not_configured':
                return JSONResponse({
                    "filename": file.filename,
                    "prompt": prompt,
                    "status": "configuration_error",
                    "error": error_info.get('error_message', 'API 설정 오류'),
                    "error_type": "configuration",
                    "action_required": error_info.get('action_required', 'API 키를 확인하세요.')
                }, status_code=500)
            else:
                return JSONResponse({
                    "filename": file.filename,
                    "prompt": prompt,
                    "status": "extraction_failed",
                    "error": error_info.get('error_message', '데이터 추출에 실패했습니다.'),
                    "error_type": error_info.get('error_type', 'extraction_error'),
                    "suggestion": error_info.get('suggestion', '다른 PDF를 시도해보세요.')
                }, status_code=400)

        # AI 추출 결과 임시 저장 (디버깅용)
        extraction_id = f"{file.filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ai_extraction_results[extraction_id] = {
            "filename": file.filename,
            "prompt": prompt,
            "extraction_time": datetime.now().isoformat(),
            "total_extracted": len(tables),
            "ai_results": tables,
            "analysis": {
                "complete_records": len([t for t in tables if t.get('품명') and t.get('공급자') and t.get('공급가액')]),
                "empty_records": len([t for t in tables if not t.get('품명')]),
                "suppliers": list(set([t.get('공급자', '') for t in tables if t.get('공급자')]))
            }
        }

        # extract_pdf_tables에서 이미 DB 저장이 처리됨
        # 저장된 데이터 수는 응답에서 확인
        saved_count = 0
        if tables and isinstance(tables[0], dict) and 'saved_count' in tables[0]:
            saved_count = tables[0].get('saved_count', 0)

        # AI 원시 추출 데이터와 디버그 정보 포함
        ai_raw_data = []
        debug_info = None

        if tables and isinstance(tables[0], dict):
            if 'data' in tables[0]:
                ai_raw_data = tables[0]['data']
            if 'debug_info' in tables[0]:
                debug_info = tables[0]['debug_info']

        return JSONResponse({
            "filename": file.filename,
            "prompt": prompt,
            "status": "success",
            "tables": tables,
            "saved_count": saved_count,
            "ai_used": True,
            "ai_raw_extraction": ai_raw_data,  # AI가 추출한 원시 데이터
            "debug_info": debug_info,  # 디버그 정보
            "extraction_details": {
                "total_extracted": len(ai_raw_data) if ai_raw_data else 0,
                "saved_to_db": saved_count,
                "extraction_time": datetime.now().isoformat()
            }
        })
    except Exception as e:
        print(f"❌ Error processing PDF: {e}")
        print(f"❌ Full traceback:")
        traceback.print_exc()
        return JSONResponse({
            "filename": file.filename,
            "prompt": prompt,
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }, status_code=500)

@app.get("/data/")
async def get_all_data():
    """저장된 모든 데이터 조회"""
    try:
        if db is None:
            # 테스트 모드용 빈 데이터
            data = []
        else:
            data = db.get_all_data()

        return JSONResponse({
            "status": "success",
            "data": data
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)

@app.get("/statistics/")
async def get_statistics():
    """통계 정보 조회"""
    try:
        if db is None:
            # 테스트 모드용 Mock 통계
            stats = {
                "total_transactions": 0,
                "total_files": 0,
                "total_suppliers": 0,
                "total_amount": 0
            }
        else:
            stats = db.get_statistics()

        return JSONResponse({
            "status": "success",
            "statistics": stats
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)

@app.get("/ai-extractions/")
async def get_ai_extractions():
    """AI 추출 결과 목록 조회"""
    try:
        extractions = []
        for extraction_id, data in ai_extraction_results.items():
            extractions.append({
                "extraction_id": extraction_id,
                "filename": data["filename"],
                "extraction_time": data["extraction_time"],
                "total_extracted": data["total_extracted"],
                "analysis": data["analysis"]
            })

        # 최신순 정렬
        extractions.sort(key=lambda x: x["extraction_time"], reverse=True)

        return JSONResponse({
            "status": "success",
            "extractions": extractions
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)

@app.get("/ai-extractions/{extraction_id}")
async def get_ai_extraction_detail(extraction_id: str):
    """특정 AI 추출 결과 상세 조회"""
    try:
        if extraction_id not in ai_extraction_results:
            return JSONResponse({
                "status": "error",
                "error": "추출 결과를 찾을 수 없습니다."
            }, status_code=404)

        return JSONResponse({
            "status": "success",
            "data": ai_extraction_results[extraction_id]
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)

@app.post("/ai-extractions/test/{filename}")
async def test_ai_extraction(filename: str, prompt: Optional[str] = None):
    """기존 파일에 대한 AI 추출 테스트 (DB 저장하지 않음)"""
    try:
        file_location = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_location):
            return JSONResponse({
                "status": "error",
                "error": "파일을 찾을 수 없습니다."
            }, status_code=404)

        # AI 추출만 수행 (DB 저장 안함)
        tables = extract_pdf_tables(file_location, user_prompt=prompt, debug_mode=False, save_to_db=False)

        # 분석 결과
        analysis = {
            "total_extracted": len(tables),
            "complete_records": len([t for t in tables if t.get('품명') and t.get('공급자') and t.get('공급가액')]),
            "empty_records": len([t for t in tables if not t.get('품명')]),
            "suppliers": list(set([t.get('공급자', '') for t in tables if t.get('공급자')])),
            "page_breakdown": {}
        }

        # 페이지별 분석
        for table in tables:
            supplier = table.get('공급자', 'Unknown')
            if supplier not in analysis["page_breakdown"]:
                analysis["page_breakdown"][supplier] = 0
            analysis["page_breakdown"][supplier] += 1

        return JSONResponse({
            "status": "success",
            "filename": filename,
            "prompt": prompt,
            "ai_results": tables,
            "analysis": analysis
        })

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)

@app.delete("/data/{data_id}")
async def delete_data(data_id: int):
    """특정 데이터 삭제"""
    try:
        if db is None:
            return JSONResponse({
                "status": "error",
                "message": "테스트 모드에서는 데이터 삭제를 지원하지 않습니다."
            }, status_code=400)

        # SQLite에서 데이터 삭제
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM extracted_data WHERE id = ?", (data_id,))
            if cursor.rowcount == 0:
                return JSONResponse({
                    "status": "error",
                    "error": "Data not found"
                }, status_code=404)
            conn.commit()

        return JSONResponse({
            "status": "success",
            "message": "Data deleted successfully"
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)

@app.delete("/data/")
async def clear_all_data():
    """모든 데이터 초기화"""
    try:
        if db is None:
            return JSONResponse({
                "status": "success",
                "message": "테스트 모드에서는 초기화할 데이터가 없습니다."
            })

        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # 모든 데이터 삭제
            cursor.execute("DELETE FROM extracted_data")
            cursor.execute("DELETE FROM upload_history")

            # AUTO_INCREMENT 초기화
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='extracted_data'")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='upload_history'")

            conn.commit()

        return JSONResponse({
            "status": "success",
            "message": "All data cleared successfully"
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)