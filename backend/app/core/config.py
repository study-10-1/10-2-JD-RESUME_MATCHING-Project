"""
Application Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application Settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra='ignore'  # 추가 필드 무시
    )
    
    # App Configuration
    APP_NAME: str = "Auto-Match"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Database Configuration
    DATABASE_URL: str
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "auto_match"
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # ML Models
    EMBEDDING_MODEL: str = "jhgan/ko-sroberta-multitask"
    EMBEDDING_DIMENSION: int = 768
    ML_MODELS_PATH: str = "/app/ml_models"
    
    # File Upload
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: str = "pdf,docx,txt"
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    
    # AWS S3 (optional)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_BUCKET_NAME: Optional[str] = None
    AWS_REGION: str = "ap-northeast-2"
    
    # Matching Algorithm
    DEFAULT_MATCH_LIMIT: int = 50
    MIN_SIMILARITY_THRESHOLD: float = 0.6
    
    # Default Weights (전체 임베딩 방식 - 참고용)
    DEFAULT_WEIGHTS: dict = {
        "similarity": 0.50,        # 의미 기반 (가장 신뢰도 높음)
        "technical_skills": 0.20,  # 키워드 매칭 (보조)
        "experience": 0.15,        # 경력 체크
        "education": 0.10,         # 학력
        "certification": 0.025,    # 자격증
        "language": 0.025,         # 언어
    }
    
    # Sectional Weights (55점 기준으로 조정) ⭐ 기본 사용!
    SECTIONAL_WEIGHTS: dict = {
        "required": 0.40,          # 자격요건 매칭 (1순위 - 가장 중요)
        "experience": 0.30,        # 경력 매칭 (2순위 - 매우 중요, 가중치 증가)
        "overall": 0.20,           # 전체 유사도 (3순위 - 중요)
        "preferred": 0.08,         # 우대조건 매칭 (4순위 - 보조적)
        "education": 0.015,        # 학력 (낮은 가중치)
        "certification": 0.005,    # 자격증 (매우 낮은 가중치)
        "language": 0.0,           # 언어 (0으로 설정)
    }
    
    # Default Thresholds
    DEFAULT_THRESHOLDS: dict = {
        "min_similarity": 0.6,
        "good_match": 0.75,
        "excellent_match": 0.9,
    }
    
    # Grade Thresholds (현실적 조정 - 55점 기준)
    GRADE_THRESHOLDS: dict = {
        "excellent": 0.85,  # 매우 우수 - 서류 통과 가능성 높음
        "good": 0.70,       # 양호 - 지원 권장
        "fair": 0.55,       # 보통 - 일부 조건 보완 필요 (현실적 기준)
        "caution": 0.40,    # 주의 - 신중히 검토 필요
        "poor": 0.0,        # 부적합
    }
    
    # Default Penalties (합리적으로 조정)
    DEFAULT_PENALTIES: dict = {
        "experience_level_mismatch": 0.25,      # 경력 레벨 불일치 (합리적 수준)
        "experience_significantly_lacking": 0.20, # 경력 부족 (합리적 수준)
        "domain_mismatch": 0.20,                # 도메인 불일치 (적당한 수준)
        "role_mismatch": 0.15,                  # 역할 불일치 (적당한 수준)
        "required_skill_missing": 0.15,         # 필수 스킬 부족 (적당한 수준)
        "required_skill_critical_missing": 0.25, # 핵심 필수 스킬 부족 (적당한 수준)
    }

    # Caps
    EXPERIENCE_PENALTY_CAP: float = 0.15  # 경력 관련 페널티 총합 상한 (최대 15점 감점)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()

