"""
Static Ad Template Registry.

Loads static ad template definitions from template.json and provides
lookup and filtering capabilities.  Each template describes a visual
layout for a static advertisement image.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Path to the template JSON file (project root)
_TEMPLATE_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "template.json",
)


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
def _load_templates_from_json() -> List[StaticAdTemplate]:
    """Load and parse all templates from template.json."""
    templates: List[StaticAdTemplate] = []

    json_path = _TEMPLATE_JSON_PATH
    if not os.path.isfile(json_path):
        logger.warning("template_json_not_found", path=json_path)
        return templates

    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        for item in data.get("ad_templates", []):
            tpl = StaticAdTemplate(
                template_id=item["template_id"],
                template_name=item["template_name"],
                description=item.get("description", ""),
                visual_structure=item.get("visual_structure", {}),
                best_for=item.get("best_for", []),
                color_psychology=item.get("color_psychology", ""),
                effectiveness_factors=item.get("effectiveness_factors", ""),
                category=_derive_category(item["template_id"]),
            )
            templates.append(tpl)

        logger.info("static_ad_templates_loaded", count=len(templates))
    except Exception as exc:
        logger.error("failed_loading_static_ad_templates", error=str(exc))

    return templates


def get_all_templates() -> List[StaticAdTemplate]:
    """Return all available static ad templates."""
    return _load_templates_from_json()


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
