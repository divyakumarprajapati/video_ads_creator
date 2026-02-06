"""
Deterministic decision matrices.

Every creative decision is derived from lookup tables – **no AI guessing**.
These matrices map (market conditions, campaign goal, product attributes) to
concrete visual / messaging / pacing choices.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.core.enums import (
    CampaignGoal,
    LayoutType,
    MarketSaturation,
    MessageAngle,
    Sentiment,
    VisualStyle,
    VideoStyle,
)

# ────────────────────────────────────────────────────────────
#  Market Saturation × Competitive Edge → Visual Style
# ────────────────────────────────────────────────────────────
# Key: (saturation, competitive_edge_bucket)
#   competitive_edge_bucket:  "low" < 40,  "mid" 40-70,  "high" > 70

VISUAL_STYLE_MATRIX: Dict[Tuple[MarketSaturation, str], VisualStyle] = {
    # Low saturation – room to be bold
    (MarketSaturation.LOW, "low"):      VisualStyle.MINIMALIST,
    (MarketSaturation.LOW, "mid"):      VisualStyle.SOFT_PREMIUM,
    (MarketSaturation.LOW, "high"):     VisualStyle.BOLD_VIBRANT,
    # Medium saturation – stand out without alienating
    (MarketSaturation.MEDIUM, "low"):   VisualStyle.SOFT_PREMIUM,
    (MarketSaturation.MEDIUM, "mid"):   VisualStyle.ELEGANT,
    (MarketSaturation.MEDIUM, "high"):  VisualStyle.BOLD_VIBRANT,
    # High saturation – differentiate strongly
    (MarketSaturation.HIGH, "low"):     VisualStyle.PLAYFUL,
    (MarketSaturation.HIGH, "mid"):     VisualStyle.HIGH_ENERGY,
    (MarketSaturation.HIGH, "high"):    VisualStyle.BOLD_VIBRANT,
    # Very high saturation – maximum differentiation
    (MarketSaturation.VERY_HIGH, "low"):  VisualStyle.HIGH_ENERGY,
    (MarketSaturation.VERY_HIGH, "mid"):  VisualStyle.BOLD_VIBRANT,
    (MarketSaturation.VERY_HIGH, "high"): VisualStyle.BOLD_VIBRANT,
}


def resolve_visual_style(
    saturation: MarketSaturation,
    competitive_edge: float,
) -> VisualStyle:
    bucket = "low" if competitive_edge < 40 else ("mid" if competitive_edge < 70 else "high")
    return VISUAL_STYLE_MATRIX.get(
        (saturation, bucket),
        VisualStyle.SOFT_PREMIUM,
    )


# ────────────────────────────────────────────────────────────
#  Campaign Goal → Message angle priority ordering
# ────────────────────────────────────────────────────────────

GOAL_ANGLE_PRIORITY: Dict[CampaignGoal, List[MessageAngle]] = {
    CampaignGoal.AWARENESS:     [MessageAngle.BENEFIT, MessageAngle.SOCIAL_PROOF, MessageAngle.URGENCY],
    CampaignGoal.CONSIDERATION: [MessageAngle.SOCIAL_PROOF, MessageAngle.BENEFIT, MessageAngle.URGENCY],
    CampaignGoal.CONVERSION:    [MessageAngle.URGENCY, MessageAngle.SOCIAL_PROOF, MessageAngle.BENEFIT],
    CampaignGoal.RETENTION:     [MessageAngle.BENEFIT, MessageAngle.URGENCY, MessageAngle.SOCIAL_PROOF],
}


def resolve_message_angles(goal: CampaignGoal, count: int = 3) -> List[MessageAngle]:
    """Return *count* message angles in priority order for the given goal."""
    base = GOAL_ANGLE_PRIORITY[goal]
    # Cycle if count > len(base)
    return [base[i % len(base)] for i in range(count)]


# ────────────────────────────────────────────────────────────
#  Visual Style → Pacing (BPM metaphor: seconds per scene)
# ────────────────────────────────────────────────────────────

PACING_MAP: Dict[VisualStyle, str] = {
    VisualStyle.BOLD_VIBRANT:  "fast",
    VisualStyle.HIGH_ENERGY:   "fast",
    VisualStyle.PLAYFUL:       "fast",
    VisualStyle.SOFT_PREMIUM:  "slow",
    VisualStyle.ELEGANT:       "slow",
    VisualStyle.MINIMALIST:    "medium",
}

# seconds-per-scene for each pacing label
PACING_SECONDS: Dict[str, float] = {
    "fast":   2.0,
    "medium": 3.0,
    "slow":   4.0,
}


def resolve_pacing(visual_style: VisualStyle) -> Tuple[str, float]:
    label = PACING_MAP.get(visual_style, "medium")
    return label, PACING_SECONDS[label]


# ────────────────────────────────────────────────────────────
#  Campaign Goal → CTA texts (product-specific vs brand)
# ────────────────────────────────────────────────────────────

PRODUCT_CTAS: Dict[CampaignGoal, List[str]] = {
    CampaignGoal.AWARENESS:     ["Discover Now", "Learn More", "See Details"],
    CampaignGoal.CONSIDERATION: ["Shop Now", "Compare Options", "See Why"],
    CampaignGoal.CONVERSION:    ["Buy Now", "Get Yours", "Add to Cart"],
    CampaignGoal.RETENTION:     ["Reorder Now", "Try Again", "Come Back"],
}

BRAND_CTAS: Dict[CampaignGoal, List[str]] = {
    CampaignGoal.AWARENESS:     ["Visit Site", "Explore Now", "Learn More"],
    CampaignGoal.CONSIDERATION: ["Shop Collection", "Browse All", "See Lineup"],
    CampaignGoal.CONVERSION:    ["Shop Now", "Grab the Deal", "Limited Time"],
    CampaignGoal.RETENTION:     ["Welcome Back", "New Arrivals", "Just For You"],
}


def resolve_cta(goal: CampaignGoal, is_brand: bool, variant_idx: int) -> str:
    pool = BRAND_CTAS[goal] if is_brand else PRODUCT_CTAS[goal]
    return pool[variant_idx % len(pool)]


# ────────────────────────────────────────────────────────────
#  Product tags → primary message templates
# ────────────────────────────────────────────────────────────

PRODUCT_MESSAGE_TEMPLATES: Dict[str, List[str]] = {
    "is_new":        ["Just Dropped", "New Arrival", "Fresh In"],
    "is_bestseller": ["Fan Favorite", "#1 Bestseller", "Most Loved"],
    "default":       ["Check This Out", "Spotlight", "Featured"],
}

BRAND_MESSAGE_TEMPLATES: Dict[MessageAngle, List[str]] = {
    MessageAngle.BENEFIT:      ["Premium Quality", "Designed for You", "Made Different"],
    MessageAngle.SOCIAL_PROOF: ["Loved by Thousands", "5-Star Rated", "Customer Choice"],
    MessageAngle.URGENCY:      ["Limited Collection", "Don't Miss Out", "Selling Fast"],
}


def resolve_product_primary_message(tags: dict | None, variant_idx: int) -> str:
    tags = tags or {}
    if tags.get("is_new"):
        pool = PRODUCT_MESSAGE_TEMPLATES["is_new"]
    elif tags.get("is_bestseller"):
        pool = PRODUCT_MESSAGE_TEMPLATES["is_bestseller"]
    else:
        pool = PRODUCT_MESSAGE_TEMPLATES["default"]
    return pool[variant_idx % len(pool)]


def resolve_brand_primary_message(angle: MessageAngle, variant_idx: int) -> str:
    pool = BRAND_MESSAGE_TEMPLATES[angle]
    return pool[variant_idx % len(pool)]


# ────────────────────────────────────────────────────────────
#  Product Category → Video Style preference
# ────────────────────────────────────────────────────────────

CATEGORY_VIDEO_STYLE: Dict[str, VideoStyle] = {
    "skincare":    VideoStyle.LIFESTYLE_SCENE,
    "cosmetics":   VideoStyle.LIFESTYLE_SCENE,
    "beauty":      VideoStyle.LIFESTYLE_SCENE,
    "fashion":     VideoStyle.LIFESTYLE_SCENE,
    "tech":        VideoStyle.PRODUCT_HERO,
    "electronics": VideoStyle.PRODUCT_HERO,
    "gadgets":     VideoStyle.PRODUCT_HERO,
    "food":        VideoStyle.KINETIC_TEXT,
    "beverage":    VideoStyle.KINETIC_TEXT,
    "fitness":     VideoStyle.ABSTRACT_MOTION,
    "sports":      VideoStyle.ABSTRACT_MOTION,
}


def resolve_video_style(category: str | None) -> VideoStyle:
    if not category:
        return VideoStyle.PRODUCT_HERO
    return CATEGORY_VIDEO_STYLE.get(category.lower(), VideoStyle.PRODUCT_HERO)


# ────────────────────────────────────────────────────────────
#  Number of products → General-brand layout
# ────────────────────────────────────────────────────────────

def resolve_layout_type(product_count: int, variant_idx: int) -> LayoutType:
    """Pick layout based on how many products we have."""
    if product_count == 1:
        return LayoutType.HERO_SUPPORTING
    if product_count <= 4:
        layouts = [LayoutType.SEQUENTIAL_CAROUSEL, LayoutType.GRID_LAYOUT, LayoutType.HERO_SUPPORTING]
    elif product_count <= 9:
        layouts = [LayoutType.GRID_LAYOUT, LayoutType.SEQUENTIAL_CAROUSEL, LayoutType.LIFESTYLE_MONTAGE]
    else:
        layouts = [LayoutType.SEQUENTIAL_CAROUSEL, LayoutType.LIFESTYLE_MONTAGE, LayoutType.HERO_SUPPORTING]
    return layouts[variant_idx % len(layouts)]


# ────────────────────────────────────────────────────────────
#  Sentiment → secondary message modifier
# ────────────────────────────────────────────────────────────

SENTIMENT_MODIFIERS: Dict[Sentiment, str] = {
    Sentiment.POSITIVE: "Join the movement",
    Sentiment.NEUTRAL:  "See what's new",
    Sentiment.NEGATIVE: "Time for a change",
    Sentiment.MIXED:    "Discover the difference",
}


def resolve_secondary_message(sentiment: Sentiment) -> str:
    return SENTIMENT_MODIFIERS.get(sentiment, "See what's new")
