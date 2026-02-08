"""
SQLAlchemy ORM models for the campaign domain.

Tables
------
campaigns             – top-level campaign record
campaign_products     – products attached to a campaign
campaign_videos       – individual video records (product-specific or general-brand)
campaign_platform_exports – per-platform encoded files for each video
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    CampaignGoal,
    CampaignStatus,
    LayoutType,
    MessageAngle,
    Platform,
    ProductGenerationStatus,
    StaticAdStatus,
    StaticAdType,
    VariantType,
    VideoStatus,
    VideoType,
)
from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def _string_enum(enum_cls, *, name: str) -> Enum:  # type: ignore[type-arg]
    """
    Store domain enums as VARCHAR in Postgres.

    Our Alembic schema uses plain string columns (not native Postgres ENUM types).
    Using SQLAlchemy's default Enum(...) with Postgres will otherwise try to bind
    values as ::<enumtype> (e.g. ::campaigngoal), which fails if the DB type
    doesn't exist.
    """

    return Enum(
        enum_cls,
        native_enum=False,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
        name=name,
    )

# ────────────────────────────────────────────────────────────
#  Campaign
# ────────────────────────────────────────────────────────────

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    campaign_name: Mapped[str] = mapped_column(String(256), nullable=False)

    # Strategy inputs
    campaign_goal: Mapped[CampaignGoal] = mapped_column(
        _string_enum(CampaignGoal, name="campaign_goal"),
        default=CampaignGoal.AWARENESS,
    )
    platforms: Mapped[list] = mapped_column(JSONB, default=list)  # list[Platform]
    duration_preference: Mapped[int] = mapped_column(Integer, default=15)  # seconds

    # Brand identity (JSONB blob)
    brand_identity: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Market research (JSONB blob)
    market_research: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Generation knobs
    product_specific_variants: Mapped[int] = mapped_column(Integer, default=3)
    general_brand_variants: Mapped[int] = mapped_column(Integer, default=3)

    # Overall strategy plan produced by StrategyEngine
    strategy_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Progress
    status: Mapped[CampaignStatus] = mapped_column(
        _string_enum(CampaignStatus, name="campaign_status"),
        default=CampaignStatus.DRAFT,
        index=True,
    )
    overall_progress: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_completion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    products: Mapped[list["CampaignProduct"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )
    videos: Mapped[list["CampaignVideo"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )
    static_ads: Mapped[list["CampaignStaticAd"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )


# ────────────────────────────────────────────────────────────
#  Campaign Product
# ────────────────────────────────────────────────────────────

class CampaignProduct(Base):
    __tablename__ = "campaign_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )

    product_name: Mapped[str] = mapped_column(String(256), nullable=False)
    product_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    product_image_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_features: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {"is_new": bool, "is_bestseller": bool}
    image_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Per-product creative plan produced by the strategy engine
    creative_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Processing state
    generation_status: Mapped[ProductGenerationStatus] = mapped_column(
        _string_enum(ProductGenerationStatus, name="product_generation_status"),
        default=ProductGenerationStatus.PENDING,
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)

    # Processed asset paths (populated during asset-prep)
    processed_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    background_removed_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    upscaled_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="products")
    videos: Mapped[list["CampaignVideo"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_campaign_products_campaign", "campaign_id"),
    )


# ────────────────────────────────────────────────────────────
#  Campaign Video
# ────────────────────────────────────────────────────────────

class CampaignVideo(Base):
    __tablename__ = "campaign_videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_products.id", ondelete="SET NULL"),
        nullable=True,
    )

    video_type: Mapped[VideoType] = mapped_column(
        _string_enum(VideoType, name="video_type"), nullable=False
    )
    variant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_type: Mapped[VariantType] = mapped_column(
        _string_enum(VariantType, name="variant_type"), nullable=False
    )
    message_angle: Mapped[MessageAngle] = mapped_column(
        _string_enum(MessageAngle, name="message_angle"), nullable=False
    )

    # Messaging
    primary_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    secondary_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cta_text: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Template
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_templates.id", ondelete="SET NULL"), nullable=True
    )
    layout_type: Mapped[LayoutType | None] = mapped_column(
        _string_enum(LayoutType, name="layout_type"), nullable=True
    )
    products_shown: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Status
    status: Mapped[VideoStatus] = mapped_column(
        _string_enum(VideoStatus, name="video_status"),
        default=VideoStatus.QUEUED,
        index=True,
    )
    generation_progress: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Output artefacts
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="videos")
    product: Mapped["CampaignProduct | None"] = relationship(back_populates="videos")
    template: Mapped["VideoTemplate | None"] = relationship(lazy="selectin")
    exports: Mapped[list["CampaignPlatformExport"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_campaign_videos_campaign", "campaign_id"),
        Index("ix_campaign_videos_product", "product_id"),
        Index("ix_campaign_videos_status", "status"),
    )


# ────────────────────────────────────────────────────────────
#  Platform Export
# ────────────────────────────────────────────────────────────

class CampaignPlatformExport(Base):
    __tablename__ = "campaign_platform_exports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_videos.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[Platform] = mapped_column(
        _string_enum(Platform, name="platform"), nullable=False
    )

    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    aspect_ratio: Mapped[str | None] = mapped_column(String(16), nullable=True)
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    video: Mapped["CampaignVideo"] = relationship(back_populates="exports")


# ────────────────────────────────────────────────────────────
#  Video Template
# ────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────
#  Campaign Static Ad
# ────────────────────────────────────────────────────────────

class CampaignStaticAd(Base):
    __tablename__ = "campaign_static_ads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_products.id", ondelete="SET NULL"),
        nullable=True,
    )

    ad_type: Mapped[StaticAdType] = mapped_column(
        _string_enum(StaticAdType, name="static_ad_type"), nullable=False
    )
    variant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_type: Mapped[VariantType] = mapped_column(
        _string_enum(VariantType, name="static_ad_variant_type"), nullable=False
    )
    message_angle: Mapped[MessageAngle] = mapped_column(
        _string_enum(MessageAngle, name="static_ad_message_angle"), nullable=False
    )

    # Template reference
    static_template_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    static_template_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Messaging
    headline: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subheading: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cta_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Image reference (user-provided or product image)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Output artefacts
    status: Mapped[StaticAdStatus] = mapped_column(
        _string_enum(StaticAdStatus, name="static_ad_status"),
        default=StaticAdStatus.QUEUED,
        index=True,
    )
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full template spec used for generation
    template_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="static_ads")
    product: Mapped["CampaignProduct | None"] = relationship()

    __table_args__ = (
        Index("ix_campaign_static_ads_campaign", "campaign_id"),
        Index("ix_campaign_static_ads_product", "product_id"),
        Index("ix_campaign_static_ads_status", "status"),
    )


class VideoTemplate(Base):
    __tablename__ = "video_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Full definition: layers, keyframes, animations, timing, text placement
    template_spec: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Compatibility filters
    compatible_visual_styles: Mapped[list] = mapped_column(JSONB, default=list)
    compatible_video_styles: Mapped[list] = mapped_column(JSONB, default=list)
    compatible_industries: Mapped[list] = mapped_column(JSONB, default=list)

    requires_product_image: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_background: Mapped[bool] = mapped_column(Boolean, default=False)

    min_duration: Mapped[int] = mapped_column(Integer, default=5)
    max_duration: Mapped[int] = mapped_column(Integer, default=30)
    supported_aspect_ratios: Mapped[list] = mapped_column(JSONB, default=list)

    # Performance tracking
    performance_score: Mapped[float] = mapped_column(Float, default=50.0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
