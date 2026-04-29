# Remicon - 레미콘 거래명세서 AI 분석 시스템

AI를 활용한 레미콘 거래명세서 자동 분석 및 데이터 추출 시스템입니다.

## 🚀 주요 기능

- **AI 기반 PDF 분석**: Google Gemini AI를 활용한 정확한 데이터 추출
- **한국어 특화 처리**: 레미콘 업계 전용 용어 및 양식 대응
- **실시간 데이터 저장**: SQLite 데이터베이스 자동 저장
- **웹 인터페이스**: 직관적인 업로드 및 결과 확인

## 📋 기술 스택

### Backend
- **FastAPI**: Python 웹 프레임워크
- **Google Gemini AI**: 문서 분석 AI
- **PDFplumber**: PDF 텍스트 추출
- **Tesseract OCR**: 이미지 기반 텍스트 인식
- **SQLite**: 데이터 저장

### Frontend  
- **React**: UI 프레임워크
- **Vite**: 빌드 도구
- **Axios**: HTTP 클라이언트

## 🛠️ 설치 및 설정

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/remicon.git
cd remicon
```

### 2. 백엔드 설정
```bash
cd backend

# Python 가상환경 생성
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 종속성 설치
pip install -r requirements.txt

# 환경변수 설정
cp ../.env.example .env
# .env 파일에서 GOOGLE_API_KEY를 실제 값으로 설정
```

### 3. 프론트엔드 설정
```bash
cd frontend

# 종속성 설치
npm install
```

### 4. Google AI API 키 발급
1. [Google AI Studio](https://makersuite.google.com/app/apikey) 방문
2. 새 API 키 생성
3. `.env` 파일에 키 추가

### 5. Tesseract OCR 설치 (macOS)
```bash
brew install tesseract tesseract-lang
```

## 🚀 실행

### 개발 환경
```bash
# 백엔드 서버 실행 (포트 8000)
cd backend
source .venv/bin/activate
export GOOGLE_API_KEY="your_api_key"
python main.py

# 프론트엔드 서버 실행 (포트 3000)
cd frontend
npm run dev
```

### 프로덕션 빌드
```bash
# 프론트엔드 빌드
cd frontend
npm run build

# 백엔드는 uvicorn으로 실행
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📊 API 할당량 정보

- **무료 티어**: 일일 20회 요청
- **복구 시간**: 매일 오후 4시 (한국시간)
- **할당량 소진시**: 자동 안내 메시지 표시

## 🔧 사용 방법

1. **PDF 업로드**: 레미콘 거래명세서 PDF 파일 선택
2. **자동 분석**: AI가 공급자, 품명, 금액 등 자동 추출
3. **결과 확인**: 추출된 데이터 테이블 형태로 표시
4. **데이터 관리**: 저장된 데이터 조회 및 관리

## 🐛 문제 해결

### API 할당량 소진
- **현상**: "API 할당량이 소진되어..." 메시지
- **해결**: 오후 4시까지 대기 또는 유료 플랜 업그레이드

### OCR 오류
- **현상**: "tesseract is not installed" 오류
- **해결**: `brew install tesseract tesseract-lang`

### 환경변수 오류
- **현상**: "GOOGLE_API_KEY 환경변수가 설정되지 않았습니다"
- **해결**: `.env` 파일 확인 및 API 키 설정

## 📄 라이선스

MIT License

## 🤝 기여

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📞 문의

프로젝트 관련 문의사항이 있으시면 Issues를 통해 연락해주세요.