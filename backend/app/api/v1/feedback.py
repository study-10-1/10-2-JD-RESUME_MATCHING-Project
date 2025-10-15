"""
Feedback API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.feedback import (
    LLMFeedbackRequest,
    LLMFeedbackResponse,
    UserFeedbackRequest,
    UserFeedbackResponse
)

router = APIRouter()


@router.post("/generate", response_model=LLMFeedbackResponse)
async def generate_llm_feedback(
    request: LLMFeedbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    LLM 피드백 생성
    
    TODO: Implement LLM feedback generation logic
    - Get resume and job details
    - Calculate matching result if not exists
    - Generate prompt for LLM
    - Call OpenAI API
    - Parse and structure feedback
    - Save to database
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="LLM feedback generation not implemented yet"
    )


@router.post("/user-feedback", response_model=UserFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_user_feedback(
    request: UserFeedbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    사용자 피드백 제출
    
    TODO: Implement user feedback submission logic
    - Validate matching_result_id
    - Save user feedback to database
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User feedback submission not implemented yet"
    )

