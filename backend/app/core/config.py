import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load in priority order: last file wins.
        # The local backend/.env overrides root-level .env files so that
        # workspace-level defaults do not bleed into EquiLens AI settings.
        env_file=("../../.env", "../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "EquiLens AI"
    APP_DEBUG: bool = True
    DATA_MODE: str = "demo"  # "demo" or "live"
    API_V1_PREFIX: str = "/api/v1"

    # Server URLs
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database (PostgreSQL + pgvector or Supabase PostgreSQL)
    DATABASE_URL: Optional[str] = None
    DIRECT_URL: Optional[str] = None

    # Supabase (Managed Auth & Storage)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "equilens-documents"

    # MongoDB Atlas Vector Search
    MONGODB_URI: Optional[str] = None
    MONGODB_DB: str = "equilens_rag"

    # AI & LLM Providers
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_FALLBACK_MODEL: Optional[str] = None

    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: Optional[str] = None

    # Embedding Model
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_MAX_SEQ_LENGTH: int = 512

    # RAG Pipeline defaults
    RAG_CHUNK_SIZE: int = 600
    RAG_CHUNK_OVERLAP: int = 100
    RAG_RETRIEVAL_TOP_K: int = 8
    RAG_HYBRID_ENABLED: bool = True
    RAG_RERANKING_ENABLED: bool = False
    RAG_VECTOR_WEIGHT: float = 0.6
    RAG_KEYWORD_WEIGHT: float = 0.4

    # Market Data Providers (Indian Equities - NSE/BSE)
    DHAN_CLIENT_ID: Optional[str] = None
    DHAN_ACCESS_TOKEN: Optional[str] = None

    # Financial News Provider
    MARKETAUX_API_TOKEN: Optional[str] = None

    # Fundamentals Provider (Optional)
    FMP_API_KEY: Optional[str] = None

    # Observability and Monitoring
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_BASE_URL: Optional[str] = None
    SENTRY_DSN: Optional[str] = None

    @property
    def effective_langfuse_host(self) -> str:
        raw = self.LANGFUSE_BASE_URL or self.LANGFUSE_HOST or "https://cloud.langfuse.com"
        return raw.strip('"\'').rstrip('/')

    # Security
    SECRET_KEY: str = "equilens_ai_default_jwt_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Local storage fallback directory
    LOCAL_UPLOAD_DIR: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../uploads")
    )


settings = Settings()
