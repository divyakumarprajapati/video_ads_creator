#!/usr/bin/env python3
"""
Seed the video_templates table with 108 curated templates.

Usage:
    python scripts/seed_templates.py

Requires DATABASE_SYNC_URL in env (or .env file).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_sync_url)

# ── Template definitions ────────────────────────────────────

VISUAL_STYLES = [
    "bold_vibrant", "soft_premium", "minimalist",
    "high_energy", "elegant", "playful",
]

VIDEO_STYLES = [
    "product_hero", "lifestyle_scene", "kinetic_text", "abstract_motion",
]

INDUSTRIES = [
    "skincare", "cosmetics", "fashion", "tech",
    "food", "fitness", "home", "general",
]

ASPECT_RATIOS = ["1:1", "9:16"]

# ── Single-product template specs ──────────────────────────

def _single_product_spec(style: str, pacing: str) -> dict:
    """Generate a template_spec for a single-product template."""
    duration_map = {"fast": (5, 15), "medium": (10, 20), "slow": (15, 30)}
    min_d, max_d = duration_map.get(pacing, (10, 20))
    return {
        "type": "single_product",
        "layers": [
            {"name": "background", "type": "solid_or_gradient", "z": 0},
            {"name": "product", "type": "image", "z": 1, "animation": style},
            {"name": "headline", "type": "text", "z": 2, "position": "top_center"},
            {"name": "subline", "type": "text", "z": 2, "position": "center"},
            {"name": "cta", "type": "text", "z": 3, "position": "bottom_center"},
        ],
        "keyframes": {
            "product_enter": 0.5,
            "headline_enter": 0.8,
            "subline_enter_ratio": 0.4,
            "cta_enter_ratio": 0.75,
        },
        "pacing": pacing,
        "min_duration": min_d,
        "max_duration": max_d,
    }


# ── Multi-product template specs ───────────────────────────

def _multi_product_spec(layout: str) -> dict:
    return {
        "type": "multi_product",
        "layout": layout,
        "layers": [
            {"name": "background", "type": "solid_or_gradient", "z": 0},
            {"name": "products", "type": "image_grid_or_sequence", "z": 1},
            {"name": "headline", "type": "text", "z": 2, "position": "top_center"},
            {"name": "cta", "type": "text", "z": 3, "position": "bottom_center"},
        ],
        "keyframes": {
            "products_enter": 0.3,
            "headline_enter": 0.5,
            "cta_enter_ratio": 0.8,
        },
        "min_duration": 10,
        "max_duration": 30,
    }


# ── Build template list ────────────────────────────────────

templates = []

# 72 single-product templates: 4 styles × 6 visual × 3 pacings
for vs in VIDEO_STYLES:
    for vis in VISUAL_STYLES:
        for pacing in ("fast", "medium", "slow"):
            idx = len(templates) + 1
            templates.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tpl-single-{idx}")),
                "name": f"{vis.replace('_', ' ').title()} {vs.replace('_', ' ').title()} – {pacing.title()}",
                "description": f"Single-product {vs.replace('_', ' ')} template with {vis.replace('_', ' ')} aesthetic, {pacing} pacing.",
                "category": vs,
                "subcategory": pacing,
                "template_spec": _single_product_spec(vs, pacing),
                "compatible_visual_styles": [vis],
                "compatible_video_styles": [vs],
                "compatible_industries": INDUSTRIES,
                "requires_product_image": True,
                "requires_background": False,
                "min_duration": _single_product_spec(vs, pacing)["min_duration"],
                "max_duration": _single_product_spec(vs, pacing)["max_duration"],
                "supported_aspect_ratios": ASPECT_RATIOS,
                "performance_score": 50.0 + (hash(f"{vs}{vis}{pacing}") % 30),
            })

# 36 multi-product templates: 4 layouts × 6 visual styles + 12 extras
LAYOUTS = ["sequential_carousel", "grid_layout", "hero_supporting", "lifestyle_montage"]

for layout in LAYOUTS:
    for vis in VISUAL_STYLES:
        idx = len(templates) + 1
        spec = _multi_product_spec(layout)
        templates.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tpl-multi-{idx}")),
            "name": f"{vis.replace('_', ' ').title()} {layout.replace('_', ' ').title()} Collection",
            "description": f"Multi-product {layout.replace('_', ' ')} with {vis.replace('_', ' ')} visual style.",
            "category": "multi_product",
            "subcategory": layout,
            "template_spec": spec,
            "compatible_visual_styles": [vis],
            "compatible_video_styles": VIDEO_STYLES,
            "compatible_industries": INDUSTRIES,
            "requires_product_image": True,
            "requires_background": False,
            "min_duration": spec["min_duration"],
            "max_duration": spec["max_duration"],
            "supported_aspect_ratios": ASPECT_RATIOS,
            "performance_score": 55.0 + (hash(f"{layout}{vis}") % 25),
        })

# 12 extras: industry-focused collection templates (4 layouts × 3 industries)
EXTRA_INDUSTRY_VARIANTS = [
    ("skincare", "soft_premium"),
    ("fashion", "elegant"),
    ("tech", "bold_vibrant"),
]

for layout in LAYOUTS:
    for industry, vis in EXTRA_INDUSTRY_VARIANTS:
        seed = f"tpl-multi-industry-{layout}-{industry}"
        tpl_id = uuid.uuid5(uuid.NAMESPACE_DNS, seed)
        spec = _multi_product_spec(layout) | {"focus_industry": industry}
        templates.append({
            "id": str(tpl_id),
            "name": f"{industry.title()} {layout.replace('_', ' ').title()} Collection",
            "description": f"Industry-focused multi-product {layout.replace('_', ' ')} for {industry}.",
            "category": "multi_product",
            "subcategory": f"{layout}_{industry}",
            "template_spec": spec,
            "compatible_visual_styles": [vis],
            "compatible_video_styles": VIDEO_STYLES,
            "compatible_industries": [industry],
            "requires_product_image": True,
            "requires_background": False,
            "min_duration": spec["min_duration"],
            "max_duration": spec["max_duration"],
            "supported_aspect_ratios": ASPECT_RATIOS,
            # Use uuid-derived int for stable scoring across runs.
            "performance_score": 60.0 + (tpl_id.int % 25),
        })

assert len(templates) >= 100, f"Only {len(templates)} templates – need ≥ 100"

# ── Insert into DB ──────────────────────────────────────────

INSERT = text("""
    INSERT INTO video_templates (
        id, name, description, category, subcategory,
        template_spec,
        compatible_visual_styles, compatible_video_styles, compatible_industries,
        requires_product_image, requires_background,
        min_duration, max_duration, supported_aspect_ratios,
        performance_score, usage_count, is_active,
        created_at, updated_at
    ) VALUES (
        :id, :name, :description, :category, :subcategory,
        CAST(:template_spec AS jsonb),
        CAST(:compatible_visual_styles AS jsonb),
        CAST(:compatible_video_styles AS jsonb),
        CAST(:compatible_industries AS jsonb),
        :requires_product_image, :requires_background,
        :min_duration, :max_duration,
        CAST(:supported_aspect_ratios AS jsonb),
        :performance_score, 0, true,
        now(), now()
    )
    ON CONFLICT (id) DO NOTHING
""")


def main():
    import json

    with engine.connect() as conn:
        for tpl in templates:
            conn.execute(INSERT, {
                **tpl,
                "template_spec": json.dumps(tpl["template_spec"]),
                "compatible_visual_styles": json.dumps(tpl["compatible_visual_styles"]),
                "compatible_video_styles": json.dumps(tpl["compatible_video_styles"]),
                "compatible_industries": json.dumps(tpl["compatible_industries"]),
                "supported_aspect_ratios": json.dumps(tpl["supported_aspect_ratios"]),
            })
        conn.commit()
    print(f"Seeded {len(templates)} templates.")


if __name__ == "__main__":
    main()
