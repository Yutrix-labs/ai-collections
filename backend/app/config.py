"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0")
    use_mock_redis: bool = Field(default=False)  # NEW: For testing without Redis

    # Database Configuration
    database_url: str = Field(default="postgresql+asyncpg://user:password@localhost:5432/collections_db")

    # Claude API
    claude_api_key: str = Field(default="")

    # JWT Authentication
    jwt_secret_key: str = Field(default="dev-secret-key-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=60)

    # Application Settings
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")

    # CORS Settings
    allowed_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ]
    )

    # Worker Settings
    transcript_worker_poll_interval: float = Field(default=0.1)
    insights_worker_poll_interval: float = Field(default=0.1)

    # AI Insights Configuration
    llm_temperature: float = Field(default=0.3)
    llm_max_tokens: int = Field(default=500)
    llm_model: str = Field(default="claude-sonnet-4-5-20250929")

    # Rate Limiting (seconds)
    rate_limit_sentiment: int = Field(default=45)
    rate_limit_intent: int = Field(default=30)
    rate_limit_policy: int = Field(default=60)

    # Redis Stream Settings
    stream_ttl: int = Field(default=1800)  # 30 minutes in seconds
    stream_read_count: int = Field(default=10)
    stream_block_ms: int = Field(default=1000)

    # Call Settings
    call_context_cache_ttl: int = Field(default=3600)  # 1 hour


# Global settings instance
settings = Settings()
