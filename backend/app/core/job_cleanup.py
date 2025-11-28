"""
만료된 공고 삭제 서비스
"""
from datetime import date
from typing import Dict, List
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.job import JobPosting
from app.models.sentences import JobSentence


def cleanup_expired_jobs(db: Session, dry_run: bool = False) -> Dict:
    """
    만료된 공고 삭제
    
    Args:
        db: 데이터베이스 세션
        dry_run: True면 실제 삭제하지 않고 조회만 수행
        
    Returns:
        {
            "deleted_count": int,
            "deleted_jobs": List[dict],
            "errors": List[str]
        }
    """
    today = date.today()
    
    try:
        # expires_at이 오늘보다 이전인 공고 조회
        expired_jobs = db.query(JobPosting).filter(
            JobPosting.expires_at.isnot(None),
            JobPosting.expires_at < today
        ).all()
        
        if not expired_jobs:
            logger.info("만료된 공고가 없습니다.")
            return {
                "deleted_count": 0,
                "deleted_jobs": [],
                "errors": []
            }
        
        logger.info(f"만료된 공고 {len(expired_jobs)}개 발견 (기준일: {today})")
        
        deleted_count = 0
        deleted_jobs = []
        errors = []
        
        for job in expired_jobs:
            try:
                # 관련 JobSentence 삭제
                sentence_count = db.query(JobSentence).filter(
                    JobSentence.job_id == job.id
                ).delete()
                
                job_info = {
                    "id": str(job.id),
                    "title": job.title[:50],
                    "external_id": job.external_id,
                    "expires_at": str(job.expires_at),
                    "sentence_count": sentence_count
                }
                
                if not dry_run:
                    # JobPosting 삭제
                    db.delete(job)
                    deleted_count += 1
                    logger.info(f"삭제: {job.title[:50]}... (만료일: {job.expires_at}, 문장 {sentence_count}개)")
                else:
                    logger.info(f"[DRY RUN] 삭제 예정: {job.title[:50]}... (만료일: {job.expires_at}, 문장 {sentence_count}개)")
                
                deleted_jobs.append(job_info)
                
            except Exception as e:
                error_msg = f"공고 삭제 실패 (ID: {job.id}): {e}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
        
        if not dry_run:
            db.commit()
            logger.info(f"✅ 만료된 공고 {deleted_count}개 삭제 완료")
        else:
            logger.info(f"[DRY RUN] 만료된 공고 {len(expired_jobs)}개 삭제 예정")
        
        return {
            "deleted_count": deleted_count if not dry_run else 0,
            "deleted_jobs": deleted_jobs,
            "errors": errors
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"만료된 공고 삭제 중 오류 발생: {e}", exc_info=True)
        return {
            "deleted_count": 0,
            "deleted_jobs": [],
            "errors": [str(e)]
        }


def cleanup_expired_jobs_by_source(db: Session, source: str, dry_run: bool = False) -> Dict:
    """
    특정 소스의 만료된 공고만 삭제
    
    Args:
        db: 데이터베이스 세션
        source: 공고 소스 (예: 'work24')
        dry_run: True면 실제 삭제하지 않고 조회만 수행
    """
    today = date.today()
    
    try:
        expired_jobs = db.query(JobPosting).filter(
            JobPosting.source == source,
            JobPosting.expires_at.isnot(None),
            JobPosting.expires_at < today
        ).all()
        
        if not expired_jobs:
            logger.info(f"소스 '{source}'의 만료된 공고가 없습니다.")
            return {
                "deleted_count": 0,
                "deleted_jobs": [],
                "errors": []
            }
        
        logger.info(f"소스 '{source}'의 만료된 공고 {len(expired_jobs)}개 발견")
        
        deleted_count = 0
        deleted_jobs = []
        errors = []
        
        for job in expired_jobs:
            try:
                sentence_count = db.query(JobSentence).filter(
                    JobSentence.job_id == job.id
                ).delete()
                
                job_info = {
                    "id": str(job.id),
                    "title": job.title[:50],
                    "external_id": job.external_id,
                    "expires_at": str(job.expires_at),
                    "sentence_count": sentence_count
                }
                
                if not dry_run:
                    db.delete(job)
                    deleted_count += 1
                    logger.info(f"삭제: {job.title[:50]}... (만료일: {job.expires_at})")
                else:
                    logger.info(f"[DRY RUN] 삭제 예정: {job.title[:50]}... (만료일: {job.expires_at})")
                
                deleted_jobs.append(job_info)
                
            except Exception as e:
                error_msg = f"공고 삭제 실패 (ID: {job.id}): {e}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
        
        if not dry_run:
            db.commit()
            logger.info(f"✅ 소스 '{source}'의 만료된 공고 {deleted_count}개 삭제 완료")
        
        return {
            "deleted_count": deleted_count if not dry_run else 0,
            "deleted_jobs": deleted_jobs,
            "errors": errors
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"만료된 공고 삭제 중 오류 발생: {e}", exc_info=True)
        return {
            "deleted_count": 0,
            "deleted_jobs": [],
            "errors": [str(e)]
        }

