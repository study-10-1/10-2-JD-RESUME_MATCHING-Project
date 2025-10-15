"""
Scoring Service - 카테고리별 매칭 점수 계산
"""
from typing import Dict, Any, List, Set
from app.models.job import JobPosting
from app.models.resume import Resume
from app.core.config import settings
from app.core.logging import logger


class ScoringService:
    """점수 계산 서비스"""
    
    def calculate_skill_score(
        self,
        job: JobPosting,
        resume: Resume
    ) -> Dict[str, Any]:
        """
        기술 스킬 매칭 점수 계산
        필수 조건과 우대 조건을 구분하여 계산
        
        Returns:
            {
                "score": 0.85,
                "matched_required": ["python", "django"],
                "missing_required": ["kubernetes"],
                "matched_preferred": ["aws", "docker"],
                "missing_preferred": ["react"],
                "required_score": 0.67,
                "preferred_score": 0.40
            }
        """
        try:
            # 이력서의 보유 스킬
            resume_skills = set(resume.extracted_skills or [])
            resume_skills_lower = {s.lower() for s in resume_skills}
            
            # requirements에서 필수/우대 조건 추출
            requirements = job.requirements or {}
            required_conditions = requirements.get('required', [])
            preferred_conditions = requirements.get('preferred', [])
            
            # 공고의 parsed_skills도 활용
            job_skills = set(job.parsed_skills or [])
            
            # 1. 필수 조건 매칭 (더 중요 - 70% 가중치)
            required_skills = self._extract_skills_from_conditions(required_conditions)
            required_skills.update({s.lower() for s in job_skills})  # parsed_skills도 필수로 간주
            
            if required_skills:
                # 정확한 키워드 매칭
                matched_required = required_skills & resume_skills_lower
                missing_required = required_skills - resume_skills_lower
                
                # 의미적 매칭 추가 (키워드가 포함된 조건 찾기)
                semantic_matches = self._find_semantic_matches(required_conditions, resume_skills_lower)
                matched_required.update(semantic_matches)
                
                required_score = len(matched_required) / len(required_skills)
            else:
                matched_required = set()
                missing_required = set()
                required_score = 0.5  # 필수 조건 없으면 중립 점수
            
            # 2. 우대 조건 매칭 (추가 점수 - 30% 가중치)
            preferred_skills = self._extract_skills_from_conditions(preferred_conditions)
            
            if preferred_skills:
                # 정확한 키워드 매칭
                matched_preferred = preferred_skills & resume_skills_lower
                missing_preferred = preferred_skills - resume_skills_lower
                
                # 의미적 매칭 추가
                semantic_matches_pref = self._find_semantic_matches(preferred_conditions, resume_skills_lower)
                matched_preferred.update(semantic_matches_pref)
                
                preferred_score = len(matched_preferred) / len(preferred_skills)
            else:
                matched_preferred = set()
                missing_preferred = set()
                preferred_score = 0.0  # 우대 조건 없으면 0점 (영향 없음)
            
            # 3. 조건 개수에 따른 난이도 조정
            # 조건이 많을수록 충족하기 어려우므로 가중치 부여
            difficulty_factor = self._calculate_difficulty_factor(
                len(required_skills),
                len(preferred_skills)
            )
            
            # 4. 최종 점수 계산
            # 필수 70%, 우대 30%
            if required_skills:
                base_score = required_score * 0.7 + preferred_score * 0.3
                # 난이도 보정 적용
                final_score = base_score * (1 + difficulty_factor * 0.1)  # 최대 10% 보너스
            else:
                # 필수 조건이 없으면 우대 조건만으로 평가
                final_score = preferred_score if preferred_skills else 0.5
            
            # 4. 원래 표기로 복원 (UI 표시용) - 조건 단위로 중복 제거
            matched_required_original, missing_required_original = self._split_conditions_by_resume_match(
                required_conditions,
                resume_skills_lower
            )
            matched_preferred_original, missing_preferred_original = self._split_conditions_by_resume_match(
                preferred_conditions,
                resume_skills_lower
            )
            
            return {
                "score": min(final_score, 1.0),
                "matched_required": matched_required_original,
                "missing_required": missing_required_original,
                "matched_preferred": matched_preferred_original,
                "missing_preferred": missing_preferred_original,
                "required_score": round(required_score, 3),
                "preferred_score": round(preferred_score, 3),
                "total_required": len(required_skills),
                "total_preferred": len(preferred_skills),
                "difficulty_factor": round(difficulty_factor, 3),
                "match_rate": f"{len(matched_required)}/{len(required_skills)} 필수, {len(matched_preferred)}/{len(preferred_skills)} 우대"
            }
            
        except Exception as e:
            logger.error(f"Error calculating skill score: {e}")
            import traceback
            traceback.print_exc()
            return {
                "score": 0.5,
                "matched_required": [],
                "missing_required": [],
                "matched_preferred": [],
                "missing_preferred": [],
                "required_score": 0.5,
                "preferred_score": 0.0,
                "total_required": 0,
                "total_preferred": 0
            }
    
    def _find_semantic_matches(self, conditions: List[str], resume_skills: Set[str]) -> Set[str]:
        """
        의미적 매칭: 이력서 스킬이 공고 조건에 포함되어 있는지 확인
        
        Args:
            conditions: 공고 조건 리스트
            resume_skills: 이력서 스킬 세트 (소문자)
            
        Returns:
            매칭된 조건들의 세트
        """
        matched_conditions = set()
        
        # 스킬-조건 매핑 테이블 (더 포괄적으로)
        skill_mappings = {
            'python': ['python', '백엔드', '백엔드 개발', '웹 개발', '개발 경험', '웹 프론트엔드/백엔드', '서비스 개발'],
            'java': ['java', '백엔드', '백엔드 개발', '웹 개발', '개발 경험', '웹 프론트엔드/백엔드', '서비스 개발'],
            'django': ['django', '백엔드', '백엔드 개발', '웹 개발', '개발 경험', '웹 프론트엔드/백엔드', '서비스 개발'],
            'spring': ['spring', 'java', '백엔드', '백엔드 개발', '웹 개발', '개발 경험', '웹 프론트엔드/백엔드', '서비스 개발'],
            'spring boot': ['spring', 'java', '백엔드', '백엔드 개발', '웹 개발', '개발 경험', '웹 프론트엔드/백엔드', '서비스 개발'],
            'spring data jpa': ['spring', 'java', '백엔드', '백엔드 개발', '웹 개발', '개발 경험', '웹 프론트엔드/백엔드', '서비스 개발'],
            'react': ['react', '프론트엔드', '프론트엔드 개발', '웹 개발', '개발 경험', '웹 프론트엔드/백엔드'],
            'javascript': ['javascript', '프론트엔드', '프론트엔드 개발', '웹 개발', '개발 경험', '웹 프론트엔드/백엔드'],
            'aws': ['aws', '클라우드', '클라우드 환경', '클라우드 경험', 'aws, gcp, azure', '서비스 개발·운영'],
            'aws (ec2, s3)': ['aws', '클라우드', '클라우드 환경', '클라우드 경험', 'aws, gcp, azure', '서비스 개발·운영'],
            'docker': ['docker', '컨테이너', 'devops', '배포', '운영', '서비스 개발·운영'],
            'mysql': ['mysql', '데이터베이스', 'db', '데이터베이스 경험'],
            'postgresql': ['postgresql', '데이터베이스', 'db', '데이터베이스 경험'],
            'redis': ['redis', '캐시', '데이터베이스', 'db'],
            'nginx': ['nginx', '웹서버', '서버', '운영', '서비스 개발·운영'],
            'git': ['git', '버전관리', '협업', '개발'],
            'github actions': ['github actions', 'ci/cd', 'jenkins', 'devops', '배포', '서비스 개발·운영'],
            'api': ['api', 'rest api', '웹 api', '개발 경험', '서비스 개발'],
            'ai': ['ai', '머신러닝', 'ml', 'llm', '인공지능', 'ai 기반', 'llm 또는 ai'],
            'llm': ['llm', 'ai', '머신러닝', 'ml', '인공지능', 'ai 기반', 'llm 또는 ai']
        }
        
        for condition in conditions:
            condition_lower = condition.lower()
            
            # 각 이력서 스킬에 대해 매핑 테이블 확인
            for skill in resume_skills:
                if skill in skill_mappings:
                    for keyword in skill_mappings[skill]:
                        if keyword in condition_lower:
                            matched_conditions.add(condition)
                            break
        
        return matched_conditions

    def _extract_skills_from_conditions(self, conditions: List[str]) -> Set[str]:
        """
        조건 문장에서 기술 스킬 추출
        
        Args:
            conditions: ["Python 3년 이상", "Django 경험", "AWS 사용 경험"]
            
        Returns:
            {"python", "django", "aws"}
        """
        common_skills = {
            # 프로그래밍 언어
            "python", "java", "javascript", "typescript", "kotlin", "go", "rust",
            "c++", "c#", "php", "ruby", "swift", "scala", "html", "css",
            
            # 프레임워크 & 라이브러리
            "react", "vue", "angular", "svelte", "next.js", "nuxt.js", "react.js", "vue.js",
            "redux", "recoil", "zustand", "mobx", "react query", "tanstack query",
            "django", "flask", "fastapi", "spring", "spring boot", "springboot",
            "express", "nestjs", "nodejs", "node.js", "express.js",
            "jetpack compose", "rxjava", "coroutine",
            
            # CSS 프레임워크
            "tailwind", "tailwind css", "sass", "scss", "styled-components", 
            "bootstrap", "mui", "material-ui", "ant design",
            
            # 데이터베이스
            "mysql", "postgresql", "postgres", "mongodb", "redis", "elasticsearch",
            "oracle", "mssql", "mariadb", "dynamodb", "cassandra",
            
            # 클라우드/인프라
            "aws", "azure", "gcp", "docker", "kubernetes", "k8s",
            "terraform", "ansible", "jenkins", "github actions",
            "gitlab ci", "circleci", "travis ci", "ec2", "s3", "rds",
            
            # 도구 & 테스팅
            "git", "jira", "confluence", "slack", "notion",
            "figma", "sketch", "zeplin", "grafana", "prometheus",
            "jest", "cypress", "junit", "mockito", "storybook",
            "sentry", "datadog",
            
            # AI/ML
            "llm", "langchain", "pytorch", "tensorflow", "scikit-learn",
            "huggingface", "openai", "rag", "vector db", "embedding",
            
            # 데이터
            "airflow", "kafka", "rabbitmq", "spark", "hadoop", "etl",
            
            # 기타
            "rest api", "restful api", "graphql", "grpc", "websocket",
            "microservices", "msa", "ci/cd", "tdd", "agile", "nginx"
        }
        
        extracted_skills = set()
        
        for condition in conditions:
            condition_lower = condition.lower()
            
            # 각 기술 스킬이 조건에 포함되어 있는지 확인
            for skill in common_skills:
                if skill in condition_lower:
                    extracted_skills.add(skill)
        
        return extracted_skills
    
    def _split_conditions_by_resume_match(self, conditions: List[str], resume_skills_lower: Set[str]) -> (List[str], List[str]):
        """조건 리스트를 이력서 스킬과의 매칭 여부로 분리

        - 동일 조건 문장이 matched와 missing에 중복 등장하지 않도록 보장
        - 조건 내 포함 스킬이 하나라도 이력서 스킬에 있으면 matched로 간주, 없으면 missing
        - 의미적 매칭도 포함
        """
        matched_conditions: List[str] = []
        missing_conditions: List[str] = []
        
        # 의미적 매칭 결과 가져오기
        semantic_matches = self._find_semantic_matches(conditions, resume_skills_lower)
        
        for condition in conditions or []:
            cond_lower = condition.lower()
            has_match = False
            
            # 1. 정확한 키워드 매칭
            for skill in self._common_skills_cache():
                if skill in cond_lower and skill in resume_skills_lower:
                    has_match = True
                    break
            
            # 2. 의미적 매칭 확인
            if not has_match and condition in semantic_matches:
                has_match = True
            
            if has_match:
                matched_conditions.append(condition)
            else:
                missing_conditions.append(condition)
        return matched_conditions, missing_conditions

    def _common_skills_cache(self) -> Set[str]:
        """_extract_skills_from_conditions과 동일한 공통 스킬 집합 반환"""
        return {
            "python", "java", "javascript", "typescript", "kotlin", "go", "rust",
            "c++", "c#", "php", "ruby", "swift", "scala", "html", "css",
            "react", "vue", "angular", "svelte", "next.js", "nuxt.js", "react.js", "vue.js",
            "redux", "recoil", "zustand", "mobx", "react query", "tanstack query",
            "django", "flask", "fastapi", "spring", "spring boot", "springboot",
            "express", "nestjs", "nodejs", "node.js", "express.js",
            "jetpack compose", "rxjava", "coroutine",
            "tailwind", "tailwind css", "sass", "scss", "styled-components",
            "bootstrap", "mui", "material-ui", "ant design",
            "mysql", "postgresql", "postgres", "mongodb", "redis", "elasticsearch",
            "oracle", "mssql", "mariadb", "dynamodb", "cassandra",
            "aws", "azure", "gcp", "docker", "kubernetes", "k8s",
            "terraform", "ansible", "jenkins", "github actions",
            "gitlab ci", "circleci", "travis ci", "ec2", "s3", "rds",
            "git", "jira", "confluence", "slack", "notion",
            "figma", "sketch", "zeplin", "grafana", "prometheus",
            "jest", "cypress", "junit", "mockito", "storybook",
            "sentry", "datadog",
            "llm", "langchain", "pytorch", "tensorflow", "scikit-learn",
            "huggingface", "openai", "rag", "vector db", "embedding",
            "airflow", "kafka", "rabbitmq", "spark", "hadoop", "etl",
            "rest api", "restful api", "graphql", "grpc", "websocket",
            "microservices", "msa", "ci/cd", "tdd", "nginx"
        }
    
    def _calculate_difficulty_factor(self, num_required: int, num_preferred: int) -> float:
        """
        조건 개수에 따른 난이도 계산
        
        조건이 많을수록 충족하기 어려우므로, 충족 시 보너스 점수 부여
        
        Args:
            num_required: 필수 조건 개수
            num_preferred: 우대 조건 개수
            
        Returns:
            0.0 ~ 1.0 (조건이 많을수록 높음)
        """
        total_conditions = num_required + num_preferred
        
        if total_conditions == 0:
            return 0.0
        
        # 조건 개수별 난이도
        # 1-3개: 쉬움 (0.0)
        # 4-6개: 보통 (0.3)
        # 7-10개: 어려움 (0.6)
        # 11개 이상: 매우 어려움 (1.0)
        
        if total_conditions <= 3:
            return 0.0
        elif total_conditions <= 6:
            return 0.3
        elif total_conditions <= 10:
            return 0.6
        else:
            return min(1.0, 0.6 + (total_conditions - 10) * 0.05)
    
    def calculate_experience_score(
        self,
        job: JobPosting,
        resume: Resume
    ) -> Dict[str, Any]:
        """
        경력 매칭 점수 계산
        
        Returns:
            {
                "score": 0.75,
                "required_years": 3,
                "candidate_years": 4,
                "level_match": true,
                "details": "4년 경력 (요구: 3년 이상)"
            }
        """
        try:
            score = 0.5  # 기본 점수
            
            required_years = job.min_experience_years or 0
            max_years = job.max_experience_years
            candidate_years = resume.extracted_experience_years or 0
            
            # 1. 경력 연수 비교
            if required_years == 0:
                # 경력 무관
                year_score = 0.8
            elif candidate_years >= required_years:
                # 최소 요구사항 충족
                if max_years and candidate_years > max_years:
                    # 최대 경력 초과 (over-qualified)
                    year_score = 0.7
                else:
                    # 적정 범위
                    year_score = 1.0
            elif candidate_years >= required_years * 0.7:
                # 70% 이상 충족 (약간 부족)
                year_score = 0.6
            elif candidate_years >= required_years * 0.5:
                # 50% 이상 충족 (많이 부족)
                year_score = 0.4
            else:
                # 경력 많이 부족
                year_score = 0.2
            
            # 2. 경력 수준 비교
            level_match = self._compare_experience_level(
                job.experience_level,
                candidate_years
            )
            level_score = 1.0 if level_match else 0.5
            
            # 3. 최종 점수 (경력 연수 70%, 경력 수준 30%)
            score = year_score * 0.7 + level_score * 0.3
            
            # 상세 정보
            details = f"{candidate_years}년 경력"
            if required_years > 0:
                if max_years:
                    details += f" (요구: {required_years}~{max_years}년)"
                else:
                    details += f" (요구: {required_years}년 이상)"
            else:
                details += " (경력무관)"
            
            return {
                "score": min(score, 1.0),
                "required_years": required_years,
                "max_years": max_years,
                "candidate_years": candidate_years,
                "level_match": level_match,
                "year_score": round(year_score, 3),
                "level_score": round(level_score, 3),
                "details": details
            }
            
        except Exception as e:
            logger.error(f"Error calculating experience score: {e}")
            return {
                "score": 0.5,
                "required_years": 0,
                "candidate_years": 0,
                "level_match": False,
                "details": "경력 정보 없음"
            }
    
    def _compare_experience_level(self, job_level: str, candidate_years: int) -> bool:
        """
        경력 수준 비교
        
        Args:
            job_level: junior, mid, senior
            candidate_years: 후보자 경력 연수
            
        Returns:
            매칭 여부
        """
        if not job_level:
            return True
        
        level_map = {
            "junior": (0, 3),
            "mid": (3, 7),
            "senior": (7, 100)
        }
        
        min_years, max_years = level_map.get(job_level.lower(), (0, 100))
        
        return min_years <= candidate_years < max_years
    
    def calculate_education_score(
        self,
        job: JobPosting,
        resume: Resume
    ) -> float:
        """
        학력 매칭 점수 계산
        
        TODO: 실제 학력 정보 파싱 후 구현
        현재는 기본 점수 반환
        """
        # 학력 정보가 파싱되면 구현
        return 0.5
    
    def calculate_certification_score(
        self,
        job: JobPosting,
        resume: Resume
    ) -> float:
        """
        자격증 매칭 점수 계산
        
        TODO: 실제 자격증 정보 파싱 후 구현
        """
        return 0.5
    
    def calculate_language_score(
        self,
        job: JobPosting,
        resume: Resume
    ) -> float:
        """
        언어 능력 매칭 점수 계산
        
        TODO: 실제 언어 정보 파싱 후 구현
        """
        return 0.5
