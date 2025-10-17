"""
SentenceIndexer: Use GPT-5 (LLMParser) to split text into high-quality sentences,
then store sentence-level embeddings for resumes and jobs.
"""
from typing import List, Tuple
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.resume import Resume
from app.models.job import JobPosting
from app.models.sentences import ResumeSentence, JobSentence
from app.services.ml.embedding import EmbeddingService


class SentenceIndexer:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedding = EmbeddingService()

    def _llm_split_sentences(self, text: str) -> List[str]:
        """Prefer GPT-5 parsing; fallback to simple rules if LLM unavailable."""
        if not text:
            return []
        try:
            # Lazy import to avoid hard dependency here
            from app.services.parsing.llm_parser import LLMParser
            parser = LLMParser()
            # Expect LLM to return { "sentences": ["..."] }
            res = parser.extract_sentences(text)
            sentences = [s.strip() for s in (res.get("sentences") or []) if isinstance(s, str) and s.strip()]
            if sentences:
                return sentences
        except Exception as e:
            logger.warning(f"LLM sentence split failed, using fallback: {e}")

        # Fallback: naive split by punctuation and newlines
        import re
        raw = re.split(r"(?<=[.!?\n])\s+", text)
        sentences: List[str] = []
        for s in raw:
            s = " ".join(s.strip().split())
            if 20 <= len(s) <= 300 and " " in s and "_" not in s:
                sentences.append(s)
        return sentences

    def index_resume(self, resume: Resume) -> int:
        """Split resume into sentences and persist embeddings. Returns count."""
        text = resume.raw_text or ""
        sentences = self._llm_split_sentences(text)
        count = 0
        for idx, s in enumerate(sentences):
            try:
                emb = self.embedding.generate_embedding(s)
                self.db.add(ResumeSentence(resume_id=resume.id, section=None, idx=idx, text=s, embedding=emb))
                count += 1
            except Exception as e:
                logger.warning(f"Failed to embed resume sentence: {e}")
                continue
        self.db.commit()
        return count

    def index_job(self, job: JobPosting) -> Tuple[int, int]:
        """Split job required/preferred sentences and persist embeddings. Returns (req_count, pref_count)."""
        req_sentences: List[str] = []
        pref_sentences: List[str] = []
        try:
            requirements = job.requirements or {}
            req_src = requirements.get("required") or []
            pref_src = requirements.get("preferred") or []
            # If items are long paragraphs, split via LLM; else use as-is
            req_joined = "\n".join(str(x) for x in req_src)
            pref_joined = "\n".join(str(x) for x in pref_src)
            req_sentences = self._llm_split_sentences(req_joined) if req_joined else []
            pref_sentences = self._llm_split_sentences(pref_joined) if pref_joined else []
        except Exception as e:
            logger.warning(f"Job requirements access failed: {e}")

        r_count = 0
        p_count = 0
        for idx, s in enumerate(req_sentences):
            try:
                emb = self.embedding.generate_embedding(s)
                self.db.add(JobSentence(job_id=job.id, section="required", idx=idx, text=s, embedding=emb))
                r_count += 1
            except Exception as e:
                logger.warning(f"Failed to embed job required sentence: {e}")
        for idx, s in enumerate(pref_sentences):
            try:
                emb = self.embedding.generate_embedding(s)
                self.db.add(JobSentence(job_id=job.id, section="preferred", idx=idx, text=s, embedding=emb))
                p_count += 1
            except Exception as e:
                logger.warning(f"Failed to embed job preferred sentence: {e}")
        self.db.commit()
        return r_count, p_count


