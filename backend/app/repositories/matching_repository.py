"""
Matching Repository - 매칭 결과 데이터 액세스
"""
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.models.matching import MatchingResult, MatchingConfig


class MatchingRepository:
    """매칭 결과 데이터 액세스 레이어"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, matching_result: MatchingResult) -> MatchingResult:
        """매칭 결과 생성"""
        self.db.add(matching_result)
        self.db.commit()
        self.db.refresh(matching_result)
        return matching_result
    
    def get_by_id(self, matching_id: UUID) -> Optional[MatchingResult]:
        """매칭 결과 ID로 조회"""
        return self.db.query(MatchingResult).filter(
            MatchingResult.id == matching_id
        ).first()
    
    def get_by_job_and_resume(
        self,
        job_id: UUID,
        resume_id: UUID
    ) -> Optional[MatchingResult]:
        """특정 채용공고-이력서 매칭 결과 조회"""
        return self.db.query(MatchingResult).filter(
            MatchingResult.job_id == job_id,
            MatchingResult.resume_id == resume_id
        ).order_by(
            MatchingResult.created_at.desc()
        ).first()
    
    def get_active_config(self) -> Optional[MatchingConfig]:
        """활성화된 매칭 설정 조회"""
        return self.db.query(MatchingConfig).filter(
            MatchingConfig.is_active == True
        ).first()
