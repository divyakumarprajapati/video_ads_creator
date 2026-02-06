"""
AI Copywriter – OpenAI-powered ad-copy generation.

Generates product headlines, secondary messages, CTAs, and brand taglines
using GPT-5.1.  Falls back to the deterministic template lookup tables in
``decision_matrices.py`` when:
  - ``OPENAI_API_KEY`` is not set
  - the OpenAI call fails for any reason

This keeps the system functional even without an API key, while producing
significantly higher-quality, brand-aware copy when enabled.
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
class ProductCopy:
    """Generated copy for a single product variant."""
    primary_message: str
    secondary_message: str
    cta_text: str


@dataclass
class BrandCopy:
    """Generated copy for a general-brand video variant."""
    primary_message: str
    secondary_message: str
    cta_text: str


@dataclass
class CampaignCopyPlan:
    """All generated copy for the entire campaign."""
    product_copies: Dict[int, List[ProductCopy]]  # product_index → list per variant
    brand_copies: List[BrandCopy]


# ────────────────────────────────────────────────────────────
#  OpenAI client (lazy singleton)
# ────────────────────────────────────────────────────────────

_client = None


def _get_openai_client():
    global _client
    if _client is None:
        from openai import OpenAI
        kwargs: dict = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        _client = OpenAI(**kwargs)
    return _client


def _chat(system: str, user: str) -> str:
    """Single-turn chat completion.  Raises on any failure."""
    client = _get_openai_client()

    base_kwargs: dict = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    # Some models (notably GPT-5.* chat models) only support the default temperature (1),
    # and will error if any other value is provided. Avoid sending temperature in that case.
    model_name = (settings.openai_model or "").lower()
    if not model_name.startswith("gpt-5"):
        base_kwargs["temperature"] = settings.openai_temperature
    elif settings.openai_temperature == 1:
        # Explicit 1 is safe, but leaving it unset also works.
        base_kwargs["temperature"] = 1

    # Model compatibility:
    # - Some newer models reject `max_tokens` and require `max_completion_tokens`.
    # - Some older models/servers don't know about `max_completion_tokens`.
    try:
        response = client.chat.completions.create(
            **base_kwargs,
            max_completion_tokens=settings.openai_max_tokens,
        )
    except Exception as exc:
        msg = str(exc)

        # Retry without custom temperature if the model rejects it.
        if "param': 'temperature'" in msg or "param\": \"temperature\"" in msg:
            base_kwargs.pop("temperature", None)

        if (
            "max_completion_tokens" in msg
            and ("unsupported parameter" in msg.lower() or "unknown parameter" in msg.lower())
        ):
            response = client.chat.completions.create(
                **base_kwargs,
                max_tokens=settings.openai_max_tokens,
            )
        elif "Unsupported parameter: 'max_tokens'" in msg and "max_completion_tokens" in msg:
            # If we ever start with max_tokens again, retry with max_completion_tokens.
            response = client.chat.completions.create(
                **base_kwargs,
                max_completion_tokens=settings.openai_max_tokens,
            )
        elif "Unsupported value: 'temperature'" in msg and "Only the default (1) value is supported" in msg:
            response = client.chat.completions.create(
                **base_kwargs,
                max_completion_tokens=settings.openai_max_tokens,
            )
        else:
            raise

    return response.choices[0].message.content.strip()


# ────────────────────────────────────────────────────────────
#  System prompts
# ────────────────────────────────────────────────────────────

_SYSTEM_PRODUCT_COPY = """\
You are an expert social-media ad copywriter.  You write punchy, scroll-stopping
video ad text overlays.  Every line must be SHORT (≤6 words for headlines,
≤10 words for secondary, ≤4 words for CTA).

Rules:
- Never use hashtags, emojis, or quotation marks.
- Match the brand voice and tone provided.
- The primary_message is the BIG headline shown in the first 2 seconds.
- The secondary_message adds context, shown after the headline fades.
- The cta_text is the call-to-action button/overlay at the end.

Respond ONLY with valid JSON, no markdown fences."""

_SYSTEM_BRAND_COPY = """\
You are an expert social-media ad copywriter specialising in brand campaigns.
You write short, punchy text for video ad overlays that showcase an entire
product collection.

Rules:
- Never use hashtags, emojis, or quotation marks.
- Match the brand voice and tone provided.
- Headlines ≤6 words, secondary ≤10 words, CTA ≤4 words.

Respond ONLY with valid JSON, no markdown fences."""


# ────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────

async def generate_product_copy(
    *,
    product_name: str,
    product_description: str | None,
    product_category: str | None,
    product_tags: dict | None,
    brand_name: str,
    brand_voice: str,
    brand_tone: str,
    message_angle: str,
    campaign_goal: str,
    num_variants: int = 3,
) -> List[ProductCopy] | None:
    """
    Generate ad copy for all variants of a single product.

    Returns None if OpenAI is not available (caller falls back to templates).
    """
    if not settings.openai_enabled:
        return None

    tags_str = ""
    if product_tags:
        if product_tags.get("is_new"):
            tags_str = "This is a NEW product just launched."
        if product_tags.get("is_bestseller"):
            tags_str = "This is the #1 BESTSELLER."

    user_prompt = f"""\
Brand: {brand_name}
Brand voice: {brand_voice}, Brand tone: {brand_tone}
Product: {product_name}
Description: {product_description or 'N/A'}
Category: {product_category or 'General'}
{tags_str}
Campaign goal: {campaign_goal}
Message angle: {message_angle}

Generate {num_variants} different ad-copy variants for this product.
Each variant should take a slightly different angle while staying on-message.

Return a JSON array of objects with keys: primary_message, secondary_message, cta_text
Example: [{{"primary_message": "...", "secondary_message": "...", "cta_text": "..."}}]"""

    try:
        raw = _chat(_SYSTEM_PRODUCT_COPY, user_prompt)
        # Strip markdown fences if model wraps them
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)
        copies = []
        for item in data[:num_variants]:
            copies.append(ProductCopy(
                primary_message=str(item.get("primary_message", ""))[:80],
                secondary_message=str(item.get("secondary_message", ""))[:120],
                cta_text=str(item.get("cta_text", ""))[:40],
            ))
        # Pad if model returned fewer than requested
        while len(copies) < num_variants:
            copies.append(copies[-1] if copies else ProductCopy("Check This Out", "See what's new", "Shop Now"))

        # Very chatty; keep at debug so normal runs stay clean.
        logger.debug("openai_product_copy_generated", product=product_name, variants=len(copies))
        return copies

    except Exception as exc:
        logger.warning("openai_product_copy_failed", product=product_name, error=str(exc))
        return None


async def generate_brand_copy(
    *,
    brand_name: str,
    brand_voice: str,
    brand_tone: str,
    brand_industry: str | None,
    product_names: List[str],
    campaign_goal: str,
    message_angles: List[str],
    num_variants: int = 3,
) -> List[BrandCopy] | None:
    """
    Generate ad copy for general-brand / collection video variants.

    Returns None if OpenAI is not available (caller falls back to templates).
    """
    if not settings.openai_enabled:
        return None

    products_str = ", ".join(product_names[:10])
    if len(product_names) > 10:
        products_str += f" ... and {len(product_names) - 10} more"
    angles_str = ", ".join(message_angles[:num_variants])

    user_prompt = f"""\
Brand: {brand_name}
Brand voice: {brand_voice}, Brand tone: {brand_tone}
Industry: {brand_industry or 'General'}
Products in collection: {products_str}
Campaign goal: {campaign_goal}
Message angles (one per variant): {angles_str}

Generate {num_variants} brand-level ad-copy variants for a video showcasing the
entire product collection.  Each variant should match its corresponding message angle.

Return a JSON array of objects with keys: primary_message, secondary_message, cta_text
Example: [{{"primary_message": "...", "secondary_message": "...", "cta_text": "..."}}]"""

    try:
        raw = _chat(_SYSTEM_BRAND_COPY, user_prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)
        copies = []
        for item in data[:num_variants]:
            copies.append(BrandCopy(
                primary_message=str(item.get("primary_message", ""))[:80],
                secondary_message=str(item.get("secondary_message", ""))[:120],
                cta_text=str(item.get("cta_text", ""))[:40],
            ))
        while len(copies) < num_variants:
            copies.append(copies[-1] if copies else BrandCopy("Explore the Collection", "See what's new", "Visit Site"))

        # Very chatty; keep at debug so normal runs stay clean.
        logger.debug("openai_brand_copy_generated", variants=len(copies))
        return copies

    except Exception as exc:
        logger.warning("openai_brand_copy_failed", error=str(exc))
        return None
