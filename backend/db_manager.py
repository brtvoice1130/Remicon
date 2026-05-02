import os
from datetime import datetime
from typing import List, Dict, Optional
from supabase import create_client, Client

# Supabase 클라이언트 초기화
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print("✅ Supabase 클라이언트 초기화 완료")
else:
    supabase = None
    print("⚠️ Supabase 환경변수가 설정되지 않았습니다.")

def save_extracted_data(filename: str, extracted_records: List[Dict]) -> Dict:
    """
    추출된 PDF 데이터를 DB에 저장합니다.
    유효한 거래 데이터만 필터링해서 저장합니다.
    """
    if not supabase:
        return {
            "status": "error",
            "message": "DB 연결이 설정되지 않았습니다.",
            "saved_count": 0
        }

    if not extracted_records:
        return {
            "status": "success",
            "message": "저장할 데이터가 없습니다.",
            "saved_count": 0
        }

    try:
        # 현재 시간으로 업로드 날짜 설정
        upload_date = datetime.now().isoformat()

        # DB 저장할 레코드들 준비
        db_records = []
        saved_count = 0

        for record in extracted_records:
            # 유효성 재검증 (DB 저장 전 마지막 체크)
            if not is_valid_for_db(record):
                continue

            # DB 스키마에 맞게 데이터 변환
            db_record = {
                "upload_date": upload_date,
                "filename": filename,
                "site_name": record.get("현장명", "") or record.get("customer", ""),
                "supplier": record.get("공급자", "") or record.get("supplier", ""),
                "item_name": record.get("품명", "") or record.get("item", ""),
                "specification": record.get("규격", "") or record.get("specification", ""),
                "unit": record.get("단위", "") or record.get("unit", "M3"),
                "quantity": safe_float(record.get("물량", 0)),
                "unit_price": safe_int(record.get("단가", 0)),
                "amount": safe_int(record.get("공급가액", 0)),
                "tax_amount": safe_int(record.get("세액", 0)),
                "total_amount": safe_int(record.get("합계", 0)),
                "delivery_date": record.get("출하일", ""),
                "currency": "KRW",
                "notes": record.get("비고", "")
            }

            db_records.append(db_record)

        if db_records:
            # Supabase에 배치 저장
            result = supabase.table("remicon_data").insert(db_records).execute()

            if result.data:
                saved_count = len(result.data)
                print(f"✅ DB 저장 완료: {saved_count}개 레코드")

                return {
                    "status": "success",
                    "message": f"{saved_count}개 레코드가 DB에 저장되었습니다.",
                    "saved_count": saved_count,
                    "filtered_count": len(extracted_records) - saved_count
                }
            else:
                return {
                    "status": "error",
                    "message": "DB 저장 중 오류가 발생했습니다.",
                    "saved_count": 0
                }
        else:
            return {
                "status": "warning",
                "message": "유효한 데이터가 없어 저장하지 않았습니다.",
                "saved_count": 0,
                "total_filtered": len(extracted_records)
            }

    except Exception as e:
        print(f"❌ DB 저장 오류: {e}")
        return {
            "status": "error",
            "message": f"DB 저장 중 오류: {str(e)}",
            "saved_count": 0
        }

def is_valid_for_db(record: Dict) -> bool:
    """
    DB 저장을 위한 최종 유효성 검사
    더 엄격한 기준 적용
    """
    # 필수 금액 데이터 확인
    amount = safe_int(record.get("공급가액", 0))
    total = safe_int(record.get("합계", 0))
    quantity = safe_float(record.get("물량", 0))

    # 최소한 금액이나 수량 중 하나는 있어야 함
    has_financial_data = amount > 0 or total > 0
    has_quantity_data = quantity > 0

    if not (has_financial_data or has_quantity_data):
        return False

    # 공급자나 현장명 중 하나는 있어야 함
    supplier = record.get("공급자", "") or record.get("supplier", "")
    site = record.get("현장명", "") or record.get("customer", "")

    if not (supplier.strip() or site.strip()):
        return False

    return True

def safe_int(value) -> int:
    """안전하게 정수로 변환"""
    if not value:
        return 0
    try:
        if isinstance(value, str):
            # 쉼표 제거하고 변환
            cleaned = value.replace(",", "").replace(".", "")
            return int(float(cleaned))
        return int(float(value))
    except (ValueError, TypeError):
        return 0

def safe_float(value) -> float:
    """안전하게 실수로 변환"""
    if not value:
        return 0.0
    try:
        if isinstance(value, str):
            # 쉼표 제거하고 변환
            cleaned = value.replace(",", "")
            return float(cleaned)
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def get_saved_data() -> List[Dict]:
    """저장된 데이터 조회"""
    if not supabase:
        return []

    try:
        result = supabase.table("remicon_data").select("*").order("upload_date", desc=True).execute()
        return result.data or []
    except Exception as e:
        print(f"❌ 데이터 조회 오류: {e}")
        return []

def delete_data_item(item_id: int) -> bool:
    """개별 데이터 삭제"""
    if not supabase:
        return False

    try:
        result = supabase.table("remicon_data").delete().eq("id", item_id).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"❌ 데이터 삭제 오류: {e}")
        return False

def clear_all_data() -> bool:
    """모든 데이터 삭제"""
    if not supabase:
        return False

    try:
        result = supabase.table("remicon_data").delete().neq("id", 0).execute()
        return True
    except Exception as e:
        print(f"❌ 전체 데이터 삭제 오류: {e}")
        return False

def get_statistics() -> Dict:
    """통계 정보 조회"""
    if not supabase:
        return {
            "total_records": 0,
            "total_files": 0,
            "total_amount": 0,
            "supabase_configured": False
        }

    try:
        # 전체 레코드 수와 합계 조회
        result = supabase.table("remicon_data").select("amount, total_amount, filename").execute()

        if result.data:
            records = result.data
            total_records = len(records)
            total_files = len(set(record.get("filename", "") for record in records))
            total_amount = sum(record.get("total_amount", 0) or 0 for record in records)

            return {
                "total_records": total_records,
                "total_files": total_files,
                "total_amount": total_amount,
                "supabase_configured": True
            }
        else:
            return {
                "total_records": 0,
                "total_files": 0,
                "total_amount": 0,
                "supabase_configured": True
            }

    except Exception as e:
        print(f"❌ 통계 조회 오류: {e}")
        return {
            "total_records": 0,
            "total_files": 0,
            "total_amount": 0,
            "supabase_configured": True,
            "error": str(e)
        }