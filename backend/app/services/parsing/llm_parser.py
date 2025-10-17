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
            # 텍스트가 너무 길면 앞부분만 (토큰 제한)
            max_chars = 8000
            text_to_parse = raw_text[:max_chars] if len(raw_text) > max_chars else raw_text
            
            prompt = self._create_parsing_prompt(text_to_parse)
            
            # API 호출 파라미터 구성
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
            
            # GPT-5가 아닌 경우에만 temperature 설정
            if "gpt-5" not in self.model.lower():
                completion_params["temperature"] = 0.1
            
            response = self.client.chat.completions.create(**completion_params)
            
            result_text = response.choices[0].message.content
            parsed_data = json.loads(result_text)
            
            logger.info(f"LLM parsing successful. Model: {self.model}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return self._fallback_parsing(raw_text)

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
            # 텍스트가 너무 길면 앞부분만 (토큰 제한)
            max_chars = 8000
            text_to_parse = raw_text[:max_chars] if len(raw_text) > max_chars else raw_text
            
            prompt = self._create_job_parsing_prompt(text_to_parse, title)
            
            # API 호출 파라미터 구성
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
            
            # GPT-5가 아닌 경우에만 temperature 설정
            if "gpt-5" not in self.model.lower():
                completion_params["temperature"] = 0.1
            
            response = self.client.chat.completions.create(**completion_params)
            
            result_text = response.choices[0].message.content
            parsed_data = json.loads(result_text)
            
            logger.info(f"Job posting LLM parsing successful. Model: {self.model}")
            return parsed_data
            
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

