from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict

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

# 데이터베이스 매니저 초기화
db = DatabaseManager()

@app.post("/upload_pdf/")
async def upload_pdf(
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(None)
):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as f:
        f.write(await file.read())

    # PDF 표 데이터 추출 (Google Gemini AI 사용)
    try:
        tables = extract_pdf_tables(file_location, prompt)

        # API 할당량 소진 감지
        if tables and len(tables) > 0 and tables[0].get('api_quota_exceeded'):
            return JSONResponse({
                "filename": file.filename,
                "prompt": prompt,
                "status": "api_quota_exceeded",
                "error": "API 할당량이 소진되어 작업을 진행할 수 없습니다.",
                "error_type": "quota_exceeded",
                "retry_info": "할당량은 매일 오전 9시(한국시간)에 복구됩니다."
            }, status_code=429)

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

        # 데이터베이스에 저장 (유효한 데이터만)
        valid_tables = [table for table in tables if not ('raw_text' in table and len(table) == 1)]
        saved_count = db.save_extracted_data(file.filename, valid_tables, prompt) if valid_tables else 0

        return JSONResponse({
            "filename": file.filename,
            "prompt": prompt,
            "status": "success",
            "tables": tables,
            "saved_count": saved_count,
            "ai_used": True,
            "extraction_id": extraction_id,
            "analysis": ai_extraction_results[extraction_id]["analysis"]
        })
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return JSONResponse({
            "filename": file.filename,
            "prompt": prompt,
            "status": "error",
            "error": str(e)
        }, status_code=500)

@app.get("/data/")
async def get_all_data():
    """저장된 모든 데이터 조회"""
    try:
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
        tables = extract_pdf_tables(file_location, prompt)

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