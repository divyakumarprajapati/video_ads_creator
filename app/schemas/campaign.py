"""
Pydantic models for campaign create / read / status / results.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.enums import (
    CampaignGoal,
    CampaignStatus,
    Platform,
    StaticAdStatus,
    StaticAdType,
    VideoStatus,
    VideoType,
)
from app.schemas.brand import BrandIdentity, MarketResearch
from app.schemas.product import ProductInput, ProductOut


# ── Request: create campaign ────────────────────────────────

class WebhookConfig(BaseModel):
    """Optional webhook configuration for async notifications."""
    url: str = Field(..., description="HTTPS endpoint to receive event callbacks")
    secret: Optional[str] = Field(None, description="Shared secret for HMAC verification")
    events: List[str] = Field(
        default=["campaign.completed", "campaign.failed", "video.available"],
        description="Events to subscribe to: campaign.completed, campaign.failed, video.available, progress.update",
    )


class CampaignCreate(BaseModel):
    """
    The **single** request body that kicks off an entire multi-product campaign.
    """
    campaign_name: str = Field(..., min_length=1, max_length=256)
    project_id: str = Field("default", max_length=64)

    brand_identity: BrandIdentity
    market_research: MarketResearch
    products: List[ProductInput] = Field(default_factory=list)

    campaign_goal: CampaignGoal = CampaignGoal.AWARENESS
    platforms: List[Platform] = Field(
        default=[Platform.INSTAGRAM_FEED],
        description="Target platforms for video export",
    )
    duration_preference: int = Field(15, ge=5, le=60, description="Preferred video length in seconds")
    product_specific_variants: int = Field(3, ge=1, le=5)
    general_brand_variants: int = Field(3, ge=1, le=5)
    webhook: Optional[WebhookConfig] = Field(None, description="Webhook for async event notifications")


# ── Response: campaign summary ──────────────────────────────

class CampaignOut(BaseModel):
    id: uuid.UUID
    project_id: str
    campaign_name: str
    campaign_goal: CampaignGoal
    platforms: List[str]
    duration_preference: int
    product_specific_variants: int
    general_brand_variants: int
    status: CampaignStatus
    overall_progress: float
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    total_products: int = 0
    total_videos: int = 0
    total_static_ads: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Response: campaign status (lightweight poll) ────────────

class VideoStatusItem(BaseModel):
    video_id: uuid.UUID
    video_type: VideoType
    product_name: Optional[str] = None
    variant_id: int
    status: VideoStatus
    generation_progress: float
    quality_score: Optional[float] = None

    model_config = {"from_attributes": True}


class CampaignStatusOut(BaseModel):
    campaign_id: uuid.UUID
    status: CampaignStatus
    overall_progress: float
    estimated_completion: Optional[datetime] = None
    total_videos: int
    completed_videos: int
    failed_videos: int
    videos: List[VideoStatusItem]
    total_static_ads: int = 0
    completed_static_ads: int = 0
    failed_static_ads: int = 0
    static_ads: List[StaticAdStatusItem] = []


# ── Response: campaign results (full artefact links) ────────

class PlatformExportOut(BaseModel):
    platform: str
    file_path: Optional[str] = None
    public_url: Optional[str] = None
    file_size_mb: Optional[float] = None
    resolution: Optional[str] = None
    aspect_ratio: Optional[str] = None

    model_config = {"from_attributes": True}


class VideoResultOut(BaseModel):
    video_id: uuid.UUID
    video_type: VideoType
    product_id: Optional[uuid.UUID] = None
    product_name: Optional[str] = None
    variant_id: int
    variant_type: str
    message_angle: str
    primary_message: Optional[str] = None
    secondary_message: Optional[str] = None
    cta_text: Optional[str] = None
    template_id: Optional[uuid.UUID] = None
    layout_type: Optional[str] = None
    status: VideoStatus
    quality_score: Optional[float] = None
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    file_size_mb: Optional[float] = None
    duration_seconds: Optional[float] = None
    exports: List[PlatformExportOut] = []
    metadata: Optional[dict] = None

    model_config = {"from_attributes": True}


# ── Response: static ad results ─────────────────────────────

class StaticAdStatusItem(BaseModel):
    ad_id: uuid.UUID
    ad_type: StaticAdType
    product_name: Optional[str] = None
    variant_id: int
    status: StaticAdStatus
    quality_score: Optional[float] = None

    model_config = {"from_attributes": True}


class StaticAdResultOut(BaseModel):
    ad_id: uuid.UUID
    ad_type: StaticAdType
    product_id: Optional[uuid.UUID] = None
    product_name: Optional[str] = None
    variant_id: int
    variant_type: str
    message_angle: str
    headline: Optional[str] = None
    subheading: Optional[str] = None
    cta_text: Optional[str] = None
    body_text: Optional[str] = None
    image_url: Optional[str] = None
    static_template_id: Optional[str] = None
    static_template_name: Optional[str] = None
    status: StaticAdStatus
    quality_score: Optional[float] = None
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    file_size_mb: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    metadata: Optional[dict] = None

    model_config = {"from_attributes": True}


class CampaignResultsOut(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    status: CampaignStatus
    overall_progress: float
    products: List[ProductOut]
    videos: List[VideoResultOut]
    static_ads: List[StaticAdResultOut] = []
    download_url: Optional[str] = None
    summary: Dict


# ── Request: regenerate specific videos ─────────────────────

class RegenerateRequest(BaseModel):
    video_ids: List[uuid.UUID] = Field(..., min_length=1, description="IDs of videos to regenerate")
