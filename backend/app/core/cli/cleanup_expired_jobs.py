"""
만료된 공고 삭제 CLI
expires_at이 지난 공고를 자동으로 삭제합니다.
"""
from app.core.database import SessionLocal
from app.core.job_cleanup import cleanup_expired_jobs as _cleanup_expired_jobs, cleanup_expired_jobs_by_source as _cleanup_expired_jobs_by_source
from app.core.logging import logger


def cleanup_expired_jobs(dry_run: bool = False) -> dict:
    """
    만료된 공고 삭제 (CLI 래퍼)
    core의 cleanup_expired_jobs를 사용합니다.
    """
    db = SessionLocal()
    try:
        return _cleanup_expired_jobs(db, dry_run=dry_run)
    finally:
        db.close()


def cleanup_expired_jobs_by_source(source: str, dry_run: bool = False) -> dict:
    """
    특정 소스의 만료된 공고만 삭제 (CLI 래퍼)
    core의 cleanup_expired_jobs_by_source를 사용합니다.
    """
    db = SessionLocal()
    try:
        return _cleanup_expired_jobs_by_source(db, source, dry_run=dry_run)
    finally:
        db.close()


def main():
    """CLI 진입점"""
    import argparse
    
    parser = argparse.ArgumentParser(description='만료된 공고 삭제')
    parser.add_argument('--source', type=str, help='특정 소스만 삭제 (예: work24)')
    parser.add_argument('--dry-run', action='store_true', help='실제 삭제하지 않고 조회만 수행')
    
    args = parser.parse_args()
    
    if args.source:
        result = cleanup_expired_jobs_by_source(args.source, dry_run=args.dry_run)
    else:
        result = cleanup_expired_jobs(dry_run=args.dry_run)
    
    print("=" * 80)
    if args.dry_run:
        print("[DRY RUN] 삭제 예정 공고")
    else:
        print("삭제 완료")
    print("=" * 80)
    print(f"삭제된 공고 수: {result['deleted_count']}")
    if result['errors']:
        print(f"오류 수: {len(result['errors'])}")
        for error in result['errors']:
            print(f"  - {error}")


if __name__ == "__main__":
    main()

