"""
XLSX Parser - 엑셀 이력서 텍스트 추출
"""
from typing import List


class XLSXParser:
    """간단한 XLSX 파서: 모든 시트의 셀 텍스트를 이어붙여 반환"""

    def extract_text(self, file_path: str) -> str:
        try:
            import openpyxl
        except Exception:
            # openpyxl 미설치 시 빈 문자열 반환 (업스트림에서 fallback 처리)
            return ""

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        except Exception:
            return ""

        parts: List[str] = []
        for ws in wb.worksheets:
            parts.append(f"[Sheet] {ws.title}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    parts.append(" \t ".join(cells))
        wb.close()
        return "\n".join(parts)


