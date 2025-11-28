"""
채용공고 크롤러 서비스
"""
import time
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import logger
from app.utils.job_list_scraper import scrape_job_list
from app.utils.job_scraper import JobScraper
from app.utils.job_parser import JobParser
from app.utils.job_cleaner import JobCleaner
from app.utils.job_structurizer import JobStructurizer
from app.utils.job_saver import JobSaver
from app.core.job_cleanup import cleanup_expired_jobs


class JobCrawlerService:
    """채용공고 크롤러 서비스"""
    
    def __init__(self, source: str = "work24", max_retries: int = 3, retry_delay: int = 5):
        self.source = source
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def crawl_all_pages(self, base_url: str, max_pages: Optional[int] = None) -> List[Dict[str, str]]:
        """
        모든 페이지를 수집합니다.
        
        Args:
            base_url: 채용공고 목록 페이지 URL
            max_pages: 최대 페이지 수 (None이면 모든 페이지)
            
        Returns:
            채용공고 목록 (link, registered_date, closing_date)
        """
        logger.info(f"모든 페이지 수집 시작 (소스: {self.source})")
        if max_pages:
            logger.info(f"최대 페이지 수: {max_pages}")
        else:
            logger.info("모든 페이지 수집 (빈 페이지를 만나면 종료)")
        
        # max_pages가 None이면 scrape_job_list에 None을 전달하여 모든 페이지 수집
        # max_pages가 지정되면 그만큼만 수집
        if max_pages:
            # 제한된 페이지 수만 수집
            all_jobs = []
            page = 1
            consecutive_empty_pages = 0
            max_empty_pages = 3  # 연속으로 3페이지가 비어있으면 종료
            
            while page <= max_pages:
                try:
                    logger.info(f"페이지 {page}/{max_pages} 수집 중...")
                    
                    # 재시도 로직
                    page_jobs = None
                    for attempt in range(self.max_retries):
                        try:
                            # 한 페이지만 수집 (start_page로 페이지 번호 지정)
                            page_jobs = scrape_job_list(base_url, max_pages=1, start_page=page)
                            break
                        except Exception as e:
                            if attempt < self.max_retries - 1:
                                logger.warning(f"페이지 {page} 수집 실패 (시도 {attempt + 1}/{self.max_retries}): {e}. {self.retry_delay}초 후 재시도...")
                                time.sleep(self.retry_delay)
                            else:
                                logger.error(f"페이지 {page} 수집 최종 실패: {e}")
                                raise
                    
                    if not page_jobs:
                        consecutive_empty_pages += 1
                        logger.warning(f"페이지 {page}에 공고가 없습니다. (연속 빈 페이지: {consecutive_empty_pages})")
                        
                        if consecutive_empty_pages >= max_empty_pages:
                            logger.info(f"연속으로 {max_empty_pages}페이지가 비어있어 수집을 종료합니다.")
                            break
                    else:
                        consecutive_empty_pages = 0
                        all_jobs.extend(page_jobs)
                        logger.info(f"페이지 {page}: {len(page_jobs)}개 공고 수집 완료 (누적: {len(all_jobs)}개)")
                    
                    page += 1
                    time.sleep(1)  # 서버 부하 방지
                    
                except Exception as e:
                    logger.error(f"페이지 {page} 처리 중 오류 발생: {e}", exc_info=True)
                    consecutive_empty_pages += 1
                    
                    if consecutive_empty_pages >= max_empty_pages:
                        logger.error(f"연속으로 {max_empty_pages}페이지에서 오류가 발생하여 수집을 종료합니다.")
                        break
                    
                    page += 1
                    continue
        else:
            # 모든 페이지 수집 (빈 페이지를 만나면 자동 종료)
            logger.info("모든 페이지 수집 모드: scrape_job_list에 max_pages=None 전달")
            all_jobs = scrape_job_list(base_url, max_pages=None, start_page=1)
        
        logger.info(f"총 {len(all_jobs)}개 공고 수집 완료")
        return all_jobs
    
    def scrape_and_save_jobs(self, base_url: str, max_pages: Optional[int] = None) -> Dict:
        """
        채용공고를 크롤링하고 저장합니다.
        
        Returns:
            {
                "total_jobs": int,
                "saved_count": int,
                "failed_count": int,
                "deleted_count": int,
                "errors": List[str],
                "duration_seconds": float
            }
        """
        start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("채용공고 크롤링 시작")
        logger.info("=" * 80)
        logger.info(f"URL: {base_url}")
        logger.info(f"소스: {self.source}")
        logger.info(f"시작 시간: {start_time}")
        
        errors = []
        saved_count = 0
        failed_count = 0
        
        try:
            # 1. 모든 페이지에서 공고 목록 수집
            logger.info("\nStep 1: 채용공고 목록 수집 중...")
            job_list = self.crawl_all_pages(base_url, max_pages=max_pages)
            
            if not job_list:
                logger.warning("수집된 채용공고가 없습니다.")
                return {
                    "total_jobs": 0,
                    "saved_count": 0,
                    "failed_count": 0,
                    "deleted_count": 0,
                    "errors": ["수집된 공고가 없습니다."],
                    "duration_seconds": 0
                }
            
            logger.info(f"✅ 총 {len(job_list)}개의 채용공고를 찾았습니다.")
            
            # 2. 각 공고 스크래핑 및 저장
            logger.info("\nStep 2: 각 공고 스크래핑 및 저장 중...")
            db = SessionLocal()
            saver = JobSaver(db)
            scraper = JobScraper()
            parser = JobParser(follow_links=True, max_links=3)
            cleaner = JobCleaner()
            structurizer = JobStructurizer()
            
            for idx, job_info in enumerate(job_list, 1):
                url = job_info.get('link')
                if not url:
                    logger.warning(f"[{idx}/{len(job_list)}] URL이 없어 스킵합니다.")
                    failed_count += 1
                    continue
                
                registered_date = job_info.get('registered_date')
                closing_date = job_info.get('closing_date')
                company_name_from_list = job_info.get('company_name')  # 목록 페이지에서 추출한 회사명
                
                logger.info(f"\n[{idx}/{len(job_list)}] 처리 중: {url}")
                
                # 재시도 로직
                success = False
                for attempt in range(self.max_retries):
                    try:
                        # Step 1: 스크래핑
                        scraped = scraper.fetch_html(url)
                        if not scraped['success']:
                            raise Exception(f"스크래핑 실패: {scraped.get('error')}")
                        
                        # Step 2: 파싱
                        parsed = parser.parse_html(scraped['html'], base_url=url)
                        if not parsed['success']:
                            raise Exception(f"파싱 실패: {parsed.get('error')}")
                        
                        # Step 3: 정제
                        cleaned = cleaner.validate_panels(parsed['panels'])
                        if not cleaned.get('valid', False):
                            raise Exception(f"정제 실패: {cleaned.get('errors', [])}")
                        
                        # 메타 정보 병합 (목록 페이지에서 추출한 회사명 우선)
                        meta_info = parsed.get('meta', {})
                        if company_name_from_list and not meta_info.get('company_name'):
                            meta_info['company_name'] = company_name_from_list
                        
                        # Step 4: 구조화 (메타 정보 포함)
                        structured = structurizer.structure(
                            panels=cleaned['panels'],
                            url=url,
                            registered_date=registered_date,
                            closing_date=closing_date,
                            source=self.source,
                            meta_info=meta_info
                        )
                        
                        # Step 5: DB 저장 (중복 방지 포함)
                        job_id = saver.save(structured)
                        
                        if job_id:
                            saved_count += 1
                            logger.info(f"  ✅ 저장 완료: {job_id}")
                            success = True
                            break
                        else:
                            raise Exception("저장 실패: job_id가 None")
                            
                    except Exception as e:
                        if attempt < self.max_retries - 1:
                            logger.warning(f"  ⚠️ 오류 발생 (시도 {attempt + 1}/{self.max_retries}): {e}. {self.retry_delay}초 후 재시도...")
                            time.sleep(self.retry_delay)
                        else:
                            error_msg = f"[{idx}/{len(job_list)}] 최종 실패: {url} - {e}"
                            logger.error(error_msg, exc_info=True)
                            errors.append(error_msg)
                            failed_count += 1
                
                if not success:
                    continue
                
                time.sleep(1)  # 서버 부하 방지
            
            # 3. 만료된 공고 삭제
            logger.info("\nStep 3: 만료된 공고 삭제 중...")
            cleanup_result = cleanup_expired_jobs(db)
            deleted_count = cleanup_result.get('deleted_count', 0)
            logger.info(f"✅ 만료된 공고 {deleted_count}개 삭제 완료")
            
            db.close()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("=" * 80)
            logger.info("크롤링 완료!")
            logger.info("=" * 80)
            logger.info(f"총 공고 수: {len(job_list)}개")
            logger.info(f"✅ 성공적으로 저장된 공고: {saved_count}개")
            logger.info(f"❌ 실패한 공고: {failed_count}개")
            logger.info(f"🗑️ 삭제된 만료 공고: {deleted_count}개")
            logger.info(f"⏱️ 소요 시간: {duration:.1f}초")
            logger.info("=" * 80)
            
            return {
                "total_jobs": len(job_list),
                "saved_count": saved_count,
                "failed_count": failed_count,
                "deleted_count": deleted_count,
                "errors": errors,
                "duration_seconds": duration
            }
            
        except Exception as e:
            logger.error(f"크롤링 중 치명적 오류 발생: {e}", exc_info=True)
            return {
                "total_jobs": 0,
                "saved_count": saved_count,
                "failed_count": failed_count,
                "deleted_count": 0,
                "errors": [str(e)],
                "duration_seconds": 0
            }

