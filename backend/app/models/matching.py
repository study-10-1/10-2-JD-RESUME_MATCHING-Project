"""
Matching Models
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, DECIMAL
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class MatchingResult(Base):
    __tablename__ = "matching_result"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_posting.id", ondelete="CASCADE"), index=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resume.id", ondelete="CASCADE"), index=True)
    
    # Score Info
    overall_score = Column(DECIMAL(5, 4), nullable=False, index=True)  # 0.0000 ~ 1.0000
    grade = Column(String(50), index=True)  # excellent, good, fair, caution, poor
    
    # Category Scores
    category_scores = Column(JSONB, nullable=False)
    """
    {
        "technical_skills": {"score": 0.94, "weight": 0.5},
        "experience": {"score": 0.64, "weight": 0.3},
        "similarity": {"score": 0.56, "weight": 0.15},
        "education": {"score": 0.50, "weight": 0.03},
        "certification": {"score": 0.50, "weight": 0.01},
        "language": {"score": 0.50, "weight": 0.01}
    }
    """
    
    # Matching Evidence
    matching_evidence = Column(JSONB)
    """
    {
        "matched_skills": ["python", "django", "aws"],
        "missing_skills": ["kubernetes"],
        "experience_evidence": {...},
        "similarity_evidence": {...}
    }
    """
    
    # Penalties
    penalties = Column(JSONB)
    """
    {
        "experience_level_mismatch": -0.30,
        "domain_mismatch": -0.25
    }
    """
    
    # Meta Info
    algorithm_version = Column(String(50))
    calculation_time_ms = Column(Integer)
    is_viewed = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job = relationship("JobPosting", back_populates="matching_results")
    resume = relationship("Resume", back_populates="matching_results")
    llm_feedback = relationship("LLMFeedback", back_populates="matching_result", uselist=False)
    user_feedbacks = relationship("UserFeedback", back_populates="matching_result")


class MatchingConfig(Base):
    __tablename__ = "matching_config"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    version = Column(String(50), nullable=False)
    
    # Configuration
    weights = Column(JSONB, nullable=False)  # 가중치 설정
    thresholds = Column(JSONB, nullable=False)  # 임계치 설정
    penalties = Column(JSONB, nullable=False)  # 페널티 설정
    
    # Status
    is_active = Column(Boolean, default=False, index=True)
    description = Column(String)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

