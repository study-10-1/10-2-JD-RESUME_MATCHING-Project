"""
Feedback Schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class LLMFeedbackRequest(BaseModel):
    """LLM feedback generation request"""
    resume_id: UUID
    job_id: UUID


class OverallAnalysis(BaseModel):
    """Overall analysis schema"""
    strengths: List[str]
    weaknesses: List[str]
    overall_comment: str
    match_level: str


class CategoryAnalysis(BaseModel):
    """Category analysis schema"""
    score: float
    strengths: List[str]
    improvements: List[str]
    recommendations: List[str]


class LLMFeedbackResponse(BaseModel):
    """LLM feedback response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    feedback_id: UUID
    overall_analysis: OverallAnalysis
    category_analysis: dict  # Dict of CategoryAnalysis
    recommendations: List[str]
    llm_model: str
    generation_time_ms: int


class LLMFeedbackDetail(BaseModel):
    """LLM feedback detail schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    feedback_json: dict
    llm_model: str
    token_count: Optional[int] = None
    generation_time_ms: Optional[int] = None
    created_at: datetime


class UserFeedbackRequest(BaseModel):
    """User feedback submission request"""
    matching_result_id: UUID
    feedback_type: str  # rating, report, suggestion
    rating: Optional[int] = None  # 1-5
    comment: Optional[str] = None
    tags: Optional[List[str]] = None


class UserFeedbackResponse(BaseModel):
    """User feedback response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    feedback_id: UUID
    message: str

