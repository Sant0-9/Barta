"""
Configuration management for Barta API
"""
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://barta:barta@db:5432/barta"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # API
    SECRET_KEY: str = "your-secret-key-here"
    API_KEY: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://web:3000"]
    
    # External APIs (stubs for future use)
    NEWS_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    
    # Retrieval Configuration
    RERANKER_ENABLED: bool = True
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RETRIEVAL_K_BM25: int = 100
    RETRIEVAL_K_DENSE: int = 100
    RETRIEVAL_MMR_K: int = 40
    RETRIEVAL_FINAL_K: int = 8
    RETRIEVAL_MMR_LAMBDA: float = 0.7
    CACHE_TTL_SECONDS: int = 3600
    
    # LLM Chat Configuration
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 700
    LLM_TEMPERATURE: float = 0.2
    CITATION_STRICT: bool = True
    PLAN_MAX_BULLETS: int = 8
    
    class Config:
        env_file = "../../.env"

settings = Settings()