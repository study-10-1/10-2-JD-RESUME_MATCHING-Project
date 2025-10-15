"""
Resume Repository - 이력서 데이터 액세스
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.models.resume import Resume


class ResumeRepository:
    """이력서 데이터 액세스 레이어"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, resume: Resume) -> Resume:
        """이력서 생성"""
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        return resume
    
    def get_by_id(self, resume_id: UUID) -> Optional[Resume]:
        """이력서 ID로 조회"""
        return self.db.query(Resume).filter(Resume.id == resume_id).first()
    
    def get_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20
    ) -> List[Resume]:
        """사용자의 이력서 목록 조회"""
        return self.db.query(Resume).filter(
            Resume.user_id == user_id
        ).order_by(
            Resume.created_at.desc()
        ).offset(skip).limit(limit).all()
    
    def update(self, resume: Resume) -> Resume:
        """이력서 업데이트"""
        self.db.commit()
        self.db.refresh(resume)
        return resume
    
    def delete(self, resume_id: UUID) -> bool:
        """이력서 삭제"""
        resume = self.get_by_id(resume_id)
        if resume:
            self.db.delete(resume)
            self.db.commit()
            return True
        return False
