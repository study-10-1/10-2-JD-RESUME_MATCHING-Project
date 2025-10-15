"""
DOCX Parser - DOCX/DOC 파일에서 텍스트 추출
"""
from docx import Document
from typing import Dict, Any
import openpyxl


class DOCXParser:
    """DOCX/DOC 파일 파서"""
    
    def extract_text(self, file_path: str) -> str:
        """
        DOCX 파일에서 텍스트 추출
        
        Args:
            file_path: DOCX 파일 경로
            
        Returns:
            추출된 텍스트
        """
        try:
            doc = Document(file_path)
            text = ""
            
            # 단락에서 텍스트 추출
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            # 표에서 텍스트 추출
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text += cell.text + " "
                    text += "\n"
            
            # 텍스트 정리
            text = self._clean_text(text)
            
            return text
            
        except Exception as e:
            raise Exception(f"DOCX 텍스트 추출 실패: {e}")
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        # 불필요한 공백 제거
        text = text.strip()
        
        # 연속된 공백을 하나로
        import re
        text = re.sub(r' +', ' ', text)
        
        # 연속된 줄바꿈을 두 개로
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text
    
    def parse_resume(self, text: str) -> Dict[str, Any]:
        """
        이력서 텍스트에서 구조화된 정보 추출
        (PDF Parser와 동일한 로직 사용)
        """
        from app.services.parsing.pdf_parser import PDFParser
        pdf_parser = PDFParser()
        return pdf_parser.parse_resume(text)


class XLSXParser:
    """XLSX 파일 파서"""
    
    def extract_text(self, file_path: str) -> str:
        """
        XLSX 파일에서 텍스트 추출
        
        Args:
            file_path: XLSX 파일 경로
            
        Returns:
            추출된 텍스트
        """
        try:
            workbook = openpyxl.load_workbook(file_path)
            text = ""
            
            # 모든 시트에서 텍스트 추출
            for sheet in workbook.worksheets:
                text += f"\n## {sheet.title} ##\n"
                
                for row in sheet.iter_rows():
                    row_text = []
                    for cell in row:
                        if cell.value:
                            row_text.append(str(cell.value))
                    
                    if row_text:
                        text += " | ".join(row_text) + "\n"
            
            # 텍스트 정리
            text = self._clean_text(text)
            
            return text
            
        except Exception as e:
            raise Exception(f"XLSX 텍스트 추출 실패: {e}")
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        # 불필요한 공백 제거
        text = text.strip()
        
        # 연속된 공백을 하나로
        import re
        text = re.sub(r' +', ' ', text)
        
        return text
    
    def parse_resume(self, text: str) -> Dict[str, Any]:
        """
        이력서 텍스트에서 구조화된 정보 추출
        """
        from app.services.parsing.pdf_parser import PDFParser
        pdf_parser = PDFParser()
        return pdf_parser.parse_resume(text)
