"""
HWP Parser - HWP 파일에서 텍스트 추출
"""
import logging
from typing import Dict, Any


class HWPParser:
    """HWP 파일 파서"""
    
    def extract_text(self, file_path: str) -> str:
        """
        HWP 파일에서 텍스트 추출 (모든 페이지 처리)
        
        Args:
            file_path: HWP 파일 경로
            
        Returns:
            추출된 텍스트
        """
        logger = logging.getLogger(__name__)
        
        try:
            # olefile을 사용한 HWP 파싱 시도
            import olefile
            
            if olefile.isOleFile(file_path):
                ole = olefile.OleFileIO(file_path)
                is_hwp_file = True
            else:
                # HWP 파일이 아닌 경우 일반 텍스트로 처리
                is_hwp_file = False
                ole = None
            
            # HWP 파일 구조에서 텍스트 추출
            text = ""
            page_count = 0
            
            if is_hwp_file:
                try:
                    # HWP 파일의 BodyText 스트림에서 텍스트 추출
                    if ole._olestream_exists('BodyText'):
                        body_text = ole.openfile('BodyText').read()
                        
                        # HWP 바이너리 데이터에서 텍스트 추출
                        # 간단한 텍스트 추출 (실제로는 더 복잡한 파싱 필요)
                        import re
                        
                        # 유니코드 텍스트 추출 시도
                        try:
                            # UTF-16 LE로 디코딩 시도
                            decoded_text = body_text.decode('utf-16le', errors='ignore')
                            # 한글과 영문만 추출
                            korean_text = re.sub(r'[^\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F\uA-Za-z0-9\s]', '', decoded_text)
                            text = korean_text.strip()
                        except:
                            # UTF-8로 디코딩 시도
                            try:
                                decoded_text = body_text.decode('utf-8', errors='ignore')
                                korean_text = re.sub(r'[^\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F\uA-Za-z0-9\s]', '', decoded_text)
                                text = korean_text.strip()
                            except:
                                # 기본 텍스트 추출
                                text = str(body_text, errors='ignore')
                    
                    # 페이지 구분자 추가 (HWP는 페이지 정보를 직접 추출하기 어려우므로 텍스트 길이로 추정)
                    if text:
                        # 텍스트 길이에 따라 페이지 수 추정 (800자당 1페이지로 더 정확하게)
                        estimated_pages = max(1, len(text) // 800)
                        
                        # 페이지 구분자 추가
                        page_text = ""
                        for page_num in range(1, estimated_pages + 1):
                            start_idx = (page_num - 1) * 800
                            end_idx = min(page_num * 800, len(text))
                            page_content = text[start_idx:end_idx]
                            
                            if page_content.strip():
                                page_text += f"\n--- 페이지 {page_num} ---\n"
                                page_text += page_content + "\n"
                                logger.info(f"페이지 {page_num} 파싱 완료: {len(page_content)} 문자")
                        
                        text = page_text
                        page_count = estimated_pages
                        
                        logger.info(f"HWP 총 페이지 수 (추정): {page_count}")
                        logger.info(f"HWP 전체 파싱 완료: {len(text)} 문자")
                
                except Exception as e:
                    logger.warning(f"HWP BodyText 추출 실패, 대체 방법 시도: {e}")
                    
                    # 대체 방법: 파일을 텍스트로 읽기 시도
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                        
                        if text.strip():
                            text = f"\n--- 페이지 1 ---\n{text}\n"
                            page_count = 1
                            logger.info(f"HWP 대체 방법으로 파싱 완료: {len(text)} 문자")
                        else:
                            raise Exception("텍스트 추출 실패")
                            
                    except Exception as e2:
                        logger.error(f"HWP 모든 파싱 방법 실패: {e2}")
                        raise Exception(f"HWP 파싱 실패: {e2}")
                
                finally:
                    if ole:
                        ole.close()
            
            else:
                # 일반 텍스트 파일로 처리
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                    
                    if text.strip():
                        # 텍스트 길이에 따라 페이지 수 추정 (1000자당 1페이지)
                        estimated_pages = max(1, len(text) // 1000)
                        
                        # 페이지 구분자 추가
                        page_text = ""
                        for page_num in range(1, estimated_pages + 1):
                            start_idx = (page_num - 1) * 1000
                            end_idx = min(page_num * 1000, len(text))
                            page_content = text[start_idx:end_idx]
                            
                            if page_content.strip():
                                page_text += f"\n--- 페이지 {page_num} ---\n"
                                page_text += page_content + "\n"
                                logger.info(f"페이지 {page_num} 파싱 완료: {len(page_content)} 문자")
                        
                        text = page_text
                        page_count = estimated_pages
                        
                        logger.info(f"텍스트 파일 총 페이지 수 (추정): {page_count}")
                        logger.info(f"텍스트 파일 전체 파싱 완료: {len(text)} 문자")
                    else:
                        raise Exception("텍스트 추출 실패")
                        
                except Exception as e2:
                    logger.error(f"텍스트 파일 파싱 실패: {e2}")
                    raise Exception(f"텍스트 파일 파싱 실패: {e2}")
            
            return text
            
        except Exception as e:
            logger.error(f"HWP 텍스트 추출 실패: {e}")
            raise Exception(f"HWP 텍스트 추출 실패: {e}")
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        import re
        
        # 불필요한 공백 제거
        text = text.strip()
        
        # 연속된 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        
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