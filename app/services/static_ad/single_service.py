"""
Service for generating a single static ad synchronously.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Dict, Optional

from app.core.config import get_settings
from app.schemas.static_ad import SingleStaticAdCreate
from app.services.static_ad.anthropic_svg_generator import AnthropicSvgGenerator
from app.services.static_ad.generator import StaticAdGenerator
from app.services.static_ad.template_registry import get_all_templates, get_template_by_id
from app.utils.file_utils import ensure_dir, file_size_mb, tmp_dir

settings = get_settings()


class SingleStaticAdService:
    def __init__(self, *, output_root: str):
        self.output_root = output_root

    async def create_single_ad(self, payload: SingleStaticAdCreate, user_id: str) -> Optional[Dict]:
        """
        Generate a single static ad from the payload.

        Returns a dict with file paths and metadata, or None on failure.
        """
        ad_id = str(uuid.uuid4())
        work_dir = tmp_dir(prefix="single_static_ad_")
        out_dir = self._output_dir(user_id, ad_id)
        ensure_dir(out_dir)

        brand_identity = payload.brand_identity.model_dump()
        brand_colors = brand_identity.get("colors", {})
        brand_name = brand_identity.get("brand_name", "")
        business_type = (brand_identity.get("business_type") or "").strip().lower()
        use_raw_images = business_type in {
            "saas",
            "software as a service",
            "software-as-a-service",
        }

        if payload.image_url:
            width = payload.width or 900
            height = payload.height or 1200
        else:
            width = payload.width or 1200
            height = payload.height or 900

        # Generate copy from user prompt (deterministic).
        copy = self._copy_from_prompt(
            prompt=payload.prompt,
            brand_identity=brand_identity,
            market_research=payload.market_research.model_dump(),
        )

        if not copy:
            return None

        image_url = payload.image_url
        style_hint = payload.style_hint or ""

        output_path = None
        if image_url:
            # Prefer Anthropic SVG when available; no background processing.
            svg_generator = AnthropicSvgGenerator(work_dir)
            output_path = svg_generator.generate(
                headline=copy["headline"],
                subheading=copy.get("subheading", ""),
                cta_text=copy.get("cta_text", ""),
                body_text=copy.get("body_text", ""),
                brand_colors=brand_colors,
                brand_name=brand_name,
                product_images=[image_url],
                product_names=[payload.product_name or "Product"],
                style_hint=style_hint,
                width=width,
                height=height,
                variant_id=1,
                ad_id=ad_id,
                ad_type="product_specific",
                use_raw_images=True,
            )

        if not output_path:
            # Fallback to template-based generator (supports no-image layouts).
            template = None
            if payload.template_id:
                template = get_template_by_id(payload.template_id)
            if not template:
                templates = get_all_templates()
                template = templates[0] if templates else None
            if not template:
                return None

            generator = StaticAdGenerator(work_dir)
            output_path = generator.generate(
                template=template,
                headline=copy["headline"],
                subheading=copy.get("subheading", ""),
                cta_text=copy.get("cta_text", ""),
                body_text=copy.get("body_text", ""),
                brand_colors=brand_colors,
                brand_name=brand_name,
                logo_url=brand_identity.get("logo_url"),
                product_image_url=None,
                image_url=image_url,
                width=width,
                height=height,
                variant_id=1,
                ad_id=ad_id,
                use_raw_images=use_raw_images or bool(image_url),
            )

        if not output_path or not os.path.exists(output_path):
            return None

        final_path = os.path.join(out_dir, os.path.basename(output_path))
        if not os.path.exists(final_path):
            import shutil
            shutil.copy2(output_path, final_path)

        # For SVGs, reuse the same file as thumbnail.
        thumb_path = final_path
        if not final_path.lower().endswith(".svg"):
            try:
                from PIL import Image as PILImage
                thumb = PILImage.open(final_path)
                thumb.thumbnail((300, 300), PILImage.LANCZOS)
                thumb_path = os.path.join(out_dir, f"thumb_{os.path.basename(final_path)}")
                thumb.save(thumb_path, quality=85)
            except Exception:
                thumb_path = final_path

        return {
            "ad_id": ad_id,
            "ad_type": "product_specific" if image_url else "general_brand",
            "status": "completed",
            "prompt": payload.prompt,
            "headline": copy["headline"],
            "subheading": copy.get("subheading"),
            "cta_text": copy.get("cta_text"),
            "body_text": copy.get("body_text"),
            "image_url": image_url,
            "file_path": final_path,
            "thumbnail_path": thumb_path,
            "file_size_mb": file_size_mb(final_path),
            "width": width,
            "height": height,
        }

    def _copy_from_prompt(
        self,
        *,
        prompt: str,
        brand_identity: Dict,
        market_research: Dict,
    ) -> Optional[Dict]:
        text = (prompt or "").strip()
        if not text:
            return None

        if settings.openai_enabled:
            try:
                from app.services.strategy.copywriter import _chat
                system = (
                    "You are a senior ad copywriter. Follow the user's prompt as the PRIMARY "
                    "creative direction. Return ONLY valid JSON with keys: "
                    "headline, subheading, cta_text, body_text. "
                    "Limits: headline<=100 chars, subheading<=200 chars, "
                    "cta_text<=40 chars, body_text<=500 chars. "
                    "No markdown, no extra keys."
                )
                user = f"""User prompt (most important): {text}
Brand: {brand_identity.get('brand_name', '')}
Brand voice: {brand_identity.get('voice', 'professional')}
Brand tone: {brand_identity.get('tone', 'confident')}
Industry: {brand_identity.get('industry', '')}
Target audience: ages {market_research.get('target_audience_age_min', 18)}-{market_research.get('target_audience_age_max', 65)}, gender {market_research.get('target_audience_gender', 'all')}
Trending keywords: {', '.join(market_research.get('trending_keywords', []) or [])}"""

                raw = _chat(system, user).strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
                data = json.loads(raw)
                return {
                    "headline": str(data.get("headline", ""))[:100],
                    "subheading": str(data.get("subheading", ""))[:200],
                    "cta_text": str(data.get("cta_text", ""))[:40],
                    "body_text": str(data.get("body_text", ""))[:500],
                }
            except Exception:
                pass

        # Fallback: simple extraction from prompt.
        parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
        headline = (parts[0] if parts else text)[:100]
        subheading = (parts[1] if len(parts) > 1 else "")[:200]
        return {
            "headline": headline,
            "subheading": subheading,
            "cta_text": "",
            "body_text": text[:500],
        }

    def _output_dir(self, user_id: str, ad_id: str) -> str:
        # Keep assets under campaign-like prefix so /assets can serve them.
        return os.path.join(self.output_root, f"campaign_{user_id}", "static_ads", "single", ad_id)
