# Gemini API 할당량 문제 해결 가이드

## 현재 문제
- "프로젝트의 할당량 등급을 사용할 수 없습니다" 오류
- API 사용량 데이터 로드 실패

## 해결 단계

### 1. 결제 계정 확인
1. Google Cloud Console → 결제 메뉴
2. 프로젝트에 활성 결제 계정이 연결되어 있는지 확인
3. 결제 계정이 활성 상태인지 확인

### 2. Gemini API 서비스 활성화 확인
1. Google Cloud Console → API 및 서비스 → 라이브러리
2. "Gemini API" 또는 "Generative Language API" 검색
3. 서비스가 활성화되어 있는지 확인

### 3. 할당량 설정 확인
1. Google Cloud Console → API 및 서비스 → 할당량
2. "Gemini" 또는 "Generative Language" 필터링
3. 할당량 한도 확인 및 증가 요청 (필요시)

### 4. IAM 권한 확인
1. Google Cloud Console → IAM 및 관리자
2. 현재 계정이 다음 역할을 가지고 있는지 확인:
   - 편집자(Editor) 또는 소유자(Owner)
   - AI Platform Admin

### 5. API 키 재생성 (마지막 수단)
1. Google Cloud Console → API 및 서비스 → 사용자 인증 정보
2. 기존 API 키 삭제
3. 새 API 키 생성
4. 환경변수 업데이트

## 임시 해결책
현재 문제가 해결될 때까지 다른 AI 서비스 사용 고려:
- OpenAI GPT API
- Claude API (Anthropic)
- 로컬 LLM (Ollama)