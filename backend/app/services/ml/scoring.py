"""
Scoring Service - 카테고리별 매칭 점수 계산
"""
from typing import Dict, Any, List, Set
from sqlalchemy.orm import Session
from app.models.job import JobPosting
from app.models.resume import Resume
from app.core.config import settings
from app.core.logging import logger


class ScoringService:
    """점수 계산 서비스"""
    def __init__(self, db: Session = None):
        self.db = db
        # 간단한 프로세스 내 캐시: resume_id -> { 'lines': [...], 'embs': [...], 'sections': [...] }
        self._resume_sentence_cache: dict = {}
    
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
            
            # 1) 이력서 문장 수집 및 임베딩 (문장 단위 의미 매칭 준비)
            sent_lines, sent_embeddings, _ = self._get_cached_sentences(resume)

            # 정규화: 조건 분해 및 동의어 확장 (DB 문장화가 있으면 우선 사용)
            db_required = self._load_job_sentences(job, section="required")
            db_preferred = self._load_job_sentences(job, section="preferred")
            required_conditions = self._normalize_conditions(db_required or required_conditions)
            preferred_conditions = self._normalize_conditions(db_preferred or preferred_conditions)

            # 2) 필수 조건: 소프트 점수 평균 + 키워드 보조
            required_skills = self._extract_skills_from_conditions(required_conditions)
            required_skills.update({s.lower() for s in job_skills})
            if required_conditions:
                required_per_scores = [
                    self._condition_soft_score(cond, sent_lines, sent_embeddings, section="required", resume_skills_lower=resume_skills_lower)
                    for cond in required_conditions
                ]
                keyword_required = 0.0
                if required_skills:
                    matched_required_kw = required_skills & resume_skills_lower
                    keyword_required = len(matched_required_kw) / max(1, len(required_skills))
                required_score = float(min(1.0, 0.9 * (sum(required_per_scores) / max(1, len(required_per_scores))) + 0.1 * keyword_required))
            else:
                required_score = 0.5

            # 3) 우대 조건: 소프트 점수 평균 + 키워드 보조
            preferred_skills = self._extract_skills_from_conditions(preferred_conditions)
            if preferred_conditions:
                preferred_per_scores = [
                    self._condition_soft_score(cond, sent_lines, sent_embeddings, section="preferred", resume_skills_lower=resume_skills_lower)
                    for cond in preferred_conditions
                ]
                keyword_preferred = 0.0
                if preferred_skills:
                    matched_preferred_kw = preferred_skills & resume_skills_lower
                    keyword_preferred = len(matched_preferred_kw) / max(1, len(preferred_skills))
                preferred_score = float(min(1.0, 0.9 * (sum(preferred_per_scores) / max(1, len(preferred_per_scores))) + 0.1 * keyword_preferred))
            else:
                preferred_score = 0.0
            
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
                resume_skills_lower,
                sent_lines,
                sent_embeddings,
                section="required"
            )
            matched_preferred_original, missing_preferred_original = self._split_conditions_by_resume_match(
                preferred_conditions,
                resume_skills_lower,
                sent_lines,
                sent_embeddings,
                section="preferred"
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
                "match_rate": f"{len(matched_required_original)}/{len(required_conditions)} 필수, {len(matched_preferred_original)}/{len(preferred_conditions)} 우대"
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
        의미적 매칭: 임베딩 기반으로 이력서 스킬과 공고 조건의 의미적 유사도 계산
        
        Args:
            conditions: 공고 조건 리스트
            resume_skills: 이력서 스킬 세트 (소문자)
            
        Returns:
            매칭된 조건들의 세트
        """
        matched_conditions = set()
        
        if not conditions or not resume_skills:
            return matched_conditions
            
        try:
            from app.services.ml.embedding import EmbeddingService
            embedding_service = EmbeddingService()
            
            # 이력서 스킬들을 하나의 텍스트로 결합
            resume_skills_text = ", ".join(resume_skills)
            
            # 이력서 스킬 임베딩 생성
            resume_embedding = embedding_service.generate_embedding(resume_skills_text)
            
            # 각 조건에 대해 의미적 유사도 계산
            for condition in conditions:
                try:
                    # 조건 임베딩 생성
                    condition_embedding = embedding_service.generate_embedding(condition)
                    
                    # 코사인 유사도 계산
                    similarity = self._cosine_similarity(resume_embedding, condition_embedding)
                    
                    # 임계값 0.75 이상이면 매칭으로 간주 (매우 엄격한 의미 매칭)
                    if similarity > 0.75:
                        matched_conditions.add(condition)
                        logger.info(f"✅ Semantic match: '{condition}' (similarity: {similarity:.3f})")
                    else:
                        logger.debug(f"❌ Semantic no match: '{condition}' (similarity: {similarity:.3f})")
                        
                except Exception as e:
                    logger.warning(f"Failed to process condition '{condition}': {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Semantic matching failed: {e}")
            # 폴백: 키워드 매칭으로 대체
            return self._fallback_keyword_matching(conditions, resume_skills)
        
        return matched_conditions
    
    def _cosine_similarity(self, vec1, vec2):
        """코사인 유사도 계산"""
        import numpy as np
        
        # 벡터를 numpy 배열로 변환
        if hasattr(vec1, 'tolist'):
            vec1 = vec1.tolist()
        if hasattr(vec2, 'tolist'):
            vec2 = vec2.tolist()
            
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        # 정규화
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return np.dot(vec1, vec2) / (norm1 * norm2)
    
    def _fallback_keyword_matching(self, conditions: List[str], resume_skills: Set[str]) -> Set[str]:
        """폴백: 간단한 키워드 매칭"""
        matched_conditions = set()
        
        # 확장된 키워드 매핑 (정확한 매칭)
        keyword_mappings = {
            'fastapi': ['api', 'rest api', 'restful api', '웹 api', '서비스 연동'],
            'rest api': ['rest api', 'restful', 'restful api', 'api 설계', 'openapi', 'swagger', '엔드포인트', 'endpoint'],
            'react': ['react', 'react.js', '프론트엔드'],
            'next.js': ['next.js', 'nextjs', '프론트엔드'],
            'javascript': ['javascript', 'js', '프론트엔드'],
            'typescript': ['typescript', 'ts', '프론트엔드'],
            'git': ['git', '버전관리', '협업', 'ci/cd'],
            'docker': ['docker', '컨테이너', '도커'],
            'postgresql': ['postgresql', 'postgres', '데이터베이스', 'db', '관계형 db'],
            'python': ['python', '백엔드', '파이썬'],
            'java': ['java', '백엔드', '자바'],
            'spring': ['spring', 'spring boot', '백엔드'],
            'gcp': ['gcp', 'google cloud', '클라우드', 'aws', 'azure'],
            'ci/cd': ['ci/cd', 'cicd', '지속적 통합', '지속적 배포', '배포 자동화', '파이프라인', 'pipeline', 'github actions', 'gitlab ci', 'jenkins'],
            'sql': ['sql', '쿼리', '데이터 모델링', 'erd', '정규화', '인덱스', '인덱싱', 'join', '트랜잭션', 'rdbms'],
            'rdbms': ['관계형 db', 'rdbms', 'sql', '스키마 설계', '모델링'],
            'testing': ['테스트', '테스트 자동화', '단위 테스트', '통합 테스트', 'e2e 테스트', 'coverage', '커버리지', 'qa', '품질'],
            'pytest': ['pytest', 'python 테스트', '단위 테스트'],
            'junit': ['junit', 'java 테스트', '단위 테스트'],
            'jest': ['jest', '프론트엔드 테스트', '단위 테스트'],
            'cypress': ['cypress', 'e2e 테스트'],
            'openapi': ['openapi', 'swagger', 'api 명세', 'api 문서화', '스웨거'],
            'swagger': ['swagger', 'openapi', 'api 명세', 'api 문서화']
        }
        
        for condition in conditions:
            condition_lower = condition.lower()
            
            for skill in resume_skills:
                if skill in keyword_mappings:
                    for keyword in keyword_mappings[skill]:
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
    
    def _split_conditions_by_resume_match(self, conditions: List[str], resume_skills_lower: Set[str], sent_lines: List[str] = None, sent_embeddings: list = None, section: str = "required") -> (List[str], List[str]):
        """조건 리스트를 이력서 스킬과의 매칭 여부로 분리

        - 동일 조건 문장이 matched와 missing에 중복 등장하지 않도록 보장
        - 조건 내 포함 스킬이 하나라도 이력서 스킬에 있으면 matched로 간주, 없으면 missing
        - 의미적 매칭도 포함
        """
        matched_conditions: List[str] = []
        missing_conditions: List[str] = []
        
        # 의미적 매칭 결과 & 문장 기반 임계 확인
        semantic_matches = self._find_semantic_matches(conditions, resume_skills_lower)
        thr = 0.70 if section == "required" else 0.60
        
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
            # 3. 문장-문장 최고 유사도 임계 통과
            if not has_match and sent_lines is not None and sent_embeddings is not None:
                best_sim, _ = self._best_sentence_match(condition, sent_lines, sent_embeddings)
                if best_sim >= thr:
                    has_match = True
            
            if has_match:
                matched_conditions.append(condition)
            else:
                missing_conditions.append(condition)
        return matched_conditions, missing_conditions

    def _analyze_condition_matching(self, conditions: List[str], resume_skills: Set[str], resume: Resume = None, section: str = "required") -> Dict:
        """각 조건별 상세 매칭 분석"""
        detailed_analysis = []
        matched_conditions = set()
        
        # 의미적 매칭 결과 가져오기
        semantic_matches = self._find_semantic_matches(conditions, resume_skills)
        thr = 0.70 if section == "required" else 0.60
        sent_lines = None
        sent_embeddings = None
        sections_map = {}
        if resume is not None:
            sent_lines, sent_embeddings, sections = self._get_cached_sentences(resume)
            sections_map = {line: sec for line, sec in zip(sent_lines, sections)}
        
        for condition in conditions or []:
            cond_lower = condition.lower()
            matched_skills = []
            match_type = "none"
            best_sim = 0.0
            best_sentence = ""
            if sent_lines is not None and sent_embeddings is not None:
                try:
                    best_sim, best_sentence = self._best_sentence_match(condition, sent_lines, sent_embeddings)
                except Exception:
                    best_sim, best_sentence = 0.0, ""
            
            # 1. 정확한 키워드 매칭 확인
            for skill in self._common_skills_cache():
                if skill in cond_lower and skill in resume_skills:
                    matched_skills.append(skill)
                    match_type = "keyword"
                    matched_conditions.add(condition)
                    break
            
            # 2. 의미적 매칭 확인
            if not matched_skills and condition in semantic_matches:
                match_type = "semantic"
                matched_conditions.add(condition)
            # 3. 문장-문장 임계 통과 시 의미 매칭으로 인정
            if condition not in matched_conditions and best_sim >= thr:
                match_type = "semantic"
                matched_conditions.add(condition)
            
            detailed_analysis.append({
                'condition': condition,
                'matched': condition in matched_conditions,
                'matched_skills': matched_skills,
                'match_type': match_type,
                'similarity_score': round(best_sim, 3),
                'matched_sentence': best_sentence,
                'matched_section': sections_map.get(best_sentence)
            })
        
        return {
            'matched': list(matched_conditions),
            'missing': [c for c in conditions if c not in matched_conditions],
            'detailed_analysis': detailed_analysis,
            'match_rate': f"{len(matched_conditions)}/{len(conditions)}",
            'score': self._soft_average_score(detailed_analysis, section)
        }

    def _soft_average_score(self, detailed_analysis: List[Dict[str, Any]], section: str) -> float:
        thr = 0.70 if section == "required" else 0.60
        floor = 0.50 if section == "required" else 0.50
        scores = []
        for d in detailed_analysis:
            if d.get('matched'):
                scores.append(1.0)
            else:
                sim = float(d.get('similarity_score') or 0.0)
                if sim <= floor:
                    scores.append(0.0)
                elif sim >= thr:
                    scores.append(1.0)
                else:
                    scores.append((sim - floor) / max(1e-6, (thr - floor)))
        return float(sum(scores) / max(1, len(scores)))

    def _normalize_conditions(self, conditions: List[str]) -> List[str]:
        """조건을 원자적 하위 조건으로 분해하고 동의어/표현을 확장"""
        out: List[str] = []
        if not conditions:
            return out
        # 간단한 동의어/표현 매핑 (한/영 혼용 포함)
        synonyms = {
            "rest api": ["restful api", "api 연동", "api integration", "서비스 연동", "openapi", "swagger", "api 명세", "엔드포인트"],
            "api 설계": ["api 디자인", "api 디자인 원칙", "엔드포인트 설계", "리소스 모델링"],
            "openapi": ["swagger", "api 명세", "api 문서화"],
            "ci/cd": ["cicd", "배포 파이프라인", "지속적 통합", "지속적 배포", "배포 자동화", "pipeline", "github actions", "gitlab ci", "jenkins"],
            "sql": ["데이터 모델링", "erd", "정규화", "인덱스", "인덱싱", "트랜잭션", "join", "rdbms"],
            "rdbms": ["관계형 db", "스키마 설계", "sql"],
            "테스트": ["테스트 자동화", "단위 테스트", "통합 테스트", "e2e 테스트", "coverage", "커버리지", "품질"],
            "cloud": ["클라우드", "aws", "gcp", "azure"],
        }
        separators = ["/", ",", "·", " 및 ", " and ", " 또는 ", " or "]
        for c in conditions:
            if not c:
                continue
            base = str(c).strip()
            if not base:
                continue
            parts = [base]
            # 1차 분해: 구분자 기준 쪼개기
            for sep in separators:
                new_parts = []
                for p in parts:
                    if sep in p:
                        new_parts.extend([s.strip() for s in p.split(sep) if s.strip()])
                    else:
                        new_parts.append(p)
                parts = new_parts
            # 동의어 확장
            for p in parts:
                out.append(p)
                lower = p.lower()
                for key, vals in synonyms.items():
                    if key in lower:
                        out.extend(vals)
            # 특수 규칙: "REST API 설계/연동" → 원자 항목 추가
            lower_all = base.lower()
            if "api" in lower_all and ("연동" in base or "설계" in base):
                out.extend(["REST API", "API 설계", "서비스 연동"])
            # 특수 규칙: SQL/RDBMS 관련 일반화
            if any(k in lower_all for k in ["sql", "rdbms", "데이터 모델링", "erd", "정규화", "인덱스", "트랜잭션", "join"]):
                out.extend(["SQL", "RDBMS", "데이터 모델링", "인덱스", "트랜잭션"]) 
            # 특수 규칙: 테스트 관련 일반화
            if any(k in lower_all for k in ["테스트", "단위 테스트", "통합 테스트", "e2e", "coverage", "jest", "pytest", "junit", "cypress"]):
                out.extend(["테스트", "테스트 자동화", "단위 테스트", "통합 테스트"]) 
        # 중복 제거 (순서 보존)
        seen = set()
        uniq = []
        for t in out:
            if not t:
                continue
            if t in seen:
                continue
            seen.add(t)
            uniq.append(t)
        return uniq

    def _collect_resume_sentences(self, resume: Resume) -> List[str]:
        texts: List[str] = []
        pd = resume.parsed_data or {}
        def add(txt):
            if not txt:
                return
            s = " ".join(str(txt).strip().split())
            if 10 <= len(s) <= 300:
                texts.append(s)
        add(pd.get('summary'))
        for x in (pd.get('skills') or []):
            add(x)
        for exp in (pd.get('work_experience') or []):
            if isinstance(exp, dict):
                add(exp.get('company'))
                add(exp.get('title'))
                add(exp.get('description'))
                for r in (exp.get('responsibilities') or []):
                    add(r)
        for pr in (pd.get('projects') or []):
            if isinstance(pr, dict):
                add(pr.get('name'))
                add(pr.get('role'))
                add(pr.get('description'))
                for r in (pr.get('responsibilities') or []):
                    add(r)
        for line in (resume.raw_text or '').splitlines():
            s = " ".join(line.strip().split())
            # 문장 필터: 공백 포함, 밑줄/스키마키 제외, 길이 기준 강화, ALL CAPS 헤더 배제
            if not s or ' ' not in s:
                continue
            if '_' in s:
                continue
            if s.isupper() and len(s) <= 40:
                continue
            if len(s) < 20 or len(s) > 300:
                continue
            texts.append(s)
        seen = set()
        uniq = []
        for t in texts:
            if t in seen:
                continue
            seen.add(t)
            uniq.append(t)
            if len(uniq) >= 200:
                break
        return uniq

    def _load_job_sentences(self, job: JobPosting, section: str) -> List[str]:
        try:
            from app.models.sentences import JobSentence
            # job.sentences relationship may not be eager loaded; query explicitly
            db: Session = job._sa_instance_state.session  # type: ignore
            if not db:
                return []
            q = db.query(JobSentence).filter(JobSentence.job_id == job.id)
            if section:
                q = q.filter(JobSentence.section == section)
            q = q.order_by(JobSentence.idx.asc())
            rows = q.all()
            return [r.text for r in rows]
        except Exception:
            return []

    def _collect_resume_sentences_with_sections(self, resume: Resume) -> (List[str], List[str]):
        lines: List[str] = []
        sections: List[str] = []
        pd = resume.parsed_data or {}
        def add(txt, sec):
            if not txt:
                return
            s = " ".join(str(txt).strip().split())
            if 10 <= len(s) <= 300:
                lines.append(s)
                sections.append(sec)
        add(pd.get('summary'), 'summary')
        for x in (pd.get('skills') or []):
            add(x, 'skills')
        for exp in (pd.get('work_experience') or []):
            if isinstance(exp, dict):
                add(exp.get('company'), 'experience')
                add(exp.get('title'), 'experience')
                add(exp.get('description'), 'experience')
                for r in (exp.get('responsibilities') or []):
                    add(r, 'experience')
        for pr in (pd.get('projects') or []):
            if isinstance(pr, dict):
                add(pr.get('name'), 'projects')
                add(pr.get('role'), 'projects')
                add(pr.get('description'), 'projects')
                for r in (pr.get('responsibilities') or []):
                    add(r, 'projects')
        for line in (resume.raw_text or '').splitlines():
            s = " ".join(line.strip().split())
            if not s or ' ' not in s:
                continue
            if '_' in s:
                continue
            if s.isupper() and len(s) <= 40:
                continue
            if len(s) < 20 or len(s) > 300:
                continue
            lines.append(s)
            sections.append('raw')
        # dedupe preserving first section
        seen = set()
        out_lines: List[str] = []
        out_secs: List[str] = []
        for s, sec in zip(lines, sections):
            if s in seen:
                continue
            seen.add(s)
            out_lines.append(s)
            out_secs.append(sec)
            if len(out_lines) >= 200:
                break
        return out_lines, out_secs

    def _get_cached_sentences(self, resume: Resume):
        key = str(resume.id)
        cached = self._resume_sentence_cache.get(key)
        if cached:
            return cached['lines'], cached['embs'], cached['sections']
        # Prefer DB-stored sentences if available
        db_lines, db_secs = self._load_resume_sentences(resume)
        if db_lines:
            lines, sections = db_lines, db_secs
        else:
            lines, sections = self._collect_resume_sentences_with_sections(resume)
        embs = self._embed_texts(lines)
        self._resume_sentence_cache[key] = { 'lines': lines, 'embs': embs, 'sections': sections }
        return lines, embs, sections

    def _load_resume_sentences(self, resume: Resume) -> (List[str], List[str]):
        try:
            from app.models.sentences import ResumeSentence
            if not self.db:
                return [], []
            rows = self.db.query(ResumeSentence).filter(ResumeSentence.resume_id == resume.id).order_by(ResumeSentence.idx.asc()).all()
            if not rows:
                return [], []
            return [r.text for r in rows], [r.section or 'raw' for r in rows]
        except Exception as e:
            logger.warning(f"Failed to load resume sentences: {e}")
            return [], []

    def _embed_texts(self, texts: List[str]) -> List[list]:
        try:
            from app.services.ml.embedding import EmbeddingService
            emb = EmbeddingService()
            out = []
            for t in texts:
                try:
                    out.append(emb.generate_embedding(t))
                except Exception:
                    out.append(None)
            return out
        except Exception:
            return [None for _ in texts]

    def _best_sentence_match(self, condition: str, sent_lines: List[str], sent_embeddings: List[list]) -> (float, str):
        try:
            from app.services.ml.embedding import EmbeddingService
            emb = EmbeddingService()
            cond_emb = emb.generate_embedding(condition)
        except Exception:
            return 0.0, ""
        import numpy as np
        best_sim = -1.0
        best_sent = ""
        for s, se in zip(sent_lines, sent_embeddings):
            if se is None:
                continue
            a = np.array(se, dtype='float32')
            b = np.array(cond_emb, dtype='float32')
            na = np.linalg.norm(a)
            nb = np.linalg.norm(b)
            if na == 0 or nb == 0:
                sim = 0.0
            else:
                sim = float((a @ b) / (na * nb))
            if sim > best_sim:
                best_sim = sim
                best_sent = s
        if best_sim < 0:
            best_sim = 0.0
        return best_sim, best_sent

    def _condition_soft_score(self, condition: str, sent_lines: List[str], sent_embeddings: List[list], section: str, resume_skills_lower: Set[str]) -> float:
        thr = 0.70 if section == "required" else 0.60
        floor = 0.50 if section == "required" else 0.50
        best_sim, _ = self._best_sentence_match(condition, sent_lines, sent_embeddings)
        if best_sim >= thr:
            return 1.0
        if best_sim <= floor:
            return 0.0
        return float((best_sim - floor) / max(1e-6, (thr - floor)))

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
