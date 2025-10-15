"""
Job Posting Schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal


class CompanyBase(BaseModel):
    """Company base schema"""
    name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None


class CompanyResponse(CompanyBase):
    """Company response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    logo_url: Optional[str] = None


class JobPostingBase(BaseModel):
    """Job posting base schema"""
    title: str
    description: str
    raw_text: str


class JobPostingCreate(JobPostingBase):
    """Job posting creation schema"""
    company_id: UUID
    requirements: Optional[dict] = None
    responsibilities: Optional[dict] = None
    qualifications: Optional[dict] = None
    benefits: Optional[dict] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    min_experience_years: Optional[int] = None
    max_experience_years: Optional[int] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    location: Optional[str] = None
    remote_type: Optional[str] = None


class JobPostingUpdate(BaseModel):
    """Job posting update schema"""
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class JobPostingResponse(JobPostingBase):
    """Job posting response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    company: Optional[CompanyResponse] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    location: Optional[str] = None
    remote_type: Optional[str] = None
    parsed_skills: Optional[List[str]] = None
    posted_at: Optional[date] = None
    is_active: bool
    created_at: datetime


class JobPostingDetail(JobPostingResponse):
    """Job posting detail schema"""
    requirements: Optional[dict] = None
    responsibilities: Optional[dict] = None
    qualifications: Optional[dict] = None
    benefits: Optional[dict] = None
    min_experience_years: Optional[int] = None
    max_experience_years: Optional[int] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    parsed_domains: Optional[List[str]] = None
    view_count: int
    application_count: int


class JobListResponse(BaseModel):
    """Job list response schema"""
    items: List[JobPostingResponse]
    total: int
    page: int
    page_size: int

