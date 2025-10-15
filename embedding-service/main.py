"""
Embedding API Service
임베딩 생성 전용 마이크로서비스
"""
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np
import logging

# Logging 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(
    title="Embedding Service",
    description="Text Embedding Generation Service",
    version="1.0.0"
)

# 전역 모델 (싱글톤)
model = None
MODEL_NAME = "jhgan/ko-sroberta-multitask"


def get_model():
    """모델 로드 (lazy loading)"""
    global model
    if model is None:
        logger.info(f"Loading model: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME)
        logger.info("Model loaded successfully!")
    return model


# Request/Response 스키마
class EmbeddingRequest(BaseModel):
    """임베딩 요청"""
    text: str


class BatchEmbeddingRequest(BaseModel):
    """배치 임베딩 요청"""
    texts: List[str]


class EmbeddingResponse(BaseModel):
    """임베딩 응답"""
    embedding: List[float]
    dimension: int


class BatchEmbeddingResponse(BaseModel):
    """배치 임베딩 응답"""
    embeddings: List[List[float]]
    count: int
    dimension: int


@app.on_event("startup")
async def startup_event():
    """시작 시 모델 미리 로드"""
    logger.info("🚀 Starting Embedding Service...")
    try:
        get_model()
        logger.info("✅ Model pre-loaded successfully!")
    except Exception as e:
        logger.error(f"❌ Error loading model: {e}")


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "Embedding Service",
        "model": MODEL_NAME,
        "status": "running",
        "endpoints": {
            "health": "/health",
            "embed": "/embed",
            "embed_batch": "/embed/batch"
        }
    }
@app.post("/echo")
async def echo(request: Request):
    """POST 경로 진단용 에코 엔드포인트"""
    try:
        body = await request.body()
        logger.info(f"/echo received bytes={len(body)}")
        return {"ok": True, "bytes": len(body)}
    except Exception as e:
        logger.error(f"/echo error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "model_loaded": model is not None
    }


@app.post("/embed", response_model=EmbeddingResponse)
async def generate_embedding(request: EmbeddingRequest):
    """
    단일 텍스트 임베딩 생성
    """
    try:
        logger.info(f"/embed called, text_len={len(request.text) if request.text else 0}")
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # 모델 로드
        m = get_model()
        
        # 임베딩 생성
        embedding = m.encode(
            request.text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        logger.info("/embed success")
        
        return EmbeddingResponse(
            embedding=embedding.tolist(),
            dimension=len(embedding)
        )
        
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed/batch", response_model=BatchEmbeddingResponse)
async def generate_embeddings_batch(request: BatchEmbeddingRequest):
    """
    배치 텍스트 임베딩 생성
    """
    try:
        logger.info(f"/embed/batch called, count={len(request.texts) if request.texts else 0}")
        if not request.texts:
            raise HTTPException(status_code=400, detail="Texts cannot be empty")
        
        # 모델 로드
        m = get_model()
        
        # 배치 임베딩 생성
        embeddings = m.encode(
            request.texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        logger.info("/embed/batch success")
        
        return BatchEmbeddingResponse(
            embeddings=embeddings.tolist(),
            count=len(embeddings),
            dimension=len(embeddings[0])
        )
        
    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/similarity")
async def calculate_similarity(text1: str, text2: str):
    """
    두 텍스트 간의 유사도 계산
    """
    try:
        m = get_model()
        
        embeddings = m.encode([text1, text2], normalize_embeddings=True)
        
        # 코사인 유사도
        similarity = float(np.dot(embeddings[0], embeddings[1]))
        
        return {
            "text1": text1,
            "text2": text2,
            "similarity": similarity
        }
        
    except Exception as e:
        logger.error(f"Error calculating similarity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

