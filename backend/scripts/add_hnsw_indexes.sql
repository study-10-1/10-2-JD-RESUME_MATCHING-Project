-- HNSW 인덱스 추가 스크립트
-- pgvector의 HNSW 인덱스를 생성하여 벡터 검색 성능 향상

-- job_posting.embedding 인덱스 (전체 텍스트 임베딩)
CREATE INDEX IF NOT EXISTS idx_job_posting_embedding_hnsw 
ON job_posting 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- job_sentence.embedding 인덱스 (문장 단위 임베딩 - 가장 많이 사용)
CREATE INDEX IF NOT EXISTS idx_job_sentence_embedding_hnsw 
ON job_sentence 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- resume.embedding 인덱스
CREATE INDEX IF NOT EXISTS idx_resume_embedding_hnsw 
ON resume 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- resume_sentence.embedding 인덱스 (가장 많은 데이터 - 13,483개)
CREATE INDEX IF NOT EXISTS idx_resume_sentence_embedding_hnsw 
ON resume_sentence 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 인덱스 생성 확인
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE indexname LIKE '%hnsw%'
ORDER BY tablename, indexname;

