"""
스케줄링 설정 CLI
APScheduler를 사용한 스케줄링 설정
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import os

from app.core.logging import logger
from app.core.job_crawler import JobCrawlerService
from app.core.job_cleanup import cleanup_expired_jobs
from app.core.database import SessionLocal


def run_crawler_job():
    """크롤러 작업 실행"""
    try:
        # 환경 변수에서 설정 읽기
        base_url = os.getenv('CRAWLER_BASE_URL')
        source = os.getenv('CRAWLER_SOURCE', 'work24')
        max_retries = int(os.getenv('CRAWLER_MAX_RETRIES', '3'))
        retry_delay = int(os.getenv('CRAWLER_RETRY_DELAY', '5'))
        
        if not base_url:
            logger.error("CRAWLER_BASE_URL 환경 변수가 설정되지 않았습니다.")
            return
        
        logger.info(f"크롤러 작업 시작: {base_url}")
        
        crawler = JobCrawlerService(
            source=source,
            max_retries=max_retries,
            retry_delay=retry_delay
        )
        
        result = crawler.scrape_and_save_jobs(base_url, max_pages=None)  # 모든 페이지
        
        logger.info(f"크롤러 작업 완료: 저장={result['saved_count']}, 실패={result['failed_count']}")
        
    except Exception as e:
        logger.error(f"크롤러 작업 실행 중 오류 발생: {e}", exc_info=True)


def run_cleanup_job():
    """만료된 공고 삭제 작업 실행"""
    try:
        logger.info("만료된 공고 삭제 작업 시작")
        
        db = SessionLocal()
        try:
            result = cleanup_expired_jobs(db)
            logger.info(f"만료된 공고 삭제 완료: {result['deleted_count']}개 삭제")
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"만료된 공고 삭제 작업 실행 중 오류 발생: {e}", exc_info=True)


def start_scheduler():
    """스케줄러 시작"""
    scheduler = BlockingScheduler(timezone='Asia/Seoul')
    
    # 크롤러 작업: 매일 오전 9시 실행
    scheduler.add_job(
        run_crawler_job,
        trigger=CronTrigger(hour=9, minute=0),
        id='crawler_job',
        name='채용공고 크롤링',
        replace_existing=True,
        max_instances=1  # 동시 실행 방지 (중복 방지)
    )
    
    # 만료된 공고 삭제: 매일 오전 9시 10분 실행 (크롤링 후 실행)
    scheduler.add_job(
        run_cleanup_job,
        trigger=CronTrigger(hour=9, minute=10),
        id='cleanup_job',
        name='만료된 공고 삭제',
        replace_existing=True,
        max_instances=1  # 동시 실행 방지 (중복 방지)
    )
    
    logger.info("스케줄러 시작")
    logger.info("크롤러 작업: 매일 09:00")
    logger.info("만료된 공고 삭제: 매일 09:10")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
        scheduler.shutdown()


def main():
    """CLI 진입점"""
    import argparse
    
    parser = argparse.ArgumentParser(description='스케줄러 실행')
    parser.add_argument('--run-once', action='store_true', help='한 번만 실행하고 종료')
    parser.add_argument('--cleanup-only', action='store_true', help='만료된 공고 삭제만 실행')
    
    args = parser.parse_args()
    
    if args.cleanup_only:
        run_cleanup_job()
    elif args.run_once:
        run_crawler_job()
    else:
        start_scheduler()


if __name__ == "__main__":
    main()

