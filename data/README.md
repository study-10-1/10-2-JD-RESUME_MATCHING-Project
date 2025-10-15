# 📁 데이터 폴더

이 폴더는 Auto-Match 시스템에서 사용할 실제 데이터를 저장하는 곳입니다.

## 📂 폴더 구조

```
data/
├── README.md              # 이 파일
├── resumes/              # 이력서 데이터
│   ├── README.md         # 이력서 가이드
│   ├── resume_1.pdf      # 이력서 파일들
│   ├── resume_2.docx
│   └── ...
└── jobs/                 # 채용공고 데이터
    ├── README.md         # 채용공고 가이드
    ├── job_data_template.json  # 입력 양식
    ├── job_data_1.json   # 채용공고 데이터들
    └── ...
```

## 🎯 사용 목적

### 이력서 데이터 (`resumes/`)
- **PDF/DOCX/XLSX** 이력서 파일 저장
- 자동으로 텍스트 추출 및 파싱
- 임베딩 생성 및 DB 저장

### 채용공고 데이터 (`jobs/`)
- **JSON** 형식으로 채용공고 정보 저장
- 구조화된 데이터로 매칭 정확도 향상
- 다양한 사이트에서 수집한 공고 통합

## 🚀 데이터 준비 과정

### 1단계: 이력서 준비
```bash
# 이력서 파일들을 resumes/ 폴더에 복사
cp ~/Downloads/resume.pdf data/resumes/resume_1.pdf
cp ~/Downloads/resume.docx data/resumes/resume_2.docx
```

### 2단계: 채용공고 준비
```bash
# 템플릿 복사
cp data/jobs/job_data_template.json data/jobs/job_data_1.json

# 실제 공고 정보로 수정
# (원티드, 잡코리아 등에서 수집)
```

### 3단계: 데이터 처리
```bash
# Backend 컨테이너 접속
docker-compose exec backend bash

# 이력서 처리
python scripts/process_resumes.py

# 채용공고 처리
python scripts/insert_job_data.py
```

## 📊 권장 데이터 개수

### 개발/테스트 단계
- **이력서**: 5-10개
- **채용공고**: 10-20개

### 알고리즘 튜닝 단계
- **이력서**: 20-50개
- **채용공고**: 50-100개

### 운영 단계
- **이력서**: 100+ 개
- **채용공고**: 1000+ 개

## 🔒 개인정보 보호

### 이력서 데이터
- 실제 개인정보가 포함된 파일
- 로컬 개발 환경에서만 사용
- Git에 업로드하지 않음 (`.gitignore`에 추가됨)

### 채용공고 데이터
- 공개된 채용공고 정보
- 회사명, 직무명 등 공개 정보만 포함
- 개인정보 없음

## 📝 데이터 품질 가이드

### 좋은 이력서 파일
- ✅ 텍스트가 명확하게 읽힘
- ✅ 구조화된 정보 (표, 목록)
- ✅ 기술 스킬이 명시됨
- ✅ 경력 정보가 상세함

### 좋은 채용공고 데이터
- ✅ 직무명이 명확함
- ✅ 전체 공고 텍스트 포함
- ✅ 경력/학력 조건 명시
- ✅ 기술 스택 정보 포함

## 🛠️ 문제 해결

### 이력서 파싱 오류
```bash
# 로그 확인
docker-compose logs -f backend

# 수동 처리
python scripts/debug_resume.py data/resumes/resume_1.pdf
```

### 채용공고 JSON 오류
```bash
# JSON 검증
python -m json.tool data/jobs/job_data_1.json
```

## 📈 성능 최적화

### 대용량 데이터 처리
- 배치 처리로 메모리 사용량 최적화
- 임베딩 생성은 GPU 활용
- 병렬 처리로 속도 향상

### 데이터 정제
- 중복 데이터 제거
- 품질 낮은 데이터 필터링
- 정규화 및 표준화

---

**💡 Tip**: 처음에는 소량의 데이터로 시작해서 알고리즘이 잘 작동하는지 확인한 후, 점진적으로 데이터를 늘려가세요!
