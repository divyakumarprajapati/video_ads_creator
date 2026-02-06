"""
All domain enums live here so every layer can import from one place.
"""

from __future__ import annotations

import enum


# ── Campaign ───────────────────────────────────────────────

class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    STRATEGISING = "strategising"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CampaignGoal(str, enum.Enum):
    AWARENESS = "awareness"
    CONSIDERATION = "consideration"
    CONVERSION = "conversion"
    RETENTION = "retention"


# ── Platform ───────────────────────────────────────────────

class Platform(str, enum.Enum):
    INSTAGRAM_FEED = "instagram_feed"
    INSTAGRAM_STORY = "instagram_story"
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    META_ADS = "meta_ads"


# ── Video ──────────────────────────────────────────────────

class VideoType(str, enum.Enum):
    PRODUCT_SPECIFIC = "product_specific"
    GENERAL_BRAND = "general_brand"


class VideoStatus(str, enum.Enum):
    QUEUED = "queued"
    ASSET_PREP = "asset_prep"
    GENERATING = "generating"
    COMPOSITING = "compositing"
    ENCODING = "encoding"
    QA = "qa"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class MessageAngle(str, enum.Enum):
    BENEFIT = "benefit"
    SOCIAL_PROOF = "social_proof"
    URGENCY = "urgency"


class VariantType(str, enum.Enum):
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"
    VARIANT_C = "variant_c"


class VisualStyle(str, enum.Enum):
    BOLD_VIBRANT = "bold_vibrant"
    SOFT_PREMIUM = "soft_premium"
    MINIMALIST = "minimalist"
    HIGH_ENERGY = "high_energy"
    ELEGANT = "elegant"
    PLAYFUL = "playful"


class VideoStyle(str, enum.Enum):
    PRODUCT_HERO = "product_hero"
    LIFESTYLE_SCENE = "lifestyle_scene"
    KINETIC_TEXT = "kinetic_text"
    ABSTRACT_MOTION = "abstract_motion"


class LayoutType(str, enum.Enum):
    """Layouts used for general-brand multi-product videos."""
    SEQUENTIAL_CAROUSEL = "sequential_carousel"
    GRID_LAYOUT = "grid_layout"
    HERO_SUPPORTING = "hero_supporting"
    LIFESTYLE_MONTAGE = "lifestyle_montage"


# ── Product ────────────────────────────────────────────────

class ProductGenerationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Template ───────────────────────────────────────────────

class TemplateCategory(str, enum.Enum):
    PRODUCT_HERO = "product_hero"
    LIFESTYLE_SCENE = "lifestyle_scene"
    KINETIC_TEXT = "kinetic_text"
    ABSTRACT_MOTION = "abstract_motion"
    MULTI_PRODUCT = "multi_product"


# ── Market ─────────────────────────────────────────────────

class MarketSaturation(str, enum.Enum):
    LOW = "low"           # < 30 %
    MEDIUM = "medium"     # 30 – 60 %
    HIGH = "high"         # 60 – 80 %
    VERY_HIGH = "very_high"  # > 80 %


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"
