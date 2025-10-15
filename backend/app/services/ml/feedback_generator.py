"""
매칭 피드백 생성 서비스
"""
from typing import Dict, List, Any
import json
import openai
from app.models.job import JobPosting
from app.models.resume import Resume
from app.core.config import get_settings

settings = get_settings()


class FeedbackGenerator:
    """매칭 결과 기반 피드백 생성 (GPT-5 기반)"""
    
    def __init__(self):
        self.use_gpt = settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your-openai-api-key-here"
        if self.use_gpt:
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
    
    def generate_feedback(
        self,
        job: JobPosting,
        resume: Resume,
        matching_evidence: Dict[str, Any],
        overall_score: float,
        grade: str
    ) -> Dict[str, List[str]]:
        """
        매칭 결과 기반 피드백 생성 (GPT-5 사용)
        
        Returns:
            {
                "strengths": ["강점 1", "강점 2"],
                "improvements": ["개선점 1", "개선점 2"],
                "recommendations": ["추천 1", "추천 2"]
            }
        """
        # GPT-5가 설정되어 있으면 LLM 사용, 아니면 rule-based
        if self.use_gpt:
            return self._generate_feedback_with_gpt(
                job, resume, matching_evidence, overall_score, grade
            )
        else:
            return self._generate_feedback_rule_based(
                job, resume, matching_evidence, overall_score, grade
            )
    
    def _generate_feedback_with_gpt(
        self,
        job: JobPosting,
        resume: Resume,
        matching_evidence: Dict[str, Any],
        overall_score: float,
        grade: str
    ) -> Dict[str, List[str]]:
        """GPT-5를 사용한 피드백 생성 (문장별 상세 분석)"""
        
        # 매칭 정보 요약
        req = matching_evidence.get('required_skills', {})
        pref = matching_evidence.get('preferred_skills', {})
        
        # 자격요건/우대사항 문장 추출
        required_list = job.requirements.get('required', []) if job.requirements else []
        preferred_list = job.requirements.get('preferred', []) if job.requirements else []
        
        # 이력서 narrative 추출
        parsed_data = resume.parsed_data or {}
        skills_narrative = parsed_data.get('skills_narrative', '')
        projects_narrative = parsed_data.get('projects_narrative', '')
        work_exp = parsed_data.get('work_experience', [])
        work_exp_text = '\n'.join([
            f"- {exp.get('company', '')}: {', '.join(exp.get('responsibilities', []))}"
            for exp in work_exp[:3]
        ]) if work_exp else '경력 정보 없음'
        
        prompt = f"""당신은 채용 전문가입니다. 구직자의 이력서와 채용 공고를 **문장별로 상세히 비교 분석**하여 개인화된 피드백을 제공해주세요.

# 📋 채용 공고
- 직무: {job.title}
- 회사: {job.company.name if job.company else '미상'}
- 경력 요구: {job.experience_level or '미상'}

# ✅ 자격요건 (각 조건별로 분석 필요!)
{chr(10).join(f"{i+1}. {r}" for i, r in enumerate(required_list[:7]))}

# 🌟 우대사항
{chr(10).join(f"{i+1}. {p}" for i, p in enumerate(preferred_list[:7]))}

# 👤 구직자 이력서 (상세)
## 보유 스킬 및 경험:
{skills_narrative[:500] if skills_narrative else '스킬 정보 없음'}

## 프로젝트 경험:
{projects_narrative[:500] if projects_narrative else '프로젝트 정보 없음'}

## 경력:
{work_exp_text}
- 총 경력: {resume.extracted_experience_years or 0}년
- 학력: {resume.extracted_education_level or '미상'}

# 📊 매칭 점수 요약
- 종합 점수: {overall_score*100:.1f}% ({grade.upper()})
- 자격요건 충족률: {req.get('match_rate', '?')}
- 우대사항 충족률: {pref.get('match_rate', '?')}

# 📝 요청사항
다음 형식의 JSON으로 **문장별 상세 분석**과 피드백을 제공해주세요:

{{
  "detailed_matching": [
    {{
      "requirement_number": 1,
      "requirement_text": "자격요건 문장",
      "match_status": "충족|부분충족|부족",
      "match_score": "90%",
      "resume_evidence": "이력서에서 매칭되는 구체적 내용",
      "feedback": "해당 조건에 대한 구체적 피드백"
    }},
    ...
  ],
  "strengths": [
    "강점 1 (구체적으로, 이력서 내용 인용)",
    "강점 2",
    "강점 3"
  ],
  "improvements": [
    "개선점 1 (구체적인 행동 제안)",
    "개선점 2",
    "개선점 3"
  ],
  "recommendations": [
    "추천 1 (실행 가능한 제안)",
    "추천 2",
    "추천 3"
  ]
}}

**중요 지침:**
1. **detailed_matching**: 자격요건 각 조건마다 분석 (최대 7개)
   - 이력서에서 해당 조건과 매칭되는 구체적 내용 찾기
   - 충족도 평가 (충족/부분충족/부족)
   - 조건별 구체적 피드백
2. **strengths**: 전체적인 강점 3-4개 (이력서 내용 인용)
3. **improvements**: 구체적이고 실행 가능한 개선점 3-4개
4. **recommendations**: 다음 단계 행동 제안 3개
5. 긍정적이고 격려하는 톤 유지
6. 이력서의 실제 내용을 인용하여 구체성 확보"""

        try:
            # GPT-5 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 채용 전문가입니다. 구직자에게 건설적이고 실행 가능한 피드백을 제공합니다."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            feedback_text = response.choices[0].message.content
            feedback = json.loads(feedback_text)
            
            # 응답 검증 (detailed_matching 추가)
            required_keys = ['strengths', 'improvements', 'recommendations']
            if not all(k in feedback for k in required_keys):
                raise ValueError("Invalid feedback format")
            
            # detailed_matching이 없으면 빈 리스트로
            if 'detailed_matching' not in feedback:
                feedback['detailed_matching'] = []
            
            return feedback
            
        except Exception as e:
            print(f"GPT-5 피드백 생성 실패: {e}")
            # Fallback to rule-based
            return self._generate_feedback_rule_based(
                job, resume, matching_evidence, overall_score, grade
            )
    
    def _generate_feedback_rule_based(
        self,
        job: JobPosting,
        resume: Resume,
        matching_evidence: Dict[str, Any],
        overall_score: float,
        grade: str
    ) -> Dict[str, List[str]]:
        """Rule-based 피드백 생성 (Fallback)"""
        feedback = {
            "strengths": [],
            "improvements": [],
            "recommendations": []
        }
        
        # 1. 강점 (잘 매칭된 부분)
        feedback["strengths"] = self._generate_strengths(
            matching_evidence, resume, job
        )
        
        # 2. 개선점 (부족한 자격요건)
        feedback["improvements"] = self._generate_improvements(
            matching_evidence, overall_score, grade
        )
        
        # 3. 추천 사항 (우대사항, 추가 제안)
        feedback["recommendations"] = self._generate_recommendations(
            matching_evidence, job, resume, grade
        )
        
        return feedback
    
    def _generate_strengths(
        self,
        evidence: Dict[str, Any],
        resume: Resume,
        job: JobPosting
    ) -> List[str]:
        """강점 피드백 생성"""
        strengths = []
        
        # 자격요건 매칭
        required = evidence.get("required_skills", {})
        matched_required = required.get("matched", [])
        
        if matched_required:
            count = len(matched_required)
            if count >= 3:
                strengths.append(f"✅ 자격요건 {count}개 충족 (우수)")
            elif count >= 1:
                strengths.append(f"✅ 자격요건 {count}개 충족")
            
            # 구체적인 스킬 언급
            if count <= 3:
                for skill in matched_required[:3]:
                    strengths.append(f"✅ {skill}")
        
        # 우대사항 매칭
        preferred = evidence.get("preferred_skills", {})
        matched_preferred = preferred.get("matched", [])
        
        if matched_preferred:
            count = len(matched_preferred)
            strengths.append(f"✅ 우대사항 {count}개 충족")
            for skill in matched_preferred[:2]:
                strengths.append(f"✅ {skill}")
        
        # 경력 매칭
        exp_evidence = evidence.get("experience_evidence", {})
        if exp_evidence.get("level_match"):
            strengths.append(f"✅ 경력 요구사항 충족: {exp_evidence.get('details', '')}")
        
        # 유사도
        similarity = evidence.get("similarity_score", 0)
        if similarity >= 0.7:
            strengths.append(f"✅ 높은 직무 유사도: {similarity*100:.0f}%")
        elif similarity >= 0.5:
            strengths.append(f"✅ 직무 유사도: {similarity*100:.0f}%")
        
        return strengths
    
    def _generate_improvements(
        self,
        evidence: Dict[str, Any],
        overall_score: float,
        grade: str
    ) -> List[str]:
        """개선점 피드백 생성"""
        improvements = []
        
        # 자격요건 부족
        required = evidence.get("required_skills", {})
        missing_required = required.get("missing", [])
        matched_required = required.get("matched", [])
        required_score = required.get("score", 0)
        
        if required_score < 0.5:
            improvements.append(f"⚠️ 자격요건 충족도가 낮습니다 ({required_score*100:.0f}%)")
        
        if missing_required:
            # 중요한 누락 스킬 강조
            critical_count = min(3, len(missing_required))
            improvements.append(f"📝 부족한 자격요건 {len(missing_required)}개:")
            for skill in missing_required[:critical_count]:
                improvements.append(f"   • {skill}")
            
            if len(missing_required) > critical_count:
                improvements.append(f"   • 외 {len(missing_required) - critical_count}개")
        
        # 경력 부족
        exp_evidence = evidence.get("experience_evidence", {})
        required_years = exp_evidence.get("required_years", 0)
        candidate_years = exp_evidence.get("candidate_years", 0)
        
        if required_years > 0 and candidate_years < required_years:
            gap = required_years - candidate_years
            improvements.append(f"⚠️ 경력이 {gap}년 부족합니다 (요구: {required_years}년, 보유: {candidate_years}년)")
        
        # 우대사항 부족
        preferred = evidence.get("preferred_skills", {})
        missing_preferred = preferred.get("missing", [])
        
        if len(missing_preferred) > 3:
            improvements.append(f"📝 우대사항 {len(missing_preferred)}개 미충족")
        
        return improvements
    
    def _generate_recommendations(
        self,
        evidence: Dict[str, Any],
        job: JobPosting,
        resume: Resume,
        grade: str
    ) -> List[str]:
        """추천 사항 생성"""
        recommendations = []
        
        # 우대사항 추천
        preferred = evidence.get("preferred_skills", {})
        missing_preferred = preferred.get("missing", [])
        
        if missing_preferred:
            recommendations.append("💡 우대사항 보완 제안:")
            for skill in missing_preferred[:3]:
                recommendations.append(f"   • {skill}")
        
        # 경력 개선 제안
        exp_evidence = evidence.get("experience_evidence", {})
        required_years = exp_evidence.get("required_years", 0)
        candidate_years = exp_evidence.get("candidate_years", 0)
        
        if required_years > candidate_years:
            if candidate_years == 0:
                recommendations.append(f"💡 이 공고는 {required_years}년 이상 경력자를 우대합니다")
            else:
                recommendations.append(f"💡 경력 {required_years}년 이상이 되면 더 좋은 매칭이 예상됩니다")
        
        # 자격요건 중 핵심 스킬 추천
        required = evidence.get("required_skills", {})
        missing_required = required.get("missing", [])
        
        if missing_required:
            # 핵심 기술 스택 추천
            tech_keywords = ['react', 'vue', 'angular', 'next.js', 'spring', 'django', 
                           'kubernetes', 'aws', 'docker']
            
            for missing in missing_required[:2]:
                missing_lower = missing.lower()
                for tech in tech_keywords:
                    if tech in missing_lower:
                        recommendations.append(f"💡 {tech.title()} 경험을 이력서에 추가하면 매칭도가 향상됩니다")
                        break
        
        # 유사도 기반 추천
        similarity = evidence.get("similarity_score", 0)
        if similarity < 0.5:
            recommendations.append("💡 이력서 내용을 공고와 더 관련된 키워드로 보완하세요")
        
        # 등급별 추천
        if grade in ['poor', 'caution']:
            recommendations.append("💡 이 공고보다 다른 공고가 더 적합할 수 있습니다")
        elif grade == 'fair':
            recommendations.append("💡 자격요건을 더 충족하면 합격 가능성이 높아집니다")
        elif grade == 'good':
            recommendations.append("💡 우대사항을 추가로 충족하면 Excellent 등급이 가능합니다")
        
        return recommendations

