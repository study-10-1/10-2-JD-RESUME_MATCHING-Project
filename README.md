# Auto-Match: AI-based Resume & Job Matching System

한국어 특화 AI 기반 이력서-채용공고 자동 매칭 시스템

## 개요

Auto-Match는 의미 기반 임베딩과 동적 임계값 시스템을 활용하여 이력서와 채용공고를 정확하게 매칭하는 시스템입니다. 문장 단위 세밀한 분석을 통해 기술 스택, 경력, 자격요건 등을 종합적으로 평가합니다.

## 주요 기능

### 의미 기반 매칭
- Bi-encoder 임베딩 기반 코사인 유사도 계산
- 한국어 특화 모델 (jhgan/ko-sroberta-multitask, 768차원)
- 문장 단위 세밀한 매칭으로 정확도 향상
- 섹션별 임베딩 매칭 (자격요건, 우대조건, 업무설명)

### 동적 임계값 시스템
- 기술 스택별 세분화된 임계값 적용
- 충돌 기술 스택 자동 감지 및 차단
- 실시간 로깅 및 Near Miss 감지
- 테스트 데이터 기반 최적화

### 다차원 점수 계산
- 자격요건 매칭 (60% 가중치)
- 우대조건 매칭 (20% 가중치)
- 경력 매칭 (10% 가중치)
- 기술 스택 유사도 (10% 가중치)
- 경력 페널티 캡 적용 (최대 15점 감점)
- 감쇠(Dampening) 로직으로 엄격성 강화

### 상세 매칭 분석
- 자격요건/우대조건 개별 매칭 현황
- 기술 스택 추출 및 매칭 상태 표시
- 매칭 근거 및 개선 제안 제공
- 디버그 정보 포함

### 채용공고 크롤링
- 웹 크롤링을 통한 채용공고 자동 수집
- 스케줄러 기반 자동화 (매일 9시 실행)
- 만료된 공고 자동 삭제
- 중복 방지 메커니즘

### 파일 파싱
- PDF, DOCX, XLSX, HWP 형식 지원
- 모든 페이지/시트 자동 추출
- LLM 기반 구조화 파싱
- 기술 스택 자동 추출

## 기술 스택

### Backend
- FastAPI 0.104+
- Python 3.10+
- PostgreSQL 15 + pgvector
- Redis 7+ (선택사항)
- Docker + Docker Compose

### AI/ML
- Embedding: jhgan/ko-sroberta-multitask (768-dim)
- Vector Search: pgvector (Cosine Similarity, HNSW 인덱스)
- LLM: OpenAI GPT-4 (피드백 생성 및 구조화 파싱)

### 파일 파싱
- PDF: PyMuPDF
- DOCX: python-docx + LibreOffice 변환
- XLSX: openpyxl
- HWP: olefile

## 빠른 시작

### 환경 설정

```bash
# 프로젝트 클론
git clone <repository-url>
cd Project1

# 환경 변수 확인
cat .env
```

### Docker 컨테이너 시작

```bash
# 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f backend

# 서비스 상태 확인
docker-compose ps
```

### 데이터베이스 마이그레이션

```bash
# Backend 컨테이너 접속
docker-compose exec backend bash

# 마이그레이션 적용
alembic upgrade head
```

### API 접속

- Backend API: http://localhost:8000
- API 문서 (Swagger): http://localhost:8000/docs
- API 문서 (ReDoc): http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## 프로젝트 구조

```
Project1/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API 엔드포인트
│   │   │   ├── resumes.py   # 이력서 업로드/조회
│   │   │   ├── jobs.py      # 채용공고 조회
│   │   │   └── matching.py  # 매칭 검색/상세
│   │   ├── core/            # 핵심 유틸리티
│   │   │   ├── config.py    # 설정 관리
│   │   │   ├── database.py  # DB 연결
│   │   │   ├── logging.py   # 로깅 설정
│   │   │   └── cli/         # CLI 명령어
│   │   │       ├── job_crawler.py      # 크롤링
│   │   │       ├── cleanup_expired_jobs.py  # 만료 공고 삭제
│   │   │       └── scheduler.py        # 스케줄러
│   │   ├── models/          # SQLAlchemy 모델
│   │   ├── schemas/         # Pydantic 스키마
│   │   ├── services/        # 비즈니스 로직
│   │   │   ├── matching_service.py    # 매칭 통합 서비스
│   │   │   ├── ml/                    # ML 서비스
│   │   │   │   ├── embedding.py       # 임베딩 생성
│   │   │   │   ├── vector_search.py   # 벡터 검색
│   │   │   │   ├── scoring.py         # 점수 계산
│   │   │   │   ├── penalties.py       # 페널티 계산
│   │   │   │   └── feedback_generator.py  # 피드백 생성
│   │   │   ├── parsing/               # 파일 파싱
│   │   │   │   ├── pdf_parser.py
│   │   │   │   ├── docx_parser.py
│   │   │   │   ├── xlsx_parser.py
│   │   │   │   ├── hwp_parser.py
│   │   │   │   └── llm_parser.py
│   │   │   └── indexing/              # 문장 인덱싱
│   │   │       └── sentence_indexer.py
│   │   └── utils/            # 유틸리티
│   │       ├── job_scraper.py
│   │       ├── job_parser.py
│   │       ├── job_cleaner.py
│   │       ├── job_structurizer.py
│   │       └── job_saver.py
│   ├── alembic/              # DB 마이그레이션
│   └── scripts/              # 유틸리티 스크립트
├── docker-compose.yml
├── .env
└── README.md
```

## API 엔드포인트

### 이력서
- `POST /api/v1/resumes/upload-and-process` - 이력서 업로드 및 처리
- `GET /api/v1/resumes` - 이력서 목록
- `GET /api/v1/resumes/{resume_id}` - 이력서 상세

### 채용공고
- `GET /api/v1/jobs` - 채용공고 목록
- `GET /api/v1/jobs/{job_id}` - 채용공고 상세
- `POST /api/v1/jobs` - 채용공고 생성 (관리자)

### 매칭
- `POST /api/v1/matching/search-jobs` - 이력서 기반 공고 매칭
  - 요청: `{"resume_id": "uuid", "limit": 10}`
  - 응답: 점수, 등급, 매칭 근거, 기술 스택 정보 포함
- `GET /api/v1/matching/{matching_id}` - 매칭 상세
- `GET /api/v1/matching/{matching_id}/feedback` - GPT-4 피드백 (선택)

## 매칭 알고리즘

### 동적 임계값 시스템

기술 스택별로 세분화된 임계값을 적용하여 정확도를 향상시킵니다. 주요 기술 스택별 임계값은 실제 데이터 분석을 기반으로 최적화되었습니다.

```python
tech_thresholds = {
    'java': 0.56, 'kotlin': 0.55, 'spring': 0.56,
    'python': 0.56, 'fastapi': 0.56, 'django': 0.56,
    'react': 0.59, 'next.js': 0.59, 'typescript': 0.59,
    'mysql': 0.56, 'postgresql': 0.56, 'mongodb': 0.56,
    'aws': 0.59, 'gcp': 0.59, 'azure': 0.59,
    'docker': 0.58, 'kubernetes': 0.65,
    'general': 0.60
}
```

### 카테고리별 가중치

```python
WEIGHTS = {
    "required_match": 0.60,      # 자격요건 매칭
    "preferred_match": 0.20,     # 우대조건 매칭
    "experience_match": 0.10,    # 경력 매칭
    "skills_similarity": 0.10,   # 기술 스택 유사도
}
```

### 점수 계산 프로세스

1. 문장 단위 매칭: 공고의 각 조건 문장과 이력서의 모든 문장을 비교하여 최고 유사도 선택
2. 동적 임계값 적용: 기술 스택별 임계값 적용
3. 가중 합산: 각 카테고리 점수를 가중치로 합산
4. 감쇠 적용: 자격요건 매칭 실패 시 50% 감점
5. 페널티 적용: 경력 레벨 불일치, 핵심 스킬 부족 등에 대한 페널티
6. 최종 점수: 최종 점수 계산 및 등급 부여

### 등급 기준

- Excellent (85%+): 매우 우수
- Good (70-85%): 양호
- Fair (55-70%): 보통
- Caution (40-55%): 주의
- Poor (<40%): 부적합

## 채용공고 크롤링

### 스케줄러 설정

스케줄러는 매일 오전 9시에 자동으로 채용공고를 크롤링하고, 오전 9시 10분에 만료된 공고를 삭제합니다.

```bash
# 스케줄러 실행
docker compose exec backend python3 -m app.core.cli.scheduler

# 한 번만 실행 (테스트)
docker compose exec backend python3 -m app.core.cli.scheduler --run-once

# 만료된 공고만 삭제
docker compose exec backend python3 -m app.core.cli.scheduler --cleanup-only
```

### 환경 변수

`.env` 파일에 다음 변수를 설정합니다:

```env
CRAWLER_BASE_URL=https://www.work24.go.kr/...
CRAWLER_SOURCE=work24
CRAWLER_MAX_RETRIES=3
CRAWLER_RETRY_DELAY=5
```

## 파일 파싱

### 지원 형식

- PDF: PyMuPDF를 사용하여 모든 페이지 추출
- DOCX: LibreOffice를 통한 PDF 변환 후 파싱 (정확한 페이지 구조)
- XLSX: openpyxl을 사용하여 모든 시트 추출
- HWP: olefile을 사용한 텍스트 추출

### 파싱 결과

이력서 파싱 시 다음 정보를 추출합니다:

- 개인 정보: 이름, 전화번호, 이메일
- 요약: 이력서 전체 요약
- 경력 정보: 총 경력 연수, 경력 내역
- 학력 정보: 학교명, 학위, 전공, 졸업년도
- 기술 스택: 프로그래밍 언어, 프레임워크, 데이터베이스, 도구, 클라우드, AI/ML
- 자격증: 자격증 목록
- 언어 능력: 언어명, 숙련도
- 프로젝트: 프로젝트명, 기간, 설명, 기술 스택

## 성능

### 처리 속도
- 단일 공고 매칭: 약 0.1-0.5초 (임베딩 사전 생성 시)
- 전체 공고 매칭 (250개 기준): 약 1초 이내
- 벡터 검색: 약 0.01초 (pgvector HNSW)
- API 응답 시간: 0.5초 (250개 공고 기준)

### 최적화
- 섹션 임베딩 사전 생성 및 저장
- 문장 단위 임베딩 사전 생성 및 저장
- pgvector HNSW 인덱스 활용
- 로깅 레벨 최적화
- 효율적인 문장 단위 매칭 알고리즘

## 개발 가이드

### 개발 명령어

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

### 환경 변수

주요 환경 변수 (`.env` 파일):

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/auto_match

# JWT
JWT_SECRET_KEY=your-secret-key

# OpenAI
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o-mini

# Embedding
EMBEDDING_MODEL=jhgan/ko-sroberta-multitask
EMBEDDING_SERVICE_URL=http://embedding:8001

# Crawler
CRAWLER_BASE_URL=https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do?basicSetupYn=&careerTo=&keywordJobCd=&occupation=133100%2C133101&seqNo=&cloDateEndtParam=&payGbn=&templateInfo=&rot2WorkYn=&shsyWorkSecd=&resultCnt=10&keywordJobCont=&cert=&moreButtonYn=&minPay=&codeDepth2Info=11000&currentPageNo=1&eventNo=&mode=&major=&resrDutyExcYn=&eodwYn=&sortField=DATE&staArea=&sortOrderBy=DESC&keyword=&termSearchGbn=&carrEssYns=&benefitSrchAndOr=O&occupationParam=133100%2C133101&disableEmpHopeGbn=&actServExcYn=&keywordStaAreaNm=&maxPay=&emailApplyYn=&codeDepth1Info=11000&keywordEtcYn=&regDateStdtParam=&publDutyExcYn=&keywordJobCdSeqNo=&viewType=&exJobsCd=&templateDepthNmInfo=&region=&employGbn=&empTpGbcd=&computerPreferential=&infaYn=&cloDateStdtParam=&siteClcd=all&searchMode=Y&birthFromYY=&indArea=&careerTypes=&subEmpHopeYn=&tlmgYn=&academicGbn=&templateDepthNoInfo=&foriegn=&entryRoute=&mealOfferClcd=&basicSetupYnChk=&station=&holidayGbn=&srcKeyword=&academicGbnoEdu=noEdu&enterPriseGbn=&cloTermSearchGbn=&birthToYY=&keywordWantedTitle=&stationNm=&benefitGbn=&keywordFlag=&notSrcKeyword=&essCertChk=&depth2SelCode=&keywordBusiNm=&preferentialGbn=&rot3WorkYn=&regDateEndtParam=&pfMatterPreferential=&pageIndex=1&termContractMmcnt=&careerFrom=&laborHrShortYn=#scrollLoc
CRAWLER_SOURCE=work24
CRAWLER_MAX_RETRIES=3
CRAWLER_RETRY_DELAY=5
```

## 주요 개선사항

### 최근 업데이트

- 기술 스택 유사도 기반 매칭: 전체 유사도 대신 기술 스택 유사도 사용
- Experience 섹션 매칭: JobPosting.description을 문장 단위로 분석하여 경력 매칭 강화
- 기술 스택 정보 추출: 매칭 결과에 요구 기술 스택과 매칭된 기술 스택 표시
- Location 파싱 개선: 채용 인원 정보가 location에 포함되지 않도록 필터링
- 채용공고 크롤링 자동화: 스케줄러 기반 자동 크롭링 및 만료 공고 삭제
- 중복 방지: DB 레벨, 애플리케이션 레벨, 스케줄러 레벨의 3단계 중복 방지

## 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.
