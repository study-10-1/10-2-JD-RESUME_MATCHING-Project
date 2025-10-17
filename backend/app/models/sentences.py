"""
Sentence-level embeddings for resumes and jobs
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


class ResumeSentence(Base):
    __tablename__ = "resume_sentence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resume.id", ondelete="CASCADE"), index=True, nullable=False)
    section = Column(String(50), index=True)
    idx = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(768))

    # relationships
    resume = relationship("Resume", backref="sentences")


class JobSentence(Base):
    __tablename__ = "job_sentence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_posting.id", ondelete="CASCADE"), index=True, nullable=False)
    section = Column(String(50), index=True)  # required, preferred, description, etc.
    idx = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(768))

    # relationships
    job = relationship("JobPosting", backref="sentences")


