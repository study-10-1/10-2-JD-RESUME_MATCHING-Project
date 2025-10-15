"""
Feedback Service
"""
from sqlalchemy.orm import Session
from typing import Dict, Any
from uuid import UUID

from app.models.feedback import LLMFeedback, UserFeedback


class FeedbackService:
    """Feedback service for LLM feedback generation"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def generate_llm_feedback(
        self,
        resume_id: UUID,
        job_id: UUID
    ) -> LLMFeedback:
        """
        Generate LLM feedback for resume-job match
        
        TODO: Implement LLM feedback generation
        - Get resume and job details
        - Calculate or retrieve matching result
        - Build prompt for LLM
        - Call OpenAI API
        - Parse response
        - Save feedback to database
        """
        raise NotImplementedError("generate_llm_feedback not implemented")
    
    def create_user_feedback(
        self,
        user_id: UUID,
        matching_result_id: UUID,
        feedback_data: Dict[str, Any]
    ) -> UserFeedback:
        """
        Create user feedback
        
        TODO: Implement user feedback creation
        - Validate data
        - Save to database
        """
        raise NotImplementedError("create_user_feedback not implemented")

