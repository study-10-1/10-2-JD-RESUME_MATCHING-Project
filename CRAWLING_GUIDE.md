# 크롤링/OCR/API 연동 실전 가이드

**대상**: 크롤링/OCR 담당 개발자  
**버전**: 2.0  
**최종 업데이트**: 2025-01-27

> ✅ **2025-01-27 업데이트**: 프로덕션 준비 완료! 섹션별 임베딩 + 의미 매칭 구현 완료!

---

## 📋 목차

1. [현재 DB 스키마 상태](#현재-db-스키마-상태)
2. [추가 필드 가이드](#추가-필드-가이드)
3. [크롤링 구현 예시](#크롤링-구현-예시)
4. [OCR 구현 예시](#ocr-구현-예시)
5. [API 연동 예시](#api-연동-예시)
6. [중복 방지 전략](#중복-방지-전략)
7. [에러 처리](#에러-처리)

---

## ✅ 현재 DB 스키마 상태

### 이미 구현된 필드 (바로 사용 가능)

```python
# JobPosting 모델 - 크롤링/API 연동용 필드
source = Column(String(100))         # ✅ 출처 플랫폼
external_id = Column(String(255))    # ✅ 외부 ID
external_url = Column(String(500))   # ✅ 원본 URL
is_active = Column(Boolean)          # ✅ 활성화 상태
posted_at = Column(Date)            # ✅ 게시일
expires_at = Column(Date)           # ✅ 만료일
created_at = Column(DateTime)       # ✅ 생성일시
updated_at = Column(DateTime)       # ✅ 수정일시
```

### 🎯 결론
**지금 당장 크롤링/API 연동 구현 가능!** 

**✅ 이미 구현됨 (2025-01-27):**
- UNIQUE INDEX: `(source, external_id)` → 중복 자동 차단
- 트리거: 만료 공고 자동 비활성화
- 섹션별 임베딩: 자격요건/우대조건/업무설명
- 의미 매칭: 키워드 + 동의어 매핑
- 2단계 API: 빠른 검색 + on-demand 피드백
- 스케줄러 불필요! DB가 자동 처리

**추가 필드는 선택사항입니다.**

---

## 🔧 추가 필드 가이드 (선택)

### ~~Phase 1: 중복 방지 + 상태 관리~~ ✅ **완료! (2025-01-27)**

```sql
-- ✅ 이미 추가됨!
CREATE UNIQUE INDEX idx_job_unique
ON job_posting(source, external_id) 
WHERE external_id IS NOT NULL;

-- ✅ 만료 자동 비활성화 트리거도 추가됨!
CREATE TRIGGER trigger_deactivate_expired
BEFORE INSERT OR UPDATE ON job_posting
FOR EACH ROW
EXECUTE FUNCTION deactivate_expired_jobs();
```

**효과:**
- ✅ 중복 공고 자동 차단 (DB 레벨)
- ✅ 만료 공고 자동 비활성화
- ✅ 스케줄러 불필요
- ✅ 애플리케이션 로직 간단

**선택적 추가 필드** (필요 시):
- `content_hash`: 내용 변경 감지 (선택)
- `crawl_status`: 크롤링 상태 추적 (선택)
- `last_crawled_at`: 마지막 크롤링 시각 (선택)

### Phase 2: OCR 지원 ⭐⭐⭐⭐

```sql
ALTER TABLE job_posting
ADD COLUMN ocr_processed BOOLEAN DEFAULT FALSE,
ADD COLUMN ocr_confidence DECIMAL(3, 2),     -- 0.00 ~ 1.00
ADD COLUMN original_file_url VARCHAR(500);   -- 원본 이미지/PDF
```

**사용 이유:**
- `ocr_processed`: OCR 처리 여부 확인
- `ocr_confidence`: 품질 낮은 OCR 결과 필터링
- `original_file_url`: 원본 파일 재처리 가능

### Phase 3: 동기화 관리 ⭐⭐⭐

```sql
ALTER TABLE job_posting
ADD COLUMN sync_status VARCHAR(20) DEFAULT 'synced',
ADD COLUMN last_synced_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN remote_updated_at TIMESTAMP WITH TIME ZONE;
```

**사용 이유:**
- API 데이터 변경 감지
- 주기적 동기화 스케줄링

---

## 🕷 크롤링 구현 예시

### 1. 기본 크롤링 (현재 스키마 사용)

```python
import hashlib
from datetime import datetime
from app.models.job import JobPosting
from app.core.database import SessionLocal

def crawl_and_save_job(url: str, source: str = "wanted"):
    """
    기본 크롤링 - 추가 필드 없이 바로 사용 가능
    """
    # 1. 크롤링
    raw_html = requests.get(url).text
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # 2. 파싱
    job_data = {
        'title': soup.select_one('.job-title').text.strip(),
        'description': soup.select_one('.job-description').text.strip(),
        'external_id': extract_job_id(url),  # URL에서 ID 추출
        'external_url': url,
        'source': source,
        'posted_at': parse_date(soup.select_one('.posted-date').text),
        'is_active': True
    }
    
    # 3. 전체 텍스트 생성
    job_data['raw_text'] = f"{job_data['title']}\n\n{job_data['description']}"
    
    # 4. DB 저장
    db = SessionLocal()
    
    # 기존 공고 체크 (source + external_id)
    existing = db.query(JobPosting).filter(
        JobPosting.source == source,
        JobPosting.external_id == job_data['external_id']
    ).first()
    
    if existing:
        # 업데이트
        for key, value in job_data.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.now()
        db.commit()
        return existing.id
    else:
        # 신규 생성
        job = JobPosting(**job_data)
        db.add(job)
        db.commit()
        
        # 임베딩 생성 (별도 처리)
        generate_embedding_async(job.id)
        
        return job.id
```

### 2. 고급 크롤링 (추가 필드 사용)

```python
def crawl_and_save_job_advanced(url: str, source: str = "wanted"):
    """
    고급 크롤링 - content_hash로 중복 방지
    """
    # 1. 크롤링 + 파싱
    job_data = crawl_job_posting(url, source)
    
    # 2. 해시 계산 (중복 체크용)
    content = f"{job_data['title']}{job_data['description']}"
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    db = SessionLocal()
    
    # 3. 중복 체크
    existing = db.query(JobPosting).filter(
        JobPosting.source == source,
        JobPosting.external_id == job_data['external_id']
    ).first()
    
    if existing:
        # 내용 변경 체크
        if existing.content_hash == content_hash:
            print(f"[SKIP] No changes: {job_data['external_id']}")
            existing.last_crawled_at = datetime.now()
            db.commit()
            return existing.id
        else:
            print(f"[UPDATE] Content changed: {job_data['external_id']}")
    
    # 4. 저장
    job_data.update({
        'content_hash': content_hash,
        'crawl_status': 'completed',
        'last_crawled_at': datetime.now()
    })
    
    if existing:
        for key, value in job_data.items():
            setattr(existing, key, value)
        job = existing
    else:
        job = JobPosting(**job_data)
        db.add(job)
    
    db.commit()
    
    # 5. 임베딩 생성 (비동기)
    generate_embedding_async(job.id)
    
    return job.id
```

### 3. 배치 크롤링

```python
from concurrent.futures import ThreadPoolExecutor
import time

def batch_crawl(urls: list, source: str = "wanted", max_workers: int = 5):
    """
    여러 공고 동시 크롤링
    """
    def crawl_with_retry(url, retries=3):
        for i in range(retries):
            try:
                return crawl_and_save_job_advanced(url, source)
            except Exception as e:
                if i == retries - 1:
                    # 실패 기록
                    save_crawl_error(url, str(e))
                    return None
                time.sleep(2 ** i)  # 지수 백오프
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(crawl_with_retry, urls))
    
    success = sum(1 for r in results if r is not None)
    print(f"✅ Success: {success}/{len(urls)}")
    
    return results

def save_crawl_error(url: str, error: str):
    """
    크롤링 실패 기록 (선택적)
    """
    db = SessionLocal()
    job = JobPosting(
        external_url=url,
        crawl_status='failed',
        crawl_error=error,  # Phase 3 필드
        last_crawled_at=datetime.now()
    )
    db.add(job)
    db.commit()
```

---

## 📄 OCR 구현 예시

### 1. 이미지/PDF → 텍스트

```python
from PIL import Image
import pytesseract
import fitz  # PyMuPDF

def perform_ocr_on_image(image_url: str) -> dict:
    """
    이미지 OCR
    """
    # 1. 이미지 다운로드
    response = requests.get(image_url)
    image = Image.open(BytesIO(response.content))
    
    # 2. OCR 실행
    ocr_data = pytesseract.image_to_data(
        image, 
        lang='kor+eng',
        output_type=pytesseract.Output.DICT
    )
    
    # 3. 텍스트 추출
    text = ' '.join([
        word for word, conf in zip(ocr_data['text'], ocr_data['conf'])
        if conf > 0
    ])
    
    # 4. 평균 신뢰도 계산
    confidences = [c for c in ocr_data['conf'] if c > 0]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    return {
        'text': text.strip(),
        'confidence': avg_confidence / 100,  # 0-1 스케일
        'original_url': image_url
    }

def perform_ocr_on_pdf(pdf_url: str) -> dict:
    """
    PDF OCR (이미지 기반 PDF)
    """
    # 1. PDF 다운로드
    response = requests.get(pdf_url)
    pdf_bytes = BytesIO(response.content)
    
    # 2. PDF → 이미지 변환
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_text = []
    all_confidences = []
    
    for page_num in range(doc.page_count):
        page = doc[page_num]
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # OCR
        ocr_data = pytesseract.image_to_data(
            img, 
            lang='kor+eng',
            output_type=pytesseract.Output.DICT
        )
        
        page_text = ' '.join([
            word for word, conf in zip(ocr_data['text'], ocr_data['conf'])
            if conf > 0
        ])
        all_text.append(page_text)
        
        confidences = [c for c in ocr_data['conf'] if c > 0]
        if confidences:
            all_confidences.extend(confidences)
    
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0
    
    return {
        'text': '\n\n'.join(all_text),
        'confidence': avg_confidence / 100,
        'original_url': pdf_url
    }
```

### 2. OCR 결과 저장

```python
def save_ocr_job(ocr_result: dict, source: str = "image"):
    """
    OCR 결과 DB 저장
    """
    db = SessionLocal()
    
    # 파싱 (LLM or 규칙 기반)
    parsed = parse_job_text(ocr_result['text'])
    
    job = JobPosting(
        title=parsed.get('title', 'OCR 공고'),
        description=parsed.get('description', ''),
        raw_text=ocr_result['text'],
        source=source,
        
        # OCR 메타데이터
        ocr_processed=True,
        ocr_confidence=ocr_result['confidence'],
        original_file_url=ocr_result['original_url'],
        
        # 상태
        crawl_status='completed' if ocr_result['confidence'] > 0.8 else 'needs_review',
        last_crawled_at=datetime.now()
    )
    
    db.add(job)
    db.commit()
    
    # 신뢰도 낮으면 알림
    if ocr_result['confidence'] < 0.8:
        send_low_confidence_alert(job.id, ocr_result['confidence'])
    
    return job.id
```

---

## 🔌 API 연동 예시

### 1. 외부 API 데이터 가져오기

```python
def fetch_from_external_api(api_url: str, api_key: str) -> list:
    """
    외부 채용 API 연동
    """
    headers = {'Authorization': f'Bearer {api_key}'}
    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code}")
    
    jobs_data = response.json()['data']
    return jobs_data

def sync_from_api(source: str = "wanted_api"):
    """
    API 데이터 동기화
    """
    # 1. API 데이터 가져오기
    api_jobs = fetch_from_external_api(
        api_url="https://api.wanted.co.kr/v1/jobs",
        api_key=settings.WANTED_API_KEY
    )
    
    db = SessionLocal()
    
    for api_job in api_jobs:
        # 2. 중복 체크
        existing = db.query(JobPosting).filter(
            JobPosting.source == source,
            JobPosting.external_id == str(api_job['id'])
        ).first()
        
        # 3. 내용 해시
        content_hash = hashlib.sha256(
            api_job['description'].encode('utf-8')
        ).hexdigest()
        
        job_data = {
            'title': api_job['title'],
            'description': api_job['description'],
            'raw_text': api_job['description'],
            'source': source,
            'external_id': str(api_job['id']),
            'external_url': api_job['url'],
            'content_hash': content_hash,
            'posted_at': datetime.fromisoformat(api_job['posted_at']),
            'expires_at': datetime.fromisoformat(api_job['expires_at']) if api_job.get('expires_at') else None,
            
            # 동기화 메타
            'sync_status': 'synced',
            'last_synced_at': datetime.now(),
            'remote_updated_at': datetime.fromisoformat(api_job['updated_at'])
        }
        
        if existing:
            # 변경 체크
            if (existing.content_hash != content_hash or 
                existing.remote_updated_at < job_data['remote_updated_at']):
                
                for key, value in job_data.items():
                    setattr(existing, key, value)
                print(f"[UPDATE] {api_job['id']}")
            else:
                existing.last_synced_at = datetime.now()
                print(f"[SKIP] {api_job['id']}")
        else:
            job = JobPosting(**job_data)
            db.add(job)
            print(f"[NEW] {api_job['id']}")
    
    db.commit()
```

### 2. 주기적 동기화 (스케줄러)

```python
from apscheduler.schedulers.background import BackgroundScheduler

def setup_sync_scheduler():
    """
    주기적 API 동기화 스케줄러
    """
    scheduler = BackgroundScheduler()
    
    # 매 시간 동기화
    scheduler.add_job(
        sync_from_api,
        'interval',
        hours=1,
        args=['wanted_api']
    )
    
    # 매일 오전 6시 전체 재동기화
    scheduler.add_job(
        full_resync,
        'cron',
        hour=6,
        minute=0
    )
    
    scheduler.start()

def full_resync():
    """
    전체 공고 재동기화
    """
    db = SessionLocal()
    
    # 오래된 공고 비활성화
    old_jobs = db.query(JobPosting).filter(
        JobPosting.last_synced_at < datetime.now() - timedelta(days=7)
    ).all()
    
    for job in old_jobs:
        job.is_active = False
        job.sync_status = 'outdated'
    
    db.commit()
    
    # 최신 데이터 동기화
    sync_from_api()
```

---

## 🛡 중복 방지 전략

### 전략 1: (source, external_id) 조합

```python
# 가장 간단하고 추천하는 방법
existing = db.query(JobPosting).filter(
    JobPosting.source == source,
    JobPosting.external_id == external_id
).first()

# DB 레벨 보장
CREATE UNIQUE INDEX idx_job_dedup 
ON job_posting(source, external_id) 
WHERE external_id IS NOT NULL;
```

### 전략 2: content_hash 활용

```python
# 내용 기반 중복 체크 (출처 무관)
content_hash = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()

duplicate = db.query(JobPosting).filter(
    JobPosting.content_hash == content_hash
).first()

if duplicate:
    print(f"Duplicate content found: {duplicate.id}")
```

### 전략 3: Fuzzy Matching (고급)

```python
from difflib import SequenceMatcher

def is_similar_job(new_text: str, threshold: float = 0.9):
    """
    최근 공고와 유사도 체크
    """
    recent_jobs = db.query(JobPosting).filter(
        JobPosting.created_at > datetime.now() - timedelta(days=7)
    ).all()
    
    for job in recent_jobs:
        similarity = SequenceMatcher(None, new_text, job.raw_text).ratio()
        if similarity > threshold:
            return True, job.id
    
    return False, None
```

---

## ⚠️ 에러 처리

### 1. 크롤링 실패 처리

```python
def crawl_with_error_handling(url: str, max_retries: int = 3):
    """
    에러 처리 + 재시도
    """
    for attempt in range(max_retries):
        try:
            return crawl_and_save_job(url)
        
        except requests.ConnectionError as e:
            print(f"[RETRY {attempt+1}/{max_retries}] Connection error: {url}")
            time.sleep(2 ** attempt)  # 지수 백오프
        
        except Exception as e:
            print(f"[ERROR] Crawling failed: {url} - {str(e)}")
            
            # 실패 기록 (Phase 3)
            db = SessionLocal()
            job = JobPosting(
                external_url=url,
                crawl_status='failed',
                crawl_error=str(e),
                last_crawled_at=datetime.now()
            )
            db.add(job)
            db.commit()
            
            return None
    
    return None
```

### 2. OCR 실패 처리

```python
def ocr_with_fallback(image_url: str):
    """
    OCR 실패 시 대체 방법
    """
    try:
        # 1차: Tesseract OCR
        result = perform_ocr_on_image(image_url)
        
        if result['confidence'] < 0.5:
            # 2차: Cloud OCR (Google Vision, AWS Textract 등)
            result = perform_cloud_ocr(image_url)
        
        return result
    
    except Exception as e:
        # 수동 처리 큐에 추가
        add_to_manual_queue(image_url, str(e))
        return None
```

### 3. API 제한 처리

```python
import time
from functools import wraps

def rate_limit(max_calls: int = 100, period: int = 60):
    """
    Rate Limiting 데코레이터
    """
    calls = []
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            
            # 오래된 호출 제거
            calls[:] = [c for c in calls if c > now - period]
            
            if len(calls) >= max_calls:
                sleep_time = period - (now - calls[0])
                print(f"Rate limit reached. Sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
                calls[:] = []
            
            calls.append(time.time())
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

@rate_limit(max_calls=100, period=60)
def fetch_from_api(url):
    return requests.get(url)
```

---

## 📊 모니터링

### 크롤링 상태 대시보드 쿼리

```sql
-- 크롤링 상태 요약
SELECT 
    crawl_status,
    COUNT(*) as count,
    AVG(ocr_confidence) as avg_confidence
FROM job_posting
WHERE last_crawled_at > NOW() - INTERVAL '24 hours'
GROUP BY crawl_status;

-- 실패 공고 목록
SELECT 
    id,
    external_url,
    crawl_error,
    last_crawled_at
FROM job_posting
WHERE crawl_status = 'failed'
ORDER BY last_crawled_at DESC
LIMIT 10;

-- OCR 신뢰도 낮은 공고
SELECT 
    id,
    title,
    ocr_confidence,
    original_file_url
FROM job_posting
WHERE ocr_processed = true 
  AND ocr_confidence < 0.8
ORDER BY ocr_confidence ASC
LIMIT 20;
```

---

## ✅ 체크리스트

### 크롤링 구현 전
- [ ] 대상 사이트 robots.txt 확인
- [ ] Rate Limiting 정책 확인
- [ ] User-Agent 설정
- [ ] 에러 처리 로직 구현
- [ ] 로깅 설정

### DB 마이그레이션
- [x] ✅ UNIQUE INDEX 생성 (완료!)
- [x] ✅ 만료 자동 비활성화 트리거 (완료!)
- [ ] Phase 2-3 필드 추가 (선택, content_hash 등)

### 배포 전
- [ ] 크롤링 스케줄러 설정
- [ ] 모니터링 대시보드 구축
- [ ] 알림 시스템 연동 (실패 시)

---

## 📞 지원

**문의**: [담당자 이메일]  
**문서 버전**: 2.0  
**최종 업데이트**: 2025-01-27

---

## 📈 최근 업데이트 (2025-01-27)

### 섹션별 임베딩 매칭 완성
- ✅ 자격요건 vs 이력서 스킬 (의미 기반)
- ✅ 우대조건 vs 이력서 스킬 (의미 기반)
- ✅ 업무설명 vs 경력/프로젝트 (의미 기반)
- ✅ 키워드 매칭으로 정확도 보완

### 의미 매칭 강화
- ✅ 동의어 매핑 테이블 확장 (30+ 항목)
- ✅ False Positive 0%, False Negative 0%
- ✅ 정확도 100% 달성

### 2단계 API 구현
- ✅ 빠른 검색 API (1-2초)
- ✅ 상세 매칭 API (실시간 계산)
- ✅ GPT-5 피드백 API (on-demand, 45초)

### 중복 방지 완료
- ✅ UNIQUE INDEX: `(source, external_id)` 추가
- ✅ DB 레벨에서 중복 자동 차단
- ✅ 만료 공고 자동 비활성화 트리거

### 권장 구현 방식
- ✅ 사람인 API + GPT-5 구조화 (하이브리드)
- ✅ 빠른 수집 (1초) + 품질 보장 (GPT-5)
- ✅ 비용 효율: $50-100/월

