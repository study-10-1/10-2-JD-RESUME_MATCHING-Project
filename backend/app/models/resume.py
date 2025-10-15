"""
Resume Model
"""
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


class Resume(Base):
    __tablename__ = "resume"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), index=True)
    
    # File Info
    file_name = Column(String(500), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(50))  # pdf, docx, txt
    file_size = Column(Integer)
    
    # Text Info
    raw_text = Column(Text, nullable=False)
    
    # Parsed Info
    parsed_data = Column(JSONB)  # 구조화된 이력서 데이터
    """
    {
        "personal_info": {...},
        "summary": "...",
        "work_experience": [...],
        "education": [...],
        "skills": [...],
        "certifications": [...],
        "languages": [...],
        "projects": [...]
    }
    """
    
    # Extracted Key Info
    extracted_skills = Column(ARRAY(Text))
    extracted_experience_years = Column(Integer)
    extracted_domains = Column(ARRAY(Text))
    extracted_education_level = Column(String(50))
    
    # AI Related
    embedding = Column(Vector(768))  # pgvector (전체 텍스트)
    embedding_model = Column(String(100), default="jhgan/ko-sroberta-multitask")
    
    # Sectional Embeddings (섹션별 임베딩)
    skills_embedding = Column(Vector(768))  # 스킬 섹션 임베딩
    experience_embedding = Column(Vector(768))  # 경력 섹션 임베딩
    projects_embedding = Column(Vector(768))  # 프로젝트 섹션 임베딩
    
    # Meta Info
    is_primary = Column(Boolean, default=False)
    version = Column(Integer, default=1)
    is_public = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="resumes")
    matching_results = relationship("MatchingResult", back_populates="resume", cascade="all, delete-orphan")
    llm_feedbacks = relationship("LLMFeedback", back_populates="resume", cascade="all, delete-orphan")

