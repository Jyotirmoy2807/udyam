from datetime import datetime, timezone
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    CLOCK_FIXED_DATE: datetime = Field(
        default_factory=lambda: datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
    )
    DATABASE_URL: str = "postgresql+psycopg://udyam:udyam_pass@localhost:5432/udyam_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET: str = "kyc-documents"
    MINIO_SECURE: bool = False
    GROQ_API_KEY: str = "gsk_replace_with_real_key"
    ADVISOR_MODEL: str = "llama-3.3-70b-versatile"
    VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    STT_MODEL: str = "whisper-large-v3-turbo"
    LLM_TIMEOUT_SECONDS: float = 4.0
    EXTRACTOR: str = "tesseract"
    JWT_SECRET_KEY: str = "super-secret-demo-jwt-key-2026"
    JWT_ALGORITHM: str = "HS256"
    DEMO_FIXED_OTP: str = "123456"
    FERNET_KEY: str = "3zgZbIWg6YYN9t5u6fSbziC7D6x97QyNW-Id-YDSlTw="
    DOCUMENT_RETENTION_DAYS: int = 30


settings = Settings()
