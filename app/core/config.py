"""
Centralised application configuration.

All settings are read from environment variables (or .env file) and validated
by Pydantic at startup so that the rest of the code never touches raw env vars.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings – every field maps to an environment variable."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────
    app_name: str = "video-ads-engine"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # ── API ────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    allowed_origins: str = "http://localhost:3000,http://localhost:8080"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # ── Auth ───────────────────────────────────────────────
    jwt_secret_key: str = "change-me-to-a-random-64-char-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    api_key_header: str = "X-API-Key"

    # ── Database ───────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/video_ads"
    database_sync_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/video_ads"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # ── Redis ──────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── S3 Storage ─────────────────────────────────────────
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "video-ads"
    s3_region: str = "us-east-1"
    s3_public_url: str = "http://localhost:9000/video-ads"

    # ── AI Models ──────────────────────────────────────────
    models_dir: str = "/models"
    sdxl_model_path: str = "/models/stable-diffusion-xl-base-1.0"
    animatediff_model_path: str = "/models/animatediff-v3"
    svd_model_path: str = "/models/stable-video-diffusion"
    realesrgan_model_path: str = "/models/realesrgan"
    rembg_model_path: str = "/models/u2net"
    llm_model_path: str = "/models/mistral-7b"
    comfyui_api_url: str = "http://localhost:8188"

    # ── Video Processing ──────────────────────────────────
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    max_video_duration: int = 60
    default_fps: int = 30
    default_crf: int = 23

    # ── Worker Settings ────────────────────────────────────
    worker_concurrency: int = 2
    worker_max_retries: int = 2
    worker_retry_delay: int = 30
    gpu_devices: str = "0"

    @property
    def gpu_device_list(self) -> List[int]:
        return [int(d.strip()) for d in self.gpu_devices.split(",") if d.strip()]

    # ── Limits ─────────────────────────────────────────────
    max_products_per_campaign: int = 500
    max_image_size_mb: int = 10
    max_concurrent_campaigns: int = 10
    rate_limit_per_minute: int = 60

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v = v.upper()
        if v not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log level: {v}")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance, cached after first call."""
    return Settings()
