"""
Feedback Models
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, ARRAY, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class LLMFeedback(Base):
    __tablename__ = "llm_feedback"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matching_result_id = Column(UUID(as_uuid=True), ForeignKey("matching_result.id", ondelete="CASCADE"), index=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_posting.id", ondelete="CASCADE"), index=True)
    
    # Feedback Content
    feedback_json = Column(JSONB, nullable=False)
    """
    {
        "overall_analysis": {
            "strengths": [...],
            "weaknesses": [...],
            "overall_comment": "...",
            "match_level": "높음"
        },
        "category_analysis": {
            "technical_skills": {...},
            "experience": {...}
        },
        "recommendations": [...]
    }
    """
    
    # Meta Info
    llm_model = Column(String(100))  # gpt-3.5-turbo, gpt-4
    token_count = Column(Integer)
    generation_time_ms = Column(Integer)
    is_helpful = Column(Boolean)  # 사용자 피드백
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    matching_result = relationship("MatchingResult", back_populates="llm_feedback")
    resume = relationship("Resume", back_populates="llm_feedbacks")
    job = relationship("JobPosting", back_populates="llm_feedbacks")


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), index=True)
    matching_result_id = Column(UUID(as_uuid=True), ForeignKey("matching_result.id", ondelete="SET NULL"), index=True)
    
    # Feedback Type
    feedback_type = Column(String(50), index=True)  # rating, report, suggestion
    
    # Rating (1-5)
    rating = Column(Integer, CheckConstraint("rating >= 1 AND rating <= 5"), index=True)
    
    # Details
    comment = Column(Text)
    tags = Column(ARRAY(Text))  # helpful, not_relevant, accurate, inaccurate
    
    # Meta Info
    is_resolved = Column(Boolean, default=False)
    admin_response = Column(Text)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="feedbacks")
    matching_result = relationship("MatchingResult", back_populates="user_feedbacks")

