"""
LLM Prompt Templates
"""
from typing import Dict, Any


def build_feedback_prompt(
    resume_data: Dict[str, Any],
    job_data: Dict[str, Any],
    matching_result: Dict[str, Any]
) -> str:
    """
    Build prompt for LLM feedback generation
    
    TODO: Implement prompt building
    - Format resume information
    - Format job requirements
    - Format matching scores
    - Create comprehensive prompt
    """
    raise NotImplementedError("build_feedback_prompt not implemented")


# Prompt template examples
FEEDBACK_TEMPLATE = """
당신은 취업 컨설턴트입니다. 다음 이력서와 채용공고의 매칭 결과를 분석하고 피드백을 제공하세요.

## 이력서 정보
{resume_info}

## 채용공고 정보
{job_info}

## 매칭 점수
- 전체 점수: {overall_score}
- 기술 스킬: {technical_score}
- 경험: {experience_score}

## 요청사항
1. 강점 3가지
2. 약점 3가지
3. 개선 방안 3가지
4. 전반적인 코멘트

JSON 형식으로 응답해주세요.
"""

