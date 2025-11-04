"""
XLSX Parser - XLSX/XLS 파일에서 텍스트 추출
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class XLSXParser:
    """XLSX 파일 파서 - 실제 시트 구조 읽기"""
    
    def extract_text(self, file_path: str) -> str:
        """
        XLSX 파일에서 텍스트 추출 (실제 시트 구조 읽기)
        
        Args:
            file_path: XLSX 파일 경로
            
        Returns:
            추출된 텍스트
        """
        logger = logging.getLogger(__name__)
        
        try:
            import openpyxl
        except Exception:
            logger.error("openpyxl 미설치")
            return ""

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        except Exception as e:
            logger.error(f"XLSX 파일 로드 실패: {e}")
            return ""

        parts: List[str] = []
        sheet_count = 0
        
        logger.info(f"XLSX 총 시트 수: {len(wb.worksheets)}")
        
        for ws in wb.worksheets:
            sheet_count += 1
            parts.append(f"\n--- 시트 {sheet_count}: {ws.title} ---\n")
            
            row_count = 0
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    parts.append(" | ".join(cells))
                    row_count += 1
            
            logger.info(f"시트 '{ws.title}' 파싱 완료: {row_count}행")
        
        wb.close()
        
        result = "\n".join(parts)
        logger.info(f"XLSX 전체 파싱 완료: {len(result)} 문자, {sheet_count}개 시트")
        return result
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        import re
        
        # 불필요한 공백 제거
        text = text.strip()
        
        # 연속된 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def parse_resume(self, text: str) -> Dict[str, Any]:
        """
        이력서 텍스트에서 구조화된 정보 추출
        """
        from app.services.parsing.pdf_parser import PDFParser
        pdf_parser = PDFParser()
        return pdf_parser.parse_resume(text)