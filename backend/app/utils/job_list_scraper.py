"""
채용공고 목록 페이지에서 공고 링크 수집
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, urlunparse
import time
from typing import List, Dict
import re


def scrape_job_list(base_url: str, max_pages: int = 1, start_page: int = 1) -> List[Dict[str, str]]:
    """
    work24.go.kr 채용공고 목록 페이지에서 채용공고 링크, 등록일, 마감일을 수집합니다.
    
    Args:
        base_url: 채용공고 목록 페이지 URL
        max_pages: 수집할 최대 페이지 수
        start_page: 시작 페이지 번호 (기본값: 1)
        
    Returns:
        채용공고 목록 (link, registered_date, closing_date)
    """
    results = []
    
    # URL 검증
    if not base_url or not base_url.startswith(('http://', 'https://')):
        print(f"❌ 잘못된 URL 형식: {base_url}")
        return results
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        parsed_url = urlparse(base_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            print(f"❌ URL 파싱 실패: {base_url}")
            return results
    except Exception as e:
        print(f"❌ URL 파싱 오류: {str(e)}")
        return results
    
    query_params = parse_qs(parsed_url.query)
    
    # max_pages가 None이면 모든 페이지 수집 (빈 페이지를 만나면 종료)
    # max_pages가 지정되면 해당 페이지 수만 수집
    end_page = start_page + max_pages - 1 if max_pages else None
    
    page = start_page
    while True:
        # max_pages가 지정된 경우에만 end_page 체크
        if max_pages and end_page and page > end_page:
            break
        try:
            print(f"  📄 페이지 {page} 처리 중...")
            
            # 쿼리 파라미터 업데이트
            page_query_params = query_params.copy()
            page_query_params['currentPageNo'] = [str(page)]
            page_query_params['pageIndex'] = [str(page)]
            
            try:
                new_query = urlencode(page_query_params, doseq=True)
                page_url = urlunparse((
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    new_query,
                    parsed_url.fragment
                ))
            except Exception as e:
                print(f"  ❌ URL 생성 오류: {str(e)}")
                # max_pages가 1이 아니면 다음 페이지로, 1이면 종료
                if max_pages == 1:
                    break
                page += 1
                continue
            
            print(f"  🔗 요청 URL: {page_url}")
            
            try:
                response = requests.get(page_url, headers=headers, timeout=30, allow_redirects=True)
                response.raise_for_status()
                response.encoding = 'utf-8'
            except requests.exceptions.RequestException as e:
                print(f"  ❌ 페이지 {page} 요청 오류: {str(e)}")
                # max_pages가 1이 아니면 다음 페이지로, 1이면 종료
                if max_pages == 1:
                    break
                page += 1
                continue
            
            print(f"  ✅ 응답 받음: {len(response.text)}자")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # #list1, #list2 등의 ID 패턴으로 공고 목록 찾기
            job_items = []
            list_elements = soup.find_all(id=re.compile(r'^list\d+$'))
            if list_elements:
                job_items = list_elements
                print(f"  ✓ 'list숫자' 패턴으로 {len(job_items)}개 찾음")
            elif not job_items:
                list_elements = soup.find_all(id=re.compile(r'^list'))
                if list_elements:
                    job_items = list_elements
                    print(f"  ✓ 'list' 패턴으로 {len(job_items)}개 찾음")
            
            if not job_items:
                print(f"  ⚠️ 페이지 {page}: 공고 목록을 찾을 수 없습니다.")
                # 빈 페이지이면 종료 (다음 페이지로 진행하지 않음)
                # max_pages가 1이면 즉시 종료, 아니면 빈 페이지로 간주하고 종료
                if max_pages == 1:
                    break
                # 디버깅: HTML 구조 확인 (첫 페이지만)
                if page == start_page:
                    print(f"  🔍 디버깅 정보:")
                    print(f"     - HTML 길이: {len(response.text)}자")
                    # list 관련 요소 찾기
                    all_list_elements = soup.find_all(id=re.compile(r'list', re.I))
                    print(f"     - 'list'가 포함된 ID 요소: {len(all_list_elements)}개")
                    # table이나 tr 요소 확인
                    tables = soup.find_all('table')
                    print(f"     - table 요소: {len(tables)}개")
                    trs = soup.find_all('tr')
                    print(f"     - tr 요소: {len(trs)}개")
                # 빈 페이지를 만나면 종료 (모든 페이지 크롤링 시)
                if not max_pages:
                    print(f"  ℹ️ 빈 페이지를 만나 크롤링을 종료합니다.")
                    break
                # max_pages가 지정된 경우 다음 페이지로
                page += 1
                continue
            
            print(f"  ✓ 페이지 {page}: {len(job_items)}개 공고 항목 발견")
            page_results = []
            for item in job_items:
                try:
                    job_data = {}
                    
                    # 채용공고 링크 찾기
                    link = None
                    href = None
                    
                    td_element = item.find('td', class_=re.compile(r'al_left|pd24', re.I))
                    if td_element:
                        divs = td_element.find_all('div', recursive=False)
                        if len(divs) >= 1:
                            inner_divs = divs[0].find_all('div', recursive=False)
                            if len(inner_divs) >= 2:
                                link = inner_divs[1].find('a', href=True)
                            elif len(inner_divs) == 1:
                                link = inner_divs[0].find('a', href=True)
                            else:
                                link = divs[0].find('a', href=True)
                    
                    if not link:
                        td_element = item.find('td', class_=re.compile(r'al_left|pd24', re.I))
                        if td_element:
                            link = td_element.find('a', href=True)
                    
                    if not link:
                        tds = item.find_all('td')
                        for td in tds:
                            link = td.find('a', href=True)
                            if link:
                                break
                    
                    if not link:
                        all_links = item.find_all('a', href=True)
                        for l in all_links:
                            href_val = l.get('href', '')
                            if 'retriveDtlEmpSrchList' in href_val or 'seqNo' in href_val:
                                link = l
                                break
                    
                    if link:
                        href = link.get('href')
                    else:
                        onclick_elem = item.find(attrs={'onclick': re.compile(r'seqNo', re.I)})
                        if onclick_elem:
                            onclick = onclick_elem.get('onclick', '')
                            seq_match = re.search(r'seqNo[=:\'"](\d+)', onclick)
                            if seq_match:
                                seq_no = seq_match.group(1)
                                href = f"/wk/a/b/1200/retriveDtlEmpSrchList.do?seqNo={seq_no}"
                    
                    # URL 처리
                    if href:
                        if href.startswith('/'):
                            job_data['link'] = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
                        elif href.startswith('http'):
                            job_data['link'] = href
                        elif href.startswith('javascript:'):
                            onclick = href
                            seq_match = re.search(r'seqNo[=:\'"](\d+)', onclick)
                            if seq_match:
                                seq_no = seq_match.group(1)
                                job_data['link'] = f"{parsed_url.scheme}://{parsed_url.netloc}/wk/a/b/1200/retriveDtlEmpSrchList.do?seqNo={seq_no}"
                            else:
                                job_data['link'] = None
                        else:
                            job_data['link'] = urljoin(f"{parsed_url.scheme}://{parsed_url.netloc}", href)
                    else:
                        job_data['link'] = None
                    
                    # 등록일 찾기
                    reg_date = None
                    tds = item.find_all('td')
                    item_text = item.get_text()
                    
                    reg_date_patterns = [
                        r'등록일[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'등록[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'작성일[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'게시일[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'접수시작[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                    ]
                    
                    for pattern in reg_date_patterns:
                        match = re.search(pattern, item_text)
                        if match:
                            reg_date = match.group(1)
                            break
                    
                    if not reg_date and tds:
                        for td in tds:
                            td_text = td.get_text(strip=True)
                            date_match = re.search(r'(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})', td_text)
                            if date_match and '마감' not in td_text.lower():
                                reg_date = date_match.group(1)
                                break
                    
                    if not reg_date:
                        dates = re.findall(r'\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}', item_text)
                        if dates:
                            reg_date = dates[0]
                    
                    if reg_date:
                        reg_date = normalize_date(reg_date)
                    
                    job_data['registered_date'] = reg_date
                    
                    # 마감일 찾기
                    close_date = None
                    close_date_patterns = [
                        r'마감일[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'마감[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'접수마감[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'채용마감[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'지원마감[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                        r'접수종료[:\s]*(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
                    ]
                    
                    for pattern in close_date_patterns:
                        match = re.search(pattern, item_text)
                        if match:
                            close_date = match.group(1)
                            break
                    
                    if not close_date and tds:
                        for td in tds:
                            td_text = td.get_text(strip=True)
                            if '마감' in td_text:
                                date_match = re.search(r'(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})', td_text)
                                if date_match:
                                    close_date = date_match.group(1)
                                    break
                    
                    if not close_date:
                        dates = re.findall(r'\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}', item_text)
                        if len(dates) >= 2:
                            close_date = dates[1]
                    
                    if close_date:
                        close_date = normalize_date(close_date)
                    
                    job_data['closing_date'] = close_date
                    
                    # 회사명 추출 (목록 페이지에서)
                    company_name = None
                    # 첫 번째 TD나 첫 번째 줄에서 회사명 찾기
                    tds = item.find_all('td')
                    if tds:
                        first_td_text = tds[0].get_text(strip=True, separator='\n')
                        lines = first_td_text.split('\n')
                        # 첫 번째 줄이 회사명일 가능성이 높음 (너무 길지 않은 경우)
                        if lines:
                            first_line = lines[0].strip()
                            # 회사명은 보통 2-50자 사이
                            if 2 <= len(first_line) <= 50 and not any(kw in first_line for kw in ['요약보기', '상세보기', 'http', 'www']):
                                company_name = first_line
                    
                    job_data['company_name'] = company_name
                    
                    # 링크가 있는 경우에만 결과에 추가
                    if job_data.get('link'):
                        page_results.append(job_data)
                    
                except Exception:
                    continue
            
            results.extend(page_results)
            print(f"  ✅ 페이지 {page}: {len(page_results)}개 공고 수집 완료")
            
            # 빈 페이지이면 종료 (모든 페이지 크롤링 시)
            if not page_results:
                if max_pages == 1:
                    break
                # max_pages가 None이면 빈 페이지를 만나면 종료
                if not max_pages:
                    print(f"  ℹ️ 빈 페이지를 만나 크롤링을 종료합니다.")
                    break
            
            page += 1
            if max_pages == 1:  # max_pages가 1이면 한 페이지만 처리하고 종료
                break
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 페이지 {page} 요청 오류: {str(e)}")
            if max_pages == 1:
                break
            if not max_pages:  # 모든 페이지 크롤링 시 오류면 종료
                print(f"  ℹ️ 오류로 인해 크롤링을 종료합니다.")
                break
            page += 1
            continue
        except Exception as e:
            print(f"  ❌ 페이지 {page} 처리 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            if max_pages == 1:
                break
            if not max_pages:  # 모든 페이지 크롤링 시 오류면 종료
                print(f"  ℹ️ 오류로 인해 크롤링을 종료합니다.")
                break
            page += 1
            continue
    
    return results


def normalize_date(date_str: str) -> str:
    """
    날짜 문자열을 YYYY-MM-DD 형식으로 정규화합니다.
    """
    if not date_str:
        return None
    
    date_str = date_str.replace('.', '-').replace('/', '-')
    parts = date_str.split('-')
    if len(parts) == 3:
        year = parts[0].strip()
        month = parts[1].strip().zfill(2)
        day = parts[2].strip().zfill(2)
        return f"{year}-{month}-{day}"
    
    return date_str

