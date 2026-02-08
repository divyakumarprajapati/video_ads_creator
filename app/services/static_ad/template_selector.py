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


# ────────────────────────────────────────────────────────────
#  Audience → template category preferences
# ────────────────────────────────────────────────────────────

# Age-group preferred aesthetics
AGE_CATEGORY_AFFINITY: Dict[str, List[str]] = {
    "gen_z": ["ugc_authenticity", "lifestyle_context", "social_proof_carousel"],
    "millennial": ["hero_product_showcase", "lifestyle_context", "feature_highlight"],
    "gen_x": ["comparison_table", "benefit_grid", "testimonial_trust"],
    "boomer": ["testimonial_trust", "stat_impact_dashboard", "how_it_works"],
}

# Sentiment → template tone
SENTIMENT_CATEGORY_AFFINITY: Dict[str, List[str]] = {
    "positive": ["hero_product_showcase", "lifestyle_context", "ugc_authenticity"],
    "neutral": ["benefit_grid", "feature_highlight", "comparison_table"],
    "negative": ["problem_agitation_solution", "before_after", "urgency_countdown"],
    "mixed": ["testimonial_trust", "social_proof_carousel", "stat_impact_dashboard"],
}

# Price tier → template style
PRICE_TIER_AFFINITY: Dict[str, List[str]] = {
    "budget": ["urgency_countdown", "comparison_table", "social_proof_carousel"],
    "mid": ["hero_product_showcase", "benefit_grid", "feature_highlight"],
    "premium": ["minimalist_luxury", "lifestyle_context", "testimonial_trust"],
    "luxury": ["minimalist_luxury", "lifestyle_context", "hero_product_showcase"],
}


def _classify_audience_age(age_min: int, age_max: int) -> str:
    mid = (age_min + age_max) / 2
    if mid < 26:
        return "gen_z"
    if mid < 41:
        return "millennial"
    if mid < 57:
        return "gen_x"
    return "boomer"


def _classify_price(price: Optional[float]) -> str:
    if price is None:
        return "mid"
    if price < 15:
        return "budget"
    if price < 75:
        return "mid"
    if price < 300:
        return "premium"
    return "luxury"


def _score_template(
    template: StaticAdTemplate,
    *,
    goal: CampaignGoal,
    message_angle: MessageAngle,
    industry: Optional[str],
    product_category: Optional[str],
    visual_style: str,
    has_product_image: bool,
    sentiment: Optional[str] = None,
    target_age_min: int = 18,
    target_age_max: int = 65,
    target_gender: str = "all",
    price: Optional[float] = None,
    trending_keywords: Optional[List[str]] = None,
) -> float:
    """
    Score a template for how well it fits the **full** campaign context.

    Scoring (deterministic, multi-dimensional):
      +40  campaign goal affinity (category match)
      +25  message angle affinity (category match)
      +20  industry/product keyword match in best_for
      +15  audience age-group category affinity
      +12  sentiment alignment
      +10  visual style alignment
      +10  price-tier template preference
      +8   trending keyword relevance in template best_for
      +5   product image template suitability
    Total possible: ~145
    """
    score = 0.0

    # 1. Campaign goal category affinity (highest weight — drives action)
    preferred_cats = GOAL_CATEGORY_AFFINITY.get(goal, [])
    for idx, cat in enumerate(preferred_cats):
        if template.category.startswith(cat) or cat in template.category:
            score += 40 - idx * 5  # First match = 40, second = 35, etc.
            break

    # 2. Message angle affinity
    angle_cats = ANGLE_CATEGORY_AFFINITY.get(message_angle, [])
    for idx, cat in enumerate(angle_cats):
        if template.category.startswith(cat) or cat in template.category:
            score += 25 - idx * 3
            break

    # 3. Industry / product keyword match in best_for
    best_for_text = " ".join(template.best_for).lower()
    desc_text = template.description.lower()
    keywords_to_check: List[str] = []
    if industry:
        keywords_to_check.extend(INDUSTRY_KEYWORDS.get(industry.lower(), [industry.lower()]))
    if product_category:
        keywords_to_check.extend(INDUSTRY_KEYWORDS.get(product_category.lower(), [product_category.lower()]))

    if keywords_to_check:
        matches = sum(1 for kw in set(keywords_to_check) if kw in best_for_text or kw in desc_text)
        score += min(20, matches * 5)

    # 4. Audience age-group affinity
    age_group = _classify_audience_age(target_age_min, target_age_max)
    age_preferred = AGE_CATEGORY_AFFINITY.get(age_group, [])
    for cat in age_preferred:
        if template.category.startswith(cat):
            score += 15
            break

    # 5. Market sentiment alignment
    if sentiment:
        sent_preferred = SENTIMENT_CATEGORY_AFFINITY.get(sentiment.lower(), [])
        for cat in sent_preferred:
            if template.category.startswith(cat):
                score += 12
                break

    # 6. Visual style alignment
    color_psych = template.color_psychology.lower()
    effectiveness = template.effectiveness_factors.lower()
    style_map = {
        "bold_vibrant": ["vibrant", "bold", "energy", "high contrast", "dynamic"],
        "soft_premium": ["professional", "clean", "soft", "neutral", "trust"],
        "minimalist": ["minimal", "sophisticated", "clean", "white", "restraint"],
        "high_energy": ["dynamic", "vibrant", "energy", "bold", "urgency"],
        "elegant": ["elegant", "sophisticated", "premium", "luxury", "artistic"],
        "playful": ["playful", "fun", "color", "bright", "community"],
    }
    style_kws = style_map.get(visual_style, [])
    style_hits = sum(1 for kw in style_kws if kw in color_psych or kw in effectiveness)
    score += min(10, style_hits * 3)

    # 7. Price-tier template preference
    price_tier = _classify_price(price)
    price_preferred = PRICE_TIER_AFFINITY.get(price_tier, [])
    for cat in price_preferred:
        if template.category.startswith(cat):
            score += 10
            break

    # 8. Trending keyword relevance
    if trending_keywords:
        trend_text = " ".join(trending_keywords).lower()
        # Check if any trending keywords appear in template best_for
        trend_hits = sum(1 for kw in trending_keywords if kw.lower() in best_for_text)
        score += min(8, trend_hits * 4)
        # Boost lifestyle templates when trending keywords suggest lifestyle
        lifestyle_signals = ["lifestyle", "wellness", "self-care", "outdoor", "travel", "fitness"]
        if any(s in trend_text for s in lifestyle_signals) and "lifestyle" in template.category:
            score += 5

    # 9. Product image template suitability
    if has_product_image:
        struct = template.visual_structure
        product_keys = ["product_placement", "main_product", "product_hero",
                        "product_image", "product_visual", "action_photo"]
        if any(k in struct for k in product_keys):
            score += 5
    else:
        # Templates that work without product images
        no_img_friendly = ["benefit_grid", "stat_impact", "testimonial_trust",
                           "social_proof", "comparison_table", "how_it_works"]
        if any(template.category.startswith(cat) for cat in no_img_friendly):
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
    sentiment: Optional[str] = None,
    target_age_min: int = 18,
    target_age_max: int = 65,
    target_gender: str = "all",
    price: Optional[float] = None,
    trending_keywords: Optional[List[str]] = None,
) -> List[StaticAdTemplate]:
    """
    Select the top-N static ad templates that best fit the full campaign context.

    Uses multi-dimensional scoring across goal, angle, audience, sentiment,
    price tier, industry, visual style, and trending keywords.

    Ensures diversity by:
    - Picking each variant's template using its own specific message angle
    - Preferring different categories across variants
    """
    all_templates = get_all_templates()
    if not all_templates:
        return []

    exclude_set = set(exclude_ids or [])

    # Score per variant using each variant's own angle for targeted selection
    selected: List[StaticAdTemplate] = []
    used_categories: set = set()
    used_ids: set = set()

    for vi in range(count):
        angle = message_angles[vi % len(message_angles)] if message_angles else MessageAngle.BENEFIT

        scored: List[Tuple[float, StaticAdTemplate]] = []
        for tpl in all_templates:
            if tpl.template_id in exclude_set or tpl.template_id in used_ids:
                continue
            s = _score_template(
                tpl,
                goal=goal,
                message_angle=angle,
                industry=industry,
                product_category=product_category,
                visual_style=visual_style,
                has_product_image=has_product_image,
                sentiment=sentiment,
                target_age_min=target_age_min,
                target_age_max=target_age_max,
                target_gender=target_gender,
                price=price,
                trending_keywords=trending_keywords,
            )
            # Diversity bonus: penalise already-used categories
            if tpl.category in used_categories:
                s -= 20
            scored.append((s, tpl))

        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            best_tpl = scored[0][1]
            selected.append(best_tpl)
            used_categories.add(best_tpl.category)
            used_ids.add(best_tpl.template_id)

    return selected[:count]


def select_brand_static_templates(
    *,
    goal: CampaignGoal,
    message_angles: List[MessageAngle],
    industry: Optional[str] = None,
    visual_style: str = "soft_premium",
    product_count: int = 1,
    count: int = 3,
    sentiment: Optional[str] = None,
    target_age_min: int = 18,
    target_age_max: int = 65,
    trending_keywords: Optional[List[str]] = None,
) -> List[StaticAdTemplate]:
    """
    Select static ad templates for general-brand (collection) ads.

    Prefers templates that showcase multiple products or brand-level messaging.
    Uses per-variant angle scoring like the product selector.
    """
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
    selected: List[StaticAdTemplate] = []
    used_categories: set = set()
    used_ids: set = set()

    for vi in range(count):
        angle = message_angles[vi % len(message_angles)] if message_angles else MessageAngle.BENEFIT

        scored: List[Tuple[float, StaticAdTemplate]] = []
        for tpl in all_templates:
            if tpl.template_id in used_ids:
                continue
            s = _score_template(
                tpl,
                goal=goal,
                message_angle=angle,
                industry=industry,
                product_category=None,
                visual_style=visual_style,
                has_product_image=product_count > 0,
                sentiment=sentiment,
                target_age_min=target_age_min,
                target_age_max=target_age_max,
                trending_keywords=trending_keywords,
            )
            for pref in brand_preferred_categories:
                if tpl.category.startswith(pref):
                    s += 15
                    break
            if tpl.category in used_categories:
                s -= 20
            scored.append((s, tpl))

        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            best = scored[0][1]
            selected.append(best)
            used_categories.add(best.category)
            used_ids.add(best.template_id)

    return selected[:count]
