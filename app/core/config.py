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
    # Default to quiet logs; set LOG_LEVEL=INFO/DEBUG to see more.
    log_level: str = "ERROR"

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
    database_echo: bool = False  # log SQL statements (very noisy)

    # ── Feature Flags (local-first defaults) ───────────────
    use_celery: bool = False          # False = run workers in-process (thread)
    redis_enabled: bool = False       # False = in-memory rate-limit & progress
    storage_backend: str = "local"    # "local", "s3", or "gcs"

    # ── Redis (only used when redis_enabled=True) ──────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Local Storage ──────────────────────────────────────
    local_storage_root: str = "./output"
    local_storage_url_prefix: str = "http://localhost:8000/static"

    # ── S3 Storage (only used when storage_backend="s3") ───
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "video-ads"
    s3_region: str = "us-east-1"
    s3_public_url: str = "http://localhost:9000/video-ads"

    # ── GCS Storage (only used when storage_backend="gcs") ──
    gcs_project: str = ""
    gcs_bucket_name: str = "video-ads"
    gcs_credentials_json: str = ""  # optional service-account JSON content
    gcs_location: str = "US"
    gcs_public_url: str = ""        # default: https://storage.googleapis.com/<bucket>
    gcs_make_public: bool = True
    gcs_signed_url_expiry_seconds: int = 3600

    # ── OpenAI (for ad-copy generation) ──────────────────────
    openai_api_key: str = ""              # set to enable AI copywriting
    openai_model: str = "gpt-5.1-chat-latest"
    openai_max_tokens: int = 512
    openai_temperature: float = 0.7
    openai_base_url: str = ""             # leave empty for default api.openai.com

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)

    # ── Anthropic (for SVG static ad generation) ─────────────
    anthropic_api_key: str = ""           # set to enable Anthropic SVG ads
    anthropic_model: str = "claude-opus-4-5"
    anthropic_max_tokens: int = 4000
    anthropic_temperature: float = 0.6
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_request_timeout_s: int = 120
    use_anthropic_svg_ads: bool = True
    static_ad_copy_provider: str = "deterministic"  # deterministic | openai
    static_ads_max_total: int = 15
    static_ads_min_total: int = 10
    static_ads_brand_count: int = 3

    # ── AI Models (vision / video – open source) ──────────
    models_dir: str = "/models"
    sdxl_model_path: str = "/models/stable-diffusion-xl-base-1.0"
    animatediff_model_path: str = "/models/animatediff-v3"
    svd_model_path: str = "/models/stable-video-diffusion"
    realesrgan_model_path: str = "/models/realesrgan"
    rembg_model_path: str = "/models/u2net"
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
