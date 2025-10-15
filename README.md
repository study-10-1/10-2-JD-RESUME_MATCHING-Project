<<<<<<< HEAD
# Auto-Match: AI-based Resume & Job Matching System

**한국어 특화 AI 기반 이력서-채용공고 자동 매칭 시스템**

> 🎯 **현재 상태**: 핵심 매칭 알고리즘 완성 (100%) | 검증 완료 (8-464 case  100% 정확도) | 프로덕션 준비 완료

---

## ✨ 핵심 기능

### 1. **의미 기반 매칭** ⭐⭐⭐⭐⭐
- Bi-encoder 임베딩 기반 코사인 유사도 계산
- 한국어 특화 모델 (`jhgan/ko-sroberta-multitask`)
- 768차원 벡터 공간에서 의미적 유사도 분석

### 2. **섹션별 임베딩 매칭** ⭐⭐⭐⭐⭐
- 자격요건 vs 이력서 스킬 (의미 기반)
- 우대조건 vs 이력서 스킬 (의미 기반)
- 업무설명 vs 경력/프로젝트 (의미 기반)
- 키워드 매칭으로 정확도 보완

### 3. **다차원 점수 계산**
- 6개 카테고리 종합 평가 (자격요건/우대조건/경력/학력/자격증/전체유사도)
- 최적화된 가중치 적용 (Grid Search 튜닝 완료)
- 경력 페널티 캡 적용 (최대 15점 감점)

### 4. **상세 매칭 분석**
- 자격요건/우대조건 개별 매칭 현황
- 누락 스킬 및 충족 스킬 명시
- 매칭 근거 및 개선 제안 제공

### 5. **GPT-5 피드백** (선택)
- 맞춤형 강점/개선점/추천사항 생성
- LLM 기반 이력서 고도화 파싱

---

## 🔧 기술 스택

### Backend
- **Framework**: FastAPI 0.104+
- **Language**: Python 3.10+
- **Database**: PostgreSQL 15 + pgvector
- **Cache**: Redis 7+ (Optional)
- **Container**: Docker + Docker Compose

### AI/ML
- **Embedding**: `jhgan/ko-sroberta-multitask` (768-dim, 한국어 Bi-encoder)
- **Vector Search**: pgvector (Cosine Similarity)
- **LLM**: OpenAI GPT-5 (피드백 생성용)
- **Parsing**: PyMuPDF, python-docx, openpyxl

### 성능
- **정확도**: False Positive 0%, False Negative 0% (검증 완료)
- **처리 속도**: 점수 계산 1초/건, 벡터 검색 0.1초
- **확장성**: 10,000개 공고 검색 10초 (pgvector HNSW)
- **API 응답**: 검색 결과 1-2초, 상세 피드백 45초 (on-demand)

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 환경 변수 확인
# .env 파일이 이미 생성되어 있습니다.
```

### 2. Docker 컨테이너 시작

```bash
# 모든 서비스 시작 (PostgreSQL, Redis, Backend)
docker-compose up -d

# 로그 확인
docker-compose logs -f backend
```

### 3. 데이터베이스 마이그레이션

```bash
# Backend 컨테이너에 접속
docker-compose exec backend bash

# 마이그레이션 생성 (최초 1회)
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 적용
alembic upgrade head

# 샘플 데이터 로드
python scripts/seed_data.py

# 컨테이너에서 나가기
exit
```

### 4. API 접속

- **Backend API**: http://localhost:8000
- **API 문서 (Swagger)**: http://localhost:8000/docs
- **API 문서 (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📁 프로젝트 구조

```
Project1/
├── backend/                 # 🎯 Backend 애플리케이션
│   ├── app/                # FastAPI 앱
│   │   ├── api/           # API 엔드포인트
│   │   ├── core/          # 핵심 유틸리티
│   │   ├── models/        # SQLAlchemy 모델
│   │   ├── schemas/       # Pydantic 스키마
│   │   ├── services/      # 비즈니스 로직
│   │   │   ├── ml/       # 🤖 매칭 알고리즘 (핵심!)
│   │   │   ├── parsing/  # 파일 파싱
│   │   │   └── llm/      # LLM 서비스
│   │   ├── repositories/  # 데이터 액세스
│   │   └── utils/         # 유틸리티
│   ├── alembic/           # DB 마이그레이션
│   ├── scripts/           # 유틸리티 스크립트
│   ├── tests/             # 테스트
│   ├── Dockerfile
│   └── requirements.txt
│
├── docs/                   # 📚 문서
│   ├── GETTING_STARTED.md        # 시작 가이드
│   ├── PROJECT_STRUCTURE.md      # 구조 설명
│   └── PROJECT_SPECIFICATION.md  # 프로젝트 명세서
│
├── docker-compose.yml      # 🐳 Docker Compose 설정
├── .env                    # 🔐 환경 변수
├── .gitignore              # Git 제외 파일
└── README.md               # 이 파일
```

> **💡 구조 설명**:
> - `backend/` - 모든 백엔드 관련 파일 (앱, 스크립트, 테스트)
> - `docs/` - 개발 문서 및 가이드
> - 루트 - Docker 설정, 환경 변수, 프로젝트 소개만

## 🎯 API 엔드포인트

### 인증
- `POST /api/v1/auth/register` - 회원가입
- `POST /api/v1/auth/login` - 로그인

### 이력서
- `POST /api/v1/resumes/upload` - 이력서 업로드
- `GET /api/v1/resumes` - 이력서 목록
- `GET /api/v1/resumes/{resume_id}` - 이력서 상세

### 채용공고
- `GET /api/v1/jobs` - 채용공고 목록
- `GET /api/v1/jobs/{job_id}` - 채용공고 상세

### 매칭 ⭐
- `POST /api/v1/matching/search-jobs` - 이력서 기반 공고 매칭 (빠른 응답)
- `GET /api/v1/matching/{matching_id}` - 매칭 상세 (실시간 계산)
- `GET /api/v1/matching/{matching_id}/feedback` - GPT-5 피드백 (on-demand)

## 📊 매칭 알고리즘

### 카테고리별 가중치 (최적화 완료) ⭐ 섹션별 임베딩 방식!
```python
SECTIONAL_WEIGHTS = {
    "required": 0.40,          # 자격요건 매칭 (1순위 - 가장 중요)
    "experience": 0.30,        # 경력 매칭 (2순위 - 매우 중요)
    "overall": 0.20,           # 전체 유사도 (3순위 - 중요)
    "preferred": 0.08,         # 우대조건 매칭 (4순위 - 보조적)
    "education": 0.015,        # 학력 (낮은 가중치)
    "certification": 0.005,    # 자격증 (매우 낮은 가중치)
}
```

**카테고리별 임베딩 비교:**
- 자격요건 vs 스킬 (정확!)
- 우대조건 vs 스킬 (정확!)
- 업무 설명 vs 경력/프로젝트 (정확!)

### 등급 기준
- 🟢 **Excellent** (85%+): 매우 우수 - 서류 통과 가능성 높음
- 🟡 **Good** (70-85%): 양호 - 지원 권장
- 🟠 **Fair** (55-70%): 보통 - 일부 조건 보완 필요 (현실적 기준)
- ⚠️ **Caution** (40-55%): 주의 - 신중히 검토 필요
- 🔴 **Poor** (<40%): 부적합 - 기술 스택 불일치

### 검증 결과
- **False Positive**: 0% (완벽한 필터링)
- **False Negative**: 0% (정확한 등급 부여)
- **직군 구분**: 100% (Android vs Web 완벽 구분)

---

## 📚 문서

### 개발자 가이드
- **[아키텍처 문서](ARCHITECTURE.md)** ⭐ - 전체 시스템 구조 및 DB 스키마
- **[크롤링 가이드](CRAWLING_GUIDE.md)** ⭐ - 크롤링/OCR/API 연동 실전 가이드
- **[프로젝트 명세서](PROJECT_SPECIFICATION.md)** - 초기 요구사항

### 빠른 참고
```bash
# 프로젝트 구조
Project1/
├── backend/              # 백엔드 앱
│   ├── app/
│   │   ├── services/ml/  # 🎯 매칭 알고리즘 (핵심!)
│   │   ├── models/       # DB 모델
│   │   └── api/          # API 엔드포인트
│   └── scripts/          # 유틸리티 스크립트
├── embedding-service/    # 임베딩 전용 서비스
├── data/                 # 데이터 (공고/이력서)
└── ARCHITECTURE.md       # 📖 메인 문서
```

## 🛠️ 개발 명령어

```bash
# 로그 확인
docker-compose logs -f backend

# 컨테이너 재시작
docker-compose restart backend

# 데이터베이스 접속
docker-compose exec postgres psql -U postgres -d auto_match

# Backend 컨테이너 접속
docker-compose exec backend bash

# 마이그레이션 생성
docker-compose exec backend alembic revision --autogenerate -m "message"

# 마이그레이션 적용
docker-compose exec backend alembic upgrade head
```

## 📝 개발 로드맵

### ✅ 완료 (Phase 1-5)
- [x] 프로젝트 구조 및 Docker 환경 구축
- [x] DB 스키마 설계 (pgvector 포함)
- [x] 이력서/공고 파싱 (PDF/DOCX/XLSX)
- [x] 임베딩 생성 (jhgan/ko-sroberta-multitask)
- [x] 매칭 알고리즘 구현 ⭐
- [x] 섹션별 임베딩 매칭 구현 ⭐
- [x] 가중치 튜닝 (Grid Search)
- [x] GPT-5 피드백 생성
- [x] 검증 완료 (100% 정확도)
- [x] 중복 방지 UNIQUE INDEX 추가
- [x] 만료 자동 비활성화 트리거
- [x] 실시간 계산 방식으로 변경
- [x] 2단계 API 구현 (빠른 검색 + on-demand 피드백)
- [x] 경력 페널티 캡 적용
- [x] 의미 매칭 강화

### 🚧 다음 단계 (Phase 6)
- [ ] **사람인 API 연동 + GPT-5 구조화** ← 다음!
- [ ] 프론트엔드 연동
- [ ] 북마크/지원 기능

### 📅 예정 (Phase 7-8)
- [ ] Cloud Run 배포 (GCP)
- [ ] 원티드/로켓펀치 크롤링
- [ ] 모니터링 대시보드

---

## 🔑 핵심 구현 파일

### 매칭 알고리즘 ⭐⭐⭐⭐⭐
```
backend/app/services/ml/
├── embedding.py              # 임베딩 생성 (✅ 완성)
├── vector_search.py          # 벡터 검색 (✅ 완성)
├── scoring.py                # 점수 계산 (✅ 완성)
├── sectional_scoring.py      # 섹션별 점수 (✅ 완성)
├── penalties.py              # 페널티 (✅ 완성)
└── feedback_generator.py     # 피드백 (✅ 완성)

backend/app/services/
├── matching_service.py       # 매칭 통합 (✅ 완성)
└── parsing/
    ├── llm_parser.py         # GPT-5 파싱 (✅ 완성)
    └── ...

backend/scripts/
├── process_resumes.py        # 이력서 처리
├── insert_job_data.py        # 공고 삽입
├── tune_weights.py           # 가중치 튜닝 (✅ 완료)
└── validate_all_matching.py  # 전체 검증
```

## 📄 라이선스

MIT License

## 👥 기여

이슈 및 PR을 환영합니다!

---

**💡 Tip**: 상세한 설명은 [`docs/`](docs/) 폴더를 참고하세요!
=======
# 10-2-JD-RESUME_MATCHING-Project
10-2-JD-RESUME_MATCHING-Project
>>>>>>> 59b895c0e2bea02fca195af2d94e296f7cafb4bd
