"""
Backfill resume/job sentences using GPT-5 parsing and store embeddings.
Run: docker compose exec backend python backend/scripts/backfill_sentences.py
"""
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logging import logger
from app.models.resume import Resume
from app.models.job import JobPosting
from app.models.sentences import ResumeSentence, JobSentence
from app.services.indexing.sentence_indexer import SentenceIndexer


def main() -> None:
    db: Session = next(get_db())
    indexer = SentenceIndexer(db)

    # Backfill resumes (skip if sentences already exist)
    resumes = db.query(Resume).all()
    done_r = 0
    for r in resumes:
        exists = db.query(ResumeSentence).filter(ResumeSentence.resume_id == r.id).limit(1).first()
        if exists:
            continue
        try:
            cnt = indexer.index_resume(r)
            done_r += 1
            logger.info(f"Indexed resume {r.id} sentences: {cnt}")
        except Exception as e:
            logger.warning(f"Resume {r.id} failed: {e}")

    # Backfill jobs (skip if sentences already exist)
    jobs = db.query(JobPosting).all()
    done_j = 0
    for j in jobs:
        exists = db.query(JobSentence).filter(JobSentence.job_id == j.id).limit(1).first()
        if exists:
            continue
        try:
            rc, pc = indexer.index_job(j)
            done_j += 1
            logger.info(f"Indexed job {j.id} sentences: required={rc}, preferred={pc}")
        except Exception as e:
            logger.warning(f"Job {j.id} failed: {e}")

    print({
        "resumes_processed": done_r,
        "jobs_processed": done_j,
    })


if __name__ == "__main__":
    main()


