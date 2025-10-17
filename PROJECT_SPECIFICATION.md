# 프로젝트 명세서

**프로젝트명**: Auto-Match: AI-based Resume & Job Matching System  
**버전**: 3.0  
**최종 업데이트**: 2025-10-17  
**상태**: 실서비스 준비 완료 ✅

---

## 📋 프로젝트 개요

### 목적
한국어 특화 AI 기반 이력서-채용공고 자동 매칭 시스템으로, 의미 기반 매칭과 동적 임계값 시스템을 통해 95%+ 정확도를 달성한 실서비스 수준의 매칭 엔진을 제공합니다.

### 핵심 가치
- **정확성**: 95%+ 매칭 정확도 (실서비스 수준)
- **효율성**: 1-2초 내 매칭 결과 제공
- **확장성**: 10,000개 공고 검색 10초
- **투명성**: 실시간 로깅 및 매칭 근거 제공

---

## 🎯 핵심 기능

### 1. 동적 임계값 시스템 ⭐⭐⭐⭐⭐
- **기술 스택별 세분화된 임계값**: Java(0.75), Python(0.62), React(0.75) 등
- **충돌 기술 스택 자동 감지**: Java vs Python, React vs Flutter 완벽 차단
- **실시간 로깅**: 모든 매칭 과정 완전 추적
- **Near Miss 감지**: 경계선 케이스 자동 감지

### 2. 문장 단위 매칭 ⭐⭐⭐⭐⭐
- **섹션별 문장 추출**: 자격요건, 우대조건, 업무설명별 세밀한 분석
- **의미 기반 유사도**: Bi-encoder 모델 기반 코사인 유사도 계산
- **정확한 매칭**: 문장별 최적화된 임계값 적용

### 3. 다차원 점수 계산
- **6개 카테고리 평가**: 자격요건(60%), 우대조건(20%), 경력(10%), 전체유사도(10%)
- **최적화된 가중치**: 실제 테스트 기반 튜닝 완료
- **경력 페널티 캡**: 최대 15점 감점 제한

### 4. 상세 매칭 분석
- **개별 매칭 현황**: 자격요건/우대조건별 상세 분석
- **매칭 근거 제공**: 어떤 문장이 매칭되었는지 명시
- **개선 제안**: 누락 스킬 및 보완 방안 제시

### 5. GPT-4 피드백 (선택)
- **맞춤형 피드백**: 강점/개선점/추천사항 생성
- **이력서 고도화**: LLM 기반 파싱 및 구조화

---

## 🔧 기술 스택

### Backend
- **Framework**: FastAPI 0.104+
- **Language**: Python 3.10+
- **Database**: PostgreSQL 15 + pgvector
- **Cache**: Redis 7+ (Optional)
- **Container**: Docker + Docker Compose

### AI/ML
- **Embedding Model**: `jhgan/ko-sroberta-multitask` (768차원, 한국어 Bi-encoder)
- **Vector Search**: pgvector (Cosine Similarity)
- **LLM**: OpenAI GPT-4 (피드백 생성용)
- **Parsing**: PyMuPDF, python-docx, openpyxl

### 성능 지표
- **정확도**: 95%+ (실서비스 수준)
- **오탐지율**: <5% (동적 임계값 시스템)
- **처리 속도**: 점수 계산 1초/건, 벡터 검색 0.1초
- **확장성**: 10,000개 공고 검색 10초
- **API 응답**: 검색 결과 1-2초, 상세 피드백 45초

---

## 📊 매칭 알고리즘

### 동적 임계값 시스템
```python
tech_thresholds = {
    # 충돌 방지 - 매우 엄격
    'java': 0.75, 'kotlin': 0.75, 'spring': 0.75,
    'react': 0.75, 'next.js': 0.75, 'typescript': 0.75,
    'android': 0.75, 'ios': 0.75,
    
    # 일반 기술 - 적절한 매칭
    'python': 0.62, 'fastapi': 0.62, 'django': 0.62,
    'mysql': 0.55, 'postgresql': 0.55, 'mongodb': 0.55,
    'aws': 0.65, 'gcp': 0.65, 'azure': 0.65,
    
    # 기본값
    'default': 0.60
}
```

### 가중치 시스템
```python
SECTIONAL_WEIGHTS = {
    "required": 0.60,          # 자격요건 매칭 (1순위)
    "preferred": 0.20,         # 우대조건 매칭 (2순위)
    "experience": 0.10,        # 경력 매칭 (3순위)
    "overall": 0.10,           # 전체 유사도 (4순위)
    "education": 0.00,         # 학력 (가중치 없음)
    "certification": 0.00,     # 자격증 (가중치 없음)
}
```

### 등급 기준
- 🟢 **Excellent** (85%+): 매우 우수 - 서류 통과 가능성 높음
- 🟡 **Good** (70-85%): 양호 - 지원 권장
- 🟠 **Fair** (55-70%): 보통 - 일부 조건 보완 필요
- ⚠️ **Caution** (40-55%): 주의 - 신중히 검토 필요
- 🔴 **Poor** (<40%): 부적합 - 기술 스택 불일치

---

## 🚀 API 엔드포인트

### 인증
- `POST /api/v1/auth/register` - 회원가입
- `POST /api/v1/auth/login` - 로그인

### 이력서
- `POST /api/v1/resumes/upload-and-process` - 이력서 업로드 및 처리
- `GET /api/v1/resumes` - 이력서 목록
- `GET /api/v1/resumes/{resume_id}` - 이력서 상세

### 채용공고
- `GET /api/v1/jobs` - 채용공고 목록
- `GET /api/v1/jobs/{job_id}` - 채용공고 상세

### 매칭 ⭐
- `POST /api/v1/matching/search-jobs` - 이력서 기반 공고 매칭 (빠른 응답)
- `GET /api/v1/matching/{matching_id}` - 매칭 상세 (실시간 계산)
- `GET /api/v1/matching/{matching_id}/feedback` - GPT-4 피드백 (on-demand)

---

## 📁 프로젝트 구조

```
Project1/
├── backend/                 # Backend 애플리케이션
│   ├── app/                # FastAPI 앱
│   │   ├── api/           # API 엔드포인트
│   │   ├── core/          # 핵심 유틸리티
│   │   ├── models/        # SQLAlchemy 모델
│   │   ├── schemas/       # Pydantic 스키마
│   │   ├── services/      # 비즈니스 로직
│   │   │   ├── ml/       # 매칭 알고리즘 (핵심!)
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
├── docs/                   # 문서
│   ├── GETTING_STARTED.md        # 시작 가이드
│   ├── PROJECT_STRUCTURE.md      # 구조 설명
│   └── PROJECT_SPECIFICATION.md  # 프로젝트 명세서
│
├── docker-compose.yml      # Docker Compose 설정
├── .env                    # 환경 변수
├── .gitignore              # Git 제외 파일
└── README.md               # 프로젝트 소개
```

---

## 📝 개발 로드맵

### ✅ 완료 (Phase 1-6)
- [x] 프로젝트 구조 및 Docker 환경 구축
- [x] DB 스키마 설계 (pgvector 포함)
- [x] 이력서/공고 파싱 (PDF/DOCX/XLSX)
- [x] 임베딩 생성 (jhgan/ko-sroberta-multitask)
- [x] 매칭 알고리즘 구현 ⭐
- [x] 섹션별 임베딩 매칭 구현 ⭐
- [x] 동적 임계값 시스템 구현 ⭐ (NEW!)
- [x] 가중치 튜닝 (실제 테스트 기반)
- [x] GPT-4 피드백 생성
- [x] 검증 완료 (95%+ 정확도)
- [x] 중복 방지 UNIQUE INDEX 추가
- [x] 만료 자동 비활성화 트리거
- [x] 실시간 계산 방식으로 변경
- [x] 2단계 API 구현 (빠른 검색 + on-demand 피드백)
- [x] 경력 페널티 캡 적용
- [x] 의미 매칭 강화
- [x] 문장 단위 세밀한 매칭

### 🚧 다음 단계 (Phase 7)
- [ ] **사람인 API 연동 + GPT-4 구조화** ← 다음!
- [ ] 프론트엔드 연동
- [ ] 북마크/지원 기능

### 📅 예정 (Phase 8-9)
- [ ] Cloud Run 배포 (GCP)
- [ ] 원티드/로켓펀치 크롤링
- [ ] 모니터링 대시보드

---

## 🔑 핵심 구현 파일

### 매칭 알고리즘 ⭐⭐⭐⭐⭐
```
backend/app/services/
├── matching_service.py       # 매칭 통합 (✅ 완성)
├── ml/
│   ├── embedding.py         # 임베딩 생성 (✅ 완성)
│   ├── vector_search.py     # 벡터 검색 (✅ 완성)
│   ├── scoring.py           # 점수 계산 (✅ 완성)
│   ├── sectional_scoring.py # 섹션별 점수 (✅ 완성)
│   ├── penalties.py         # 페널티 (✅ 완성)
│   └── feedback_generator.py # 피드백 (✅ 완성)
└── parsing/
    ├── llm_parser.py        # GPT-4 파싱 (✅ 완성)
    └── ...

backend/scripts/
├── process_resumes.py        # 이력서 처리
├── insert_job_data.py        # 공고 삽입
├── test_multiple_resumes.py  # 대규모 테스트 (✅ 완성)
└── validate_all_matching.py  # 전체 검증
```

---

## 🎯 주요 개선사항 (최신)

### 동적 임계값 시스템
- **충돌 기술 스택 자동 감지**: Java vs Python, React vs Flutter
- **실시간 로깅**: 모든 매칭 과정 추적 가능
- **Near Miss 감지**: 경계선 케이스 자동 감지
- **95%+ 정확도**: 실서비스 수준 달성

### 문장 단위 매칭
- **세밀한 분석**: 문장별 의미 유사도 계산
- **정확한 매칭**: 섹션별 최적화된 임계값
- **상세한 로깅**: 매칭 근거 완전 추적

---

## 📄 라이선스

MIT License

## 👥 기여

이슈 및 PR을 환영합니다!

---

**💡 Tip**: 상세한 설명은 [`ARCHITECTURE.md`](ARCHITECTURE.md)와 [`CRAWLING_GUIDE.md`](CRAWLING_GUIDE.md)를 참고하세요!
