"""
Static Ad Template Selector.

Selects the best static ad templates for a campaign based on brand identity,
market research, product information, and campaign goals.  Uses deterministic
scoring (no AI) to match templates to campaign context.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.core.enums import CampaignGoal, MessageAngle
from app.core.logging import get_logger
from app.services.static_ad.template_registry import StaticAdTemplate, get_all_templates

logger = get_logger(__name__)


# ────────────────────────────────────────────────────────────
#  Goal → preferred template categories
# ────────────────────────────────────────────────────────────

GOAL_CATEGORY_AFFINITY: Dict[CampaignGoal, List[str]] = {
    CampaignGoal.AWARENESS: [
        "hero_product_showcase",
        "lifestyle_context",
        "feature_highlight",
        "minimalist_luxury",
    ],
    CampaignGoal.CONSIDERATION: [
        "benefit_grid",
        "comparison_table",
        "feature_highlight",
        "how_it_works",
        "testimonial_trust",
    ],
    CampaignGoal.CONVERSION: [
        "urgency_countdown",
        "before_after",
        "social_proof_carousel",
        "problem_agitation_solution",
        "testimonial_trust",
    ],
    CampaignGoal.RETENTION: [
        "testimonial_trust",
        "ugc_authenticity",
        "lifestyle_context",
        "stat_impact_dashboard",
        "seasonal_themed",
    ],
}


# ────────────────────────────────────────────────────────────
#  Message Angle → preferred template categories
# ────────────────────────────────────────────────────────────

ANGLE_CATEGORY_AFFINITY: Dict[MessageAngle, List[str]] = {
    MessageAngle.BENEFIT: [
        "hero_product_showcase",
        "benefit_grid",
        "feature_highlight",
        "lifestyle_context",
    ],
    MessageAngle.SOCIAL_PROOF: [
        "testimonial_trust",
        "social_proof_carousel",
        "ugc_authenticity",
        "stat_impact_dashboard",
    ],
    MessageAngle.URGENCY: [
        "urgency_countdown",
        "before_after",
        "problem_agitation_solution",
        "seasonal_themed",
    ],
}


# ────────────────────────────────────────────────────────────
#  Industry → keyword matching for best_for
# ────────────────────────────────────────────────────────────

INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "skincare": ["beauty", "skincare", "cosmetics", "skin", "treatment", "wellness"],
    "cosmetics": ["beauty", "cosmetics", "makeup", "skincare"],
    "beauty": ["beauty", "cosmetics", "skincare", "spa"],
    "fashion": ["fashion", "apparel", "clothing", "designer", "wear"],
    "tech": ["tech", "electronics", "gadgets", "software", "saas", "platform", "app"],
    "electronics": ["electronics", "gadgets", "tech", "device"],
    "food": ["food", "beverage", "nutrition", "dining", "restaurant"],
    "beverage": ["beverage", "drink", "food"],
    "fitness": ["fitness", "sports", "athletic", "gym", "exercise", "wellness"],
    "sports": ["sports", "athletic", "fitness", "outdoor"],
    "health": ["health", "wellness", "medical", "healthcare"],
    "finance": ["financial", "finance", "investment", "insurance", "banking"],
    "education": ["education", "learning", "course", "program", "academy"],
    "travel": ["travel", "hospitality", "tourism"],
    "luxury": ["luxury", "premium", "designer", "high-end", "exclusive"],
    "saas": ["saas", "platform", "software", "b2b", "enterprise"],
    "ecommerce": ["e-commerce", "ecommerce", "shop", "retail", "product"],
}


def _score_template(
    template: StaticAdTemplate,
    *,
    goal: CampaignGoal,
    message_angle: MessageAngle,
    industry: Optional[str],
    product_category: Optional[str],
    visual_style: str,
    has_product_image: bool,
) -> float:
    """
    Score a template for how well it fits the campaign context.

    Scoring (deterministic):
      +40  campaign goal affinity (category match)
      +25  message angle affinity (category match)
      +20  industry/product keyword match in best_for
      +10  visual style alignment
      +5   bonus for templates with product image when we have one
    """
    score = 0.0

    # 1. Campaign goal category affinity
    preferred_cats = GOAL_CATEGORY_AFFINITY.get(goal, [])
    for cat in preferred_cats:
        if template.category.startswith(cat) or cat in template.category:
            score += 40
            break

    # 2. Message angle affinity
    angle_cats = ANGLE_CATEGORY_AFFINITY.get(message_angle, [])
    for cat in angle_cats:
        if template.category.startswith(cat) or cat in template.category:
            score += 25
            break

    # 3. Industry / product keyword match in best_for
    best_for_text = " ".join(template.best_for).lower()
    keywords_to_check: List[str] = []
    if industry:
        keywords_to_check.extend(INDUSTRY_KEYWORDS.get(industry.lower(), [industry.lower()]))
    if product_category:
        keywords_to_check.extend(INDUSTRY_KEYWORDS.get(product_category.lower(), [product_category.lower()]))

    if keywords_to_check:
        matches = sum(1 for kw in keywords_to_check if kw in best_for_text)
        score += min(20, matches * 5)

    # 4. Visual style alignment
    color_psych = template.color_psychology.lower()
    style_map = {
        "bold_vibrant": ["vibrant", "bold", "energy", "high contrast"],
        "soft_premium": ["professional", "clean", "soft", "neutral"],
        "minimalist": ["minimal", "sophisticated", "clean", "white"],
        "high_energy": ["dynamic", "vibrant", "energy", "bold"],
        "elegant": ["elegant", "sophisticated", "premium", "luxury"],
        "playful": ["playful", "fun", "color", "bright"],
    }
    for kw in style_map.get(visual_style, []):
        if kw in color_psych:
            score += 10
            break

    # 5. Product image bonus
    if has_product_image:
        struct = template.visual_structure
        product_keys = ["product_placement", "main_product", "product_hero", "product_image"]
        if any(k in struct for k in product_keys):
            score += 5

    return score


def select_static_ad_templates(
    *,
    goal: CampaignGoal,
    message_angles: List[MessageAngle],
    industry: Optional[str] = None,
    product_category: Optional[str] = None,
    visual_style: str = "soft_premium",
    has_product_image: bool = True,
    count: int = 3,
    exclude_ids: Optional[List[str]] = None,
) -> List[StaticAdTemplate]:
    """
    Select the top-N static ad templates that best fit the campaign context.

    Ensures diversity by picking from different categories when possible.
    """
    all_templates = get_all_templates()
    if not all_templates:
        return []

    exclude_set = set(exclude_ids or [])
    primary_angle = message_angles[0] if message_angles else MessageAngle.BENEFIT

    # Score all templates
    scored: List[Tuple[float, StaticAdTemplate]] = []
    for tpl in all_templates:
        if tpl.template_id in exclude_set:
            continue
        s = _score_template(
            tpl,
            goal=goal,
            message_angle=primary_angle,
            industry=industry,
            product_category=product_category,
            visual_style=visual_style,
            has_product_image=has_product_image,
        )
        scored.append((s, tpl))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Select with diversity: prefer different categories
    selected: List[StaticAdTemplate] = []
    used_categories: set = set()

    # First pass: pick best from each unique category
    for s, tpl in scored:
        if len(selected) >= count:
            break
        if tpl.category not in used_categories:
            selected.append(tpl)
            used_categories.add(tpl.category)

    # Second pass: fill remaining from top scores regardless of category
    if len(selected) < count:
        for s, tpl in scored:
            if len(selected) >= count:
                break
            if tpl not in selected:
                selected.append(tpl)

    return selected[:count]


def select_brand_static_templates(
    *,
    goal: CampaignGoal,
    message_angles: List[MessageAngle],
    industry: Optional[str] = None,
    visual_style: str = "soft_premium",
    product_count: int = 1,
    count: int = 3,
) -> List[StaticAdTemplate]:
    """
    Select static ad templates for general-brand (collection) ads.

    Prefers templates that showcase multiple products or brand-level messaging.
    """
    # For brand-level ads, prefer categories that work well for multi-product
    brand_preferred_categories = [
        "social_proof_carousel",
        "benefit_grid",
        "stat_impact_dashboard",
        "comparison_table",
        "how_it_works",
        "testimonial_trust",
        "feature_highlight",
    ]

    all_templates = get_all_templates()
    primary_angle = message_angles[0] if message_angles else MessageAngle.BENEFIT

    scored: List[Tuple[float, StaticAdTemplate]] = []
    for tpl in all_templates:
        s = _score_template(
            tpl,
            goal=goal,
            message_angle=primary_angle,
            industry=industry,
            product_category=None,
            visual_style=visual_style,
            has_product_image=product_count > 0,
        )
        # Extra bonus for brand-suitable categories
        for pref in brand_preferred_categories:
            if tpl.category.startswith(pref):
                s += 15
                break
        scored.append((s, tpl))

    scored.sort(key=lambda x: x[0], reverse=True)

    selected: List[StaticAdTemplate] = []
    used_categories: set = set()

    for s, tpl in scored:
        if len(selected) >= count:
            break
        if tpl.category not in used_categories:
            selected.append(tpl)
            used_categories.add(tpl.category)

    if len(selected) < count:
        for s, tpl in scored:
            if len(selected) >= count:
                break
            if tpl not in selected:
                selected.append(tpl)

    return selected[:count]
