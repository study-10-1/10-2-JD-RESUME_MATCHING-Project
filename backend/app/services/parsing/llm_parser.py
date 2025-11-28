"""
LLM 기반 파싱 서비스 (이력서, 채용공고)
"""
import json
import os
from typing import Dict, Any, Optional
from openai import OpenAI
from app.core.logging import logger


class LLMParser:
    """LLM을 사용한 텍스트 구조화 파싱 (이력서, 채용공고)"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found. LLM parsing disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)
            # GPT-5가 있는지 확인, 없으면 gpt-4o-mini 사용
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            logger.info(f"LLM Parser initialized with model: {self.model}")
    
    def parse_resume(self, raw_text: str) -> Dict[str, Any]:
        """
        이력서 텍스트를 구조화된 데이터로 변환
        
        Args:
            raw_text: 이력서 원문
            
        Returns:
            {
                "personal_info": {...},
                "summary": "...",
                "work_experience": [...],
                "education": [...],
                "skills": [...],
                "certifications": [...],
                "languages": [...],
                "projects": [...]
            }
        """
        if not self.client:
            logger.warning("LLM client not available. Skipping LLM parsing.")
            return self._fallback_parsing(raw_text)
        
        try:
            # 텍스트가 길면 청크로 나눠서 처리
            max_chars = 8000
            if len(raw_text) <= max_chars:
                # 짧은 텍스트는 그대로 처리
                text_to_parse = raw_text
                prompt = self._create_parsing_prompt(text_to_parse)
                
                completion_params = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "당신은 이력서 분석 전문가입니다. 주어진 이력서에서 정확하게 정보를 추출하여 JSON 형식으로 반환합니다."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "response_format": {"type": "json_object"}
                }
                
                if "gpt-5" not in self.model.lower():
                    completion_params["temperature"] = 0.1
                
                response = self.client.chat.completions.create(**completion_params)
                result_text = response.choices[0].message.content
                parsed_data = json.loads(result_text)
                
                logger.info(f"LLM parsing successful. Model: {self.model}")
                return parsed_data
            else:
                # 긴 텍스트는 청크로 나눠서 처리
                logger.info(f"Text too long ({len(raw_text)} chars), processing in chunks...")
                return self._parse_resume_in_chunks(raw_text, max_chars)
            
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return self._fallback_parsing(raw_text)

    def extract_job_requirements(self, text: str) -> Dict[str, Any]:
        """
        채용공고 텍스트에서 자격요건(required)과 우대조건(preferred)을 추출합니다.
        
        Args:
            text: 채용공고 텍스트 (HTML 파싱 후 정제된 텍스트)
            
        Returns:
            {
                "required": List[str],  # 필수 자격요건 리스트
                "preferred": List[str]  # 우대조건 리스트
            }
        """
        if not text:
            return {"required": [], "preferred": []}
        
        if not self.client:
            logger.warning("LLM client not available. Using fallback for requirements extraction.")
            return self._fallback_extract_requirements(text)
        
        try:
            prompt = f"""
다음 채용공고 텍스트에서 자격요건(필수조건)과 우대조건을 정확하게 구분하여 추출하세요.

채용공고 텍스트:
```
{text[:6000]}  # 최대 6000자
```

주의사항:
1. **자격요건(required)**: 반드시 충족해야 하는 필수 조건
   - 예: "경력 3년 이상", "대졸 이상", "Java 개발 경험 필수", "TOEIC 800점 이상"
   - "필수", "요구", "필요", "반드시" 등의 키워드가 있는 조건
   - 모집요강의 기본 조건 (경력, 학력, 자격증 등)

2. **우대조건(preferred)**: 있으면 좋지만 필수는 아닌 조건
   - 예: "우대사항", "선호조건", "가산점", "bonus"
   - "우대", "선호", "가산", "플러스" 등의 키워드가 있는 조건

3. 각 조건을 개별 문장으로 분리하세요.
   - 예: "Java, Spring Boot 개발 경험" → ["Java 개발 경험", "Spring Boot 개발 경험"]
   - 예: "경력 3년 이상, 대졸 이상" → ["경력 3년 이상", "대졸 이상"]

4. 모집요강의 기본 정보(모집 직종, 모집 인원, 근무지 등)는 자격요건이 아닙니다.

5. 테이블 형태의 데이터도 정확히 파싱하세요.

JSON 형식으로 반환하세요:
{{
  "required": ["조건1", "조건2", ...],
  "preferred": ["조건1", "조건2", ...]
}}
"""
            
            completion_params = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "당신은 채용공고 분석 전문가입니다. 자격요건과 우대조건을 정확하게 구분하여 추출합니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            
            response = self.client.chat.completions.create(**completion_params)
            result_text = response.choices[0].message.content
            parsed_data = json.loads(result_text)
            
            # 결과 검증 및 정제
            required = parsed_data.get("required", [])
            preferred = parsed_data.get("preferred", [])
            
            # 리스트가 아닌 경우 변환
            if not isinstance(required, list):
                required = [str(required)] if required else []
            if not isinstance(preferred, list):
                preferred = [str(preferred)] if preferred else []
            
            # 빈 문자열 제거 및 정제
            required = [r.strip() for r in required if r and r.strip() and len(r.strip()) > 5]
            preferred = [p.strip() for p in preferred if p and p.strip() and len(p.strip()) > 5]
            
            logger.info(f"LLM requirements extraction successful: required={len(required)}, preferred={len(preferred)}")
            
            return {
                "required": required[:100],  # 최대 100개
                "preferred": preferred[:100]
            }
            
        except Exception as e:
            logger.error(f"LLM requirements extraction failed: {e}")
            return self._fallback_extract_requirements(text)
    
    def _fallback_extract_requirements(self, text: str) -> Dict[str, Any]:
        """LLM 실패 시 키워드 기반 fallback"""
        required = []
        preferred = []
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        for line in lines:
            line_lower = line.lower()
            # 자격요건 키워드
            if any(kw in line_lower for kw in ['필수', '요구', '필요', 'required', '반드시', '기본']):
                if len(line) > 10:  # 너무 짧은 것은 제외
                    required.append(line)
            # 우대조건 키워드
            elif any(kw in line_lower for kw in ['우대', '선호', 'preferred', 'bonus', '가산', '플러스']):
                if len(line) > 10:
                    preferred.append(line)
        
        return {
            "required": required[:50],
            "preferred": preferred[:50]
        }
    
    def extract_sentences(self, raw_text: str) -> Dict[str, Any]:
        """Split text into clean, standalone sentences using LLM; fallback to regex.

        Returns: { "sentences": ["..."] }
        """
        if not raw_text:
            return {"sentences": []}
        if not self.client:
            return {"sentences": self._fallback_sentence_split(raw_text)}
        try:
            prompt = (
                "다음 텍스트를 의미 단위의 완전한 문장으로 깔끔하게 분할하세요.\n"
                "- 각 문장은 20-200자 내외의 의미 있는 단위여야 합니다.\n"
                "- 기술 스킬, 경험, 프로젝트 내용을 명확히 구분합니다.\n"
                "- 번호/불릿/불필요한 접두사는 제거합니다.\n"
                "- 한국어/영어는 원문 어휘를 보존합니다.\n"
                "- 출력은 JSON {\"sentences\": [..]} 형식만 반환하세요.\n\n"
                "텍스트:\n```\n" + raw_text[:8000] + "\n```"
            )
            completion_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "문장 분할 전문가로서, 입력을 고품질 문장 리스트로 변환합니다."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }
            if "gpt-5" not in self.model.lower():
                completion_params["temperature"] = 0.1
            resp = self.client.chat.completions.create(**completion_params)
            data = json.loads(resp.choices[0].message.content or "{}")
            sents = [s.strip() for s in (data.get("sentences") or []) if isinstance(s, str) and s.strip()]
            if sents:
                return {"sentences": sents}
            return {"sentences": self._fallback_sentence_split(raw_text)}
        except Exception as e:
            logger.warning(f"extract_sentences failed, fallback: {e}")
            return {"sentences": self._fallback_sentence_split(raw_text)}

    def _fallback_sentence_split(self, text: str) -> list:
        import re
        raw = re.split(r"(?<=[.!?\n])\s+", text)
        sents = []
        for s in raw:
            s = " ".join(s.strip().split())
            if 20 <= len(s) <= 300 and " " in s and "_" not in s:
                sents.append(s)
        return sents
    
    def _create_parsing_prompt(self, text: str) -> str:
        """파싱 프롬프트 생성"""
        return f"""
다음 이력서에서 정보를 추출하여 JSON 형식으로 반환하세요.

이력서:
```
{text}
```

추출할 정보:
1. 개인정보 (이름, 연락처, 이메일)
2. 경력 요약
3. 회사 경력 (학교/프로젝트 제외, 실제 회사 근무만)
   - 각 경력의 회사명, 직책, 기간(YYYY.MM~YYYY.MM, 불명확하면 null), 업무내용(responsibilities: 리스트)
   - 총 경력 년수 계산 (개월 단위로 계산 후 년으로 변환, 소수점 1자리, 불명확하면 0)
4. 학력
5. 기술 스킬 (프로그래밍 언어, 프레임워크, 도구)
6. 자격증
7. 언어 능력
8. 프로젝트 경험 (회사 프로젝트 제외)

주의사항:
- 경력 년수: 학교 다닌 기간 제외, 실제 회사 근무 기간만 계산
- "2021.07 ~ 2022.02"는 7개월 (0.6년)
- "1년차"는 1년
- "만 10개월"은 0.8년
- 인턴도 경력에 포함
- 없는 정보는 빈 값 또는 null (추측 금지)

JSON 형식:
{{
  "personal_info": {{
    "name": "홍길동",
    "phone": "010-1234-5678",
    "email": "email@example.com"
  }},
  "summary": "간단한 자기소개",
  "total_experience_years": 2.5,
  "work_experience": [
    {{
      "company": "회사명",
      "position": "직책",
      "start_date": "2021.07",
      "end_date": "2022.02",
      "duration_months": 7,
      "responsibilities": ["업무1", "업무2"]
    }}
  ],
  "education": [
    {{
      "school": "대학교명",
      "degree": "학사",
      "major": "전공",
      "graduation_year": "2024"
    }}
  ],
  "skills": {{
    "programming_languages": ["Python", "Java"],
    "frameworks": ["Django", "React"],
    "databases": ["MySQL", "PostgreSQL"],
    "tools": ["Git", "Docker"],
    "cloud": ["AWS", "GCP"]
  }},
  "certifications": [
    {{
      "name": "자격증명",
      "issued_date": "2023.06"
    }}
  ],
  "languages": [
    {{
      "language": "English",
      "proficiency": "Business"
    }}
  ],
  "projects": [
    {{
      "name": "프로젝트명",
      "period": "2023.01 ~ 2023.03",
      "description": "설명",
      "tech_stack": ["React", "Node.js"]
    }}
  ],
  "skills_narrative": "React와 TypeScript로 SPA를 개발했습니다. Next.js로 SSR을 구현했습니다. Redux로 전역 상태를 관리했습니다. Django로 REST API 서버를 구축했습니다. (보유한 기술 스택과 사용 경험을 완전한 문장으로 서술)",
  "projects_narrative": "Make your World 프로젝트에서 ChatGPT API를 연동하여 대화형 소설 생성 기능을 구현했습니다. POISON 프로젝트에서 이미지 인식 AI를 활용한 독초 판별 서비스를 개발했습니다. (주요 프로젝트 경험을 완전한 문장으로 서술)"
}}

**추가 요구사항:**
- skills_narrative: 기술 스택 사용 경험을 완전한 문장으로 작성 (필수!)
- projects_narrative: 프로젝트 경험을 완전한 문장으로 작성 (필수!)
- 이 두 필드는 임베딩 생성에 사용되므로 반드시 포함
"""
    
    def _parse_resume_in_chunks(self, raw_text: str, chunk_size: int = 8000) -> Dict[str, Any]:
        """긴 텍스트를 청크로 나눠서 파싱 후 병합"""
        # 첫 번째 청크: 전체 구조 파악 (개인정보, 요약 등)
        first_chunk = raw_text[:chunk_size]
        prompt = self._create_parsing_prompt(first_chunk)
        
        completion_params = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 이력서 분석 전문가입니다. 주어진 이력서에서 정확하게 정보를 추출하여 JSON 형식으로 반환합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        if "gpt-5" not in self.model.lower():
            completion_params["temperature"] = 0.1
        
        try:
            response = self.client.chat.completions.create(**completion_params)
            result_text = response.choices[0].message.content
            merged_data = json.loads(result_text)
            
            # 나머지 청크 처리 (경력, 프로젝트 등 상세 정보)
            remaining_text = raw_text[chunk_size:]
            chunks = []
            if remaining_text:
                # 나머지 텍스트를 청크로 나눔
                chunks = [remaining_text[i:i+chunk_size] for i in range(0, len(remaining_text), chunk_size)]
                
                for i, chunk in enumerate(chunks):
                    if i >= 3:  # 최대 3개 청크만 추가 처리 (비용 절감)
                        logger.warning(f"Skipping remaining chunks (processed {i+1} chunks)")
                        break
                    
                    # 상세 정보 추출 프롬프트
                    detail_prompt = f"""
다음은 이력서의 추가 부분입니다. 이전에 추출한 정보에 추가하여 경력, 프로젝트, 스킬 등의 상세 정보를 추출하세요.

추가 텍스트:
```
{chunk}
```

이전에 추출한 정보:
- 경력: {len(merged_data.get('work_experience', []))}개
- 프로젝트: {len(merged_data.get('projects', []))}개
- 스킬: {len(merged_data.get('skills', {}).get('programming_languages', []))}개

JSON 형식으로 반환하되, 이전 정보에 **추가**되는 정보만 포함하세요.
리스트 필드(work_experience, projects, skills 등)는 이전 항목에 새로운 항목을 추가하세요.
"""
                    
                    detail_params = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "당신은 이력서 분석 전문가입니다. 주어진 이력서의 추가 부분에서 상세 정보를 추출하여 JSON 형식으로 반환합니다."
                            },
                            {
                                "role": "user",
                                "content": detail_prompt
                            }
                        ],
                        "response_format": {"type": "json_object"}
                    }
                    
                    if "gpt-5" not in self.model.lower():
                        detail_params["temperature"] = 0.1
                    
                    try:
                        detail_response = self.client.chat.completions.create(**detail_params)
                        detail_text = detail_response.choices[0].message.content
                        detail_data = json.loads(detail_text)
                        
                        # 결과 병합
                        merged_data = self._merge_parsed_data(merged_data, detail_data)
                        logger.info(f"Processed chunk {i+2}, merged additional data")
                    except Exception as e:
                        logger.warning(f"Failed to process chunk {i+2}: {e}")
                        continue
            
            num_chunks = 1 + min(len(chunks) if remaining_text else 0, 3)
            logger.info(f"LLM parsing successful (chunked). Model: {self.model}, chunks: {num_chunks}")
            return merged_data
            
        except Exception as e:
            logger.error(f"Chunked parsing failed: {e}")
            return self._fallback_parsing(raw_text)
    
    def _merge_parsed_data(self, base: Dict[str, Any], additional: Dict[str, Any]) -> Dict[str, Any]:
        """파싱된 데이터 병합 (리스트는 extend, 딕셔너리는 merge)"""
        merged = base.copy()
        
        # 리스트 필드: extend
        list_fields = ['work_experience', 'education', 'certifications', 'languages', 'projects']
        for field in list_fields:
            base_list = merged.get(field, [])
            add_list = additional.get(field, [])
            if isinstance(base_list, list) and isinstance(add_list, list):
                merged[field] = base_list + add_list
        
        # 딕셔너리 필드: merge
        dict_fields = ['personal_info', 'skills']
        for field in dict_fields:
            base_dict = merged.get(field, {})
            add_dict = additional.get(field, {})
            if isinstance(base_dict, dict) and isinstance(add_dict, dict):
                if field == 'skills':
                    # skills는 중첩 딕셔너리
                    for key in add_dict:
                        if key in base_dict and isinstance(base_dict[key], list) and isinstance(add_dict[key], list):
                            base_dict[key].extend(add_dict[key])
                        elif key not in base_dict:
                            base_dict[key] = add_dict[key]
                else:
                    base_dict.update(add_dict)
                merged[field] = base_dict
        
        # 문자열 필드: 더 긴 것으로 선택 (또는 병합)
        string_fields = ['summary']
        for field in string_fields:
            base_str = merged.get(field, "")
            add_str = additional.get(field, "")
            if add_str and len(add_str) > len(base_str):
                merged[field] = add_str
        
        # 숫자 필드: 최대값 선택
        if 'total_experience_years' in additional:
            merged['total_experience_years'] = max(
                merged.get('total_experience_years', 0),
                additional.get('total_experience_years', 0)
            )
        
        return merged
    
    def _fallback_parsing(self, raw_text: str) -> Dict[str, Any]:
        """LLM 실패 시 기본 파싱"""
        return {
            "personal_info": {},
            "summary": "",
            "total_experience_years": 0,
            "work_experience": [],
            "education": [],
            "skills": {
                "programming_languages": [],
                "frameworks": [],
                "databases": [],
                "tools": [],
                "cloud": []
            },
            "certifications": [],
            "languages": [],
            "projects": [],
            "skills_narrative": "",
            "projects_narrative": ""
        }
    
    def extract_structured_info(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM 파싱 결과를 DB 저장 형식으로 변환
        
        Returns:
            {
                "extracted_skills": ["python", "django", ...],
                "extracted_experience_years": 2.5,
                "extracted_education_level": "학사",
                "extracted_domains": ["백엔드", "데이터"],
                "extracted_certifications": ["정보처리기사"],
                "parsed_data": {...}
            }
        """
        # 모든 스킬 합치기
        all_skills = []
        skills_data = parsed_data.get("skills", {})
        
        if isinstance(skills_data, dict):
            for category in ['programming_languages', 'frameworks', 'databases', 'tools', 'cloud']:
                category_skills = skills_data.get(category, [])
                if category_skills:
                    all_skills.extend([s.lower() for s in category_skills])
        
        # 스킬 정규화 (react.js → react, next.js는 유지)
        normalized_skills = []
        for skill in all_skills:
            # .js 제거 (단, next.js, vue.js, node.js 등은 유지)
            if skill.endswith('.js') and skill not in ['next.js', 'vue.js', 'node.js', 'express.js', 'nuxt.js', 'swiper.js']:
                normalized_skills.append(skill.replace('.js', ''))
            else:
                normalized_skills.append(skill)
        
        all_skills = list(set(normalized_skills))  # 중복 제거
        
        # 경력 년수
        experience_years = parsed_data.get("total_experience_years", 0)
        
        # 학력 수준
        education_level = ""
        education_list = parsed_data.get("education", [])
        if education_list and len(education_list) > 0:
            degree = education_list[0].get("degree", "")
            if "박사" in degree:
                education_level = "박사"
            elif "석사" in degree:
                education_level = "석사"
            elif "학사" in degree or "대학" in degree:
                education_level = "학사"
        
        # 자격증
        certifications = []
        cert_list = parsed_data.get("certifications", [])
        if cert_list:
            certifications = [c.get("name", "") for c in cert_list if c.get("name")]
        
        return {
            "extracted_skills": all_skills,
            "extracted_experience_years": float(experience_years) if experience_years else 0,
            "extracted_education_level": education_level,
            "extracted_domains": [],  # TODO: 도메인 추출
            "extracted_certifications": certifications,
            "parsed_data": parsed_data
        }
    
    def parse_job_posting(self, raw_text: str, title: str = "") -> Dict[str, Any]:
        """
        채용공고 텍스트를 구조화된 데이터로 변환
        
        Args:
            raw_text: 채용공고 원문
            title: 공고 제목 (선택)
            
        Returns:
            {
                "requirements": {
                    "required": ["자격요건1", "자격요건2", ...],
                    "preferred": ["우대사항1", "우대사항2", ...]
                },
                "description": "업무 설명",
                "responsibilities": ["주요 업무1", "주요 업무2"],
                "benefits": ["복지1", "복지2"]
            }
        """
        if not self.client:
            logger.warning("LLM client not available. Skipping LLM parsing.")
            return self._fallback_job_parsing(raw_text)
        
        try:
            # 텍스트가 길면 청크로 나눠서 처리
            max_chars = 8000
            if len(raw_text) <= max_chars:
                # 짧은 텍스트는 그대로 처리
                text_to_parse = raw_text
                prompt = self._create_job_parsing_prompt(text_to_parse, title)
                
                completion_params = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "당신은 채용공고 분석 전문가입니다. 주어진 채용공고에서 정확하게 정보를 추출하여 JSON 형식으로 반환합니다."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "response_format": {"type": "json_object"}
                }
                
                if "gpt-5" not in self.model.lower():
                    completion_params["temperature"] = 0.1
                
                response = self.client.chat.completions.create(**completion_params)
                result_text = response.choices[0].message.content
                parsed_data = json.loads(result_text)
                
                logger.info(f"Job posting LLM parsing successful. Model: {self.model}")
                return parsed_data
            else:
                # 긴 텍스트는 청크로 나눠서 처리
                logger.info(f"Job text too long ({len(raw_text)} chars), processing in chunks...")
                return self._parse_job_in_chunks(raw_text, title, max_chars)
            
        except Exception as e:
            logger.error(f"Job posting LLM parsing failed: {e}")
            return self._fallback_job_parsing(raw_text)
    
    def _create_job_parsing_prompt(self, text: str, title: str) -> str:
        """채용공고 파싱 프롬프트 생성"""
        return f"""
다음 채용공고에서 정보를 추출하여 JSON 형식으로 반환하세요.

채용공고:
제목: {title}
```
{text}
```

추출할 정보:
1. 자격요건 (required) - 필수 조건, "이런 분과 함께하고 싶어요" 등
   - 각 조건을 완전한 문장으로 추출
   - 예: "React, Next.js, TypeScript 기반 프론트엔드 개발 경험이 있는 분"

2. 우대사항 (preferred) - 우대 조건, "이런 분을 우대해요" 등
   - 각 조건을 완전한 문장으로 추출
   - 예: "메시지 큐(Kafka, RabbitMQ) 경험이 있는 분"

3. 업무 설명 (description) - 주요 업무, "이런 일을 하게 돼요" 등
   - 전체 업무 내용을 문단으로 작성

4. 주요 업무 (responsibilities) - 구체적인 업무 항목들
   - 리스트 형태로 추출

5. 복지/혜택 (benefits)
   - 리스트 형태로 추출

주의사항:
- required와 preferred는 **완전한 문장**으로 추출 (임베딩 생성에 사용)
- 단순 키워드가 아닌 문맥이 있는 문장으로 작성
- 없는 정보는 빈 리스트 또는 빈 문자열

JSON 형식:
{{
  "requirements": {{
    "required": [
      "Java / Kotlin / Spring Framework를 활용한 백엔드 개발 경험이 있는 분",
      "RDBMS 설계 및 최적화 경험이 있는 분",
      "RESTful API 설계 및 구현 역량을 갖춘 분"
    ],
    "preferred": [
      "메시지 큐(Kafka, RabbitMQ 등) 및 이벤트 드리븐 아키텍처 경험이 있는 분",
      "대규모 트래픽 서비스 운영 경험이 있는 분",
      "클라우드(AWS, GCP, Azure) 기반 서비스 운영 경험이 있는 분"
    ]
  }},
  "description": "Java / Spring Boot / Kotlin 기반 백엔드 서비스를 개발·운영합니다. RESTful API, WebSocket 기반 서비스를 설계·구현하고, 대규모 데이터 처리를 위한 DB 구조를 설계하고 최적화합니다.",
  "responsibilities": [
    "Java / Spring Boot / Kotlin 기반 백엔드 서비스를 개발·운영",
    "RESTful API, WebSocket 기반 서비스를 설계·구현",
    "대규모 데이터 처리를 위한 DB 구조를 설계하고 최적화"
  ],
  "benefits": [
    "연봉 협상 가능",
    "재택근무 지원",
    "자기계발비 지원"
  ]
}}

**중요:**
- required, preferred는 반드시 완전한 문장으로 작성!
- 이 데이터는 섹션별 임베딩 생성에 사용됨
"""
    
    def _parse_job_in_chunks(self, raw_text: str, title: str, chunk_size: int = 8000) -> Dict[str, Any]:
        """긴 공고 텍스트를 청크로 나눠서 파싱 후 병합"""
        # 첫 번째 청크: 전체 구조 파악
        first_chunk = raw_text[:chunk_size]
        prompt = self._create_job_parsing_prompt(first_chunk, title)
        
        completion_params = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 채용공고 분석 전문가입니다. 주어진 채용공고에서 정확하게 정보를 추출하여 JSON 형식으로 반환합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        if "gpt-5" not in self.model.lower():
            completion_params["temperature"] = 0.1
        
        try:
            response = self.client.chat.completions.create(**completion_params)
            result_text = response.choices[0].message.content
            merged_data = json.loads(result_text)
            
            # 나머지 청크 처리
            remaining_text = raw_text[chunk_size:]
            chunks = []
            if remaining_text:
                chunks = [remaining_text[i:i+chunk_size] for i in range(0, len(remaining_text), chunk_size)]
                
                for i, chunk in enumerate(chunks):
                    if i >= 2:  # 최대 2개 청크만 추가 처리 (공고는 보통 짧음)
                        logger.warning(f"Skipping remaining chunks (processed {i+1} chunks)")
                        break
                    
                    # 상세 정보 추출 프롬프트
                    detail_prompt = f"""
다음은 채용공고의 추가 부분입니다. 이전에 추출한 정보에 추가하여 자격요건, 우대사항, 업무 내용 등의 상세 정보를 추출하세요.

추가 텍스트:
```
{chunk}
```

이전에 추출한 정보:
- 자격요건: {len(merged_data.get('requirements', {}).get('required', []))}개
- 우대사항: {len(merged_data.get('requirements', {}).get('preferred', []))}개
- 주요 업무: {len(merged_data.get('responsibilities', []))}개

JSON 형식으로 반환하되, 이전 정보에 **추가**되는 정보만 포함하세요.
리스트 필드(required, preferred, responsibilities, benefits 등)는 이전 항목에 새로운 항목을 추가하세요.
"""
                    
                    detail_params = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "당신은 채용공고 분석 전문가입니다. 주어진 채용공고의 추가 부분에서 상세 정보를 추출하여 JSON 형식으로 반환합니다."
                            },
                            {
                                "role": "user",
                                "content": detail_prompt
                            }
                        ],
                        "response_format": {"type": "json_object"}
                    }
                    
                    if "gpt-5" not in self.model.lower():
                        detail_params["temperature"] = 0.1
                    
                    try:
                        detail_response = self.client.chat.completions.create(**detail_params)
                        detail_text = detail_response.choices[0].message.content
                        detail_data = json.loads(detail_text)
                        
                        # 결과 병합
                        merged_data = self._merge_job_parsed_data(merged_data, detail_data)
                        logger.info(f"Processed job chunk {i+2}, merged additional data")
                    except Exception as e:
                        logger.warning(f"Failed to process job chunk {i+2}: {e}")
                        continue
            
            num_chunks = 1 + min(len(chunks) if remaining_text else 0, 2)
            logger.info(f"Job posting LLM parsing successful (chunked). Model: {self.model}, chunks: {num_chunks}")
            return merged_data
            
        except Exception as e:
            logger.error(f"Chunked job parsing failed: {e}")
            return self._fallback_job_parsing(raw_text)
    
    def _merge_job_parsed_data(self, base: Dict[str, Any], additional: Dict[str, Any]) -> Dict[str, Any]:
        """공고 파싱된 데이터 병합"""
        merged = base.copy()
        
        # requirements 딕셔너리 병합
        if 'requirements' in additional:
            if 'requirements' not in merged:
                merged['requirements'] = {'required': [], 'preferred': []}
            
            base_req = merged['requirements']
            add_req = additional['requirements']
            
            # required 리스트 extend
            if 'required' in add_req and isinstance(add_req['required'], list):
                base_req['required'] = (base_req.get('required', []) or []) + add_req['required']
            
            # preferred 리스트 extend
            if 'preferred' in add_req and isinstance(add_req['preferred'], list):
                base_req['preferred'] = (base_req.get('preferred', []) or []) + add_req['preferred']
        
        # 리스트 필드: extend
        list_fields = ['responsibilities', 'benefits']
        for field in list_fields:
            base_list = merged.get(field, [])
            add_list = additional.get(field, [])
            if isinstance(base_list, list) and isinstance(add_list, list):
                merged[field] = base_list + add_list
        
        # 문자열 필드: 더 긴 것으로 선택
        string_fields = ['description']
        for field in string_fields:
            base_str = merged.get(field, "")
            add_str = additional.get(field, "")
            if add_str and len(add_str) > len(base_str):
                merged[field] = add_str
        
        return merged
    
    def _fallback_job_parsing(self, raw_text: str) -> Dict[str, Any]:
        """LLM 실패 시 기본 공고 파싱"""
        return {
            "requirements": {
                "required": [],
                "preferred": []
            },
            "description": raw_text,
            "responsibilities": [],
            "benefits": []
        }

