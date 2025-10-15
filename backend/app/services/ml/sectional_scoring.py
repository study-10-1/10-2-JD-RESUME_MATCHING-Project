"""
Sectional Scoring Service - 섹션별 임베딩 기반 점수 계산
"""
import numpy as np
from typing import Dict, Any
from app.models.job import JobPosting
from app.models.resume import Resume
from app.core.config import settings
from app.core.logging import logger


class SectionalScoringService:
    """섹션별 임베딩 기반 점수 계산 서비스"""
    
    def __init__(self):
        self.weights = settings.SECTIONAL_WEIGHTS
    
    def calculate_sectional_score(
        self,
        job: JobPosting,
        resume: Resume
    ) -> Dict[str, Any]:
        """
        섹션별 임베딩을 사용한 상세 점수 계산
        
        Returns:
            {
                "required_match": 0.85,  # 자격요건 매칭
                "preferred_match": 0.65,  # 우대조건 매칭
                "experience_match": 0.75,  # 경력 매칭
                "overall_similarity": 0.70,  # 전체 유사도
                "final_score": 0.78
            }
        """
        try:
            scores = {}
            
            # 1. 자격요건 매칭 (가장 중요!)
            required_score = self._calculate_required_match(job, resume)
            scores['required_match'] = required_score
            
            # 2. 우대조건 매칭
            preferred_score = self._calculate_preferred_match(job, resume)
            scores['preferred_match'] = preferred_score
            
            # 3. 경력/프로젝트 매칭
            experience_score = self._calculate_experience_match(job, resume)
            scores['experience_match'] = experience_score
            
            # 4. 전체 유사도 (기존 방식)
            overall_score = self._calculate_overall_similarity(job, resume)
            scores['overall_similarity'] = overall_score
            
            # 5. 최종 점수 계산 (튜닝된 가중치 사용)
            final_score = (
                required_score * self.weights["required"] +      # 자격요건 50%
                preferred_score * self.weights["preferred"] +    # 우대조건 25%
                experience_score * self.weights["experience"] +  # 경력 10%
                overall_score * self.weights["overall"]          # 전체 유사도 10%
            )
            
            scores['final_score'] = final_score
            
            logger.info(f"Sectional scoring: required={required_score:.2f}, "
                       f"preferred={preferred_score:.2f}, "
                       f"experience={experience_score:.2f}, "
                       f"final={final_score:.2f}")
            
            return scores
            
        except Exception as e:
            logger.error(f"Error in sectional scoring: {e}")
            return {
                "required_match": 0.5,
                "preferred_match": 0.5,
                "experience_match": 0.5,
                "overall_similarity": 0.5,
                "final_score": 0.5
            }
    
    def _calculate_required_match(
        self,
        job: JobPosting,
        resume: Resume
    ) -> float:
        """자격요건 매칭 점수"""
        try:
            # 임베딩이 있으면 사용
            if job.required_embedding is not None and resume.skills_embedding is not None:
                job_req_emb = np.frombuffer(job.required_embedding, dtype=np.float32)
                resume_skills_emb = np.frombuffer(resume.skills_embedding, dtype=np.float32)
                
                # 코사인 유사도
                similarity = np.dot(job_req_emb, resume_skills_emb) / (
                    np.linalg.norm(job_req_emb) * np.linalg.norm(resume_skills_emb)
                )
                
                # 키워드 매칭도 함께 고려
                keyword_score = self._keyword_match(
                    job.requirements.get('required', []) if job.requirements else [],
                    resume.extracted_skills or []
                )
                
                # 임베딩(60%) + 키워드(40%)
                return float(similarity * 0.6 + keyword_score * 0.4)
            
            # 임베딩이 없으면 키워드만
            else:
                return self._keyword_match(
                    job.requirements.get('required', []) if job.requirements else [],
                    resume.extracted_skills or []
                )
                
        except Exception as e:
            logger.error(f"Error calculating required match: {e}")
            return 0.5
    
    def _calculate_preferred_match(
        self,
        job: JobPosting,
        resume: Resume
    ) -> float:
        """우대조건 매칭 점수"""
        try:
            if job.preferred_embedding is not None and resume.skills_embedding is not None:
                job_pref_emb = np.frombuffer(job.preferred_embedding, dtype=np.float32)
                resume_skills_emb = np.frombuffer(resume.skills_embedding, dtype=np.float32)
                
                similarity = np.dot(job_pref_emb, resume_skills_emb) / (
                    np.linalg.norm(job_pref_emb) * np.linalg.norm(resume_skills_emb)
                )
                
                keyword_score = self._keyword_match(
                    job.requirements.get('preferred', []) if job.requirements else [],
                    resume.extracted_skills or []
                )
                
                return float(similarity * 0.6 + keyword_score * 0.4)
            
            else:
                return self._keyword_match(
                    job.requirements.get('preferred', []) if job.requirements else [],
                    resume.extracted_skills or []
                )
                
        except Exception as e:
            logger.error(f"Error calculating preferred match: {e}")
            return 0.5
    
    def _calculate_experience_match(
        self,
        job: JobPosting,
        resume: Resume
    ) -> float:
        """경력/프로젝트 매칭 점수"""
        try:
            if job.description_embedding is not None:
                # 경력 임베딩이 있으면 사용
                if resume.experience_embedding is not None:
                    job_desc_emb = np.frombuffer(job.description_embedding, dtype=np.float32)
                    resume_exp_emb = np.frombuffer(resume.experience_embedding, dtype=np.float32)
                    
                    exp_similarity = np.dot(job_desc_emb, resume_exp_emb) / (
                        np.linalg.norm(job_desc_emb) * np.linalg.norm(resume_exp_emb)
                    )
                    
                    # 프로젝트 임베딩도 고려
                    if resume.projects_embedding is not None:
                        resume_proj_emb = np.frombuffer(resume.projects_embedding, dtype=np.float32)
                        proj_similarity = np.dot(job_desc_emb, resume_proj_emb) / (
                            np.linalg.norm(job_desc_emb) * np.linalg.norm(resume_proj_emb)
                        )
                        
                        # 경력(70%) + 프로젝트(30%)
                        return float(exp_similarity * 0.7 + proj_similarity * 0.3)
                    
                    return float(exp_similarity)
                
                # 프로젝트만 있는 경우
                elif resume.projects_embedding is not None:
                    job_desc_emb = np.frombuffer(job.description_embedding, dtype=np.float32)
                    resume_proj_emb = np.frombuffer(resume.projects_embedding, dtype=np.float32)
                    
                    proj_similarity = np.dot(job_desc_emb, resume_proj_emb) / (
                        np.linalg.norm(job_desc_emb) * np.linalg.norm(resume_proj_emb)
                    )
                    
                    return float(proj_similarity)
            
            # 임베딩이 없으면 기본값
            return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating experience match: {e}")
            return 0.5
    
    def _calculate_overall_similarity(
        self,
        job: JobPosting,
        resume: Resume
    ) -> float:
        """전체 유사도 (기존 방식)"""
        try:
            if job.embedding is not None and resume.embedding is not None:
                job_emb = np.frombuffer(job.embedding, dtype=np.float32)
                resume_emb = np.frombuffer(resume.embedding, dtype=np.float32)
                
                similarity = np.dot(job_emb, resume_emb) / (
                    np.linalg.norm(job_emb) * np.linalg.norm(resume_emb)
                )
                
                return float(similarity)
            
            return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating overall similarity: {e}")
            return 0.5
    
    def _keyword_match(
        self,
        requirements: list,
        skills: list
    ) -> float:
        """키워드 매칭 점수"""
        if not requirements:
            return 0.5
        
        # 간단한 키워드 추출
        common_skills = {
            "python", "java", "javascript", "typescript", "react", "vue", "angular",
            "django", "flask", "fastapi", "spring", "nodejs", "express",
            "mysql", "postgresql", "mongodb", "redis", "aws", "docker", "kubernetes",
            "git", "linux", "kotlin", "android", "ios", "swift"
        }
        
        # requirements에서 스킬 추출
        req_skills = set()
        for req in requirements:
            req_lower = str(req).lower()
            for skill in common_skills:
                if skill in req_lower:
                    req_skills.add(skill)
        
        if not req_skills:
            return 0.5
        
        # 이력서 스킬과 매칭
        resume_skills = {s.lower() for s in skills}
        matched = req_skills & resume_skills
        
        return len(matched) / len(req_skills) if req_skills else 0.5

