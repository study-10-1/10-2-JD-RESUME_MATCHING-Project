"""
Penalty Calculation Service - 페널티 계산
"""
from typing import Dict
from app.models.job import JobPosting
from app.models.resume import Resume
from app.core.config import settings
from app.core.logging import logger


class PenaltyService:
    """페널티 계산 서비스"""
    
    def calculate_penalties(
        self,
        job: JobPosting,
        resume: Resume
    ) -> Dict[str, float]:
        """
        모든 페널티 계산
        
        Returns:
            {
                "experience_level_mismatch": -0.30,
                "required_skill_critical_missing": -0.20
            }
        """
        penalties = {}
        
        # 1. 경력 수준 불일치 페널티
        if self.detect_experience_level_mismatch(job, resume):
            penalties["experience_level_mismatch"] = settings.DEFAULT_PENALTIES["experience_level_mismatch"]
            logger.debug(f"Applied experience level mismatch penalty: -30%")
        
        # 2. 필수 조건 대량 미충족 페널티 (50% 이상 미충족)
        missing_ratio = self.calculate_required_skill_missing_ratio(job, resume)
        if missing_ratio > 0.5:
            penalty_value = 0.25 * missing_ratio  # 최대 25% 차감
            penalties["required_skill_critical_missing"] = penalty_value
            logger.debug(f"Applied critical missing penalty: {penalty_value:.1%} ({missing_ratio:.0%} missing)")
        
        # 3. 경력 연수 크게 부족 페널티 (강화)
        if self.detect_experience_significantly_lacking(job, resume):
            penalties["experience_significantly_lacking"] = settings.DEFAULT_PENALTIES["experience_significantly_lacking"]
            logger.debug(f"Applied experience lacking penalty: {settings.DEFAULT_PENALTIES['experience_significantly_lacking']:.1%}")

        # 4. 경력 관련 페널티 상한 적용 (총합 15점 내)
        experience_keys = [
            "experience_level_mismatch",
            "experience_significantly_lacking",
        ]
        exp_sum = sum(penalties.get(k, 0.0) for k in experience_keys)
        cap = settings.EXPERIENCE_PENALTY_CAP
        if exp_sum > cap and exp_sum > 0:
            scale = cap / exp_sum
            for k in experience_keys:
                if k in penalties:
                    penalties[k] = round(penalties[k] * scale, 6)
            logger.debug(f"Scaled experience penalties by {scale:.3f} to respect cap {cap:.2f}")

        return penalties
    
    def detect_experience_level_mismatch(
        self,
        job: JobPosting,
        resume: Resume
    ) -> bool:
        """
        경력 수준 불일치 감지
        
        예: Junior 공고에 Senior 지원자 (over-qualified)
             Senior 공고에 Junior 지원자 (under-qualified)
        """
        if not job.experience_level:
            return False
        
        candidate_years = resume.extracted_experience_years or 0
        
        level_ranges = {
            "junior": (0, 3),
            "mid": (3, 7),
            "senior": (7, 100)
        }
        
        min_years, max_years = level_ranges.get(job.experience_level.lower(), (0, 100))
        
        # 범위를 크게 벗어나는 경우에만 페널티
        # Under-qualified: 최소 요구의 50% 미만
        # Over-qualified: 최대 범위의 150% 초과
        if candidate_years < min_years * 0.5:
            return True  # 경력 많이 부족
        elif candidate_years > max_years * 1.5:
            return True  # 경력 과다 (over-qualified)
        
        return False
    
    def detect_experience_significantly_lacking(
        self,
        job: JobPosting,
        resume: Resume
    ) -> bool:
        """
        경력 연수 크게 부족 감지 (더 엄격하게)
        """
        required_years = job.min_experience_years or 0
        candidate_years = resume.extracted_experience_years or 0
        
        if required_years == 0:
            return False
        
        # 요구 경력의 70% 미만 (더 엄격하게)
        if candidate_years < required_years * 0.7:
            return True
        
        return False
    
    def calculate_required_skill_missing_ratio(
        self,
        job: JobPosting,
        resume: Resume
    ) -> float:
        """
        필수 조건 미충족 비율 계산
        
        Returns:
            0.0 ~ 1.0 (0 = 모두 충족, 1 = 모두 미충족)
        """
        requirements = job.requirements or {}
        required_conditions = requirements.get('required', [])
        
        if not required_conditions:
            return 0.0
        
        resume_skills_lower = {s.lower() for s in (resume.extracted_skills or [])}
        
        missing_count = 0
        for req in required_conditions:
            req_lower = req.lower()
            # 간단한 키워드 매칭
            found = any(skill in req_lower or req_lower in skill for skill in resume_skills_lower)
            if not found:
                missing_count += 1
        
        return missing_count / len(required_conditions)
    
    def detect_domain_mismatch(
        self,
        job: JobPosting,
        resume: Resume
    ) -> bool:
        """
        도메인 불일치 감지
        
        TODO: 도메인 정보 파싱 후 구현
        """
        # 도메인 정보가 파싱되면 구현
        return False
    
    def detect_role_mismatch(
        self,
        job: JobPosting,
        resume: Resume
    ) -> bool:
        """
        역할 불일치 감지
        
        예: Backend 공고에 Frontend 지원자
        """
        # TODO: 역할 정보 추출 후 구현
        return False
