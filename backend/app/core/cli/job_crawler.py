"""
채용공고 크롤링 CLI
core의 JobCrawlerService를 사용합니다.
"""
from app.core.logging import logger
from app.core.job_crawler import JobCrawlerService


class JobCrawlerScheduler:
    """스케줄링된 채용공고 크롤러 (래퍼 클래스)"""
    
    def __init__(self, source: str = "work24", max_retries: int = 3, retry_delay: int = 5):
        self.service = JobCrawlerService(source=source, max_retries=max_retries, retry_delay=retry_delay)
        self.source = source
        
    def scrape_and_save_jobs(self, base_url: str, max_pages: int = None):
        """
        채용공고를 크롤링하고 저장합니다.
        core의 JobCrawlerService를 사용합니다.
        """
        return self.service.scrape_and_save_jobs(base_url, max_pages=max_pages)


def main():
    """CLI 진입점"""
    import argparse
    
    parser = argparse.ArgumentParser(description='스케줄링된 채용공고 크롤러')
    parser.add_argument('--url', required=True, help='채용공고 목록 페이지 URL')
    parser.add_argument('--source', type=str, default='work24', help='공고 소스 (기본값: work24)')
    parser.add_argument('--max-pages', type=int, help='최대 페이지 수 (지정하지 않으면 모든 페이지)')
    parser.add_argument('--max-retries', type=int, default=3, help='최대 재시도 횟수 (기본값: 3)')
    parser.add_argument('--retry-delay', type=int, default=5, help='재시도 대기 시간(초) (기본값: 5)')
    
    args = parser.parse_args()
    
    crawler = JobCrawlerScheduler(
        source=args.source,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay
    )
    
    result = crawler.scrape_and_save_jobs(args.url, max_pages=args.max_pages)
    
    # 결과 출력
    print("\n" + "=" * 80)
    print("최종 결과")
    print("=" * 80)
    print(f"총 공고 수: {result['total_jobs']}개")
    print(f"저장 성공: {result['saved_count']}개")
    print(f"저장 실패: {result['failed_count']}개")
    print(f"삭제된 만료 공고: {result['deleted_count']}개")
    print(f"소요 시간: {result['duration_seconds']:.1f}초")
    
    if result['errors']:
        print(f"\n오류 ({len(result['errors'])}개):")
        for error in result['errors'][:10]:  # 최대 10개만 출력
            print(f"  - {error}")


if __name__ == "__main__":
    main()

