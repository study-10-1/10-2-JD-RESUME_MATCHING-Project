"""
Step 2: HTML 파싱 - 텍스트 추출
"""
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import Dict, List, Optional
import requests
import time
import re


class JobParser:
    """HTML에서 채용공고 텍스트를 추출하는 파서"""
    
    def __init__(self, follow_links: bool = True, max_links: int = 3):
        self.follow_links = follow_links
        self.max_links = max_links
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def parse_html(self, html: str, base_url: Optional[str] = None) -> Dict[str, any]:
        """
        HTML에서 채용공고 텍스트를 추출합니다.
        
        Returns:
            {
                "panels": Dict[str, str],  # 각 패널의 텍스트
                "meta": Dict[str, str],  # 회사명, 위치, 경력레벨 등 메타 정보
                "success": bool,
                "error": Optional[str]
            }
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = {}
            meta = {}
            
            # 메타 정보 추출 (회사명, 위치, 경력레벨, 웹사이트)
            meta = self._extract_meta_info(soup, base_url)
            
            # 1단계: ID 패널 찾기 (tab-panel01, tab-panel02)
            tab_panels = ['tab-panel01', 'tab-panel02']
            found_id_panels = 0
            
            for panel_id in tab_panels:
                tab_panel = soup.find('div', id=panel_id)
                if tab_panel:
                    content = tab_panel.get_text(strip=True, separator='\n')
                    results[panel_id] = content
                    found_id_panels += 1
                    print(f"  ✓ {panel_id} 찾음 ({len(content)}자)")
            
            # 2단계: class="title" 요소 찾기
            title_elements = soup.find_all(class_='title')
            for i, title_elem in enumerate(title_elements, 1):
                title_name = f"title-element-{i:02d}"
                content = title_elem.get_text(strip=True, separator='\n')
                results[title_name] = content
                print(f"  ✓ {title_name} 찾음 ({len(content)}자)")
            
            # 3단계: ID 패널이 없으면 class="scroll" 대안 사용
            if found_id_panels == 0:
                scroll_divs = soup.find_all('div', class_='scroll')
                for i, scroll_div in enumerate(scroll_divs[:2], 1):
                    panel_name = f"scroll-panel-{i:02d}"
                    basic_content = scroll_div.get_text(strip=True, separator='\n')
                    
                    # 링크 따라가기 (옵션)
                    if self.follow_links and base_url:
                        link_contents = self._follow_links(base_url, scroll_div)
                        if link_contents:
                            basic_content += "\n\n" + "="*50 + "\n"
                            basic_content += "🔗 연결된 링크에서 수집한 추가 정보:\n"
                            basic_content += "="*50 + "\n\n"
                            for link_name, link_content in link_contents.items():
                                basic_content += f"📄 {link_name}:\n"
                                basic_content += "-" * 30 + "\n"
                                basic_content += link_content + "\n\n"
                    
                    results[panel_name] = basic_content
                    print(f"  ✓ {panel_name} 찾음 ({len(basic_content)}자)")
            
            if not results:
                return {
                    "panels": {},
                    "meta": meta,
                    "success": False,
                    "error": "ID 패널, class='title', class='scroll' 모든 요소를 찾을 수 없습니다."
                }
            
            return {
                "panels": results,
                "meta": meta,
                "success": True,
                "error": None
            }
            
        except Exception as e:
            return {
                "panels": {},
                "meta": {},
                "success": False,
                "error": f"파싱 오류: {str(e)}"
            }
    
    def _extract_meta_info(self, soup: BeautifulSoup, base_url: Optional[str] = None) -> Dict[str, Optional[str]]:
        """HTML에서 회사명, 위치, 경력레벨, 웹사이트 등 메타 정보 추출"""
        meta = {
            "company_name": None,
            "location": None,
            "experience_level": None,
            "company_website": None
        }
        
        # 전체 텍스트 가져오기 (메타 정보 추출용)
        full_text = soup.get_text(separator='\n', strip=True)
        
        # 회사명 추출 시도
        # work24.go.kr의 경우 다양한 패턴 시도
        company_patterns = [
            soup.find('span', class_=lambda x: x and 'company' in x.lower()),
            soup.find('div', class_=lambda x: x and 'company' in x.lower()),
            soup.find('td', class_=lambda x: x and 'company' in x.lower()),
            soup.find('th', string=lambda x: x and '회사' in str(x)),
        ]
        
        for elem in company_patterns:
            if elem:
                company_text = elem.get_text(strip=True)
                if company_text and len(company_text) < 100:  # 너무 긴 것은 제외
                    meta["company_name"] = company_text
                    break
        
        # 위치 추출 시도
        location_keywords = ['근무지', '위치', '지역', '소재지', '주소']
        location_patterns = [
            soup.find('th', string=lambda x: x and any(kw in str(x) for kw in location_keywords)),
            soup.find('td', class_=lambda x: x and 'location' in x.lower() if x else False),
            soup.find('div', class_=lambda x: x and 'location' in x.lower() if x else False),
        ]
        
        for elem in location_patterns:
            if elem:
                # 다음 형제 요소나 부모 요소에서 위치 정보 찾기
                location_elem = elem.find_next_sibling('td') or elem.find_next('td')
                if location_elem:
                    location_text = location_elem.get_text(strip=True)
                    # 채용 인원("3명", "5명" 등)이나 숫자만 있는 경우 제외
                    if location_text and len(location_text) < 200:
                        # "명"이 포함되어 있거나 숫자만 있는 경우 제외
                        if not re.search(r'\d+\s*명', location_text) and not re.match(r'^\d+$', location_text):
                            # 지역명 패턴 확인 (서울, 경기 등)
                            if re.search(r'(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)', location_text):
                                meta["location"] = location_text
                                break
        
        # 정규식으로 위치 정보 찾기 (서울, 경기, 부산 등)
        location_regex = r'(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)'
        location_match = re.search(location_regex, full_text[:5000])  # 처음 5000자만 검색
        if location_match and not meta["location"]:
            meta["location"] = location_match.group(1)
        
        # 경력 레벨 추출 시도
        experience_keywords = ['경력', '신입', '주니어', '시니어', '미들', 'junior', 'senior', 'mid']
        experience_patterns = [
            soup.find('th', string=lambda x: x and any(kw in str(x) for kw in experience_keywords)),
            soup.find('td', class_=lambda x: x and 'experience' in x.lower() if x else False),
        ]
        
        for elem in experience_patterns:
            if elem:
                experience_elem = elem.find_next_sibling('td') or elem.find_next('td')
                if experience_elem:
                    experience_text = experience_elem.get_text(strip=True)
                    if experience_text:
                        meta["experience_level"] = self._normalize_experience_level(experience_text)
                        break
        
        # 정규식으로 경력 레벨 찾기
        if not meta["experience_level"]:
            experience_regex = r'(신입|주니어|junior|경력\s*무관|경력\s*[0-9]+\s*년|시니어|senior|미들|mid)'
            experience_match = re.search(experience_regex, full_text[:5000], re.IGNORECASE)
            if experience_match:
                meta["experience_level"] = self._normalize_experience_level(experience_match.group(1))
        
        # 회사 웹사이트 추출
        website_patterns = [
            soup.find('a', href=lambda x: x and (x.startswith('http://') or x.startswith('https://')) and 'work24' not in x and 'mailto:' not in x),
            soup.find('a', href=lambda x: x and ('www.' in x or '.com' in x or '.co.kr' in x)),
        ]
        
        for link in website_patterns:
            if link:
                href = link.get('href', '')
                # work24 내부 링크나 메일 링크는 제외
                if href and not any(exclude in href for exclude in ['work24.go.kr', 'mailto:', 'javascript:', '#']):
                    # 상대 경로인 경우 절대 경로로 변환
                    if href.startswith('/') and base_url:
                        from urllib.parse import urljoin
                        meta["company_website"] = urljoin(base_url, href)
                    elif href.startswith(('http://', 'https://')):
                        meta["company_website"] = href
                    elif base_url:
                        from urllib.parse import urljoin
                        meta["company_website"] = urljoin(base_url, href)
                    else:
                        meta["company_website"] = href
                    break
        
        # 텍스트에서 웹사이트 URL 패턴 찾기
        if not meta["company_website"]:
            website_regex = r'(https?://(?:www\.)?[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+)'
            website_match = re.search(website_regex, full_text[:5000])
            if website_match:
                website_url = website_match.group(1)
                if 'work24.go.kr' not in website_url:
                    meta["company_website"] = website_url
        
        return meta
    
    def _normalize_experience_level(self, text: str) -> Optional[str]:
        """경력 레벨 텍스트를 표준화된 형식으로 변환 (junior, mid, senior)"""
        if not text:
            return None
        
        text_lower = text.lower().strip()
        
        # 신입/주니어
        if any(kw in text_lower for kw in ['신입', 'junior', '주니어', '경력 무관', '경력무관']):
            return "junior"
        
        # 시니어
        if any(kw in text_lower for kw in ['시니어', 'senior', '경력 10년', '10년 이상']):
            return "senior"
        
        # 미들
        if any(kw in text_lower for kw in ['미들', 'mid', '경력 3년', '경력 5년', '3년 이상', '5년 이상']):
            return "mid"
        
        # 경력 연수로 판단
        years_match = re.search(r'경력\s*(\d+)\s*년', text)
        if years_match:
            years = int(years_match.group(1))
            if years < 3:
                return "junior"
            elif years < 7:
                return "mid"
            else:
                return "senior"
        
        return None
    
    def _follow_links(self, base_url: str, soup_element) -> Dict[str, str]:
        """요소 안의 링크들을 따라가서 내용을 가져옵니다."""
        link_contents = {}
        links = soup_element.find_all('a', href=True)
        
        if not links:
            return {}
        
        for idx, link in enumerate(links[:self.max_links]):
            href = link.get('href')
            link_text = link.get_text(strip=True)
            
            # 자바스크립트 링크나 메일 링크는 건너뛰기
            if href.startswith(('javascript:', 'mailto:', '#')):
                continue
            
            full_url = urljoin(base_url, href)
            
            try:
                time.sleep(1)  # 서버 부하 방지
                response = requests.get(full_url, headers=self.headers, timeout=15)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                link_soup = BeautifulSoup(response.text, 'html.parser')
                
                # 본문 내용 찾기
                content_selectors = [
                    'div.content', 'div.main-content', 'div.article-content',
                    'div.post-content', 'div.job-content', 'div.detail',
                    'main', 'article', 'div.scroll'
                ]
                
                link_content = ""
                for selector in content_selectors:
                    content_elem = link_soup.select_one(selector)
                    if content_elem:
                        link_content = content_elem.get_text(strip=True, separator='\n')
                        break
                
                if not link_content:
                    body = link_soup.find('body')
                    if body:
                        link_content = body.get_text(strip=True, separator='\n')
                
                if link_content:
                    link_contents[f"링크_{idx + 1}_{link_text[:20]}"] = link_content
                    print(f"    ✓ 링크 {idx + 1} 수집 완료 ({len(link_content)}자)")
                    
            except Exception as e:
                print(f"    ✗ 링크 {idx + 1} 처리 실패: {str(e)}")
                continue
        
        return link_contents

