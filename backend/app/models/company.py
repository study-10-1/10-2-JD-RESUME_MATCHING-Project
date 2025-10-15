"""
Company Model
"""
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Company(Base):
    __tablename__ = "company"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic Info
    name = Column(String(255), nullable=False, index=True)
    industry = Column(String(100), index=True)
    company_size = Column(String(50))  # startup, mid-size, enterprise
    location = Column(String(255))
    website = Column(String(500))
    description = Column(Text)
    logo_url = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job_postings = relationship("JobPosting", back_populates="company", cascade="all, delete-orphan")

