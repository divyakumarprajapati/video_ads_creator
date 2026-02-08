"""
Static Ad Template Registry.

Provides built-in static ad template definitions and lookup helpers.
template.json remains a reference document and is not used at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

def _builtin_templates() -> List["StaticAdTemplate"]:
    """Built-in templates used for runtime generation."""
    return [
        StaticAdTemplate(
            template_id="hero_product_showcase_01",
            template_name="Hero Split Offer",
            description=(
                "Left 35-45%: brand logo top, offer chip, bold headline, short subheading, "
                "pill CTA bottom-left. Right 55-65%: single product hero on clean background. "
                "Soft gradient divider between zones."
            ),
            visual_structure={
                "product_placement": "Right side 55-65%, centered, soft shadow",
                "headline_placement": "Left side, mid stack, bold sans-serif",
                "subheading_placement": "Below headline, lighter weight",
                "cta_placement": "Bottom-left, pill button with contrast",
                "logo_placement": "Top-left corner, 80-120px width",
                "background": "Split gradient left + clean neutral right",
            },
            best_for=[
                "Product launches",
                "Limited-time offers",
                "Skincare/body care",
                "Fashion accessories",
                "DTC consumer goods",
            ],
            color_psychology="Soft gradients and brand accents to keep focus on product",
            effectiveness_factors="Clear hierarchy, strong CTA, immediate product focus",
            category=_derive_category("hero_product_showcase_01"),
        ),
        StaticAdTemplate(
            template_id="hero_product_showcase_02",
            template_name="Center Spotlight Hero",
            description=(
                "Product centered on soft card with radial glow; headline above, "
                "subheading below, CTA centered in lower third. Brand logo top-center."
            ),
            visual_structure={
                "product_placement": "Center 35-45% of canvas, on soft card",
                "headline_placement": "Top-center, bold, 36-48pt",
                "subheading_placement": "Below product, 18-24pt",
                "cta_placement": "Bottom-center, pill button",
                "logo_placement": "Top-center, moderate size",
                "background": "Radial gradient spotlight from product center",
            },
            best_for=[
                "New arrivals",
                "Premium electronics",
                "Eyewear",
                "Hero banners",
                "Flagship product drops",
            ],
            color_psychology="Spotlight gradients to elevate product prominence",
            effectiveness_factors="Central focus, premium feel, clean CTA",
            category=_derive_category("hero_product_showcase_02"),
        ),
        StaticAdTemplate(
            template_id="hero_product_showcase_03",
            template_name="Diagonal Energy Split",
            description=(
                "Dynamic diagonal split. Upper-left: logo, headline, short subheading, CTA. "
                "Lower-right: product hero with depth shadow. Accent line along diagonal."
            ),
            visual_structure={
                "split_angle": "Diagonal from top-left to bottom-right (30-35 degrees)",
                "product_placement": "Lower-right triangle, 45-55% area",
                "text_zone": "Upper-left triangle, stacked text",
                "cta_placement": "Lower-left, aligned to diagonal",
                "logo_placement": "Top-left, aligned with diagonal",
                "background": "High-contrast dual tones across diagonal",
            },
            best_for=[
                "Sports & athletic",
                "Streetwear",
                "Tech gadgets",
                "Energy products",
                "Youth fashion",
            ],
            color_psychology="Bold contrast and motion-driven layout",
            effectiveness_factors="High energy, modern aesthetic, clear hierarchy",
            category=_derive_category("hero_product_showcase_03"),
        ),
        StaticAdTemplate(
            template_id="hero_product_showcase_04",
            template_name="Floating Card Feature",
            description=(
                "Product on raised card left with soft shadow; right column for "
                "headline, 3-4 feature bullets, and CTA. Subtle radial accents."
            ),
            visual_structure={
                "product_placement": "Left 45% on rounded card with shadow",
                "headline_placement": "Right column top, bold",
                "feature_list": "Right column mid, 3-4 bullets",
                "cta_placement": "Right column bottom, pill button",
                "logo_placement": "Top-right or above headline",
                "background": "Soft radial accents with clean base",
            },
            best_for=[
                "Kits and bundles",
                "Multi-feature gadgets",
                "Subscription boxes",
                "Beauty sets",
            ],
            color_psychology="Soft contrast to keep focus on product card",
            effectiveness_factors="Feature clarity, premium depth, clean CTA",
            category=_derive_category("hero_product_showcase_04"),
        ),
        StaticAdTemplate(
            template_id="hero_product_showcase_05",
            template_name="Minimal Reflection",
            description=(
                "Product top-center with mirrored reflection below; headline in "
                "lower third and minimal CTA at bottom."
            ),
            visual_structure={
                "product_placement": "Top-center, 40-50% height",
                "reflection": "Below product, faded mirror",
                "headline_placement": "Lower third, centered",
                "cta_placement": "Bottom-center, minimal pill",
                "logo_placement": "Top-left or top-center",
                "background": "Subtle gradient, premium feel",
            },
            best_for=[
                "Luxury goods",
                "Jewelry and watches",
                "Premium cosmetics",
                "Designer accessories",
            ],
            color_psychology="Minimal palette for luxury positioning",
            effectiveness_factors="High-end aesthetic, calm composition",
            category=_derive_category("hero_product_showcase_05"),
        ),
        StaticAdTemplate(
            template_id="lifestyle_context_01",
            template_name="Lifestyle Overlay Card",
            description=(
                "Full-bleed lifestyle image with semi-transparent text card "
                "anchored bottom-left; CTA inside the card."
            ),
            visual_structure={
                "background": "Full-bleed lifestyle image",
                "text_card": "Bottom-left 40% width, translucent panel",
                "headline_placement": "Card top, bold",
                "subheading_placement": "Card mid, lighter weight",
                "cta_placement": "Card bottom, pill button",
                "logo_placement": "Top-left or card header",
            },
            best_for=[
                "Services",
                "Hospitality",
                "Apparel lifestyle",
                "Wellness brands",
            ],
            color_psychology="Warm, lifestyle-driven overlays",
            effectiveness_factors="Emotional context + clear CTA",
            category=_derive_category("lifestyle_context_01"),
        ),
        StaticAdTemplate(
            template_id="benefit_grid_triple_01",
            template_name="Feature Triad",
            description=(
                "Headline top, three feature cards mid with icon + short title, "
                "CTA bar at bottom."
            ),
            visual_structure={
                "headline_placement": "Top-center, bold",
                "grid_layout": "3 columns, equal width",
                "feature_card": "Icon top, title below, 1 line detail",
                "cta_placement": "Bottom bar, full width",
                "background": "Clean, minimal",
            },
            best_for=[
                "SaaS features",
                "Service packages",
                "Education programs",
            ],
            color_psychology="Clean contrast and structured layout",
            effectiveness_factors="Scannable benefits, strong CTA",
            category=_derive_category("benefit_grid_triple_01"),
        ),
        StaticAdTemplate(
            template_id="benefit_grid_quad_01",
            template_name="Benefit Quad",
            description=(
                "Headline top; 2x2 grid of benefits with icons and short copy; "
                "CTA centered below grid."
            ),
            visual_structure={
                "headline_placement": "Top-center",
                "grid_layout": "2x2 equal quadrants",
                "benefit_cell": "Icon top, title, short line",
                "cta_placement": "Below grid, centered",
                "background": "Light with subtle borders",
            },
            best_for=[
                "Platforms",
                "Multi-benefit products",
                "B2B services",
            ],
            color_psychology="Balanced, structured layout",
            effectiveness_factors="Comprehensive value coverage",
            category=_derive_category("benefit_grid_quad_01"),
        ),
        StaticAdTemplate(
            template_id="benefit_grid_six_pack_01",
            template_name="Six-Pack Feature Grid",
            description=(
                "Header 15% height; 3x2 grid of compact benefits; CTA footer."
            ),
            visual_structure={
                "headline_placement": "Top-left or top-center",
                "grid_layout": "3 columns x 2 rows",
                "benefit_cell": "Small icon, short title, one-line detail",
                "cta_placement": "Bottom bar",
                "background": "Neutral with light card separators",
            },
            best_for=[
                "Feature-rich SaaS",
                "Comprehensive services",
                "Membership plans",
            ],
            color_psychology="Efficient density with clarity",
            effectiveness_factors="Information-rich and scannable",
            category=_derive_category("benefit_grid_six_pack_01"),
        ),
        StaticAdTemplate(
            template_id="testimonial_trust_01",
            template_name="Single Testimonial Proof",
            description=(
                "Large quote center, customer photo top-left, star rating under "
                "quote, CTA bottom."
            ),
            visual_structure={
                "quote_placement": "Center, 28-36pt",
                "photo_placement": "Top-left circle",
                "rating_placement": "Below quote",
                "cta_placement": "Bottom-center",
                "logo_placement": "Top-right",
            },
            best_for=[
                "High-ticket services",
                "Premium products",
                "B2B offers",
            ],
            color_psychology="Trust-building neutrals and gold accents",
            effectiveness_factors="Social proof and credibility",
            category=_derive_category("testimonial_trust_01"),
        ),
        StaticAdTemplate(
            template_id="stat_impact_dashboard_01",
            template_name="Stat Impact Card",
            description=(
                "Headline top; big stat center; two mini stats below; CTA footer."
            ),
            visual_structure={
                "headline_placement": "Top-left or top-center",
                "primary_stat": "Center large numeric",
                "secondary_stats": "Row of 2-3 below",
                "cta_placement": "Bottom-right or bottom-center",
                "background": "Clean with light panels",
            },
            best_for=[
                "SaaS",
                "Finance",
                "Analytics",
                "B2B services",
            ],
            color_psychology="Professional and data-forward",
            effectiveness_factors="Proof-driven conversion",
            category=_derive_category("stat_impact_dashboard_01"),
        ),
        StaticAdTemplate(
            template_id="how_it_works_01",
            template_name="How It Works Steps",
            description=(
                "Three steps with numbered circles and short copy; hero image "
                "side or top; CTA at bottom."
            ),
            visual_structure={
                "step_layout": "Vertical stack, numbered circles",
                "hero_image": "Top or right",
                "cta_placement": "Bottom-center",
                "background": "Light with subtle separators",
            },
            best_for=[
                "Onboarding flows",
                "Service processes",
                "Education programs",
            ],
            color_psychology="Clear process and trust-building flow",
            effectiveness_factors="Simple, guided narrative",
            category=_derive_category("how_it_works_01"),
        ),
        StaticAdTemplate(
            template_id="comparison_table_01",
            template_name="Simple Comparison",
            description=(
                "Two-column comparison: left brand in color, right 'others' in gray; "
                "headline top; CTA bottom."
            ),
            visual_structure={
                "headline_placement": "Top-center",
                "table_layout": "Two columns, 4-6 rows",
                "brand_column": "Left, brand color emphasis",
                "others_column": "Right, muted",
                "cta_placement": "Bottom-center",
            },
            best_for=[
                "Competitive positioning",
                "SaaS alternatives",
                "Service differentiators",
            ],
            color_psychology="Contrast for differentiation",
            effectiveness_factors="Clear competitive edge",
            category=_derive_category("comparison_table_01"),
        ),
        StaticAdTemplate(
            template_id="feature_highlight_01",
            template_name="Feature Highlight",
            description=(
                "Product hero left; right column headline + 2-3 feature blocks; CTA."
            ),
            visual_structure={
                "product_placement": "Left 40-50%",
                "headline_placement": "Right column top",
                "feature_blocks": "Right column mid, stacked",
                "cta_placement": "Right column bottom",
                "background": "Clean with subtle accent shapes",
            },
            best_for=[
                "Gadgets",
                "Appliances",
                "SaaS tools",
            ],
            color_psychology="Balanced and informative",
            effectiveness_factors="Feature clarity and product focus",
            category=_derive_category("feature_highlight_01"),
        ),
        StaticAdTemplate(
            template_id="before_after_split_01",
            template_name="Before/After Slider",
            description=(
                "Single image area split by slider bar; left labeled BEFORE, right AFTER; "
                "headline top, CTA bottom."
            ),
            visual_structure={
                "image_area": "Central 70% height",
                "slider_bar": "Vertical center with handle",
                "labels": "Top corners on image",
                "headline_placement": "Top-center",
                "cta_placement": "Bottom-center",
            },
            best_for=[
                "Skincare",
                "Cleaning",
                "Restoration",
                "Editing apps",
            ],
            color_psychology="Realistic contrast for transformation",
            effectiveness_factors="Strong visual proof",
            category=_derive_category("before_after_split_01"),
        ),
        StaticAdTemplate(
            template_id="problem_agitation_solution_01",
            template_name="Problem-Agitate-Solution",
            description=(
                "Three stacked panels for Problem, Agitate, Solution; hero image top-right; CTA bottom."
            ),
            visual_structure={
                "panel_layout": "Three horizontal bands",
                "headline_placement": "Top-left",
                "support_text": "Center bands",
                "cta_placement": "Bottom-right",
                "background": "Light with subtle separators",
            },
            best_for=[
                "Service pain points",
                "SaaS problem solvers",
                "Health and wellness",
            ],
            color_psychology="Structured narrative and urgency",
            effectiveness_factors="Clear story arc to solution",
            category=_derive_category("problem_agitation_solution_01"),
        ),
        StaticAdTemplate(
            template_id="urgency_countdown_01",
            template_name="Urgency Countdown",
            description=(
                "Bold offer headline, timer block center, product below, CTA at bottom."
            ),
            visual_structure={
                "headline_placement": "Top-center, large",
                "timer_block": "Center, high contrast",
                "product_placement": "Lower-center",
                "cta_placement": "Bottom-center",
                "background": "Dark gradient for urgency",
            },
            best_for=[
                "Limited-time offers",
                "Flash sales",
                "Product launches",
            ],
            color_psychology="High contrast urgency palette",
            effectiveness_factors="Scarcity and action",
            category=_derive_category("urgency_countdown_01"),
        ),
        StaticAdTemplate(
            template_id="minimalist_luxury_01",
            template_name="Luxury Minimal",
            description=(
                "Centered product on minimal background; elegant serif headline; "
                "thin border frame; CTA as subtle pill."
            ),
            visual_structure={
                "product_placement": "Center 40-50%",
                "headline_placement": "Upper third, centered",
                "cta_placement": "Lower third, centered",
                "background": "Soft gradient with thin border",
            },
            best_for=[
                "Jewelry",
                "Perfume",
                "Luxury fashion",
            ],
            color_psychology="Minimal palette for premium feel",
            effectiveness_factors="High-end positioning",
            category=_derive_category("minimalist_luxury_01"),
        ),
        StaticAdTemplate(
            template_id="ugc_authenticity_01",
            template_name="UGC Authentic",
            description=(
                "Photo-style product shot with handwritten-style headline; "
                "small badge, CTA bottom-right."
            ),
            visual_structure={
                "background": "Natural photo texture",
                "headline_placement": "Top-left, casual",
                "badge": "Small trust badge",
                "cta_placement": "Bottom-right",
            },
            best_for=[
                "Gen Z brands",
                "Social-first products",
                "Trend-driven items",
            ],
            color_psychology="Natural, approachable tones",
            effectiveness_factors="Authenticity and relatability",
            category=_derive_category("ugc_authenticity_01"),
        ),
        StaticAdTemplate(
            template_id="seasonal_themed_01",
            template_name="Seasonal Themed",
            description=(
                "Seasonal background accents; product centered; headline top; CTA bottom."
            ),
            visual_structure={
                "background": "Seasonal accents and soft patterns",
                "product_placement": "Center",
                "headline_placement": "Top-center",
                "cta_placement": "Bottom-center",
            },
            best_for=[
                "Holiday promotions",
                "Seasonal drops",
                "Gift guides",
            ],
            color_psychology="Seasonal palette for relevance",
            effectiveness_factors="Timely urgency and relevance",
            category=_derive_category("seasonal_themed_01"),
        ),
    ]


@dataclass
class StaticAdTemplate:
    """Parsed static ad template definition."""

    template_id: str
    template_name: str
    description: str
    visual_structure: Dict[str, str]
    best_for: List[str]
    color_psychology: str
    effectiveness_factors: str
    category: str = ""  # derived from template_id prefix

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "description": self.description,
            "visual_structure": self.visual_structure,
            "best_for": self.best_for,
            "color_psychology": self.color_psychology,
            "effectiveness_factors": self.effectiveness_factors,
            "category": self.category,
        }


def _derive_category(template_id: str) -> str:
    """Extract category from template_id like 'hero_product_showcase_01'."""
    # Remove trailing _XX numeric suffix
    parts = template_id.rsplit("_", 1)
    if parts and parts[-1].isdigit():
        return parts[0]
    # Handle special cases like 'benefit_grid_triple_01'
    # Split on known category boundaries
    category_prefixes = [
        "hero_product_showcase",
        "benefit_grid_triple",
        "benefit_grid_quad",
        "benefit_grid_six_pack",
        "before_after_split",
        "before_after_triptych",
        "testimonial_trust",
        "urgency_countdown",
        "lifestyle_context",
        "stat_impact_dashboard",
        "minimalist_luxury",
        "problem_agitation_solution",
        "social_proof_carousel",
        "feature_highlight",
        "seasonal_themed",
        "comparison_table",
        "ugc_authenticity",
        "how_it_works",
    ]
    for prefix in category_prefixes:
        if template_id.startswith(prefix):
            return prefix
    return template_id


@lru_cache(maxsize=1)
def _load_templates() -> List[StaticAdTemplate]:
    """Load built-in templates (runtime source of truth)."""
    templates = _builtin_templates()
    logger.info("static_ad_templates_loaded", count=len(templates))
    return templates


def get_all_templates() -> List[StaticAdTemplate]:
    """Return all available static ad templates."""
    return _load_templates()


def get_template_by_id(template_id: str) -> Optional[StaticAdTemplate]:
    """Look up a single template by its ID."""
    for tpl in get_all_templates():
        if tpl.template_id == template_id:
            return tpl
    return None


def get_templates_by_category(category: str) -> List[StaticAdTemplate]:
    """Return all templates within a given category prefix."""
    return [t for t in get_all_templates() if t.category == category or t.template_id.startswith(category)]


def get_template_categories() -> List[str]:
    """Return unique category names."""
    return list(set(t.category for t in get_all_templates()))
