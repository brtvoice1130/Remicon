#!/usr/bin/env python3
"""
Supabase 테이블 생성 스크립트
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def create_remicon_table():
    # Supabase 클라이언트 생성
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print("❌ SUPABASE_URL 또는 SUPABASE_ANON_KEY가 설정되지 않았습니다.")
        print(f"SUPABASE_URL: {url}")
        print(f"SUPABASE_ANON_KEY: {'설정됨' if key else '설정안됨'}")
        return False

    print(f"🔗 Supabase 연결 중... {url}")

    try:
        supabase: Client = create_client(url, key)
        print("✅ Supabase 클라이언트 생성 완료")

        # 테이블 생성 SQL
        create_table_sql = """
        -- 기존 테이블이 있으면 삭제
        DROP TABLE IF EXISTS remicon_data;

        -- remicon_data 테이블 생성
        CREATE TABLE remicon_data (
          id BIGSERIAL PRIMARY KEY,
          upload_date TIMESTAMP DEFAULT NOW(),
          filename TEXT,
          site_name TEXT,
          supplier TEXT,
          item_name TEXT,
          specification TEXT,
          unit TEXT,
          quantity DECIMAL DEFAULT 0,
          unit_price INTEGER DEFAULT 0,
          amount INTEGER DEFAULT 0,
          tax_amount INTEGER DEFAULT 0,
          total_amount INTEGER DEFAULT 0,
          delivery_date TEXT,
          currency TEXT DEFAULT 'KRW',
          notes TEXT,
          created_at TIMESTAMP DEFAULT NOW()
        );
        """

        print("📝 테이블 생성 중...")

        # SQL 실행
        result = supabase.rpc('exec_sql', {'sql': create_table_sql}).execute()

        if result.data:
            print("✅ remicon_data 테이블 생성 완료!")
        else:
            print("⚠️ 결과 데이터가 없습니다. 테이블이 이미 존재할 수 있습니다.")

        # 테이블 확인
        print("🔍 테이블 존재 확인 중...")
        check_result = supabase.table('remicon_data').select('*').limit(1).execute()
        print("✅ 테이블 접근 가능 확인!")

        # RLS 비활성화 (테스트용)
        print("🔧 RLS 설정 조정 중...")
        rls_sql = "ALTER TABLE remicon_data DISABLE ROW LEVEL SECURITY;"
        try:
            supabase.rpc('exec_sql', {'sql': rls_sql}).execute()
            print("✅ RLS 비활성화 완료")
        except Exception as e:
            print(f"⚠️ RLS 설정 실패 (무시 가능): {e}")

        return True

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("🔧 수동으로 Supabase 대시보드에서 테이블을 생성해주세요.")

        # 수동 생성용 SQL 출력
        print("\n" + "="*50)
        print("수동 생성용 SQL:")
        print("="*50)
        print("""
CREATE TABLE remicon_data (
  id BIGSERIAL PRIMARY KEY,
  upload_date TIMESTAMP DEFAULT NOW(),
  filename TEXT,
  site_name TEXT,
  supplier TEXT,
  item_name TEXT,
  specification TEXT,
  unit TEXT,
  quantity DECIMAL DEFAULT 0,
  unit_price INTEGER DEFAULT 0,
  amount INTEGER DEFAULT 0,
  tax_amount INTEGER DEFAULT 0,
  total_amount INTEGER DEFAULT 0,
  delivery_date TEXT,
  currency TEXT DEFAULT 'KRW',
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- RLS 비활성화 (테스트용)
ALTER TABLE remicon_data DISABLE ROW LEVEL SECURITY;
        """)
        print("="*50)

        return False

if __name__ == "__main__":
    print("🚀 Supabase 테이블 생성 시작")
    success = create_remicon_table()

    if success:
        print("\n🎉 테이블 생성 완료! 이제 PDF 업로드를 테스트할 수 있습니다.")
    else:
        print("\n🔧 수동으로 테이블을 생성해주세요.")