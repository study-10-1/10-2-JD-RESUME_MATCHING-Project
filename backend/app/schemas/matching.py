"""
Matching Schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class MatchingFilters(BaseModel):
    """Matching filters schema"""
    location: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    min_salary: Optional[Decimal] = None
    min_experience_years: Optional[int] = None
    required_skills: Optional[List[str]] = None


class SearchJobsRequest(BaseModel):
    """Search jobs request schema"""
    resume_id: UUID
    filters: Optional[MatchingFilters] = None
    limit: int = 50


class SearchResumesRequest(BaseModel):
    """Search resumes request schema (for companies)"""
    job_id: UUID
    filters: Optional[MatchingFilters] = None
    limit: int = 100


class CategoryScore(BaseModel):
    """Category score schema"""
    score: float
    weight: float


class MatchingEvidence(BaseModel):
    """Matching evidence schema"""
    matched_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None
    experience_evidence: Optional[dict] = None
    similarity_evidence: Optional[dict] = None


class MatchingResultBase(BaseModel):
    """Matching result base schema"""
    overall_score: Decimal
    grade: str
    category_scores: dict
    matching_evidence: Optional[dict] = None


class MatchingResultResponse(MatchingResultBase):
    """Matching result response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    job_id: UUID
    resume_id: UUID
    penalties: Optional[dict] = None
    created_at: datetime


class JobMatchResponse(BaseModel):
    """Job match response schema (for resume-based search)"""
    job_id: UUID
    title: str
    company: Optional[dict] = None
    overall_score: float
    grade: str
    category_scores: dict
    matching_evidence: Optional[dict] = None
    location: Optional[str] = None
    posted_at: Optional[str] = None


class ResumeMatchResponse(BaseModel):
    """Resume match response schema (for job-based search)"""
    resume_id: UUID
    candidate_name: Optional[str] = None
    overall_score: float
    grade: str
    category_scores: dict
    matching_evidence: Optional[dict] = None
    experience_years: Optional[int] = None
    top_skills: Optional[List[str]] = None


class SearchJobsResponse(BaseModel):
    """Search jobs response schema"""
    resume_id: UUID
    matches: List[JobMatchResponse]
    total_count: int
    processing_time_ms: int


class SearchResumesResponse(BaseModel):
    """Search resumes response schema"""
    job_id: UUID
    matches: List[ResumeMatchResponse]
    total_count: int
    processing_time_ms: int


class MatchingDetailResponse(MatchingResultResponse):
    """Matching detail response schema"""
    job: Optional[dict] = None
    resume: Optional[dict] = None
    algorithm_version: Optional[str] = None
    calculation_time_ms: Optional[int] = None

