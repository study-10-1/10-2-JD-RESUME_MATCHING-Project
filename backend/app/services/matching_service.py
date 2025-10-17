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
from app.services.ml.embedding import EmbeddingService
# Cross-encoder 제거됨
from app.core.logging import logger
import numpy as np


class MatchingService:
    """매칭 서비스 - 이력서와 채용공고 매칭"""
    
    def __init__(self, db: Session, use_sectional: bool = True):  # 섹션별 문장 단위 매칭
        self.db = db
        self.vector_search = VectorSearchService(db)
        self.scoring = ScoringService(db)
        self.sectional_scoring = SectionalScoringService()
        self.penalty = PenaltyService()
        self.feedback_generator = FeedbackGenerator()
        self.embedding_service = EmbeddingService()
        # 섹션별 문장 단위 매칭 가중치 (config에서 가져오기)
        self.weights = settings.SECTIONAL_WEIGHTS
        self.thresholds = settings.DEFAULT_THRESHOLDS
        self.grade_thresholds = settings.GRADE_THRESHOLDS
        self.use_sectional = True  # 섹션별 문장 단위 매칭 활성화
    
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
        
        # 문장단위 임베딩 확인
        from app.models.sentences import ResumeSentence
        sentence_count = self.db.query(ResumeSentence).filter(ResumeSentence.resume_id == resume.id).count()
        if sentence_count == 0:
            raise ValueError(f"Resume has no sentence embeddings: {resume_id}")
        
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
        generate_feedback: bool = True,
        use_cross_encoder: bool = False  # Cross-encoder 제거됨 (사용하지 않음)
    ) -> MatchingResult:
        """
        채용공고와 이력서 간의 상세 매칭 점수 계산
        
        섹션별 임베딩 사용 시 더 정확한 매칭 제공
        
        Args:
            job: 채용공고
            resume: 이력서
            generate_feedback: AI 피드백 생성 여부
            use_cross_encoder: Cross-encoder 제거됨 (사용하지 않음)
        
        Returns:
            MatchingResult 객체
        """
        start_time = time.time()
        
        # Cross-encoder 제거됨 - 항상 Bi-encoder 사용
        # 섹션별 문장 단위 매칭 사용 (자격요건 중심)
        return self._calculate_matching_score_sectional_sentences(job, resume, generate_feedback)
    
    def _calculate_matching_score_sectional_sentences(
        self,
        job: JobPosting,
        resume: Resume,
        generate_feedback: bool
    ) -> MatchingResult:
        """섹션별 문장 단위 매칭 (자격요건 중심)"""
        start_time = time.time()
        
        # 1. 문장 단위 매칭으로 섹션별 점수 계산
        required_score = self._calculate_section_score_by_sentences(job, resume, "required")
        preferred_score = self._calculate_section_score_by_sentences(job, resume, "preferred")
        experience_score = self._calculate_section_score_by_sentences(job, resume, "experience")
        
        # 2. 전체 유사도 계산 (전체 텍스트 임베딩 기반)
        overall_similarity = self._calculate_overall_similarity(job, resume)
        
        # 3. 기존 카테고리 점수도 계산 (학력, 자격증 등)
        education_score = self.scoring.calculate_education_score(job, resume)
        certification_score = self.scoring.calculate_certification_score(job, resume)
        language_score = self.scoring.calculate_language_score(job, resume)
        
        # 4. 카테고리 점수 구조화 (자격요건 중심 가중치 + evidence 포함)
        category_scores = {
            "required_match": {
                "score": required_score["score"],
                "weight": self.weights["required_match"],
                **required_score["evidence"]  # evidence 정보 포함
            },
            "preferred_match": {
                "score": preferred_score["score"],
                "weight": self.weights["preferred_match"],
                **preferred_score["evidence"]  # evidence 정보 포함
            },
            "experience_match": {
                "score": experience_score["score"],
                "weight": self.weights["experience_match"],
                **experience_score["evidence"]  # evidence 정보 포함
            },
            "overall_similarity": {
                "score": overall_similarity,
                "weight": self.weights["overall_similarity"]
            },
            "education": {
                "score": education_score,
                "weight": 0.0  # 가중치 제거
            },
            "certification": {
                "score": certification_score,
                "weight": 0.0  # 가중치 제거
            },
            "language": {
                "score": language_score,
                "weight": 0.0  # 가중치 제거
            }
        }
        
        # 5. 가중 평균 계산
        weighted_sum = sum(
            cat["score"] * cat["weight"] 
            for cat in category_scores.values()
        )
        
        # 6. 자격요건 매칭 실패 시 50% 감점 (엄격성 강화)
        if required_score["score"] < 0.5:  # 50% 미만이면 실패로 간주
            weighted_sum *= 0.5  # 50% 감점
        
        # 7. 페널티 계산
        penalties = self.penalty.calculate_penalties(job, resume)
        penalty_sum = sum(penalties.values())
        final_score = max(0.0, weighted_sum - penalty_sum)
        
        # 8. 등급 부여
        grade = self._assign_grade(final_score)
        
        # 9. 매칭 근거 생성 (섹션별 문장 단위 매칭 결과 사용)
        matching_evidence = {
            "required_skills": category_scores.get("required_match", {}),
            "preferred_skills": category_scores.get("preferred_match", {}),
            "experience_evidence": category_scores.get("experience_match", {}),
            "sectional_scores": {
                "required_embedding": category_scores.get("required_match", {}).get("score", 0),
                "preferred_embedding": category_scores.get("preferred_match", {}).get("score", 0),
                "experience_embedding": category_scores.get("experience_match", {}).get("score", 0)
            }
        }
        
        # 10. LLM 피드백 생성 (필요시)
        if generate_feedback:
            try:
                feedback = self.feedback_generator.generate_feedback(job, resume, matching_evidence)
                matching_evidence["ai_feedback"] = feedback
            except Exception as e:
                logger.warning(f"Feedback generation failed: {e}")
                matching_evidence["ai_feedback"] = "피드백 생성 중 오류가 발생했습니다."
        
        # 11. 결과 생성
        calculation_time_ms = int((time.time() - start_time) * 1000)
        
        matching_result = MatchingResult(
            job_id=job.id,
            resume_id=resume.id,
            overall_score=Decimal(str(final_score)),
            grade=grade,
            category_scores=category_scores,
            matching_evidence=matching_evidence,
            penalties=penalties,
            algorithm_version="v3.0-sectional-sentences",
            calculation_time_ms=calculation_time_ms
        )
        
        return matching_result

    def _calculate_overall_similarity(self, job: JobPosting, resume: Resume) -> float:
        """전체 텍스트 유사도 계산"""
        try:
            # 전체 텍스트 임베딩 생성
            job_text = f"{job.title} {job.description or ''} {job.requirements or ''} {job.qualifications or ''}"
            
            # 이력서 텍스트 구성 (parsed_data에서 추출)
            parsed_data = resume.parsed_data or {}
            resume_text = f"{parsed_data.get('summary', '')} {parsed_data.get('work_experience', '')} {parsed_data.get('skills', '')} {parsed_data.get('projects', '')}"
            
            # 임베딩 생성
            job_embedding = self.embedding_service.generate_embedding(job_text)
            resume_embedding = self.embedding_service.generate_embedding(resume_text)
            
            # 코사인 유사도 계산
            similarity = self.embedding_service.cosine_similarity(job_embedding, resume_embedding)
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"Overall similarity calculation failed: {e}")
            return 0.0

    def _get_dynamic_threshold(self, condition: str, section: str) -> float:
        """조건별 동적 임계값 설정"""
        condition_lower = condition.lower()
        
        # 기술 스택별 세분화된 임계값 (실제 테스트 결과 기반 최적화)
        tech_thresholds = {
            # 백엔드 기술 스택 (충돌 방지 - 매우 엄격)
            'java': 0.75, 'kotlin': 0.75, 'spring': 0.75,
            'python': 0.62, 'fastapi': 0.62, 'django': 0.62,  # 약간 완화
            'node.js': 0.70, 'express': 0.70,
            
            # 프론트엔드 기술 스택 (충돌 방지 - 매우 엄격)
            'react': 0.75, 'next.js': 0.75, 'typescript': 0.75,
            'vue.js': 0.70, 'angular': 0.70,
            'flutter': 0.70,
            
            # 모바일 개발 (충돌 방지 - 매우 엄격)
            'android': 0.75, 'ios': 0.75,
            
            # 데이터베이스 (더 완화)
            'mysql': 0.55, 'postgresql': 0.55, 'mongodb': 0.55,
            
            # 클라우드/인프라 (현재 적절)
            'aws': 0.65, 'gcp': 0.65, 'azure': 0.65,
            'docker': 0.65, 'kubernetes': 0.70,
            
            # AI/ML (완화)
            'tensorflow': 0.62, 'pytorch': 0.62, 'opencv': 0.62,
            'langchain': 0.62, 'langgraph': 0.62
        }
        
        # 가장 높은 임계값 찾기
        max_threshold = 0.60  # 기본값
        matched_techs = []
        
        for tech, threshold in tech_thresholds.items():
            if tech in condition_lower:
                max_threshold = max(max_threshold, threshold)
                matched_techs.append(tech)
        
        # 로깅
        if matched_techs:
            logger.info(f"Dynamic threshold applied: {matched_techs} → {max_threshold:.2f} for condition: {condition[:50]}...")
        
        return max_threshold
    
    def _calculate_section_score_by_sentences(self, job: JobPosting, resume: Resume, section: str) -> dict:
        """섹션별 문장 단위 매칭 점수 계산"""
        try:
            # 공고의 해당 섹션 문장들 가져오기
            job_sentences = self._get_job_sentences_by_section(job, section)
            if not job_sentences:
                return {"score": 0.0, "evidence": {"matched": [], "missing": [], "detailed_analysis": []}}
            
            # 이력서 문장들 가져오기
            resume_sentences, resume_embeddings, resume_sections = self.scoring._get_cached_sentences(resume)
            
            # 문장 단위 매칭 분석
            detailed_analysis = []
            matched_conditions = []
            missing_conditions = []
            
            for condition in job_sentences:
                best_sim, best_sentence = self.scoring._best_sentence_match(condition, resume_sentences, resume_embeddings)
                
                # 임계값 설정 (조건별 세분화)
                threshold = self._get_dynamic_threshold(condition, section)
                
                matched = best_sim >= threshold
                analysis = {
                    'condition': condition,
                    'matched': matched,
                    'similarity_score': best_sim,
                    'matched_sentence': best_sentence,
                    'matched_section': resume_sections[resume_sentences.index(best_sentence)] if best_sentence in resume_sentences else 'unknown',
                    'match_type': 'semantic' if matched else 'none',
                    'threshold_used': threshold
                }
                
                # 상세 로깅
                logger.info(f"Condition matching: '{condition[:40]}...' → {best_sim:.3f} vs {threshold:.2f} = {'MATCH' if matched else 'NO MATCH'}")
                if not matched and best_sim > 0.5:
                    logger.warning(f"Near miss: {condition[:40]}... (score: {best_sim:.3f}, threshold: {threshold:.2f})")
                
                detailed_analysis.append(analysis)
                
                if best_sim >= threshold:
                    matched_conditions.append(condition)
                else:
                    missing_conditions.append(condition)
            
            # 점수 계산 (부분점수 허용하되 더 엄격하게)
            if detailed_analysis:
                if section == "required":
                    # 자격요건: 유사도에 완전 비례한 점수 (0.7=100%, 0.35=50%, 0.0=0%)
                    scores = []
                    for d in detailed_analysis:
                        if d['matched']:
                            scores.append(1.0)
                        else:
                            sim = d['similarity_score']
                            # 0.6을 100%로 하는 선형 비례 점수 (부분점수 가중치 50% 감소)
                            proportional_score = min(1.0, sim / 0.60) * 0.5
                            scores.append(proportional_score)
                else:
                    # 우대조건/경력: 부분 점수 허용 (더 엄격하게)
                    scores = [1.0 if d['matched'] else max(0.0, (d['similarity_score'] - 0.55) / (0.65 - 0.55)) * 0.5 for d in detailed_analysis]
                section_score = sum(scores) / len(scores)
            else:
                section_score = 0.0
            
            return {
                "score": section_score,
                "evidence": {
                    "matched": matched_conditions,
                    "missing": missing_conditions,
                    "detailed_analysis": detailed_analysis,
                    "match_rate": f"{len(matched_conditions)}/{len(job_sentences)}"
                }
            }
            
        except Exception as e:
            logger.error(f"Section score calculation failed for {section}: {e}")
            return {"score": 0.0, "evidence": {"matched": [], "missing": [], "detailed_analysis": []}}
    
    def _get_job_sentences_by_section(self, job: JobPosting, section: str) -> list:
        """공고의 특정 섹션 문장들 가져오기"""
        try:
            from app.models.sentences import JobSentence
            db = job._sa_instance_state.session
            if not db:
                return []
            
            rows = db.query(JobSentence).filter(
                JobSentence.job_id == job.id,
                JobSentence.section == section
            ).order_by(JobSentence.idx.asc()).all()
            
            return [row.text for row in rows]
        except Exception as e:
            logger.warning(f"Failed to get job sentences for section {section}: {e}")
            return []
    
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
        
        # 8. 상세 매칭 분석
        required_conditions = job.requirements.get('required', []) if job.requirements else []
        preferred_conditions = job.requirements.get('preferred', []) if job.requirements else []
        resume_skills = set((resume.extracted_skills or []))
        
        required_analysis = self.scoring._analyze_condition_matching(required_conditions, resume_skills, resume=resume, section="required")
        preferred_analysis = self.scoring._analyze_condition_matching(preferred_conditions, resume_skills, resume=resume, section="preferred")
        
        # 9. 매칭 근거 생성
        matching_evidence = {
            "required_skills": {
                "matched": required_analysis["matched"],
                "missing": required_analysis["missing"],
                "match_rate": required_analysis["match_rate"],
                "score": required_analysis["score"],
                "detailed_analysis": required_analysis["detailed_analysis"]
            },
            "preferred_skills": {
                "matched": preferred_analysis["matched"],
                "missing": preferred_analysis["missing"],
                "match_rate": preferred_analysis["match_rate"],
                "score": preferred_analysis["score"],
                "detailed_analysis": preferred_analysis["detailed_analysis"]
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
