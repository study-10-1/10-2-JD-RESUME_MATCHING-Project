"""
Step 1: 웹 스크래핑 - HTML 가져오기
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
import time


class JobScraper:
    """웹페이지에서 HTML을 가져오는 스크래퍼"""
    
    def __init__(self, timeout: int = 30, delay: float = 1.0):
        self.timeout = timeout
        self.delay = delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def fetch_html(self, url: str) -> Dict[str, any]:
        """
        URL에서 HTML을 가져옵니다.
        
        Returns:
            {
                "url": str,
                "html": str,
                "status_code": int,
                "success": bool,
                "error": Optional[str]
            }
        """
        try:
            print(f"📥 HTML 가져오는 중: {url}")
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            time.sleep(self.delay)  # 서버 부하 방지
            
            return {
                "url": url,
                "html": response.text,
                "status_code": response.status_code,
                "success": True,
                "error": None
            }
        except requests.exceptions.RequestException as e:
            return {
                "url": url,
                "html": None,
                "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                "success": False,
                "error": f"웹페이지 요청 오류: {str(e)}"
            }
        except Exception as e:
            return {
                "url": url,
                "html": None,
                "status_code": None,
                "success": False,
                "error": f"예상치 못한 오류: {str(e)}"
            }
    
    def fetch_multiple(self, urls: list[str]) -> list[Dict]:
        """여러 URL에서 HTML을 가져옵니다."""
        results = []
        for idx, url in enumerate(urls, 1):
            print(f"[{idx}/{len(urls)}] 처리 중...")
            result = self.fetch_html(url)
            results.append(result)
        return results

