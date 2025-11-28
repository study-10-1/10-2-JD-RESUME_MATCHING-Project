"""
Step 4: 구조화 - JSON 형식으로 변환
"""
from typing import Dict, List, Optional
from datetime import datetime, date
import json
from app.core.logging import logger


class JobStructurizer:
    """정제된 텍스트를 구조화된 JSON 형식으로 변환"""
    
    def __init__(self):
        self.llm_parser = None
        try:
            from app.services.parsing.llm_parser import LLMParser
            self.llm_parser = LLMParser()
            logger.info("LLM Parser initialized for requirements extraction")
        except Exception as e:
            logger.warning(f"LLM Parser initialization failed: {e}. Will use fallback method.")
    
    def structure(self, 
                  panels: Dict[str, str],
                  url: str,
                  registered_date: Optional[str] = None,
                  closing_date: Optional[str] = None,
                  source: str = "custom",
                  meta_info: Optional[Dict[str, Optional[str]]] = None) -> Dict:
        """
        패널 데이터를 구조화된 JSON 형식으로 변환합니다.
        
        Args:
            panels: 파싱된 패널 데이터
            url: 공고 URL
            registered_date: 등록일
            closing_date: 마감일
            source: 공고 소스
            meta_info: 파서에서 추출한 메타 정보 (company_name, location, experience_level)
        
        Returns:
            {
                "title": str,
                "description": str,
                "raw_text": str,
                "requirements": {
                    "required": List[str],
                    "preferred": List[str]
                },
                "responsibilities": List[str],
                "qualifications": List[str],
                "benefits": List[str],
                "meta": {
                    "url": str,
                    "source": str,
                    "registered_date": Optional[str],
                    "closing_date": Optional[str],
                    "scraped_at": str,
                    "company_name": Optional[str],
                    "location": Optional[str],
                    "experience_level": Optional[str]
                }
            }
        """
        # 전체 텍스트 합치기
        raw_text = self._combine_panels(panels)
        
        # 제목 추출 (첫 번째 패널의 첫 줄 또는 title 요소)
        title = self._extract_title(panels, raw_text)
        
        # 설명 추출 (전체 텍스트 또는 description 패널)
        description = self._extract_description(panels, raw_text)
        
        # 구조화된 데이터 추출
        requirements = self._extract_requirements(panels)
        responsibilities = self._extract_responsibilities(panels)
        qualifications = self._extract_qualifications(panels)
        benefits = self._extract_benefits(panels)
        
        # 메타 정보 병합
        meta = {
            "url": url,
            "source": source,
            "registered_date": registered_date,
            "closing_date": closing_date,
            "scraped_at": datetime.now().isoformat()
        }
        
        if meta_info:
            meta.update({
                "company_name": meta_info.get("company_name"),
                "location": meta_info.get("location"),
                "experience_level": meta_info.get("experience_level")
            })
        
        return {
            "title": title,
            "description": description,
            "raw_text": raw_text,
            "requirements": requirements,
            "responsibilities": responsibilities,
            "qualifications": qualifications,
            "benefits": benefits,
            "meta": meta
        }
    
    def _combine_panels(self, panels: Dict[str, str]) -> str:
        """모든 패널을 합쳐서 전체 텍스트 생성"""
        parts = []
        for key, value in panels.items():
            parts.append(f"=== {key} ===\n{value}\n")
        return "\n".join(parts)
    
    def _extract_title(self, panels: Dict[str, str], raw_text: str) -> str:
        """제목 추출"""
        # title-element에서 추출 시도
        for key in sorted(panels.keys()):
            if 'title' in key.lower():
                lines = panels[key].split('\n')
                if lines:
                    return lines[0].strip()[:500]  # 최대 500자
        
        # 첫 번째 패널의 첫 줄
        if panels:
            first_panel = list(panels.values())[0]
            lines = first_panel.split('\n')
            if lines:
                return lines[0].strip()[:500]
        
        return "제목 없음"
    
    def _extract_description(self, panels: Dict[str, str], raw_text: str) -> str:
        """설명 추출 (전체 텍스트 또는 description 패널)"""
        # description 관련 패널 찾기
        for key, value in panels.items():
            if 'description' in key.lower() or 'detail' in key.lower():
                return value[:10000]  # 최대 10000자
        
        # 전체 텍스트 사용
        return raw_text[:10000]
    
    def _extract_requirements(self, panels: Dict[str, str]) -> Dict[str, List[str]]:
        """
        자격요건/우대조건 추출 (LLM 기반)
        
        LLM을 사용하여 채용공고 텍스트에서 자격요건과 우대조건을 정확하게 구분하여 추출합니다.
        LLM이 실패하면 키워드 기반 fallback을 사용합니다.
        """
        # 모든 패널 텍스트 합치기
        combined_text = ""
        for key, value in panels.items():
            # title은 제외하고 내용만 사용
            if 'title' not in key.lower():
                combined_text += f"\n{value}\n"
        
        combined_text = combined_text.strip()
        
        if not combined_text:
            logger.warning("No text found in panels for requirements extraction")
            return {"required": [], "preferred": []}
        
        # LLM 기반 추출 시도
        if self.llm_parser:
            try:
                logger.info("Using LLM for requirements extraction...")
                result = self.llm_parser.extract_job_requirements(combined_text)
                
                required = result.get("required", [])
                preferred = result.get("preferred", [])
                
                if required or preferred:
                    logger.info(f"LLM extraction successful: required={len(required)}, preferred={len(preferred)}")
                    return {
                        "required": required[:100],  # 최대 100개
                        "preferred": preferred[:100]
                    }
                else:
                    logger.warning("LLM extraction returned empty results, using fallback")
            except Exception as e:
                logger.error(f"LLM requirements extraction failed: {e}, using fallback")
        
        # Fallback: 키워드 기반 추출
        logger.info("Using fallback keyword-based extraction")
        return self._fallback_extract_requirements(panels)
    
    def _fallback_extract_requirements(self, panels: Dict[str, str]) -> Dict[str, List[str]]:
        """키워드 기반 fallback 추출 (LLM 실패 시)"""
        required = []
        preferred = []
        
        # tab-panel01 또는 scroll-panel-01에서 추출 시도
        for key, value in panels.items():
            if 'panel01' in key or 'scroll-panel-01' in key or 'panel02' in key or 'scroll-panel-02' in key:
                lines = [line.strip() for line in value.split('\n') if line.strip()]
                for line in lines:
                    line_lower = line.lower()
                    # 자격요건 키워드
                    if any(keyword in line_lower for keyword in ['필수', '요구', '필요', 'required', '반드시']):
                        if len(line) > 10:  # 너무 짧은 것은 제외
                            required.append(line)
                    # 우대조건 키워드
                    elif any(keyword in line_lower for keyword in ['우대', '선호', 'preferred', 'bonus', '가산']):
                        if len(line) > 10:
                            preferred.append(line)
        
        return {
            "required": required[:50],  # 최대 50개
            "preferred": preferred[:50]
        }
    
    def _extract_responsibilities(self, panels: Dict[str, str]) -> List[str]:
        """업무 내용 추출"""
        responsibilities = []
        
        for key, value in panels.items():
            if 'responsibility' in key.lower() or '업무' in value[:200]:
                lines = [line.strip() for line in value.split('\n') if line.strip()]
                responsibilities.extend(lines[:30])  # 최대 30개
        
        return responsibilities
    
    def _extract_qualifications(self, panels: Dict[str, str]) -> List[str]:
        """자격 요건 추출"""
        qualifications = []
        
        for key, value in panels.items():
            if 'qualification' in key.lower() or '자격' in value[:200]:
                lines = [line.strip() for line in value.split('\n') if line.strip()]
                qualifications.extend(lines[:30])
        
        return qualifications
    
    def _extract_benefits(self, panels: Dict[str, str]) -> List[str]:
        """복리후생 추출"""
        benefits = []
        
        for key, value in panels.items():
            if 'benefit' in key.lower() or '복리' in value[:200] or '후생' in value[:200]:
                lines = [line.strip() for line in value.split('\n') if line.strip()]
                benefits.extend(lines[:30])
        
        return benefits
    
    def to_json(self, structured_data: Dict, indent: int = 2) -> str:
        """구조화된 데이터를 JSON 문자열로 변환"""
        return json.dumps(structured_data, ensure_ascii=False, indent=indent)

