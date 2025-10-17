"""
Matching API Routes - 매칭 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Dict, Any
import time

from app.core.database import get_db
from app.schemas.matching import SearchJobsRequest, MatchingDetailResponse
from app.services.matching_service import MatchingService
from app.repositories.matching_repository import MatchingRepository
from app.models.job import JobPosting
from app.models.resume import Resume

router = APIRouter()


def _get_grade_description(grade: str) -> str:
    """등급에 대한 사용자 친화적 설명"""
    descriptions = {
        "excellent": "매우 우수한 매칭도입니다. 서류 통과 가능성이 높습니다.",
        "good": "양호한 매칭도입니다. 지원을 권장합니다.",
        "fair": "보통 수준의 매칭도입니다. 일부 조건을 보완하면 좋겠습니다.",
        "caution": "매칭도가 낮습니다. 조건을 충분히 검토해보세요.",
        "poor": "매칭도가 매우 낮습니다. 지원을 신중히 고려하세요."
    }
    return descriptions.get(grade, "평가 결과를 확인해주세요.")


def _get_recommendation(grade: str, score: float) -> str:
    """등급과 점수 기반 추천사항"""
    if grade in ["excellent", "good"]:
        return "지원을 적극 권장합니다."
    elif grade == "fair":
        return "지원 가능하지만 부족한 부분을 보완하면 더 좋겠습니다."
    elif grade == "caution":
        return "신중히 검토 후 지원 여부를 결정하세요."
    else:
        return "현재 상태로는 지원이 어려울 수 있습니다."


def _extract_strengths(evidence: dict) -> list:
    """강점 추출"""
    strengths = []
    
    # 필수 조건 매칭
    required_matched = evidence.get('required_skills', {}).get('matched', [])
    if required_matched:
        strengths.append(f"필수 조건 {len(required_matched)}개 충족")
    
    # 우대 조건 매칭
    preferred_matched = evidence.get('preferred_skills', {}).get('matched', [])
    if preferred_matched:
        strengths.append(f"우대 조건 {len(preferred_matched)}개 충족")
    
    # 경력 레벨 매칭
    exp_evidence = evidence.get('experience_evidence', {})
    if exp_evidence.get('level_match', False):
        strengths.append("경력 레벨 적합")
    
    return strengths


def _extract_improvement_areas(evidence: dict, penalties: dict) -> list:
    """개선 영역 추출"""
    areas = []
    
    # 부족한 필수 스킬
    required_missing = evidence.get('required_skills', {}).get('missing', [])
    if required_missing:
        areas.append(f"필수 스킬 부족: {', '.join(required_missing[:3])}")
    
    # 부족한 우대 스킬
    preferred_missing = evidence.get('preferred_skills', {}).get('missing', [])
    if preferred_missing:
        areas.append(f"우대 스킬 부족: {', '.join(preferred_missing[:2])}")
    
    # 경력 부족
    if penalties.get('experience_significantly_lacking'):
        areas.append("경력 부족으로 인한 감점")
    
    return areas


@router.post("/search-jobs")
async def search_jobs_for_resume(
    request: SearchJobsRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    이력서 기반 채용공고 매칭 검색
    
    Args:
        request: resume_id, filters, limit
        
    Returns:
        매칭된 채용공고 목록
    """
    try:
        start_time = time.time()
        
        # 매칭 서비스 초기화
        matching_service = MatchingService(db)
        
        # 채용공고 검색 및 매칭 (검색 단계: 피드백 비활성)
        results = matching_service.search_jobs_for_resume(
            resume_id=request.resume_id,
            filters=request.filters.dict() if request.filters else None,
            limit=request.limit
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return {
            "resume_id": str(request.resume_id),
            "matches": results,
            "total_count": len(results),
            "processing_time_ms": processing_time
        }
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Matching error: {str(e)}"
        )


@router.get("/{matching_id}")
async def get_matching_detail_by_token(
    matching_id: str,
    # Cross-encoder 제거됨
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    매칭 결과 상세 조회 (가짜 ID 토큰 기반, DB 저장 없이 재계산)
    - 빠른 응답을 위해 LLM 피드백은 포함하지 않음
    - Cross-encoder 제거됨 (Bi-encoder만 사용)
    """
    try:
        svc = MatchingService(db)
        ids = svc.decode_matching_id(matching_id)
        if not ids.get("resume_id") or not ids.get("job_id"):
            raise HTTPException(status_code=404, detail="Invalid matching_id")

        job = db.query(JobPosting).filter(JobPosting.id == ids["job_id"]).first()
        resume = db.query(Resume).filter(Resume.id == ids["resume_id"]).first()
        if not job or not resume:
            raise HTTPException(status_code=404, detail="Job or Resume not found")

        # Bi-encoder만 사용 (Cross-encoder 제거됨)
        result = svc.calculate_matching_score(job, resume, generate_feedback=False)

        # 사용자 친화적인 응답 구조로 변환
        return {
            "matching_id": matching_id,
            "job": {
                "id": str(job.id),
                "title": job.title,
                "company": job.company.name if job.company else "Unknown Company",
                "location": job.location,
                "experience_level": job.experience_level,
                "employment_type": getattr(job, 'employment_type', None),
                "salary_range": f"{job.salary_min}-{job.salary_max} {job.salary_currency}" if job.salary_min and job.salary_max else None,
                "posted_at": job.posted_at.isoformat() if job.posted_at else None
            },
            "resume": {
                "id": str(resume.id),
                "candidate_name": resume.parsed_data.get('personal_info', {}).get('name', 'Unknown') if resume.parsed_data else 'Unknown'
            },
            "overall_assessment": {
                "score": round(float(result.overall_score) * 100, 1),  # 백분율로 변환
                "grade": result.grade,
                "description": _get_grade_description(result.grade),
                "recommendation": _get_recommendation(result.grade, result.overall_score)
            },
            "detailed_analysis": {
                "required_qualifications": {
                    "score": round(result.category_scores.get('required_match', {}).get('score', 0) * 100, 1),
                    "matched_skills": result.matching_evidence.get('required_skills', {}).get('matched', []),
                    "missing_skills": result.matching_evidence.get('required_skills', {}).get('missing', []),
                    "match_rate": result.matching_evidence.get('required_skills', {}).get('match_rate', '0/0'),
                    "detailed_analysis": result.matching_evidence.get('required_skills', {}).get('detailed_analysis', [])
                },
                "preferred_qualifications": {
                    "score": round(result.category_scores.get('preferred_match', {}).get('score', 0) * 100, 1),
                    "matched_skills": result.matching_evidence.get('preferred_skills', {}).get('matched', []),
                    "missing_skills": result.matching_evidence.get('preferred_skills', {}).get('missing', []),
                    "detailed_analysis": result.matching_evidence.get('preferred_skills', {}).get('detailed_analysis', [])
                },
                "experience_fit": {
                    "score": round(result.category_scores.get('experience_match', {}).get('score', 0) * 100, 1),
                    "required_years": result.matching_evidence.get('experience_evidence', {}).get('required_years', 0),
                    "candidate_years": result.matching_evidence.get('experience_evidence', {}).get('candidate_years', 0),
                    "level_match": result.matching_evidence.get('experience_evidence', {}).get('level_match', False),
                    "details": result.matching_evidence.get('experience_evidence', {}).get('details', '')
                },
                "overall_similarity": {
                    "score": round(result.category_scores.get('overall_similarity', {}).get('score', 0) * 100, 1),
                    "description": "전체적인 프로필과의 유사도"
                }
            },
            "strengths": _extract_strengths(result.matching_evidence),
            "improvement_areas": _extract_improvement_areas(result.matching_evidence, result.penalties),
            "technical_details": {
                "algorithm_version": "v2.0-sectional",
                "calculation_time_ms": result.calculation_time_ms,
                "penalties_applied": result.penalties
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{matching_id}/feedback")
async def generate_feedback_on_demand(
    matching_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    LLM 기반 피드백 온디맨드 생성 API
    - 동일한 matching_id 토큰을 사용해 재계산하며 피드백 포함
    """
    try:
        svc = MatchingService(db)
        ids = svc.decode_matching_id(matching_id)
        if not ids.get("resume_id") or not ids.get("job_id"):
            raise HTTPException(status_code=404, detail="Invalid matching_id")

        job = db.query(JobPosting).filter(JobPosting.id == ids["job_id"]).first()
        resume = db.query(Resume).filter(Resume.id == ids["resume_id"]).first()
        if not job or not resume:
            raise HTTPException(status_code=404, detail="Job or Resume not found")

        # 피드백 활성화하여 재계산
        result = svc.calculate_matching_score(job, resume, generate_feedback=True)

        # 사용자 친화적인 응답 구조로 변환 (피드백 포함)
        return {
            "matching_id": matching_id,
            "job": {
                "id": str(job.id),
                "title": job.title,
                "company": job.company.name if job.company else "Unknown Company",
                "location": job.location,
                "experience_level": job.experience_level,
                "employment_type": getattr(job, 'employment_type', None),
                "salary_range": f"{job.salary_min}-{job.salary_max} {job.salary_currency}" if job.salary_min and job.salary_max else None,
                "posted_at": job.posted_at.isoformat() if job.posted_at else None
            },
            "resume": {
                "id": str(resume.id),
                "candidate_name": resume.parsed_data.get('personal_info', {}).get('name', 'Unknown') if resume.parsed_data else 'Unknown'
            },
            "overall_assessment": {
                "score": round(float(result.overall_score) * 100, 1),  # 백분율로 변환
                "grade": result.grade,
                "description": _get_grade_description(result.grade),
                "recommendation": _get_recommendation(result.grade, result.overall_score)
            },
            "detailed_analysis": {
                "required_qualifications": {
                    "score": round(result.category_scores.get('required_match', {}).get('score', 0) * 100, 1),
                    "matched_skills": result.matching_evidence.get('required_skills', {}).get('matched', []),
                    "missing_skills": result.matching_evidence.get('required_skills', {}).get('missing', []),
                    "match_rate": result.matching_evidence.get('required_skills', {}).get('match_rate', '0/0'),
                    "detailed_analysis": result.matching_evidence.get('required_skills', {}).get('detailed_analysis', [])
                },
                "preferred_qualifications": {
                    "score": round(result.category_scores.get('preferred_match', {}).get('score', 0) * 100, 1),
                    "matched_skills": result.matching_evidence.get('preferred_skills', {}).get('matched', []),
                    "missing_skills": result.matching_evidence.get('preferred_skills', {}).get('missing', []),
                    "detailed_analysis": result.matching_evidence.get('preferred_skills', {}).get('detailed_analysis', [])
                },
                "experience_fit": {
                    "score": round(result.category_scores.get('experience_match', {}).get('score', 0) * 100, 1),
                    "required_years": result.matching_evidence.get('experience_evidence', {}).get('required_years', 0),
                    "candidate_years": result.matching_evidence.get('experience_evidence', {}).get('candidate_years', 0),
                    "level_match": result.matching_evidence.get('experience_evidence', {}).get('level_match', False),
                    "details": result.matching_evidence.get('experience_evidence', {}).get('details', '')
                },
                "overall_similarity": {
                    "score": round(result.category_scores.get('overall_similarity', {}).get('score', 0) * 100, 1),
                    "description": "전체적인 프로필과의 유사도"
                }
            },
            "strengths": _extract_strengths(result.matching_evidence),
            "improvement_areas": _extract_improvement_areas(result.matching_evidence, result.penalties),
            "ai_feedback": {
                "personalized_advice": result.matching_evidence.get('ai_feedback', ''),
                "generated_at": result.calculation_time_ms
            },
            "technical_details": {
                "algorithm_version": "v2.0-sectional",
                "calculation_time_ms": result.calculation_time_ms,
                "penalties_applied": result.penalties
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare/{job_id}")
async def compare_resume_and_job(
    job_id: UUID,
    resume_id: UUID,
    db: Session = Depends(get_db)
):
    """
    특정 이력서와 채용공고 상세 비교
    - 카테고리별 점수, 매칭 근거, LLM 피드백 포함
    """
    try:
        job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not job or not resume:
            raise HTTPException(status_code=404, detail="Job or Resume not found")

        matching_service = MatchingService(db)
        # 상세 단계: 피드백 활성화
        result = matching_service.calculate_matching_score(job, resume, generate_feedback=True)

        return {
            "job_id": str(job.id),
            "resume_id": str(resume.id),
            "overall_score": float(result.overall_score),
            "grade": result.grade,
            "category_scores": result.category_scores,
            "matching_evidence": result.matching_evidence,
            "penalties": result.penalties,
            "calculation_time_ms": result.calculation_time_ms,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compare failed: {e}")


@router.get("/sentence-matches/{matching_id}")
async def get_sentence_level_matches(
    matching_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    문장 단위 매칭 상세 정보 조회
    - 매칭된 문장들과 유사도 점수 포함
    - 각 조건별로 어떤 문장이 매칭되었는지 상세 정보 제공
    """
    try:
        svc = MatchingService(db)
        ids = svc.decode_matching_id(matching_id)
        if not ids.get("resume_id") or not ids.get("job_id"):
            raise HTTPException(status_code=404, detail="Invalid matching_id")

        job = db.query(JobPosting).filter(JobPosting.id == ids["job_id"]).first()
        resume = db.query(Resume).filter(Resume.id == ids["resume_id"]).first()
        if not job or not resume:
            raise HTTPException(status_code=404, detail="Job or Resume not found")

        # 문장 단위 매칭 결과 계산
        result = svc.calculate_matching_score(job, resume, generate_feedback=False)
        
        # 문장 단위 매칭 정보 추출
        sentence_matches = {
            "required_conditions": [],
            "preferred_conditions": []
        }
        
        # Required 조건 분석
        req_analysis = result.matching_evidence.get('required_skills', {}).get('detailed_analysis', [])
        for analysis in req_analysis:
            sentence_matches["required_conditions"].append({
                "condition": analysis.get('condition', ''),
                "matched": analysis.get('matched', False),
                "similarity_score": analysis.get('similarity_score', 0.0),
                "matched_sentence": analysis.get('matched_sentence', ''),
                "matched_section": analysis.get('matched_section', ''),
                "match_type": analysis.get('match_type', 'none')
            })
        
        # Preferred 조건 분석
        pref_analysis = result.matching_evidence.get('preferred_skills', {}).get('detailed_analysis', [])
        for analysis in pref_analysis:
            sentence_matches["preferred_conditions"].append({
                "condition": analysis.get('condition', ''),
                "matched": analysis.get('matched', False),
                "similarity_score": analysis.get('similarity_score', 0.0),
                "matched_sentence": analysis.get('matched_sentence', ''),
                "matched_section": analysis.get('matched_section', ''),
                "match_type": analysis.get('match_type', 'none')
            })

        return {
            "matching_id": matching_id,
            "job_title": job.title,
            "resume_name": resume.file_name,
            "overall_score": round(float(result.overall_score) * 100, 1),
            "grade": result.grade,
            "sentence_matches": sentence_matches,
            "summary": {
                "total_required": len(req_analysis),
                "matched_required": sum(1 for a in req_analysis if a.get('matched')),
                "total_preferred": len(pref_analysis),
                "matched_preferred": sum(1 for a in pref_analysis if a.get('matched'))
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_matching(db: Session = Depends(get_db)):
    """
    매칭 알고리즘 테스트 엔드포인트
    
    DB에 있는 첫 번째 이력서로 매칭 테스트
    """
    try:
        from app.models.resume import Resume
        
        # 첫 번째 이력서 가져오기
        resume = db.query(Resume).filter(Resume.embedding.isnot(None)).first()
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No resumes with embeddings found"
            )
        
        # 매칭 실행
        matching_service = MatchingService(db)
        results = matching_service.search_jobs_for_resume(
            resume_id=resume.id,
            limit=10
        )
        
        return {
            "test_resume": {
                "id": str(resume.id),
                "file_name": resume.file_name,
                "skills": resume.extracted_skills
            },
            "matches": results,
            "count": len(results)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
