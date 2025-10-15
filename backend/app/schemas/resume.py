"""
Resume Schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ResumeBase(BaseModel):
    """Resume base schema"""
    file_name: str
    file_url: str
    raw_text: str


class ResumeCreate(BaseModel):
    """Resume creation schema (for file upload)"""
    is_primary: bool = False


class ResumeUpdate(BaseModel):
    """Resume update schema"""
    is_primary: Optional[bool] = None
    is_public: Optional[bool] = None


class ResumeResponse(BaseModel):
    """Resume response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    file_name: str
    file_url: str
    extracted_skills: Optional[List[str]] = None
    extracted_experience_years: Optional[int] = None
    is_primary: bool
    created_at: datetime


class ResumeDetail(ResumeResponse):
    """Resume detail schema"""
    raw_text: str
    parsed_data: Optional[dict] = None
    extracted_domains: Optional[List[str]] = None
    extracted_education_level: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None


class ResumeUploadResponse(BaseModel):
    """Resume upload response schema"""
    resume_id: UUID
    file_name: str
    file_url: str
    parsed_data: Optional[dict] = None
    extracted_skills: Optional[List[str]] = None
    extracted_experience_years: Optional[int] = None
    processing_time_ms: int


class ResumeListResponse(BaseModel):
    """Resume list response schema"""
    items: List[ResumeResponse]
    total: int
    page: int
    page_size: int

