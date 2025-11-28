"""
Step 5: DB 저장 - 구조화된 데이터를 데이터베이스에 저장
"""
from sqlalchemy.orm import Session
from typing import Dict, Optional
from uuid import UUID
from datetime import datetime, date

from app.models.job import JobPosting
from app.models.company import Company
from app.models.sentences import JobSentence
from app.services.ml.embedding import EmbeddingService
from app.services.indexing.sentence_indexer import SentenceIndexer


class JobSaver:
    """구조화된 채용공고 데이터를 DB에 저장"""
    
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()
        self.sentence_indexer = SentenceIndexer(db)
    
    def save(self, structured_data: Dict, company_id: Optional[UUID] = None) -> Optional[UUID]:
        """
        구조화된 데이터를 DB에 저장합니다.
        
        Returns:
            저장된 JobPosting의 ID (실패 시 None)
        """
        try:
            url = structured_data['meta']['url']
            source = structured_data['meta']['source']
            external_id = self._extract_external_id(url)
            
            # 중복 체크
            existing = self.db.query(JobPosting).filter(
                JobPosting.source == source,
                JobPosting.external_id == external_id
            ).first()
            
            if existing:
                # 업데이트
                print(f"  🔄 기존 공고 업데이트: {existing.id}")
                return self._update_job(existing, structured_data, company_id)
            else:
                # 신규 생성
                print(f"  ➕ 새 공고 생성")
                return self._create_job(structured_data, company_id, source, external_id, url)
                
        except Exception as e:
            print(f"  ❌ 저장 실패: {str(e)}")
            return None
    
    def _extract_external_id(self, url: str) -> Optional[str]:
        """URL에서 외부 ID 추출"""
        from urllib.parse import urlparse, parse_qs
        
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            # work24.go.kr의 경우 wantedAuthNo 또는 seqNo 사용
            if 'wantedAuthNo' in query_params:
                return query_params['wantedAuthNo'][0]
            elif 'seqNo' in query_params:
                return query_params['seqNo'][0]
            
            # 다른 소스의 경우 URL의 마지막 부분을 ID로 사용
            parts = url.rstrip('/').split('/')
            if parts:
                last_part = parts[-1]
                # 쿼리 파라미터가 포함된 경우 제거
                if '?' in last_part:
                    last_part = last_part.split('?')[0]
                if last_part:
                    return last_part
            
            return None
        except Exception as e:
            from app.core.logging import logger
            logger.warning(f"External ID extraction failed: {e}")
            return None
    
    def _create_job(self, data: Dict, company_id: Optional[UUID], 
                    source: str, external_id: Optional[str], url: str) -> UUID:
        """새 공고 생성"""
        # 날짜 파싱
        posted_at = self._parse_date(data['meta'].get('registered_date'))
        expires_at = self._parse_date(data['meta'].get('closing_date'))
        
        # 메타 정보에서 company_name, location, experience_level, company_website 추출
        meta = data.get('meta', {})
        company_name = meta.get('company_name')
        company_website = meta.get('company_website')
        location = meta.get('location')
        experience_level = meta.get('experience_level')
        
        # 회사 정보가 있으면 Company 레코드 생성/조회
        if company_name and not company_id:
            company_id = self._get_or_create_company(company_name, company_website)
        
        job = JobPosting(
            company_id=company_id,
            title=data['title'],
            description=data['description'],
            raw_text=data['raw_text'],
            requirements=data['requirements'],
            responsibilities=data.get('responsibilities', []),
            qualifications=data.get('qualifications', []),
            benefits=data.get('benefits', []),
            location=location,
            experience_level=experience_level,
            source=source,
            external_id=external_id,
            external_url=url,
            posted_at=posted_at,
            expires_at=expires_at,
            is_active=True
        )
        
        self.db.add(job)
        self.db.flush()  # ID 생성
        
        # 임베딩 생성 (비동기로 처리 가능)
        try:
            # 전체 텍스트 임베딩
            job.embedding = self.embedding_service.generate_embedding(data['raw_text'])
            
            # 문장 단위 임베딩 (required, preferred)
            self.sentence_indexer.index_job(job)
            
        except Exception as e:
            print(f"  ⚠️ 임베딩 생성 실패 (나중에 재시도 가능): {str(e)}")
        
        self.db.commit()
        return job.id
    
    def _update_job(self, job: JobPosting, data: Dict, company_id: Optional[UUID]) -> UUID:
        """기존 공고 업데이트"""
        job.title = data['title']
        job.description = data['description']
        job.raw_text = data['raw_text']
        job.requirements = data['requirements']
        job.updated_at = datetime.now()  # 업데이트 시간 갱신
        job.responsibilities = data.get('responsibilities', [])
        job.qualifications = data.get('qualifications', [])
        job.benefits = data.get('benefits', [])
        
        # 메타 정보 업데이트
        meta = data.get('meta', {})
        if meta.get('location'):
            job.location = meta.get('location')
        if meta.get('experience_level'):
            job.experience_level = meta.get('experience_level')
        
        # URL 업데이트 (메타 정보에서)
        if meta.get('url'):
            job.external_url = meta.get('url')
        
        # 회사 정보 업데이트 (기존에 없으면 추가)
        company_name = meta.get('company_name')
        company_website = meta.get('company_website')
        if company_name:
            # company_id가 없거나 회사명이 변경된 경우
            if not job.company_id or (job.company and job.company.name != company_name):
                new_company_id = self._get_or_create_company(company_name, company_website)
                if new_company_id:
                    company_id = new_company_id
        
        if company_id:
            job.company_id = company_id
        
        # 임베딩도 업데이트 (선택적)
        try:
            job.embedding = self.embedding_service.generate_embedding(data['raw_text'])
            # 문장 단위 임베딩은 기존 것 삭제 후 재생성
            self.db.query(JobSentence).filter(JobSentence.job_id == job.id).delete()
            self.sentence_indexer.index_job(job)
        except Exception as e:
            print(f"  ⚠️ 임베딩 업데이트 실패: {str(e)}")
        
        self.db.commit()
        return job.id
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """날짜 문자열을 date 객체로 변환"""
        if not date_str:
            return None
        
        try:
            # 다양한 형식 시도
            formats = ['%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S']
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.date()
                except ValueError:
                    continue
            return None
        except Exception:
            return None
    
    def _get_or_create_company(self, company_name: str, company_website: Optional[str] = None) -> Optional[UUID]:
        """회사명으로 Company 레코드를 조회하거나 생성"""
        if not company_name:
            return None
        
        try:
            # 기존 회사 조회
            existing = self.db.query(Company).filter(
                Company.name == company_name
            ).first()
            
            if existing:
                # 웹사이트가 있고 기존에 없으면 업데이트
                if company_website and not existing.website:
                    existing.website = company_website
                    self.db.flush()
                return existing.id
            
            # 새 회사 생성
            new_company = Company(
                name=company_name,
                website=company_website
            )
            self.db.add(new_company)
            self.db.flush()
            return new_company.id
            
        except Exception as e:
            from app.core.logging import logger
            logger.warning(f"Company creation failed: {e}")
            return None

