# 📁 Remicon 프로젝트 구조 설명서

## 🏗️ 전체 프로젝트 구조

```
Remicon/
├── 📂 frontend/           # React 웹 애플리케이션
├── 📂 backend/            # FastAPI 백엔드 서버
├── 📂 .venv/              # Python 가상환경
├── 📂 .git/               # Git 버전 관리
├── 📂 .claude/            # Claude AI 메모리/설정
├── 📄 README.md           # 프로젝트 소개 및 설치 가이드
├── 📄 plan.md             # 프로젝트 기획서
├── 📄 vercel.json         # Vercel 배포 설정
└── 📄 explain.md          # 이 파일 (프로젝트 구조 설명)
```

---

## 🌐 Frontend (React 웹 애플리케이션)

### 📂 `frontend/` 폴더 구조
```
frontend/
├── 📂 src/                # 소스 코드
│   ├── 📄 App.jsx         # 메인 React 컴포넌트 (1,818줄)
│   └── 📄 main.jsx        # React 애플리케이션 진입점
├── 📂 node_modules/       # NPM 의존성 패키지들
├── 📄 package.json        # NPM 패키지 설정 및 의존성
├── 📄 package-lock.json   # 의존성 버전 잠금
├── 📄 index.html          # HTML 템플릿
├── 📄 vite.config.js      # Vite 빌드 도구 설정
├── 📄 .env                # 환경변수 (백엔드 API URL 등)
└── 📄 .env.example        # 환경변수 템플릿
```

### 🎯 Frontend 주요 파일 역할

#### 📄 `App.jsx` (1,818줄) - 메인 애플리케이션
- **역할**: 전체 사용자 인터페이스 담당
- **주요 기능**:
  - PDF 파일 업로드 (드래그 앤 드롭)
  - AI 추출 결과 실시간 표시
  - 데이터 테이블 표시 (정렬, 검색, 필터링)
  - 프롬프트 설정 관리
  - CSV 다운로드 기능
  - 에러 처리 및 사용자 알림

#### 📄 `main.jsx` - React 앱 진입점
- **역할**: React 애플리케이션을 DOM에 마운트
- **기능**: App 컴포넌트를 HTML root 엘리먼트에 렌더링

#### 📄 `package.json` - 프로젝트 설정
```json
{
  "name": "remicon-frontend",
  "dependencies": {
    "react": "^18.2.0",      # React 프레임워크
    "react-dom": "^18.2.0",  # React DOM 라이브러리
    "axios": "^1.15.2"       # HTTP 클라이언트 (백엔드 통신)
  }
}
```

#### 📄 `.env` - 환경변수
```bash
VITE_API_URL=http://localhost:8000  # 백엔드 API 서버 주소
```

---

## ⚙️ Backend (FastAPI 서버)

### 📂 `backend/` 폴더 구조
```
backend/
├── 📄 main.py             # FastAPI 메인 서버 (269줄)
├── 📄 pdf_utils.py        # PDF 처리 및 AI 추출 (556줄)
├── 📄 database.py         # SQLite 데이터베이스 관리
├── 📄 requirements.txt    # Python 의존성 패키지 목록
├── 📄 remicon.db          # SQLite 데이터베이스 파일
├── 📂 uploads/            # 업로드된 PDF 파일 저장소
│   ├── 📄 .gitkeep        # 빈 폴더 유지용
│   └── 📄 레미콘 거래명세서(금토).pdf  # 예시 PDF 파일
└── 📂 __pycache__/        # Python 컴파일 캐시
```

### 🎯 Backend 주요 파일 역할

#### 📄 `main.py` (269줄) - FastAPI 메인 서버
- **역할**: HTTP API 서버 및 요청 처리
- **주요 API 엔드포인트**:
  ```python
  POST /upload_pdf/              # PDF 업로드 및 AI 추출
  GET  /data/                    # 저장된 데이터 조회
  GET  /statistics/              # 통계 정보 조회
  GET  /ai-extractions/          # AI 추출 결과 목록
  GET  /ai-extractions/{id}      # 특정 추출 결과 상세
  POST /ai-extractions/test/{filename}  # 테스트 추출 (DB 저장 안함)
  DELETE /data/{id}              # 특정 데이터 삭제
  DELETE /data/                  # 모든 데이터 삭제
  ```
- **기능**:
  - 파일 업로드 처리
  - CORS 미들웨어 설정
  - API 할당량 소진 감지 및 처리
  - 데이터베이스와 연동

#### 📄 `pdf_utils.py` (556줄) - PDF 처리 및 AI 추출 핵심
- **역할**: PDF 텍스트 추출 및 Google Gemini AI 연동
- **주요 기능**:
  - **AI 우선 추출**: Google Gemini Flash Latest 모델 사용
  - **멀티모달 처리**: 텍스트 + OCR + 테이블 추출
  - **전통적 백업**: AI 실패시 전통적 PDF 파싱으로 fallback
  - **데이터 필터링**: 실제 거래 데이터만 추출 (헤더/합계 제외)
  - **에러 처리**: API 할당량 소진 감지 및 재시도

- **핵심 함수들**:
  ```python
  extract_pdf_tables()          # 메인 추출 함수
  extract_with_ai()            # AI 추출 로직
  flatten_transaction_data()    # nested JSON을 flat 구조로 변환
  is_actual_transaction()       # 실제 거래 데이터 필터링
  ```

#### 📄 `database.py` - 데이터베이스 관리
- **역할**: SQLite 데이터베이스 CRUD 작업
- **기능**:
  - 추출된 데이터 저장
  - 데이터 조회 및 통계
  - 파일 업로드 이력 관리

#### 📄 `requirements.txt` - Python 의존성
```txt
fastapi==0.104.1                # 웹 프레임워크
uvicorn[standard]==0.24.0        # ASGI 서버
python-multipart==0.0.6         # 파일 업로드 지원
pdfplumber==0.10.3               # PDF 텍스트 추출
pytesseract==0.3.10              # OCR 엔진
pillow==10.0.1                   # 이미지 처리
requests==2.31.0                 # HTTP 클라이언트
google-genai==1.73.1             # Google AI API (최신)
```

---

## 🗄️ 데이터베이스 (SQLite)

### 📄 `remicon.db` - SQLite 데이터베이스
- **역할**: 추출된 데이터 영구 저장
- **테이블 구조** (예상):
  ```sql
  extracted_data:           # 추출된 거래 데이터
  ├── id (INTEGER)          # 기본키
  ├── filename (TEXT)       # 원본 파일명
  ├── upload_date (TEXT)    # 업로드 날짜
  ├── supplier (TEXT)       # 공급자명
  ├── item_name (TEXT)      # 품명
  ├── amount (REAL)         # 공급가액
  └── created_at (TEXT)     # 생성일시
  
  upload_history:           # 업로드 이력
  ├── id (INTEGER)          # 기본키
  ├── filename (TEXT)       # 파일명
  ├── status (TEXT)         # 처리 상태
  └── upload_time (TEXT)    # 업로드 시간
  ```

---

## 🔧 설정 및 배포 파일

### 📄 `vercel.json` - Vercel 배포 설정
- **역할**: Vercel 플랫폼에 프론트엔드 배포
- **설정**:
  - 빌드 명령: `npm run build`
  - 출력 디렉토리: `frontend/dist`
  - SPA 라우팅 지원

### 📄 `README.md` - 프로젝트 문서
- **역할**: 프로젝트 소개, 설치법, 사용법 안내
- **내용**:
  - 기술 스택 소개
  - 단계별 설정 가이드
  - API 할당량 정보
  - 문제 해결 방법

### 📄 `plan.md` - 프로젝트 기획서
- **역할**: 초기 프로젝트 계획 및 요구사항 정의
- **내용**:
  - 화면 구성 계획
  - 주요 기능 명세
  - 기술 스택 선정 근거
  - 데이터베이스 설계

---

## 🔄 데이터 플로우 (Data Flow)

```
1. 사용자 파일 업로드
   ↓
2. Frontend (App.jsx) → POST /upload_pdf/
   ↓
3. Backend (main.py) → pdf_utils.extract_pdf_tables()
   ↓
4. AI 추출 (Google Gemini) OR 전통적 파싱
   ↓
5. 데이터 필터링 및 정제
   ↓
6. Database 저장 (remicon.db)
   ↓
7. JSON 응답 → Frontend 테이블 표시
```

---

## 🌐 네트워크 아키텍처

```
브라우저 (http://localhost:3000)
    ↓ Axios HTTP 요청
FastAPI 서버 (http://localhost:8000)
    ↓ AI API 호출
Google Gemini AI API
    ↓ 응답
SQLite Database (remicon.db)
```

---

## 🚀 실행 순서

1. **백엔드 서버 시작**:
   ```bash
   cd backend
   source .venv/bin/activate
   python main.py  # http://localhost:8000
   ```

2. **프론트엔드 서버 시작**:
   ```bash
   cd frontend
   npm run dev     # http://localhost:3000
   ```

3. **사용자 접속**: http://localhost:3000

---

## 🔑 핵심 기술 요약

| 영역 | 기술 | 역할 |
|------|------|------|
| **Frontend** | React + Vite | 사용자 인터페이스 |
| **Backend** | FastAPI | API 서버 |
| **AI** | Google Gemini | PDF 데이터 추출 |
| **OCR** | Tesseract | 이미지 텍스트 인식 |
| **PDF** | PDFplumber | PDF 텍스트 추출 |
| **DB** | SQLite | 데이터 저장 |
| **배포** | Vercel | 프론트엔드 호스팅 |

---

## 📊 성능 지표

- **처리 속도**: 3페이지 PDF 약 30-60초
- **정확도**: 실제 거래 데이터 15개 중 15개 추출 (100%)
- **필터링**: 37개 원시 데이터 → 15개 실제 거래 (60% 정확도)
- **디스크 사용량**: 
  - Frontend: 47MB
  - Backend: 84MB
  - Database: ~80KB

---

*이 문서는 Remicon 프로젝트의 전체 구조를 이해하기 위한 가이드입니다. 각 파일의 상세한 API 및 함수 정보는 해당 소스 코드를 참조하세요.*