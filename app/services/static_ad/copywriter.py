"""
Static Ad Copywriter – AI-powered + smart deterministic fallback.

Generates purpose-built copy for static ad images.  Unlike video overlays,
static ads can carry more text and benefit from precise targeting language
tuned to the campaign goal, audience demographics, message angle, product
attributes, and the visual template that will render them.

When ``OPENAI_API_KEY`` is set, copy is generated via GPT.
Otherwise, a sophisticated **deterministic template engine** produces
audience-aware, goal-aligned copy using the full campaign context.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class StaticAdCopy:
    """Generated copy for one static ad variant."""
    headline: str
    subheading: str
    cta_text: str
    body_text: str


# ────────────────────────────────────────────────────────────
#  Deterministic fallback templates (audience-aware, goal-aligned)
# ────────────────────────────────────────────────────────────

# Goal × Angle → headline templates.
# {product} and {brand} are replaced at runtime.
_HEADLINE_MATRIX: Dict[str, Dict[str, List[str]]] = {
    "awareness": {
        "benefit": [
            "Meet Your New Essential",
            "Introducing {product}",
            "The {product} Difference",
        ],
        "social_proof": [
            "Why Everyone Loves {product}",
            "Thousands Trust {product}",
            "{product}: The People's Choice",
        ],
        "urgency": [
            "Don't Miss {product}",
            "{product} Is Here — Finally",
            "Be First to Try {product}",
        ],
    },
    "consideration": {
        "benefit": [
            "Why {product} Outperforms",
            "{product}: Built Different",
            "The Smarter Choice: {product}",
        ],
        "social_proof": [
            "See Why Experts Choose {product}",
            "Rated #1: {product}",
            "Real Results with {product}",
        ],
        "urgency": [
            "Compare and Decide Today",
            "Your Search Ends Here",
            "Why Wait? Try {product}",
        ],
    },
    "conversion": {
        "benefit": [
            "Get {product} Now",
            "Transform with {product}",
            "{product}: Ready When You Are",
        ],
        "social_proof": [
            "Join 50,000+ Happy Customers",
            "Best-Seller for a Reason",
            "5-Star {product}",
        ],
        "urgency": [
            "Last Chance: {product}",
            "Sale Ends Tonight",
            "Limited Stock — Act Now",
        ],
    },
    "retention": {
        "benefit": [
            "Welcome Back — New {product}",
            "Your Favorite, Upgraded",
            "You Loved It — We Improved It",
        ],
        "social_proof": [
            "Our Community Keeps Growing",
            "Still #1 After All This Time",
            "Customers Keep Coming Back",
        ],
        "urgency": [
            "Exclusive Return Offer",
            "Members-Only: {product}",
            "Come Back — Save 20%",
        ],
    },
}

# Subheading by message angle (context-sensitive)
_SUBHEADING_MATRIX: Dict[str, List[str]] = {
    "benefit": [
        "Engineered for results you can see and feel",
        "Premium ingredients, proven performance",
        "Designed to exceed your expectations",
    ],
    "social_proof": [
        "Trusted by industry professionals worldwide",
        "4.9 stars from thousands of verified buyers",
        "As featured in leading publications",
    ],
    "urgency": [
        "This offer won't last — limited availability",
        "Only a few remaining at this price",
        "The clock is ticking on this exclusive deal",
    ],
}

# CTA by goal (action-specific)
_CTA_MATRIX: Dict[str, List[str]] = {
    "awareness": ["Learn More", "Discover Now", "Explore"],
    "consideration": ["See Why", "Compare Now", "View Details"],
    "conversion": ["Shop Now", "Buy Today", "Get Yours"],
    "retention": ["Reorder Now", "Welcome Back", "Claim Offer"],
}

# Audience-age tone adjusters
_AGE_TONE: Dict[str, str] = {
    "gen_z": "casual and authentic",       # 13–25
    "millennial": "aspirational and direct",  # 26–40
    "gen_x": "practical and trustworthy",   # 41–56
    "boomer": "clear and reassuring",       # 57+
}

# Price-tier qualifiers
_PRICE_QUALIFIERS: Dict[str, str] = {
    "budget": "Great value without compromise",
    "mid": "Premium quality at a fair price",
    "premium": "Crafted for those who demand the best",
    "luxury": "An experience reserved for the discerning few",
}


def _classify_age_group(age_min: int, age_max: int) -> str:
    mid = (age_min + age_max) / 2
    if mid < 26:
        return "gen_z"
    if mid < 41:
        return "millennial"
    if mid < 57:
        return "gen_x"
    return "boomer"


def _classify_price_tier(price: Optional[float], category: Optional[str]) -> str:
    if price is None:
        return "mid"
    if price < 15:
        return "budget"
    if price < 75:
        return "mid"
    if price < 300:
        return "premium"
    return "luxury"


def _build_body_text(
    *,
    product_name: str,
    product_description: Optional[str],
    product_features: Optional[Dict[str, str]],
    product_category: Optional[str],
    trending_keywords: List[str],
    price: Optional[float],
    tags: Optional[Dict[str, bool]],
    template_category: str,
) -> str:
    """
    Build rich body text from product data.

    Adapts output format to the template category:
    - benefit_grid → bullet-style sentences
    - stat_impact → comma-separated stats
    - how_it_works → step sentences
    - others → benefit-focused paragraph
    """
    parts: List[str] = []

    # Extract features into readable form
    if product_features:
        for k, v in list(product_features.items())[:5]:
            parts.append(f"{k}: {v}")

    # Add description snippets
    if product_description and len(parts) < 3:
        sentences = [s.strip() for s in product_description.split(".") if s.strip()]
        parts.extend(sentences[:3])

    # Add tag-based qualifiers
    if tags:
        if tags.get("is_new"):
            parts.append("Brand new release")
        if tags.get("is_bestseller"):
            parts.append("Our #1 bestseller")

    # Add trending keywords as contextual modifiers
    if trending_keywords:
        relevant = trending_keywords[:2]
        if relevant:
            parts.append("Trending: " + ", ".join(relevant))

    # Add price point
    if price is not None:
        tier = _classify_price_tier(price, product_category)
        parts.append(_PRICE_QUALIFIERS[tier])

    # Format based on template type
    if template_category.startswith("stat_impact"):
        # Needs comma-separated stat values
        stats = []
        if tags and tags.get("is_bestseller"):
            stats.append("50K+ Sold")
        stats.extend(["4.9/5.0", "98% Satisfaction", "24/7 Support"])
        return ", ".join(stats[:4])

    if template_category.startswith("how_it_works"):
        # Needs step-style sentences
        steps = ["Choose your product", "Complete your order", f"Enjoy {product_name}"]
        if parts:
            steps = parts[:3]
        return ". ".join(steps)

    if not parts:
        parts = [
            f"Premium {product_category or 'quality'} you can trust",
            "Designed with care and precision",
            "Satisfaction guaranteed",
        ]

    return ". ".join(parts[:6])


# ────────────────────────────────────────────────────────────
#  Deterministic generation (no AI needed)
# ────────────────────────────────────────────────────────────

def generate_static_ad_copy_deterministic(
    *,
    product_name: str,
    product_description: Optional[str] = None,
    product_category: Optional[str] = None,
    product_features: Optional[Dict[str, str]] = None,
    price: Optional[float] = None,
    tags: Optional[Dict[str, bool]] = None,
    brand_name: str,
    campaign_goal: str,
    message_angle: str,
    template_category: str,
    trending_keywords: Optional[List[str]] = None,
    target_age_min: int = 18,
    target_age_max: int = 65,
    target_gender: str = "all",
    variant_idx: int = 0,
) -> StaticAdCopy:
    """
    Generate targeted copy using deterministic templates + campaign context.

    Every dimension is considered:
    - Campaign goal (awareness/consideration/conversion/retention)
    - Message angle (benefit/social_proof/urgency)
    - Audience age → tone
    - Price tier → qualifiers
    - Product tags → emphasis
    - Template category → body text format
    - Trending keywords → relevance
    """
    goal = campaign_goal.lower()
    angle = message_angle.lower()

    # Select headline
    goal_headlines = _HEADLINE_MATRIX.get(goal, _HEADLINE_MATRIX["awareness"])
    angle_headlines = goal_headlines.get(angle, goal_headlines.get("benefit", ["Discover {product}"]))
    headline = angle_headlines[variant_idx % len(angle_headlines)]
    headline = headline.replace("{product}", product_name).replace("{brand}", brand_name)

    # Select subheading
    subs = _SUBHEADING_MATRIX.get(angle, _SUBHEADING_MATRIX["benefit"])
    subheading = subs[variant_idx % len(subs)]

    # Audience-aware tone adjustment for subheading
    age_group = _classify_age_group(target_age_min, target_age_max)
    if age_group == "gen_z" and angle == "benefit":
        subheading = subheading.replace("Engineered for", "Made for").replace("Premium", "The real deal —")
    elif age_group == "boomer" and angle == "social_proof":
        subheading = subheading.replace("worldwide", "since day one")

    # Select CTA
    ctas = _CTA_MATRIX.get(goal, _CTA_MATRIX["awareness"])
    cta = ctas[variant_idx % len(ctas)]

    # Build body text
    body = _build_body_text(
        product_name=product_name,
        product_description=product_description,
        product_features=product_features,
        product_category=product_category,
        trending_keywords=trending_keywords or [],
        price=price,
        tags=tags,
        template_category=template_category,
    )

    return StaticAdCopy(
        headline=headline,
        subheading=subheading,
        cta_text=cta,
        body_text=body,
    )


def generate_brand_static_ad_copy_deterministic(
    *,
    brand_name: str,
    brand_industry: Optional[str] = None,
    product_names: List[str],
    campaign_goal: str,
    message_angle: str,
    template_category: str,
    trending_keywords: Optional[List[str]] = None,
    target_age_min: int = 18,
    target_age_max: int = 65,
    variant_idx: int = 0,
) -> StaticAdCopy:
    """Generate brand-level static ad copy (collection / brand story)."""
    goal = campaign_goal.lower()
    angle = message_angle.lower()

    product_count = len(product_names)
    product_list = ", ".join(product_names[:3])
    if product_count > 3:
        product_list += f" + {product_count - 3} more"

    _BRAND_HEADLINES: Dict[str, Dict[str, List[str]]] = {
        "awareness": {
            "benefit": [f"The {brand_name} Collection", f"Discover {brand_name}", f"Welcome to {brand_name}"],
            "social_proof": [f"Why Thousands Choose {brand_name}", f"{brand_name}: Trusted Worldwide", f"The {brand_name} Community"],
            "urgency": [f"New from {brand_name}", f"{brand_name} Just Dropped", f"First Look: {brand_name}"],
        },
        "conversion": {
            "benefit": [f"Shop {brand_name} Today", f"The Complete {brand_name} Range", f"Everything You Need from {brand_name}"],
            "social_proof": [f"Join the {brand_name} Family", f"See Why {brand_name} Leads", f"Best-Selling {brand_name} Products"],
            "urgency": [f"{brand_name} Flash Sale", f"Limited: {brand_name} Deals", f"Final Hours: {brand_name}"],
        },
        "consideration": {
            "benefit": [f"Why {brand_name} Stands Out", f"The {brand_name} Advantage", f"Compare {brand_name}"],
            "social_proof": [f"Experts Recommend {brand_name}", f"{brand_name}: Award-Winning Quality", f"Critics' Choice: {brand_name}"],
            "urgency": [f"Don't Decide Without {brand_name}", f"See {brand_name} First", f"Explore Before You Buy"],
        },
        "retention": {
            "benefit": [f"New Arrivals at {brand_name}", f"Your {brand_name} Awaits", f"What's New at {brand_name}"],
            "social_proof": [f"Still #1: {brand_name}", f"Our Fans Speak", f"Returning Favorites at {brand_name}"],
            "urgency": [f"Members-Only {brand_name} Access", f"VIP Early Access", f"Exclusive Return Offer"],
        },
    }

    goal_h = _BRAND_HEADLINES.get(goal, _BRAND_HEADLINES["awareness"])
    angle_h = goal_h.get(angle, goal_h.get("benefit", [f"Discover {brand_name}"]))
    headline = angle_h[variant_idx % len(angle_h)]

    subs = _SUBHEADING_MATRIX.get(angle, _SUBHEADING_MATRIX["benefit"])
    subheading = subs[variant_idx % len(subs)]

    ctas = _CTA_MATRIX.get(goal, _CTA_MATRIX["awareness"])
    cta = ctas[variant_idx % len(ctas)]

    body = f"Featuring: {product_list}"
    if trending_keywords:
        body += ". Trending: " + ", ".join(trending_keywords[:3])

    return StaticAdCopy(
        headline=headline,
        subheading=subheading,
        cta_text=cta,
        body_text=body,
    )


# ────────────────────────────────────────────────────────────
#  AI generation (OpenAI)
# ────────────────────────────────────────────────────────────

_SYSTEM_STATIC_AD = """\
You are a world-class static ad copywriter for social media.  You write
punchy, scroll-stopping text for static image advertisements.

Static ads carry MORE text than video overlays.  You write:
- headline: Bold, attention-grabbing, ≤8 words.  Must communicate the core value.
- subheading: Supporting context, ≤15 words.  Reinforces the headline.
- cta_text: Clear action, ≤4 words.  Must create urgency or desire.
- body_text: 2-4 short benefit statements separated by periods.

Rules:
- NEVER use hashtags, emojis, or quotation marks.
- Match the brand voice and tone exactly.
- Tailor copy to the target audience age and gender.
- Align message to the campaign goal and message angle.
- If price is provided, incorporate value messaging appropriately.
- Make every word count — this is a static image, not a blog post.

Respond ONLY with valid JSON, no markdown fences."""


async def generate_static_ad_copy_ai(
    *,
    product_name: str,
    product_description: Optional[str] = None,
    product_category: Optional[str] = None,
    product_features: Optional[Dict[str, str]] = None,
    price: Optional[float] = None,
    tags: Optional[Dict[str, bool]] = None,
    brand_name: str,
    brand_voice: str,
    brand_tone: str,
    campaign_goal: str,
    message_angle: str,
    template_name: str,
    trending_keywords: Optional[List[str]] = None,
    target_age_min: int = 18,
    target_age_max: int = 65,
    target_gender: str = "all",
    num_variants: int = 3,
) -> Optional[List[StaticAdCopy]]:
    """
    Generate static ad copy via OpenAI.

    Returns None if OpenAI is unavailable (caller uses deterministic fallback).
    """
    if not settings.openai_enabled:
        return None

    tags_str = ""
    if tags:
        if tags.get("is_new"):
            tags_str += "This is a NEW product. "
        if tags.get("is_bestseller"):
            tags_str += "This is the #1 BESTSELLER. "

    features_str = ""
    if product_features:
        features_str = ", ".join(f"{k}: {v}" for k, v in list(product_features.items())[:5])

    trending_str = ", ".join(trending_keywords[:5]) if trending_keywords else "none"
    age_group = _classify_age_group(target_age_min, target_age_max)
    price_tier = _classify_price_tier(price, product_category)

    user_prompt = f"""\
Brand: {brand_name}
Brand voice: {brand_voice}, Brand tone: {brand_tone}
Product: {product_name}
Description: {product_description or 'N/A'}
Category: {product_category or 'General'}
Price: {'$' + str(price) if price else 'N/A'} (tier: {price_tier})
Features: {features_str or 'N/A'}
{tags_str}
Campaign goal: {campaign_goal}
Message angle: {message_angle}
Template style: {template_name}
Target audience: ages {target_age_min}-{target_age_max}, gender: {target_gender} ({age_group} generation)
Trending keywords in market: {trending_str}

Generate {num_variants} static ad copy variants.  Each must:
1. Target the {age_group} audience with appropriate tone ({_AGE_TONE.get(age_group, 'professional')})
2. Align with the {message_angle} message angle
3. Drive toward the {campaign_goal} campaign goal
4. Work visually in a {template_name} layout

Return a JSON array of objects with keys: headline, subheading, cta_text, body_text
Example: [{{"headline": "...", "subheading": "...", "cta_text": "...", "body_text": "..."}}]"""

    try:
        from app.services.strategy.copywriter import _chat
        raw = _chat(_SYSTEM_STATIC_AD, user_prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)
        copies = []
        for item in data[:num_variants]:
            copies.append(StaticAdCopy(
                headline=str(item.get("headline", ""))[:100],
                subheading=str(item.get("subheading", ""))[:200],
                cta_text=str(item.get("cta_text", ""))[:40],
                body_text=str(item.get("body_text", ""))[:500],
            ))
        while len(copies) < num_variants:
            copies.append(copies[-1] if copies else StaticAdCopy(
                "Discover More", "See what's new", "Shop Now", "",
            ))

        logger.debug("static_ad_copy_ai_generated", product=product_name, variants=len(copies))
        return copies

    except Exception as exc:
        logger.warning("static_ad_copy_ai_failed", product=product_name, error=str(exc))
        return None
