"""
PDF Parser - PDF 파일에서 텍스트 추출
"""
import fitz  # PyMuPDF
from typing import Dict, Any
from pathlib import Path


class PDFParser:
    """PDF 파일 파서"""
    
    def extract_text(self, file_path: str) -> str:
        """
        PDF 파일에서 텍스트 추출
        
        Args:
            file_path: PDF 파일 경로
            
        Returns:
            추출된 텍스트
        """
        try:
            doc = fitz.open(file_path)
            text = ""
            
            for page in doc:
                text += page.get_text()
            
            doc.close()
            
            # 텍스트 정리
            text = self._clean_text(text)
            
            return text
            
        except Exception as e:
            raise Exception(f"PDF 텍스트 추출 실패: {e}")
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        # 불필요한 공백 제거
        text = text.strip()
        
        # 연속된 공백을 하나로
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # 연속된 줄바꿈을 하나로
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text
    
    def parse_resume(self, text: str) -> Dict[str, Any]:
        """
        이력서 텍스트에서 구조화된 정보 추출
        
        Args:
            text: 이력서 텍스트
            
        Returns:
            구조화된 이력서 데이터
        """
        # TODO: 더 정교한 파싱 로직 구현
        # 현재는 기본 구조만 반환
        
        return {
            "personal_info": self._extract_personal_info(text),
            "summary": self._extract_summary(text),
            "work_experience": self._extract_work_experience(text),
            "education": self._extract_education(text),
            "skills": self._extract_skills(text),
            "certifications": self._extract_certifications(text),
            "languages": self._extract_languages(text),
            "projects": self._extract_projects(text)
        }
    
    def _extract_personal_info(self, text: str) -> Dict[str, str]:
        """개인정보 추출"""
        # TODO: 이름, 연락처, 이메일 등 추출
        return {}
    
    def _extract_summary(self, text: str) -> str:
        """요약 추출"""
        # TODO: 자기소개 또는 요약 부분 추출
        return ""
    
    def _extract_work_experience(self, text: str) -> list:
        """경력 정보 추출"""
        # TODO: 회사명, 직책, 근무기간, 업무 내용 추출
        return []
    
    def _extract_education(self, text: str) -> list:
        """학력 정보 추출"""
        # TODO: 학교명, 전공, 학위, 졸업년도 추출
        return []
    
    def _extract_skills(self, text: str) -> list:
        """기술 스킬 추출"""
        # 간단한 키워드 기반 스킬 추출
        common_skills = [
            # 프로그래밍 언어
            "python", "java", "javascript", "typescript", "kotlin", "go", "rust",
            "c++", "c#", "php", "ruby", "swift", "scala",
            
            # 프레임워크/라이브러리
            "react", "vue", "angular", "svelte", "next.js", "nuxt.js",
            "django", "flask", "fastapi", "spring", "spring boot",
            "express", "nestjs", "nodejs", "node.js",
            
            # 데이터베이스
            "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
            "oracle", "mssql", "sqlite", "dynamodb", "cassandra",
            
            # 클라우드/인프라
            "aws", "azure", "gcp", "docker", "kubernetes", "k8s",
            "terraform", "ansible", "jenkins", "github actions",
            "gitlab ci", "circleci",
            
            # 도구
            "git", "jira", "confluence", "slack", "notion",
            "figma", "sketch", "zeplin"
        ]
        
        text_lower = text.lower()
        extracted_skills = []
        
        for skill in common_skills:
            if skill in text_lower:
                # 원래 표기 찾기 시도
                import re
                pattern = re.compile(re.escape(skill), re.IGNORECASE)
                match = pattern.search(text)
                if match:
                    extracted_skills.append(match.group())
                else:
                    extracted_skills.append(skill)
        
        # 중복 제거
        return list(set(extracted_skills))
    
    def _extract_certifications(self, text: str) -> list:
        """자격증 추출"""
        # TODO: 자격증 정보 추출
        return []
    
    def _extract_languages(self, text: str) -> list:
        """언어 능력 추출"""
        # TODO: 외국어 능력 추출
        return []
    
    def _extract_projects(self, text: str) -> list:
        """프로젝트 경험 추출"""
        # TODO: 프로젝트 정보 추출
        return []
