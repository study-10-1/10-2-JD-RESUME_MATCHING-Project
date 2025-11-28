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
from app.models.sentences import ResumeSentence, JobSentence
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
                company_info = None
                if job.company:
                    company_info = {
                        "name": job.company.name,
                        "website": job.company.website
                    }
                
                # 기술 스택 정보 추출
                skills_info = self._extract_skills_info(job, matching_result.matching_evidence)
                
                result_dict = {
                    "matching_id": self._generate_matching_id(str(resume.id), str(job.id)),
                    "job_id": str(job.id),
                    "job_title": job.title,
                    "company_name": job.company.name if job.company else None,
                    "company": company_info,  # 회사 정보 (이름, 웹사이트) 추가
                    "location": job.location,
                    "experience_level": job.experience_level,
                    "job_url": job.external_url,  # 공고 URL 추가
                    "overall_score": round(float(matching_result.overall_score) * 100, 1),  # 백분율로 변환
                    "grade": matching_result.grade,
                    "category_scores": self._convert_category_scores_to_percentage(matching_result.category_scores),
                    "matching_evidence": matching_result.matching_evidence,
                    "penalties": matching_result.penalties,
                    "skills": skills_info  # 기술 스택 정보 추가
                }
                
                results.append(result_dict)
                
            except Exception as e:
                logger.error(f"Error calculating match for job {job.id}: {e}")
                continue
        
        # 4. 전체 점수로 재정렬
        results.sort(key=lambda x: x["overall_score"], reverse=True)
        
        # 5. 상위 n개만 반환 (limit 파라미터 적용)
        total_count = len(results)
        limited_results = results[:limit]
        
        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"Matching completed in {processing_time}ms: {len(limited_results)}/{total_count} results returned (limit={limit})")
        
        # 전체 매칭 수를 결과에 포함 (API에서 사용)
        return limited_results
    
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
        
        logger.info(
            f"Weighted components: required={category_scores['required_match']['score']:.3f}*{category_scores['required_match']['weight']:.2f}, "
            f"preferred={category_scores['preferred_match']['score']:.3f}*{category_scores['preferred_match']['weight']:.2f}, "
            f"experience={category_scores['experience_match']['score']:.3f}*{category_scores['experience_match']['weight']:.2f}, "
            f"overall={category_scores['overall_similarity']['score']:.3f}*{category_scores['overall_similarity']['weight']:.2f} → sum={weighted_sum:.3f}"
        )
        
        # 6. 자격요건 매칭 실패 시 50% 감점 (엄격성 강화)
        dampened = False
        if required_score["score"] < 0.5:  # 50% 미만이면 실패로 간주
            weighted_sum_before = weighted_sum
            weighted_sum *= 0.5  # 50% 감점
            dampened = True
            logger.info(f"Dampening applied (required<{0.5}): {weighted_sum_before:.3f} → {weighted_sum:.3f}")
        else:
            logger.info("No dampening (required>=0.5)")
        
        # 7. 페널티 계산
        penalties = self.penalty.calculate_penalties(job, resume)
        penalty_sum = sum(penalties.values())
        logger.info(f"Penalties: {penalties} (sum={penalty_sum:.3f})")
        final_score = max(0.0, weighted_sum - penalty_sum)
        logger.info(f"Final score: max(0, {weighted_sum:.3f} - {penalty_sum:.3f}) = {final_score:.3f}")
        
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
            },
            "_debug": {
                "raw_weighted_sum": float(
                    category_scores['required_match']['score'] * category_scores['required_match']['weight'] +
                    category_scores['preferred_match']['score'] * category_scores['preferred_match']['weight'] +
                    category_scores['experience_match']['score'] * category_scores['experience_match']['weight'] +
                    category_scores['overall_similarity']['score'] * category_scores['overall_similarity']['weight']
                ),
                "dampened": bool(dampened),
                "weighted_after_dampening": float(weighted_sum),
                "penalty_sum": float(penalty_sum),
                "final_score": float(final_score)
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
        """전체 텍스트 유사도 계산 (최적화: DB 임베딩 우선 사용)"""
        try:
            job_embedding = None
            resume_embedding = None
            
            # 1. 우선순위 1: DB에 저장된 전체 임베딩 사용 (가장 빠름)
            if job.embedding is not None:
                job_embedding = job.embedding
                logger.debug("Using job.embedding from DB")
            if resume.embedding is not None:
                resume_embedding = resume.embedding
                logger.debug("Using resume.embedding from DB")
            
            # 2. 우선순위 2: 문장 임베딩 평균 풀링 (빠름)
            if job_embedding is None:
                job_sentences = self.db.query(JobSentence).filter(
                    JobSentence.job_id == job.id
                ).all()
                if job_sentences:
                    # 모든 문장 임베딩을 평균
                    embeddings = [np.array(s.embedding) for s in job_sentences if s.embedding is not None]
                    if embeddings:
                        job_embedding = np.mean(embeddings, axis=0).tolist()
                        logger.debug(f"Using average of {len(embeddings)} job sentence embeddings")
            
            if resume_embedding is None:
                resume_sentences = self.db.query(ResumeSentence).filter(
                    ResumeSentence.resume_id == resume.id
                ).all()
                if resume_sentences:
                    # 모든 문장 임베딩을 평균
                    embeddings = [np.array(s.embedding) for s in resume_sentences if s.embedding is not None]
                    if embeddings:
                        resume_embedding = np.mean(embeddings, axis=0).tolist()
                        logger.debug(f"Using average of {len(embeddings)} resume sentence embeddings")
            
            # 3. 우선순위 3: 폴백 - 새로 생성 (느림, 최후의 수단)
            if job_embedding is None:
                job_text = f"{job.title} {job.description or ''} {job.requirements or ''} {job.qualifications or ''}"
                job_embedding = self.embedding_service.generate_embedding(job_text)
                logger.warning("Generated new job embedding (fallback)")
            
            if resume_embedding is None:
                parsed_data = resume.parsed_data or {}
                resume_text = f"{parsed_data.get('summary', '')} {parsed_data.get('work_experience', '')} {parsed_data.get('skills', '')} {parsed_data.get('projects', '')}"
                if not resume_text.strip():
                    resume_text = resume.raw_text or ""
                resume_embedding = self.embedding_service.generate_embedding(resume_text)
                logger.warning("Generated new resume embedding (fallback)")
            
            # 코사인 유사도 계산
            similarity = self.embedding_service.cosine_similarity(job_embedding, resume_embedding)
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"Overall similarity calculation failed: {e}")
            return 0.0

    def _evaluate_condition_with_composite_tech(
        self,
        condition: str,
        resume_sentences: List[str],
        resume_embeddings: List[list],
        condition_emb: List[float],
        section: str
    ) -> tuple:
        """
        복합 기술 조건 평가 (OR 조건)
        예: "MySQL, PostgreSQL" → 각각 개별 매칭 후 하나라도 매칭되면 True
        """
        import re
        
        # 기술 키워드 추출
        tech_keywords = [
            "python", "java", "kotlin", "javascript", "typescript",
            "react", "vue", "angular", "next.js", "nestjs", "express",
            "django", "fastapi", "spring", "spring boot", "springboot",
            "mysql", "postgresql", "mongodb", "redis", "neo4j",
            "aws", "gcp", "azure", "docker", "kubernetes", "k8s",
            "tensorflow", "pytorch", "opencv", "langchain", "langgraph", "llm", "ml", "ai",
            "node.js", "nodejs", "flutter", "android", "ios", "swift",
            # 데이터베이스 관련
            "rdbms", "database", "db", "데이터베이스",
            # AI/ML 관련
            "vectordb", "vector db", "rag", "agent", "fine-tuning", "finetuning",
            # 상태 관리/프론트엔드
            "zustand", "redux", "react query", "tanstack query",
            # 기타
            "rabbitmq", "kafka", "celery", "nginx"
        ]
        
        condition_lower = condition.lower()
        found_techs = []
        
        for tech in tech_keywords:
            pattern = r'\b' + re.escape(tech) + r'\b'
            if re.search(pattern, condition_lower):
                found_techs.append(tech)
        
        # 복합 조건인 경우 (2개 이상의 기술이 언급된 경우)
        if len(found_techs) >= 2:
            # 각 기술별로 개별 매칭 수행
            tech_matches = []
            tech_similarities = []
            tech_thresholds = []
            
            # 전체 조건에 대한 유사도 계산
            best_sim, best_sentence = self.scoring._best_sentence_match(
                condition,
                resume_sentences,
                resume_embeddings,
                condition_embedding=condition_emb
            )
            
            # 각 기술별로 검증
            resume_text_lower = " ".join(resume_sentences).lower()
            best_sentence_lower = best_sentence.lower() if best_sentence else ""
            
            for tech in found_techs:
                # 해당 기술에 대한 임계값 가져오기
                tech_threshold = self._get_dynamic_threshold(tech, section)
                
                # 기술이 이력서에 있는지 확인
                tech_in_resume = tech.lower() in resume_text_lower
                
                # 기술이 매칭된 문장에 있는지 확인
                tech_in_matched_sentence = tech.lower() in best_sentence_lower
                
                # 기술 키워드 검증: 매칭된 문장에 기술 키워드가 있어야 함 (엄격한 검증)
                if tech_in_matched_sentence:
                    # 매칭된 문장에 기술 키워드가 있으면 유사도 확인
                    tech_matched = best_sim >= tech_threshold
                else:
                    # 매칭된 문장에 기술 키워드가 없으면 무조건 False Positive로 차단
                    # 이력서 전체에 있어도 매칭된 문장에 없으면 의미가 없음
                    tech_matched = False
                    logger.debug(f"Tech '{tech}' not in matched sentence, rejecting: {best_sentence[:50] if best_sentence else 'None'}...")
                
                tech_matches.append(tech_matched)
                tech_similarities.append(best_sim)
                tech_thresholds.append(tech_threshold)
            
            # OR 조건: 하나라도 매칭되면 True
            matched = any(tech_matches)
            
            # 가장 높은 유사도와 임계값 사용
            best_sim = max(tech_similarities) if tech_similarities else 0.0
            threshold = min(tech_thresholds) if tech_thresholds else 0.6  # 가장 낮은 임계값 사용 (OR 조건이므로)
            
            if matched:
                logger.info(f"Composite condition matched (OR): {found_techs} → {matched} (best_sim: {best_sim:.3f}, threshold: {threshold:.3f})")
            else:
                logger.warning(f"Composite condition rejected: {found_techs} (best_sim: {best_sim:.3f}, threshold: {threshold:.3f}, matched_sentence: {best_sentence[:50] if best_sentence else 'None'}...)")
            
            return matched, best_sim, best_sentence, threshold
        
        # 단일 기술이거나 기술이 없는 경우 기존 로직 사용
        best_sim, best_sentence = self.scoring._best_sentence_match(
            condition,
            resume_sentences,
            resume_embeddings,
            condition_embedding=condition_emb
        )
        
        threshold = self._get_dynamic_threshold(condition, section)
        matched = best_sim >= threshold
        
        # 기술 키워드 검증: 조건에 기술 키워드가 있으면 매칭된 문장에도 해당 키워드가 있어야 함
        if matched and found_techs:
            # 매칭된 문장에 기술 키워드가 있는지 확인
            best_sentence_lower = best_sentence.lower() if best_sentence else ""
            tech_in_matched_sentence = any(
                tech.lower() in best_sentence_lower 
                for tech in found_techs
            )
            
            # 기술 키워드가 매칭된 문장에 없으면 무조건 False Positive로 차단
            if not tech_in_matched_sentence:
                logger.warning(
                    f"False Positive detected: '{condition[:50]}...' "
                    f"(tech: {found_techs}, sim: {best_sim:.3f}, threshold: {threshold:.3f}) "
                    f"matched to: '{best_sentence[:50]}...' (tech not in matched sentence)"
                )
                matched = False
        
        return matched, best_sim, best_sentence, threshold
    
    def _get_dynamic_threshold(self, condition: str, section: str) -> float:
        """조건별 동적 임계값 설정"""
        condition_lower = condition.lower()
        
        # 기술 스택별 세분화된 임계값 (2025-11-18 종합 튜닝 결과 반영)
        tech_thresholds = {
            # 백엔드 기술 스택 (튜닝 결과 반영)
            'java': 0.56, 'spring': 0.56,  # 0.64 → 0.56 (분석: 0.563 추천)
            'kotlin': 0.55,  # 0.64 → 0.55 (분석: 0.550 추천)
            'python': 0.56,  # 0.61 → 0.56 (분석: 0.562 추천)
            'fastapi': 0.55, 'django': 0.55,  # 0.61 → 0.55 (분석: 0.550 추천)
            'node.js': 0.56, 'express': 0.56,  # 0.62 → 0.56 (분석: 0.562 추천)
            'spring boot': 0.56,  # 0.60 → 0.56 (분석: 0.562 추천)
            
            # 프론트엔드 기술 스택 (튜닝 결과 반영)
            'react': 0.59, 'typescript': 0.59,  # 0.66 → 0.59 (분석: 0.593 추천)
            'next.js': 0.59,  # 0.66 → 0.59 (분석: 0.590 추천)
            'vue': 0.60, 'vue.js': 0.60,  # 0.62 → 0.60 (분석: 0.597 추천)
            'angular': 0.62,  # 유지
            'flutter': 0.62,  # 유지
            'javascript': 0.56,  # 0.60 → 0.56 (분석: 0.564 추천)
            
            # 모바일 개발 (튜닝 결과 반영)
            'android': 0.55,  # 0.70 → 0.55 (분석: 0.550 추천, 최우선 조정)
            'ios': 0.70,  # 유지 (데이터 부족)
            
            # 데이터베이스 (튜닝 결과 반영)
            'mysql': 0.55, 'postgresql': 0.55,  # 0.61 → 0.55 (분석: 0.550 추천)
            'mongodb': 0.61,  # 유지
            
            # 클라우드/인프라 (학습 데이터 기반 정밀 조정)
            'aws': 0.59, 'gcp': 0.59,  # 0.65 → 0.59 (학습 데이터: 0.592 추천)
            'azure': 0.65,  # 유지
            'docker': 0.58,  # 유지
            'kubernetes': 0.65,  # 유지
            
            # AI/ML (튜닝 결과 반영)
            'tensorflow': 0.62, 'pytorch': 0.62, 'opencv': 0.62,  # 유지
            'langchain': 0.62, 'langgraph': 0.62,  # 유지
            'llm': 0.55, 'ml': 0.55, 'ai': 0.55,  # 0.60 → 0.55 (분석: 0.550 추천)
            
            # API (추가)
            'api': 0.63, 'rest': 0.63, 'restful': 0.63,  # 유지
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
            # 공고의 해당 섹션 문장 텍스트와 임베딩 가져오기
            job_sentences, job_embeddings = self._get_job_sentences_by_section(job, section)
            if not job_sentences:
                return {"score": 0.0, "evidence": {"matched": [], "missing": [], "detailed_analysis": []}}
            
            # 이력서 문장들 가져오기
            resume_sentences, resume_embeddings, resume_sections = self.scoring._get_cached_sentences(resume)
            
            # 문장 단위 매칭 분석
            detailed_analysis = []
            matched_conditions = []
            missing_conditions = []
            
            for idx, condition in enumerate(job_sentences):
                # DB 임베딩이 있으면 사용, 없으면 None 전달 (함수 내에서 생성)
                condition_emb = job_embeddings[idx] if idx < len(job_embeddings) else None
                
                # 복합 조건 처리: 여러 기술이 함께 언급된 경우 OR 조건으로 평가
                matched, best_sim, best_sentence, threshold = self._evaluate_condition_with_composite_tech(
                    condition,
                    resume_sentences,
                    resume_embeddings,
                    condition_emb,
                    section
                )
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
    
    def _get_job_sentences_by_section(self, job: JobPosting, section: str) -> tuple:
        """공고의 특정 섹션 문장 텍스트와 임베딩 가져오기
        
        Returns:
            (texts: List[str], embeddings: List[List[float]])
        """
        try:
            from app.models.sentences import JobSentence
            db = job._sa_instance_state.session
            if not db:
                return [], []
            
            rows = db.query(JobSentence).filter(
                JobSentence.job_id == job.id,
                JobSentence.section == section
            ).order_by(JobSentence.idx.asc()).all()
            
            texts = []
            embeddings = []
            
            for row in rows:
                texts.append(row.text)
                # DB에 임베딩이 있으면 사용, 없으면 None
                if row.embedding is not None:
                    # pgvector Vector 타입을 리스트로 변환 (numpy array로 먼저 변환 후 리스트로)
                    try:
                        import numpy as np
                        emb_array = np.array(row.embedding, dtype='float32')
                        embeddings.append(emb_array.tolist())
                    except Exception as e:
                        logger.warning(f"Failed to convert embedding to list: {e}")
                        embeddings.append(None)
                else:
                    embeddings.append(None)
            
            return texts, embeddings
        except Exception as e:
            logger.warning(f"Failed to get job sentences for section {section}: {e}")
            return [], []
    
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
    
    def _extract_skills_info(self, job: JobPosting, matching_evidence: dict) -> dict:
        """
        공고에서 요구하는 기술 스택과 매칭된 기술 스택 추출
        matching_evidence의 detailed_analysis를 활용하여 실제 매칭된 조건에서 기술 추출
        
        Returns:
            {
                "required": ["Java", "Spring", "MySQL"],  # 공고에서 요구하는 기술
                "preferred": ["AWS", "Docker"],  # 공고에서 우대하는 기술
                "matched_required": ["Java", "Spring"],  # 매칭된 필수 기술
                "matched_preferred": ["AWS"],  # 매칭된 우대 기술
                "missing_required": ["MySQL"],  # 누락된 필수 기술
                "missing_preferred": ["Docker"]  # 누락된 우대 기술
            }
        """
        import re
        
        # 기술 키워드 목록 (기존 _evaluate_condition_with_composite_tech와 동일)
        tech_keywords = [
            "python", "java", "kotlin", "javascript", "typescript",
            "react", "vue", "angular", "next.js", "nestjs", "express",
            "django", "fastapi", "spring", "spring boot", "springboot",
            "mysql", "postgresql", "mongodb", "redis", "neo4j",
            "aws", "gcp", "azure", "docker", "kubernetes", "k8s",
            "tensorflow", "pytorch", "opencv", "langchain", "langgraph", "llm", "ml", "ai",
            "node.js", "nodejs", "flutter", "android", "ios", "swift",
            "rdbms", "database", "db", "데이터베이스",
            "vectordb", "vector db", "rag", "agent", "fine-tuning", "finetuning",
            "zustand", "redux", "react query", "tanstack query",
            "rabbitmq", "kafka", "celery", "nginx"
        ]
        
        def extract_techs_from_text(text: str) -> set:
            """텍스트에서 기술 키워드 추출"""
            if not text:
                return set()
            text_lower = text.lower()
            found = set()
            for tech in tech_keywords:
                pattern = r'\b' + re.escape(tech) + r'\b'
                if re.search(pattern, text_lower):
                    found.add(tech)
            return found
        
        # 1. 공고의 requirements에서 전체 기술 추출 (모든 조건 분석)
        required_skills = set()
        preferred_skills = set()
        
        if job.requirements:
            required_conditions = job.requirements.get('required', [])
            preferred_conditions = job.requirements.get('preferred', [])
            
            # 모든 조건에서 기술 추출
            for condition in required_conditions:
                required_skills.update(extract_techs_from_text(str(condition)))
            
            for condition in preferred_conditions:
                preferred_skills.update(extract_techs_from_text(str(condition)))
        
        # parsed_skills도 추가
        if job.parsed_skills:
            for skill in job.parsed_skills:
                required_skills.update(extract_techs_from_text(str(skill)))
        
        # 2. matching_evidence의 detailed_analysis를 활용하여 실제 매칭된 기술 추출
        matched_required = set()
        matched_preferred = set()
        
        if matching_evidence:
            # required_skills의 detailed_analysis에서 매칭된 조건 추출
            required_evidence = matching_evidence.get('required_skills', {})
            if required_evidence:
                detailed_analysis = required_evidence.get('detailed_analysis', [])
                for analysis in detailed_analysis:
                    condition = analysis.get('condition', '')
                    matched = analysis.get('matched', False)
                    matched_sentence = analysis.get('matched_sentence', '')
                    
                    # 매칭된 조건에서 기술 추출
                    if matched:
                        # 조건 자체에서 기술 추출
                        matched_required.update(extract_techs_from_text(str(condition)))
                        # 매칭된 문장에서도 기술 추출 (더 정확)
                        if matched_sentence:
                            matched_required.update(extract_techs_from_text(str(matched_sentence)))
                
                # matched 리스트에서도 추출 (fallback)
                matched_conditions = required_evidence.get('matched', [])
                for condition in matched_conditions:
                    matched_required.update(extract_techs_from_text(str(condition)))
            
            # preferred_skills의 detailed_analysis에서 매칭된 조건 추출
            preferred_evidence = matching_evidence.get('preferred_skills', {})
            if preferred_evidence:
                detailed_analysis = preferred_evidence.get('detailed_analysis', [])
                for analysis in detailed_analysis:
                    condition = analysis.get('condition', '')
                    matched = analysis.get('matched', False)
                    matched_sentence = analysis.get('matched_sentence', '')
                    
                    # 매칭된 조건에서 기술 추출
                    if matched:
                        # 조건 자체에서 기술 추출
                        matched_preferred.update(extract_techs_from_text(str(condition)))
                        # 매칭된 문장에서도 기술 추출 (더 정확)
                        if matched_sentence:
                            matched_preferred.update(extract_techs_from_text(str(matched_sentence)))
                
                # matched 리스트에서도 추출 (fallback)
                matched_conditions = preferred_evidence.get('matched', [])
                for condition in matched_conditions:
                    matched_preferred.update(extract_techs_from_text(str(condition)))
        
        # 3. 누락된 기술 계산 (요구 기술 - 매칭된 기술)
        missing_required = required_skills - matched_required
        missing_preferred = preferred_skills - matched_preferred
        
        return {
            "required": sorted(list(required_skills)),
            "preferred": sorted(list(preferred_skills)),
            "matched_required": sorted(list(matched_required)),
            "matched_preferred": sorted(list(matched_preferred)),
            "missing_required": sorted(list(missing_required)),
            "missing_preferred": sorted(list(missing_preferred))
        }
    
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
