"""
Embedding Service - HTTP 클라이언트
임베딩 API 서비스와 통신
"""
import httpx
from typing import List
import numpy as np
import os

EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://embedding:8001")


class EmbeddingService:
    """임베딩 생성 서비스 (HTTP 클라이언트)"""
    
    def __init__(self):
        self.service_url = EMBEDDING_SERVICE_URL
        self.dimension = 768
        self.timeout = 180.0  # 긴 텍스트 대비 타임아웃 연장
        self.max_chars = 4000  # 청크 단위 크기 (서비스 안정성용)
        self.max_chunks = 8    # 과도한 배치 요청 방지

    def _split_text_into_chunks(self, text: str) -> list:
        """긴 텍스트를 max_chars 이하의 청크로 분할 (문단/줄 단위 우선)"""
        if not text:
            return [""]
        if len(text) <= self.max_chars:
            return [text]

        paragraphs = [p for p in text.replace("\r", "\n").split("\n\n") if p.strip()]
        chunks = []
        current = []
        current_len = 0
        limit = self.max_chars

        def flush():
            if current:
                chunks.append("\n\n".join(current))
            return [] , 0

        for para in paragraphs:
            pl = len(para)
            if pl > limit:
                # 아주 긴 문단은 강제로 슬라이스
                start = 0
                while start < pl:
                    end = min(start + limit, pl)
                    piece = para[start:end]
                    if current_len + len(piece) > limit:
                        current, current_len = flush()
                    current.append(piece)
                    current_len += len(piece)
                    current, current_len = flush()
                    start = end
            else:
                if current_len + pl + (2 if current else 0) > limit:
                    current, current_len = flush()
                current.append(para)
                current_len += pl

        current, current_len = flush()

        # 청크 개수 제한 (앞에서부터 우선)
        if len(chunks) > self.max_chunks:
            chunks = chunks[: self.max_chunks]
        return chunks if chunks else [text[:limit]]
    
    def load_model(self):
        """
        모델 로드 (임베딩 서비스에서 자동으로 로드됨)
        이 메서드는 호환성을 위해 유지
        """
        # 임베딩 서비스 health check
        try:
            response = httpx.get(f"{self.service_url}/health", timeout=5.0)
            if response.status_code == 200:
                print(f"✅ Embedding service is ready at {self.service_url}")
                return True
        except Exception as e:
            print(f"⚠️  Embedding service not ready: {e}")
            return False
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        텍스트에서 임베딩 생성 (HTTP API 호출)
        
        Args:
            text: 입력 텍스트
            
        Returns:
            768차원 임베딩 벡터
        """
        try:
            # 길면 청크 배치 임베딩 → 평균 풀링
            if text and len(text) > self.max_chars:
                chunks = self._split_text_into_chunks(text)
                embs = self.generate_embeddings_batch(chunks)
                vec = np.mean(embs, axis=0)
                # 정규화 (코사인 유사도 안정화)
                norm = np.linalg.norm(vec) or 1.0
                return (vec / norm).tolist()
            else:
                response = httpx.post(
                    f"{self.service_url}/embed",
                    json={"text": text or ""},
                    timeout=self.timeout
                )
                if response.status_code != 200:
                    raise Exception(f"Embedding API error: {response.status_code} - {response.text}")
                result = response.json()
                return result["embedding"]
            
        except httpx.TimeoutException:
            raise Exception(f"Embedding service timeout after {self.timeout}s")
        except httpx.ConnectError:
            raise Exception(f"Cannot connect to embedding service at {self.service_url}")
        except Exception as e:
            raise Exception(f"Error generating embedding: {e}")
    
    def generate_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """
        여러 텍스트에 대해 임베딩 생성 (배치 처리)
        
        Args:
            texts: 텍스트 리스트
            
        Returns:
            임베딩 배열
        """
        # 1) 서버의 배치 엔드포인트 시도
        try:
            clipped = [
                (t[: self.max_chars] if isinstance(t, str) and len(t) > self.max_chars else (t or ""))
                for t in texts
            ]
            response = httpx.post(
                f"{self.service_url}/embed/batch",
                json={"texts": clipped},
                timeout=min(self.timeout * max(1, len(texts)) / 5, 300.0)
            )
            if response.status_code == 200:
                result = response.json()
                return np.array(result.get("embeddings", []))
        except Exception:
            # 배치 엔드포인트 미지원/오류 시 단건 반복으로 폴백
            pass

        # 2) 폴백: 단건 호출 반복 + 평균/스택 리턴
        embeddings: List[np.ndarray] = []
        last_error: Exception | None = None
        for t in texts:
            try:
                emb = self.generate_embedding(t)
                embeddings.append(np.array(emb))
            except Exception as err:
                last_error = err
                # 실패한 청크는 빈 벡터 대신 0벡터 삽입하여 길이 맞춤
                embeddings.append(np.zeros(self.dimension, dtype=float))
        if not embeddings:
            raise Exception(f"Error generating batch embeddings: {last_error}")
        return np.vstack(embeddings)
    
    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        두 임베딩 간의 코사인 유사도 계산
        
        Args:
            embedding1: 첫 번째 임베딩
            embedding2: 두 번째 임베딩
            
        Returns:
            코사인 유사도 (0~1)
        """
        # Numpy 배열로 변환
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # 코사인 유사도 계산
        # 이미 정규화된 벡터라면 내적이 코사인 유사도
        similarity = np.dot(vec1, vec2)
        
        # 0~1 범위로 클리핑
        similarity = np.clip(similarity, 0.0, 1.0)
        
        return float(similarity)


# 전역 인스턴스 (싱글톤 패턴)
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """임베딩 서비스 인스턴스 가져오기 (싱글톤)"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
