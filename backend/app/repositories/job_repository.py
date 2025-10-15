"""
Job Repository - 채용공고 데이터 액세스
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional, Dict, Any
from uuid import UUID

from app.models.job import JobPosting


class JobRepository:
    """채용공고 데이터 액세스 레이어"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, job: JobPosting) -> JobPosting:
        """채용공고 생성"""
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def get_by_id(self, job_id: UUID) -> Optional[JobPosting]:
        """채용공고 ID로 조회"""
        return self.db.query(JobPosting).filter(JobPosting.id == job_id).first()
    
    def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[JobPosting]:
        """채용공고 목록 조회 (필터 적용)"""
        query = self.db.query(JobPosting)
        
        # 기본적으로 활성화된 공고만
        query = query.filter(JobPosting.is_active == True)
        
        # 필터 적용
        if filters:
            if filters.get("location"):
                query = query.filter(JobPosting.location.ilike(f"%{filters['location']}%"))
            
            if filters.get("experience_level"):
                query = query.filter(JobPosting.experience_level == filters["experience_level"])
            
            if filters.get("employment_type"):
                query = query.filter(JobPosting.employment_type == filters["employment_type"])
            
            if filters.get("search"):
                search_term = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        JobPosting.title.ilike(search_term),
                        JobPosting.description.ilike(search_term)
                    )
                )
        
        # 정렬 및 페이징
        query = query.order_by(JobPosting.posted_at.desc())
        
        return query.offset(skip).limit(limit).all()
    
    def update(self, job: JobPosting) -> JobPosting:
        """채용공고 업데이트"""
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def delete(self, job_id: UUID) -> bool:
        """채용공고 삭제"""
        job = self.get_by_id(job_id)
        if job:
            self.db.delete(job)
            self.db.commit()
            return True
        return False
