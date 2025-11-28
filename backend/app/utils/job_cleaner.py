"""
Step 3: 텍스트 정제 - 클리닝 및 정규화
"""
import re
from typing import Dict, List


class JobCleaner:
    """추출된 텍스트를 정제하는 클리너"""
    
    def __init__(self):
        # 제거할 패턴들
        self.remove_patterns = [
            r'\s+',  # 연속된 공백
            r'\n{3,}',  # 3개 이상의 줄바꿈
        ]
        
        # 정규화할 패턴들
        self.normalize_patterns = [
            (r'&nbsp;', ' '),
            (r'&amp;', '&'),
            (r'&lt;', '<'),
            (r'&gt;', '>'),
            (r'&quot;', '"'),
        ]
    
    def clean_text(self, text: str) -> str:
        """단일 텍스트를 정제합니다."""
        if not text:
            return ""
        
        # HTML 엔티티 정규화
        for pattern, replacement in self.normalize_patterns:
            text = re.sub(pattern, replacement, text)
        
        # 연속된 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        
        # 3개 이상의 줄바꿈을 2개로
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    def clean_panels(self, panels: Dict[str, str]) -> Dict[str, str]:
        """여러 패널의 텍스트를 정제합니다."""
        cleaned = {}
        for key, value in panels.items():
            cleaned[key] = self.clean_text(value)
        return cleaned
    
    def validate_panels(self, panels: Dict[str, str]) -> Dict[str, any]:
        """
        패널 데이터를 검증합니다.
        
        Returns:
            {
                "valid": bool,
                "panels": Dict[str, str],
                "warnings": List[str],
                "errors": List[str]
            }
        """
        warnings = []
        errors = []
        cleaned_panels = {}
        
        for key, value in panels.items():
            cleaned = self.clean_text(value)
            
            # 빈 패널 체크
            if not cleaned:
                warnings.append(f"패널 '{key}'가 비어있습니다.")
                continue
            
            # 너무 짧은 패널 체크
            if len(cleaned) < 10:
                warnings.append(f"패널 '{key}'의 내용이 너무 짧습니다 ({len(cleaned)}자).")
            
            # 너무 긴 패널 체크
            if len(cleaned) > 50000:
                warnings.append(f"패널 '{key}'의 내용이 너무 깁니다 ({len(cleaned)}자).")
            
            cleaned_panels[key] = cleaned
        
        # 최소한 하나의 패널은 있어야 함
        if not cleaned_panels:
            errors.append("유효한 패널이 하나도 없습니다.")
        
        return {
            "valid": len(errors) == 0,
            "panels": cleaned_panels,
            "warnings": warnings,
            "errors": errors
        }

