"""
Vector Search Service - pgvector를 사용한 유사도 검색
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Tuple, Optional
from uuid import UUID

from app.models.job import JobPosting
from app.models.resume import Resume
from app.core.logging import logger


class VectorSearchService:
    """벡터 검색 서비스 (pgvector 사용)"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def search_similar_jobs(
        self,
        resume_embedding: List[float],
        limit: int = 50,
        min_similarity: float = 0.3,
        filters: Optional[dict] = None
    ) -> List[Tuple[JobPosting, float]]:
        """
        이력서 임베딩과 유사한 채용공고 검색
        
        Args:
            resume_embedding: 이력서 임베딩 벡터
            limit: 최대 결과 수
            min_similarity: 최소 유사도
            filters: 추가 필터 조건
            
        Returns:
            (JobPosting, similarity_score) 튜플 리스트
        """
        try:
            # pgvector를 사용한 코사인 유사도 검색
            # 1 - cosine_distance = cosine_similarity
            # NumPy 배열을 리스트로 변환
            if hasattr(resume_embedding, 'tolist'):
                embedding_list = resume_embedding.tolist()
            else:
                embedding_list = resume_embedding
            
            # 모든 채용공고 가져오기
            from sqlalchemy import and_
            jobs = self.db.query(JobPosting).filter(
                and_(
                    JobPosting.embedding.isnot(None),
                    JobPosting.is_active == True
                )
            ).all()
            
            if not jobs:
                logger.warning("No active jobs with embeddings found")
                return []
            
            # Python에서 유사도 계산
            jobs_with_scores = []
            for job in jobs:
                if job.embedding is None:
                    continue
                
                job_emb = job.embedding.tolist() if hasattr(job.embedding, 'tolist') else job.embedding
                
                # 코사인 유사도 계산
                import numpy as np
                vec1 = np.array(embedding_list)
                vec2 = np.array(job_emb)
                similarity = float(np.dot(vec1, vec2))
                
                if similarity >= min_similarity:
                    jobs_with_scores.append((job, similarity))
            
            # 유사도 기준 정렬
            jobs_with_scores.sort(key=lambda x: x[1], reverse=True)
            
            # limit 적용
            result = jobs_with_scores[:limit]
            
            logger.info(f"Found {len(result)} similar jobs")
            return result
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise
    
    def search_similar_resumes(
        self,
        job_embedding: List[float],
        limit: int = 100,
        min_similarity: float = 0.3,
        filters: Optional[dict] = None
    ) -> List[Tuple[Resume, float]]:
        """
        채용공고 임베딩과 유사한 이력서 검색
        
        Args:
            job_embedding: 채용공고 임베딩 벡터
            limit: 최대 결과 수
            min_similarity: 최소 유사도
            filters: 추가 필터 조건
            
        Returns:
            (Resume, similarity_score) 튜플 리스트
        """
        try:
            # embedding을 문자열로 변환
            embedding_str = "[" + ",".join(map(str, job_embedding)) + "]"
            
            query = text("""
                SELECT 
                    id,
                    1 - (embedding <=> :embedding::vector) as similarity
                FROM resume
                WHERE embedding IS NOT NULL
                    AND (1 - (embedding <=> :embedding::vector)) >= :min_similarity
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """)
            
            result = self.db.execute(
                query,
                {
                    "embedding": embedding_str,
                    "min_similarity": min_similarity,
                    "limit": limit
                }
            )
            
            rows = result.fetchall()
            
            # Resume 객체로 변환
            resumes_with_scores = []
            for row in rows:
                resume_id = row[0]
                similarity = row[1]
                
                resume = self.db.query(Resume).filter(
                    Resume.id == resume_id
                ).first()
                
                if resume:
                    resumes_with_scores.append((resume, float(similarity)))
            
            logger.info(f"Found {len(resumes_with_scores)} similar resumes")
            return resumes_with_scores
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise
