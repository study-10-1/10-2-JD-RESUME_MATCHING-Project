"""
Resume API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
import os
import shutil
import time

from app.core.database import get_db
from app.models.resume import Resume
from app.core.config import settings
from app.services.parsing.pdf_parser import PDFParser
from app.services.parsing.docx_parser import DOCXParser
from app.services.parsing.xlsx_parser import XLSXParser
from app.services.parsing.llm_parser import LLMParser
from app.services.ml.embedding import get_embedding_service
from app.core.logging import logger
from app.schemas.resume import (
    ResumeUploadResponse,
)

router = APIRouter()


def _safe_list(value):
    return value if isinstance(value, list) else []




@router.post("/upload-and-process", response_model=ResumeUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_and_process_resume(
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db)
):
    """
    이력서 업로드 + 파싱 + 임베딩 생성 + DB 저장
    - 로컬 저장소에 파일 저장
    - 파일 타입에 따라 텍스트 추출
    - LLMParser로 구조화 및 핵심 정보 추출
    - 전체/섹션 임베딩 생성
    - Resume 레코드 생성 후 반환
    """
    start_time = time.time()
    try:
        # 1) 디렉토리 보장
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        # 2) 파일 저장
        original_name = file.filename
        ext = (os.path.splitext(original_name)[1] or "").lower()
        safe_name = f"{int(time.time()*1000)}_{original_name}"
        disk_path = os.path.join(settings.UPLOAD_DIR, safe_name)

        with open(disk_path, "wb") as out:
            shutil.copyfileobj(file.file, out)

        file_size = os.path.getsize(disk_path)
        file_type = ext.replace(".", "") or "txt"

        # 3) 텍스트 추출
        if file_type == "pdf":
            raw_text = PDFParser().extract_text(disk_path)
        elif file_type in ("docx", "doc"):
            raw_text = DOCXParser().extract_text(disk_path)
        elif file_type in ("xlsx", "xls"):
            raw_text = XLSXParser().extract_text(disk_path)
        else:
            # 기본 텍스트 파일로 처리
            with open(disk_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()

        # 4) LLM 파싱 및 핵심 정보 추출
        # raw_text가 비었거나 매우 짧으면 파싱/임베딩 생략
        if not raw_text or not raw_text.strip():
            resume = Resume(
                user_id=None,
                file_name=original_name,
                file_url=disk_path,
                file_type=file_type,
                file_size=file_size,
                raw_text=raw_text or "",
                parsed_data={},
                extracted_skills=[],
                extracted_experience_years=0,
                extracted_domains=[],
                extracted_education_level="",
                embedding=None,
                embedding_model=settings.EMBEDDING_MODEL,
                skills_embedding=None,
                experience_embedding=None,
                projects_embedding=None,
                is_primary=is_primary,
            )
            db.add(resume)
            db.commit()
            db.refresh(resume)
            processing_time_ms = int((time.time() - start_time) * 1000)
            return {
                "resume_id": resume.id,
                "file_name": resume.file_name,
                "file_url": resume.file_url,
                "parsed_data": {},
                "extracted_skills": [],
                "extracted_experience_years": 0,
                "processing_time_ms": processing_time_ms,
                "message": "empty_text_skipped",
            }

        llm_parser = LLMParser()
        try:
            parsed = llm_parser.parse_resume(raw_text)
        except Exception:
            parsed = {}
        try:
            extracted = llm_parser.extract_structured_info(parsed or {})
        except Exception:
            extracted = {
                "extracted_skills": [],
                "extracted_experience_years": 0,
                "extracted_domains": [],
                "extracted_education_level": "",
            }

        # 5) 우선 DB에 저장 (임베딩 없이)
        resume = Resume(
            user_id=None,
            file_name=original_name,
            file_url=disk_path,
            file_type=file_type,
            file_size=file_size,
            raw_text=raw_text or "",
            parsed_data=parsed or {},
            extracted_skills=extracted.get("extracted_skills", []),
            extracted_experience_years=int(extracted.get("extracted_experience_years", 0) or 0),
            extracted_domains=extracted.get("extracted_domains", []),
            extracted_education_level=extracted.get("extracted_education_level", ""),
            embedding=None,
            embedding_model=settings.EMBEDDING_MODEL,
            skills_embedding=None,
            experience_embedding=None,
            projects_embedding=None,
            is_primary=is_primary,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

        # 6) 문장 단위 임베딩만 생성 (최적화)
        has_sentences = False

        try:
            # 문장 단위 임베딩 생성 (전체/섹션별 임베딩 제거)
            from app.services.indexing.sentence_indexer import SentenceIndexer
            sentence_indexer = SentenceIndexer(db)
            sentence_count = sentence_indexer.index_resume(resume)
            has_sentences = sentence_count > 0
            logger.info(f"Indexed {sentence_count} resume sentences (optimized)")

            db.add(resume)
            db.commit()
            db.refresh(resume)
        except Exception as sent_err:
            logger.warning(f"Sentence indexing failed: {sent_err}")
            has_sentences = False

        processing_time_ms = int((time.time() - start_time) * 1000)
        return {
            "resume_id": resume.id,
            "file_name": resume.file_name,
            "file_url": resume.file_url,
            "parsed_data": parsed,
            "extracted_skills": resume.extracted_skills,
            "extracted_experience_years": resume.extracted_experience_years,
            "processing_time_ms": processing_time_ms,
            "has_sentences": has_sentences,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload/process error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload/process failed: {e}")


@router.post("/{resume_id}/generate-embeddings")
async def generate_resume_embeddings(
    resume_id: str,
    db: Session = Depends(get_db)
):
    """
    업로드/파싱된 이력서에 대해 임베딩만 생성/갱신 (전체+섹션)
    """
    try:
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        # 문장 단위 임베딩만 재생성 (최적화)
        has_sentences = False
        try:
            from app.services.indexing.sentence_indexer import SentenceIndexer
            sentence_indexer = SentenceIndexer(db)
            sentence_count = sentence_indexer.index_resume(resume)
            has_sentences = sentence_count > 0
            logger.info(f"Re-indexed {sentence_count} resume sentences (optimized)")
        except Exception as sent_err:
            logger.warning(f"Sentence re-indexing failed: {sent_err}")

        return {
            "resume_id": str(resume.id),
            "updated": True,
            "has_sentences": has_sentences,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")




 

