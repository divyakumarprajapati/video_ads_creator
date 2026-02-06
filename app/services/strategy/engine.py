"""
Strategy Engine – the brain of the system.

Takes brand identity + market research + product list and outputs a complete
**CampaignStrategy** containing per-product creative plans and general-brand
creative plans, with every decision traceable to a deterministic lookup.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    CampaignGoal,
    LayoutType,
    MessageAngle,
    Platform,
    VariantType,
    VideoStyle,
    VideoType,
    VisualStyle,
)
from app.schemas.brand import BrandIdentity, MarketResearch
from app.schemas.product import ProductInput
from app.services.strategy.decision_matrices import (
    resolve_brand_primary_message,
    resolve_cta,
    resolve_layout_type,
    resolve_message_angles,
    resolve_pacing,
    resolve_product_primary_message,
    resolve_secondary_message,
    resolve_video_style,
    resolve_visual_style,
)
from app.services.strategy.platform_specs import get_platform_spec
from app.services.strategy.template_selector import select_templates


# ── Data classes that form the strategy output ──────────────

VARIANT_TYPES = [VariantType.VARIANT_A, VariantType.VARIANT_B, VariantType.VARIANT_C]


@dataclass
class VideoVariantPlan:
    """Blueprint for one video file to be generated."""
    variant_id: int
    variant_type: str
    message_angle: str
    primary_message: str
    secondary_message: str
    cta_text: str
    template_id: Optional[str] = None
    pacing: str = "medium"
    pacing_seconds: float = 3.0


@dataclass
class ProductCreativePlan:
    """Creative plan for all variants of a single product."""
    product_index: int
    product_name: str
    video_style: str
    visual_style: str
    variants: List[VideoVariantPlan] = field(default_factory=list)


@dataclass
class GeneralBrandPlan:
    """Creative plan for general-brand / collection videos."""
    layout_types: List[str] = field(default_factory=list)
    products_shown: List[str] = field(default_factory=list)  # product names
    visual_style: str = "soft_premium"
    variants: List[VideoVariantPlan] = field(default_factory=list)


@dataclass
class CampaignStrategy:
    """The complete creative strategy for an entire campaign."""
    visual_style: str
    pacing: str
    pacing_seconds: float
    message_angles: List[str]
    product_plans: List[ProductCreativePlan] = field(default_factory=list)
    brand_plan: Optional[GeneralBrandPlan] = None
    platforms: List[str] = field(default_factory=list)
    total_videos: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ── Main entry point ────────────────────────────────────────

async def generate_campaign_strategy(
    *,
    brand: BrandIdentity,
    market: MarketResearch,
    products: List[ProductInput],
    goal: CampaignGoal,
    platforms: List[Platform],
    duration: int,
    product_variants: int = 3,
    brand_variants: int = 3,
    db: Optional[AsyncSession] = None,
) -> CampaignStrategy:
    """
    Pure rule-based strategy generation.  No AI, no randomness.

    Returns a fully specified *CampaignStrategy* that the worker layer
    can execute without making any further creative decisions.
    """

    # 1. Global visual style from market position
    saturation_level = market.saturation_level
    visual_style = resolve_visual_style(saturation_level, market.competitive_edge_percent)
    pacing_label, pacing_secs = resolve_pacing(visual_style)

    # 2. Message angles (one per variant slot, cycling priority)
    angles = resolve_message_angles(goal, max(product_variants, brand_variants))

    # 3. Aspect ratios we need
    aspect_ratios = []
    for p in platforms:
        spec = get_platform_spec(p)
        if spec.aspect_ratio not in aspect_ratios:
            aspect_ratios.append(spec.aspect_ratio)

    # 4. Per-product creative plans
    product_plans: List[ProductCreativePlan] = []
    for idx, prod in enumerate(products):
        video_style = resolve_video_style(prod.product_category)
        secondary = resolve_secondary_message(market.sentiment)

        # Select templates if DB session available
        template_ids: List[str] = []
        if db is not None:
            templates = await select_templates(
                db,
                visual_style=visual_style,
                video_style=video_style,
                duration=duration,
                aspect_ratios=aspect_ratios,
                industry=brand.industry,
                limit=product_variants,
            )
            template_ids = [str(t.id) for t in templates]

        variants: List[VideoVariantPlan] = []
        for vi in range(product_variants):
            angle = angles[vi % len(angles)]
            variants.append(VideoVariantPlan(
                variant_id=vi + 1,
                variant_type=VARIANT_TYPES[vi % len(VARIANT_TYPES)].value,
                message_angle=angle.value,
                primary_message=resolve_product_primary_message(prod.tags, vi),
                secondary_message=secondary,
                cta_text=resolve_cta(goal, is_brand=False, variant_idx=vi),
                template_id=template_ids[vi] if vi < len(template_ids) else None,
                pacing=pacing_label,
                pacing_seconds=pacing_secs,
            ))

        product_plans.append(ProductCreativePlan(
            product_index=idx,
            product_name=prod.product_name,
            video_style=video_style.value,
            visual_style=visual_style.value,
            variants=variants,
        ))

    # 5. General brand plan
    product_names = [p.product_name for p in products]
    brand_variants_list: List[VideoVariantPlan] = []
    brand_template_ids: List[str] = []
    if db is not None:
        brand_templates = await select_templates(
            db,
            visual_style=visual_style,
            video_style=VideoStyle.PRODUCT_HERO,
            duration=duration,
            aspect_ratios=aspect_ratios,
            industry=brand.industry,
            limit=brand_variants,
        )
        brand_template_ids = [str(t.id) for t in brand_templates]

    for vi in range(brand_variants):
        angle = angles[vi % len(angles)]
        brand_variants_list.append(VideoVariantPlan(
            variant_id=vi + 1,
            variant_type=VARIANT_TYPES[vi % len(VARIANT_TYPES)].value,
            message_angle=angle.value,
            primary_message=resolve_brand_primary_message(angle, vi),
            secondary_message=resolve_secondary_message(market.sentiment),
            cta_text=resolve_cta(goal, is_brand=True, variant_idx=vi),
            template_id=brand_template_ids[vi] if vi < len(brand_template_ids) else None,
            pacing=pacing_label,
            pacing_seconds=pacing_secs,
        ))

    layout_types = [
        resolve_layout_type(len(products), vi).value for vi in range(brand_variants)
    ]

    brand_plan = GeneralBrandPlan(
        layout_types=layout_types,
        products_shown=product_names,
        visual_style=visual_style.value,
        variants=brand_variants_list,
    )

    total_videos = len(products) * product_variants + brand_variants

    return CampaignStrategy(
        visual_style=visual_style.value,
        pacing=pacing_label,
        pacing_seconds=pacing_secs,
        message_angles=[a.value for a in angles],
        product_plans=product_plans,
        brand_plan=brand_plan,
        platforms=[p.value for p in platforms],
        total_videos=total_videos,
    )
