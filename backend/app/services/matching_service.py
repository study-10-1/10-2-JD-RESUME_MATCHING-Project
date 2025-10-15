"""
Matching Service - 핵심 매칭 알고리즘
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime
import time
import uuid
import base64
import hmac
import hashlib
import json

from app.models.job import JobPosting
from app.models.resume import Resume
from app.models.matching import MatchingResult
from app.services.ml.vector_search import VectorSearchService
from app.services.ml.scoring import ScoringService
from app.core.config import settings
from app.services.ml.penalties import PenaltyService
from app.services.ml.feedback_generator import FeedbackGenerator
from app.services.ml.sectional_scoring import SectionalScoringService
from app.core.logging import logger
import numpy as np


class MatchingService:
    """매칭 서비스 - 이력서와 채용공고 매칭"""
    
    def __init__(self, db: Session, use_sectional: bool = True):  # ✅ 기본값 True로 변경!
        self.db = db
        self.vector_search = VectorSearchService(db)
        self.scoring = ScoringService()
        self.sectional_scoring = SectionalScoringService()
        self.penalty = PenaltyService()
        self.feedback_generator = FeedbackGenerator()
        # 섹션별 임베딩 사용 시 SECTIONAL_WEIGHTS, 아니면 DEFAULT_WEIGHTS
        self.weights = settings.SECTIONAL_WEIGHTS if use_sectional else settings.DEFAULT_WEIGHTS
        self.thresholds = settings.DEFAULT_THRESHOLDS
        self.grade_thresholds = settings.GRADE_THRESHOLDS
        self.use_sectional = use_sectional  # 섹션별 임베딩 사용 여부
    
    def _generate_matching_id(self, resume_id: str, job_id: str) -> str:
        """결정적 토큰 생성 (DB 저장 없이 식별/복호화 가능)
        포맷: v1.<base64url(payload)>.<base64url(hmac)>
        payload: {"resume_id":..., "job_id":...}
        """
        payload = {"resume_id": resume_id, "job_id": job_id}
        payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=")
        secret = (getattr(settings, "JWT_SECRET_KEY", "dev")).encode("utf-8")
        sig = hmac.new(secret, b"v1." + b64, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=")
        return f"v1.{b64.decode()}.{sig_b64.decode()}"

    def decode_matching_id(self, token: str) -> Dict[str, str]:
        """토큰에서 resume_id, job_id 복호화 및 서명 검증. 구형(uuid5)도 허용하지 않음."""
        # v1.<b64>.<sig> 형태만 지원
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != "v1":
            raise ValueError("invalid token format")
        b64 = parts[1]
        sig = parts[2]
        secret = (getattr(settings, "JWT_SECRET_KEY", "dev")).encode("utf-8")
        expected = hmac.new(secret, ("v1." + b64).encode("utf-8"), hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected).rstrip(b"=")
        if not hmac.compare_digest(expected_b64, sig.encode("utf-8")):
            raise ValueError("invalid signature")
        pad = '=' * (-len(b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(b64 + pad)
        payload = json.loads(payload_bytes.decode("utf-8"))
        return {"resume_id": payload.get("resume_id"), "job_id": payload.get("job_id")}

    def search_jobs_for_resume(
        self,
        resume_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        이력서 기반 채용공고 검색 및 매칭
        
        Args:
            resume_id: 이력서 ID
            filters: 필터 조건
            limit: 최대 결과 수
            
        Returns:
            매칭 결과 리스트
        """
        start_time = time.time()
        
        # 1. 이력서 조회
        resume = self.db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            raise ValueError(f"Resume not found: {resume_id}")
        
        if resume.embedding is None:
            raise ValueError(f"Resume has no embedding: {resume_id}")
        
        logger.info(f"Searching jobs for resume: {resume.file_name}")
        
        # 2. 모든 활성 공고 대상으로 매칭 (검색 단계: 전체 스캔)
        try:
            # is_active 컬럼이 있으면 필터, 없으면 전체
            q = self.db.query(JobPosting)
            if hasattr(JobPosting, "is_active"):
                q = q.filter(JobPosting.is_active == True)
            all_jobs = q.all()
        except Exception:
            all_jobs = self.db.query(JobPosting).all()

        logger.info(f"Scanning all jobs for matching: count={len(all_jobs)}")

        # 3. 각 채용공고에 대해 상세 매칭 점수 계산 (피드백 비활성)
        results = []
        for job in all_jobs:
            try:
                # 매칭 점수 계산
                matching_result = self.calculate_matching_score(job, resume, generate_feedback=False)
                
                # 결과에 벡터 유사도 포함
                result_dict = {
                    "matching_id": self._generate_matching_id(str(resume.id), str(job.id)),
                    "job_id": str(job.id),
                    "job_title": job.title,
                    "company_name": job.company.name if job.company else None,
                    "location": job.location,
                    "experience_level": job.experience_level,
                    "overall_score": round(float(matching_result.overall_score) * 100, 1),  # 백분율로 변환
                    "grade": matching_result.grade,
                    "category_scores": self._convert_category_scores_to_percentage(matching_result.category_scores),
                    "matching_evidence": matching_result.matching_evidence,
                    "penalties": matching_result.penalties
                }
                
                results.append(result_dict)
                
            except Exception as e:
                logger.error(f"Error calculating match for job {job.id}: {e}")
                continue
        
        # 4. 전체 점수로 재정렬
        results.sort(key=lambda x: x["overall_score"], reverse=True)
        
        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"Matching completed in {processing_time}ms")
        
        return results
    
    def calculate_matching_score(
        self,
        job: JobPosting,
        resume: Resume,
        generate_feedback: bool = True
    ) -> MatchingResult:
        """
        채용공고와 이력서 간의 상세 매칭 점수 계산
        
        섹션별 임베딩 사용 시 더 정확한 매칭 제공
        
        Returns:
            MatchingResult 객체
        """
        start_time = time.time()
        
        # 섹션별 임베딩 사용 여부 확인
        if self.use_sectional and self._has_sectional_embeddings(job, resume):
            return self._calculate_matching_score_sectional(job, resume, generate_feedback)
        else:
            return self._calculate_matching_score_traditional(job, resume, generate_feedback)
    
    def _has_sectional_embeddings(self, job: JobPosting, resume: Resume) -> bool:
        """섹션별 임베딩이 모두 있는지 확인"""
        return (
            job.required_embedding is not None and
            resume.skills_embedding is not None
        )
    
    def _calculate_matching_score_traditional(
        self,
        job: JobPosting,
        resume: Resume,
        generate_feedback: bool
    ) -> MatchingResult:
        """기존 방식 (전체 임베딩)"""
        start_time = time.time()
        
        # 1. 임베딩 유사도
        similarity_score = 0.5
        if job.embedding is not None and resume.embedding is not None:
            job_emb = np.frombuffer(job.embedding, dtype=np.float32)
            resume_emb = np.frombuffer(resume.embedding, dtype=np.float32)
            similarity_score = float(np.dot(job_emb, resume_emb) / (
                np.linalg.norm(job_emb) * np.linalg.norm(resume_emb)
            ))
        
        # 2. 카테고리별 점수 계산
        skill_result = self.scoring.calculate_skill_score(job, resume)
        experience_result = self.scoring.calculate_experience_score(job, resume)
        education_score = self.scoring.calculate_education_score(job, resume)
        certification_score = self.scoring.calculate_certification_score(job, resume)
        language_score = self.scoring.calculate_language_score(job, resume)
        
        # 3. 카테고리 점수 구조화
        category_scores = {
            "technical_skills": {
                "score": skill_result["score"],
                "weight": self.weights["technical_skills"]
            },
            "experience": {
                "score": experience_result["score"],
                "weight": self.weights["experience"]
            },
            "similarity": {
                "score": similarity_score,
                "weight": self.weights["similarity"]
            },
            "education": {
                "score": education_score,
                "weight": self.weights["education"]
            },
            "certification": {
                "score": certification_score,
                "weight": self.weights["certification"]
            },
            "language": {
                "score": language_score,
                "weight": self.weights["language"]
            }
        }
        
        # 4. 가중 평균 계산
        weighted_sum = sum(
            cat["score"] * cat["weight"] 
            for cat in category_scores.values()
        )
        
        # 5. 페널티 계산
        penalties = self.penalty.calculate_penalties(job, resume)
        
        # 6. 페널티 적용
        penalty_sum = sum(penalties.values())
        final_score = max(0.0, weighted_sum - penalty_sum)
        
        # 7. 등급 부여
        grade = self._assign_grade(final_score)
        
        # 8. 매칭 근거 생성 (상세 정보 포함)
        matching_evidence = {
            "required_skills": {
                "matched": skill_result.get("matched_required", []),
                "missing": skill_result.get("missing_required", []),
                "match_rate": f"{len(skill_result.get('matched_required', []))}/{skill_result.get('total_required', 0)}",
                "score": skill_result.get("required_score", 0)
            },
            "preferred_skills": {
                "matched": skill_result.get("matched_preferred", []),
                "missing": skill_result.get("missing_preferred", []),
                "match_rate": f"{len(skill_result.get('matched_preferred', []))}/{skill_result.get('total_preferred', 0)}",
                "score": skill_result.get("preferred_score", 0)
            },
            "experience_evidence": experience_result,
            "similarity_score": similarity_score,
            "difficulty_factor": skill_result.get("difficulty_factor", 0)
        }
        
        # 9. 피드백 생성 (옵션)
        if generate_feedback:
            feedback = self.feedback_generator.generate_feedback(
                job=job,
                resume=resume,
                matching_evidence=matching_evidence,
                overall_score=final_score,
                grade=grade
            )
            matching_evidence["feedback"] = feedback
        
        # 10. 계산 시간
        calculation_time = int((time.time() - start_time) * 1000)
        
        # 11. MatchingResult 객체 생성
        matching_result = MatchingResult(
            job_id=job.id,
            resume_id=resume.id,
            overall_score=Decimal(str(round(final_score, 4))),
            grade=grade,
            category_scores=category_scores,
            matching_evidence=matching_evidence,
            penalties=penalties,
            algorithm_version="v1.0",
            calculation_time_ms=calculation_time
        )
        
        logger.info(
            f"Matching calculated: {job.title} x {resume.file_name} = {final_score:.2%} ({grade})"
        )
        
        return matching_result
    
    def _calculate_matching_score_sectional(
        self,
        job: JobPosting,
        resume: Resume,
        generate_feedback: bool
    ) -> MatchingResult:
        """섹션별 임베딩 방식 (개선 버전)"""
        start_time = time.time()
        
        # 1. 섹션별 점수 계산
        sectional_scores = self.sectional_scoring.calculate_sectional_score(job, resume)
        
        # 2. 기존 카테고리 점수도 계산 (학력, 자격증 등)
        education_score = self.scoring.calculate_education_score(job, resume)
        certification_score = self.scoring.calculate_certification_score(job, resume)
        language_score = self.scoring.calculate_language_score(job, resume)
        skill_result = self.scoring.calculate_skill_score(job, resume)
        experience_result = self.scoring.calculate_experience_score(job, resume)
        
        # 3. 카테고리 점수 구조화 (섹션별 점수 반영, 튜닝된 가중치 사용)
        sectional_weights = settings.SECTIONAL_WEIGHTS
        
        category_scores = {
            "required_match": {
                "score": sectional_scores["required_match"],
                "weight": sectional_weights["required"]
            },
            "preferred_match": {
                "score": sectional_scores["preferred_match"],
                "weight": sectional_weights["preferred"]
            },
            "experience_match": {
                "score": sectional_scores["experience_match"],
                "weight": sectional_weights["experience"]
            },
            "overall_similarity": {
                "score": sectional_scores["overall_similarity"],
                "weight": sectional_weights["overall"]
            },
            "education": {
                "score": education_score,
                "weight": sectional_weights["education"]
            },
            "certification": {
                "score": certification_score,
                "weight": sectional_weights["certification"]
            }
        }
        
        # 4. 가중 평균 계산
        weighted_sum = sum(
            cat["score"] * cat["weight"] 
            for cat in category_scores.values()
        )
        
        # 5. 페널티 계산
        penalties = self.penalty.calculate_penalties(job, resume)
        
        # 6. 페널티 적용
        penalty_sum = sum(penalties.values())
        final_score = max(0.0, weighted_sum - penalty_sum)
        
        # 7. 등급 부여
        grade = self._assign_grade(final_score)
        
        # 8. 매칭 근거 생성
        matching_evidence = {
            "required_skills": {
                "matched": skill_result.get("matched_required", []),
                "missing": skill_result.get("missing_required", []),
                "match_rate": f"{len(skill_result.get('matched_required', []))}/{skill_result.get('total_required', 0)}",
                "score": skill_result.get("required_score", 0)
            },
            "preferred_skills": {
                "matched": skill_result.get("matched_preferred", []),
                "missing": skill_result.get("missing_preferred", []),
                "match_rate": f"{len(skill_result.get('matched_preferred', []))}/{skill_result.get('total_preferred', 0)}",
                "score": skill_result.get("preferred_score", 0)
            },
            "experience_evidence": experience_result,
            "sectional_scores": {
                "required_embedding": sectional_scores["required_match"],
                "preferred_embedding": sectional_scores["preferred_match"],
                "experience_embedding": sectional_scores["experience_match"]
            },
            "similarity_score": sectional_scores["overall_similarity"],
            "difficulty_factor": skill_result.get("difficulty_factor", 0)
        }
        
        # 9. 피드백 생성 (옵션)
        if generate_feedback:
            feedback = self.feedback_generator.generate_feedback(
                job=job,
                resume=resume,
                matching_evidence=matching_evidence,
                overall_score=final_score,
                grade=grade
            )
            matching_evidence["feedback"] = feedback
        
        # 10. 계산 시간
        calculation_time = int((time.time() - start_time) * 1000)
        
        # 11. MatchingResult 객체 생성
        matching_result = MatchingResult(
            job_id=job.id,
            resume_id=resume.id,
            overall_score=Decimal(str(round(final_score, 4))),
            grade=grade,
            category_scores=category_scores,
            matching_evidence=matching_evidence,
            penalties=penalties,
            algorithm_version="v2.0-sectional",
            calculation_time_ms=calculation_time
        )
        
        logger.info(
            f"Sectional matching: {job.title} x {resume.file_name} = {final_score:.2%} ({grade})"
        )
        
        return matching_result
    
    def _convert_category_scores_to_percentage(self, category_scores: dict) -> dict:
        """카테고리 점수들을 백분율로 변환"""
        converted = {}
        for key, value in category_scores.items():
            if isinstance(value, dict) and 'score' in value:
                converted[key] = {
                    'score': round(value['score'] * 100, 1),
                    'weight': value.get('weight', 0)
                }
            else:
                converted[key] = value
        return converted

    def _assign_grade(self, overall_score: float) -> str:
        """
        점수에 따른 등급 부여
        
        Args:
            overall_score: 전체 점수 (0~1)
            
        Returns:
            excellent | good | fair | caution | poor
        """
        thresholds = self.grade_thresholds
        
        if overall_score >= thresholds["excellent"]:
            return "excellent"
        elif overall_score >= thresholds["good"]:
            return "good"
        elif overall_score >= thresholds["fair"]:
            return "fair"
        elif overall_score >= thresholds["caution"]:
            return "caution"
        else:
            return "poor"
