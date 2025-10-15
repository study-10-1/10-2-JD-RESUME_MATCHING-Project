"""
Job Posting Model
"""
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, DECIMAL, Date, ForeignKey, ARRAY, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


class JobPosting(Base):
    __tablename__ = "job_posting"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE"))
    
    # Basic Info
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=False)  # 전체 텍스트
    
    # Structured Data
    requirements = Column(JSONB)  # 필수/우대 조건
    responsibilities = Column(JSONB)  # 업무 내용
    qualifications = Column(JSONB)  # 자격 요건
    benefits = Column(JSONB)  # 복리후생
    
    # Conditions
    employment_type = Column(String(50))  # full-time, part-time, contract
    experience_level = Column(String(50), index=True)  # junior, mid, senior
    min_experience_years = Column(Integer)
    max_experience_years = Column(Integer)
    salary_min = Column(DECIMAL(12, 2))
    salary_max = Column(DECIMAL(12, 2))
    salary_currency = Column(String(10), default="KRW")
    
    # Location
    location = Column(String(255), index=True)
    remote_type = Column(String(50))  # onsite, remote, hybrid
    
    # AI Related
    embedding = Column(Vector(768))  # pgvector (전체 텍스트)
    embedding_model = Column(String(100), default="jhgan/ko-sroberta-multitask")
    parsed_skills = Column(ARRAY(Text))  # 추출된 기술 스택
    parsed_domains = Column(ARRAY(Text))  # 추출된 도메인
    
    # Sectional Embeddings (섹션별 임베딩)
    required_embedding = Column(Vector(768))  # 자격요건 임베딩
    preferred_embedding = Column(Vector(768))  # 우대조건 임베딩
    description_embedding = Column(Vector(768))  # 업무 설명 임베딩
    
    # Meta Info
    source = Column(String(100))  # wanted, jobkorea, saramin
    external_id = Column(String(255))
    external_url = Column(String(500))
    is_active = Column(Boolean, default=True, index=True)
    posted_at = Column(Date, index=True)
    expires_at = Column(Date)
    view_count = Column(Integer, default=0)
    application_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="job_postings")
    matching_results = relationship("MatchingResult", back_populates="job", cascade="all, delete-orphan")
    llm_feedbacks = relationship("LLMFeedback", back_populates="job", cascade="all, delete-orphan")
    
    # Table Arguments (Indexes, Constraints)
    __table_args__ = (
        # UNIQUE INDEX: 중복 방지 (source + external_id)
        Index(
            'idx_job_unique',
            'source', 'external_id',
            unique=True,
            postgresql_where=Column('external_id').isnot(None)
        ),
    )

