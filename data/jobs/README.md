# 채용공고 데이터

## 📁 폴더 구조

```
data/jobs/
├── README.md                    # 이 파일
├── job_data_template.json      # 채용공고 입력 양식
├── job_data_1.json            # 실제 채용공고 데이터 1
├── job_data_2.json            # 실제 채용공고 데이터 2
└── ...                        # 추가 채용공고 데이터
```

## 📝 사용 방법

### 1. 양식 복사
```bash
# 템플릿을 복사해서 새 파일 생성
cp job_data_template.json job_data_1.json
```

### 2. 데이터 입력
`job_data_1.json` 파일을 열어서 실제 채용공고 정보로 수정하세요.

### 3. 필수 필드 확인
- ✅ `company.name` - 회사명
- ✅ `job_posting.title` - 직무명
- ✅ `job_posting.raw_text` - 전체 공고 텍스트
- ✅ `job_posting.experience_level` - 경력 수준
- ✅ `job_posting.location` - 근무지역

### 4. 선택 필드
- `salary_min/max` - 연봉 정보 (없으면 null)
- `requirements` - 필수/우대 조건
- `responsibilities` - 주요 업무
- `benefits` - 복리후생

## 🎯 매칭에 중요한 정보

### ⭐⭐⭐ 최우선
- **`title`** - 직무명 (매칭 핵심)
- **`raw_text`** - 전체 텍스트 (임베딩용)
- **`experience_level`** - 경력 수준
- **`min_experience_years`** - 최소 경력

### ⭐⭐ 중요
- **`requirements.required`** - 필수 조건
- **`responsibilities`** - 업무 내용
- **`location`** - 근무지역

## 📋 데이터 수집 팁

### 원티드에서 수집할 때
1. **직무명** - 정확한 직무명 복사
2. **전체 공고** - 모든 텍스트 복사 (raw_text)
3. **조건** - 경력, 학력, 연봉 정보
4. **기술 스택** - 사용 기술들
5. **업무 내용** - 주요 업무 설명

### 잡코리아/사람인에서 수집할 때
1. **기본 정보** - 직무명, 회사명, 지역
2. **상세 조건** - 경력, 학력, 연봉
3. **업무 내용** - 담당 업무
4. **자격 요건** - 필수/우대 조건

## 🔄 DB 삽입 방법

데이터를 준비한 후:

```bash
# Backend 컨테이너 접속
docker-compose exec backend bash

# 데이터 삽입 스크립트 실행
python scripts/insert_job_data.py
```

## 📊 예상 데이터 개수

- **테스트용**: 10-20개 공고
- **개발용**: 50-100개 공고  
- **운영용**: 1000+ 공고

## 💡 추천 수집 사이트

1. **원티드** - 개발자 직무 많음, 정보 정리 잘됨
2. **잡코리아** - 다양한 직무, 상세 정보
3. **사람인** - 전통적인 구직 사이트
4. **로켓펀치** - 스타트업 중심
5. **프로그래머스** - 개발자 전용

---

**💡 Tip**: 처음에는 10-20개 정도만 수집해서 매칭 알고리즘을 테스트해보세요!
