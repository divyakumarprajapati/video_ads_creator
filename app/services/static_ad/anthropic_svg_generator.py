"""
Anthropic SVG Static Ad Generator.

Generates SVG ads using Anthropic Messages API.
"""

from __future__ import annotations

import base64
import hashlib
import html
import os
import re
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.image import download_image, remove_background_best, trim_transparent

logger = get_logger(__name__)
settings = get_settings()

_FILENAME_RE = re.compile(r"\b[\w\-.]+?\.(?:png|jpe?g|webp|gif|svg|bmp)\b", re.I)
_URL_RE = re.compile(r"https?://\S+", re.I)


class AnthropicSvgGenerator:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

    def generate(
        self,
        *,
        headline: str,
        subheading: str = "",
        cta_text: str = "",
        body_text: str = "",
        brand_name: str = "",
        brand_colors: Dict[str, str],
        product_images: List[str],
        product_names: Optional[List[str]] = None,
        style_hint: str = "",
        width: int = 1080,
        height: int = 1080,
        variant_id: int = 1,
        ad_id: Optional[str] = None,
        ad_type: str = "product_specific",
        use_raw_images: bool = False,
    ) -> Optional[str]:
        if not settings.anthropic_api_key:
            return None

        headline = _sanitize_display_text(headline)
        subheading = _sanitize_display_text(subheading)
        body_text = _sanitize_display_text(body_text)
        cta_text = _sanitize_display_text(cta_text)

        out_name = f"static_ad_{ad_id}.svg" if ad_id else f"static_ad_svg_v{variant_id}.svg"
        output_path = os.path.join(self.work_dir, out_name)
        if os.path.exists(output_path):
            return output_path

        tokens = self._prepare_product_tokens(
            product_images,
            product_names=product_names or [],
            use_raw_images=use_raw_images,
        )
        if not tokens:
            return None

        prompt = self._build_prompt(
            headline=headline,
            subheading=subheading,
            cta_text=cta_text,
            body_text=body_text,
            brand_name=brand_name,
            brand_colors=brand_colors,
            style_hint=style_hint,
            width=width,
            height=height,
            ad_type=ad_type,
            product_tokens=tokens,
        )

        svg_text = self._call_anthropic(prompt)
        if not svg_text:
            return None

        svg = self._extract_svg(svg_text)
        svg = self._apply_tokens(svg, tokens)
        svg = self._ensure_svg_root(svg, width, height)
        svg = self._ensure_background(svg, brand_colors.get("background", "#FFFFFF"))

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg)

        logger.info("anthropic_svg_generated", path=output_path)
        return output_path

    def generate_brand_only(
        self,
        *,
        headline: str,
        subheading: str = "",
        cta_text: str = "",
        body_text: str = "",
        brand_name: str = "",
        brand_colors: Dict[str, str],
        logo_svg: str = "",
        market_research: Optional[Dict[str, Any]] = None,
        style_hint: str = "",
        width: int = 1200,
        height: int = 900,
        variant_id: int = 1,
        ad_id: Optional[str] = None,
        ad_type: str = "general_brand",
    ) -> Optional[str]:
        if not settings.anthropic_api_key:
            return None

        headline = _sanitize_display_text(headline)
        subheading = _sanitize_display_text(subheading)
        body_text = _sanitize_display_text(body_text)
        cta_text = _sanitize_display_text(cta_text)

        out_name = f"static_ad_{ad_id}.svg" if ad_id else f"static_ad_svg_v{variant_id}.svg"
        output_path = os.path.join(self.work_dir, out_name)
        if os.path.exists(output_path):
            return output_path

        prompt = self._build_brand_only_prompt(
            headline=headline,
            subheading=subheading,
            cta_text=cta_text,
            body_text=body_text,
            brand_name=brand_name,
            brand_colors=brand_colors,
            style_hint=style_hint,
            width=width,
            height=height,
            ad_type=ad_type,
            market_research=market_research or {},
        )

        svg_text = self._call_anthropic(prompt)
        if not svg_text:
            return None

        svg = self._extract_svg(svg_text)
        svg = self._ensure_svg_root(svg, width, height)
        svg = self._ensure_background(svg, brand_colors.get("background", "#FFFFFF"))
        svg = self._ensure_logo_slot(svg, width, height)
        svg = self._inject_logo(
            svg,
            logo_svg,
            width,
            height,
            brand_name=brand_name,
            brand_colors=brand_colors,
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg)

        logger.info("anthropic_svg_generated_brand_only", path=output_path)
        return output_path

    def _call_anthropic(self, prompt: str) -> Optional[str]:
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": settings.anthropic_model,
            "max_tokens": settings.anthropic_max_tokens,
            "temperature": settings.anthropic_temperature,
            "system": (
                "You are a senior advertising designer. "
                "Return only valid SVG. No markdown, no commentary."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        max_retries = 3
        max_attempts = max_retries + 1
        attempt_timeout_s = 180

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=attempt_timeout_s) as client:
                    resp = client.post(
                        f"{settings.anthropic_base_url.rstrip('/')}/v1/messages",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                parts = data.get("content", [])
                texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
                svg_text = "\n".join([t for t in texts if t]).strip()
                if svg_text:
                    if attempt > 1:
                        logger.info(
                            "anthropic_request_recovered",
                            attempt=attempt,
                            max_attempts=max_attempts,
                        )
                    return svg_text
                raise ValueError("anthropic_empty_response")
            except Exception as exc:
                logger.warning(
                    "anthropic_request_failed",
                    error=str(exc),
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                if attempt >= max_attempts:
                    break
                logger.info(
                    "anthropic_retry_immediate",
                    attempt=attempt,
                    max_attempts=max_attempts,
                )

        return None

    def _prepare_product_tokens(
        self,
        product_images: List[str],
        *,
        product_names: List[str],
        use_raw_images: bool = False,
    ) -> Dict[str, Dict[str, str]]:
        tokens: Dict[str, Dict[str, str]] = {}
        normalize_sizes = len(product_images) > 1
        for idx, img in enumerate(product_images):
            if not img:
                continue
            name = _sanitize_product_name(
                product_names[idx] if idx < len(product_names) else "", idx=idx
            )
            data_uri, w, h = self._image_to_svg_data_uri(
                img,
                pad_to_square=normalize_sizes,
                use_raw_images=use_raw_images,
            )
            if not data_uri:
                continue
            token = f"PRODUCT_{idx + 1}"
            tokens[token] = {
                "name": name,
                "data_uri": data_uri,
                "width": str(w),
                "height": str(h),
            }
        return tokens

    def _image_to_svg_data_uri(
        self,
        path_or_url: str,
        *,
        max_size: int = 512,
        pad_to_square: bool = False,
        use_raw_images: bool = False,
    ) -> Tuple[str, int, int]:
        src = path_or_url
        if src.startswith(("http://", "https://")):
            safe = re.sub(r"[^a-zA-Z0-9]+", "_", src)[:32]
            local = os.path.join(self.work_dir, f"_dl_{safe}.png")
            if not os.path.exists(local):
                download_image(src, local)
            src = local

        if str(src).lower().endswith(".svg"):
            try:
                import cairosvg

                png_bytes = cairosvg.svg2png(url=src, output_width=max_size, output_height=max_size)
                img = Image.open(BytesIO(png_bytes)).convert("RGBA")
                if use_raw_images:
                    img.thumbnail((max_size, max_size), Image.LANCZOS)
                    if pad_to_square:
                        canvas = Image.new("RGBA", (max_size, max_size), (0, 0, 0, 0))
                        offset = ((max_size - img.width) // 2, (max_size - img.height) // 2)
                        canvas.paste(img, offset, img if img.mode == "RGBA" else None)
                        img = canvas
                else:
                    img = _prepare_product_image(img, max_size=max_size, pad_to_square=pad_to_square)
                return _raster_to_svg_data_uri(img, max_size=max_size, pad_to_square=pad_to_square)
            except Exception:
                with open(src, "rb") as f:
                    svg_bytes = f.read()
                b64 = base64.b64encode(svg_bytes).decode("utf-8")
                # Dimensions unknown; fallback to max_size square
                return f"data:image/svg+xml;base64,{b64}", max_size, max_size

        img = Image.open(src).convert("RGBA")
        if use_raw_images:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
            if pad_to_square:
                canvas = Image.new("RGBA", (max_size, max_size), (0, 0, 0, 0))
                offset = ((max_size - img.width) // 2, (max_size - img.height) // 2)
                canvas.paste(img, offset, img if img.mode == "RGBA" else None)
                img = canvas
        else:
            img = _prepare_product_image(img, max_size=max_size, pad_to_square=pad_to_square)
        return _raster_to_svg_data_uri(img, max_size=max_size, pad_to_square=pad_to_square)

    def _inline_svg_to_svg_data_uri(
        self,
        svg_text: str,
        *,
        max_size: int = 256,
    ) -> Tuple[str, int, int]:
        key = hashlib.sha1(svg_text.encode("utf-8")).hexdigest()[:10]
        svg_path = os.path.join(self.work_dir, f"_inline_logo_{key}.svg")
        if not os.path.exists(svg_path):
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_text)
        return self._image_to_svg_data_uri(svg_path, max_size=max_size, pad_to_square=False)

    def _build_prompt(
        self,
        *,
        headline: str,
        subheading: str,
        cta_text: str,
        body_text: str,
        brand_name: str,
        brand_colors: Dict[str, str],
        style_hint: str,
        width: int,
        height: int,
        ad_type: str,
        product_tokens: Dict[str, Dict[str, str]],
    ) -> str:
        primary = brand_colors.get("primary", "#1F2937")
        secondary = brand_colors.get("secondary", "#F3F4F6")
        accent = brand_colors.get("accent", primary)
        bg = brand_colors.get("background", "#FFFFFF")
        text = brand_colors.get("text", "#111827")

        product_lines = []
        for token, info in product_tokens.items():
            product_lines.append(
                f"- token: {{{{{token}}}}} | name: {info['name']} | size: {info['width']}x{info['height']}"
            )

        style_line = ""
        if style_hint:
            style_line = f"Style hint: {style_hint}\n\n"

        return (
            "Create a premium static advertisement as a single SVG.\n"
            f"Canvas: {width}x{height} (3:4 portrait), viewBox='0 0 {width} {height}'.\n"
            f"Ad type: {ad_type}.\n"
            "Use the exact placeholders for product images in <image href> attributes.\n"
            "Do not invent external URLs. Use placeholders exactly as provided.\n"
            "Placeholders:\n"
            + "\n".join(product_lines)
            + "\n\n"
            f"Brand: {brand_name}\n"
            f"Colors: primary={primary}, secondary={secondary}, accent={accent}, "
            f"background={bg}, text={text}\n"
            f"Headline (tagline): {headline or '[short, punchy tagline]'}\n"
            f"Description: {subheading or body_text or '[single supporting line]'}\n"
            f"CTA (one action): {cta_text or '[short CTA button text]'}\n\n"
            + style_line +
            "Design rules:\n"
            "- Clean, modern, high-contrast layout with minimal elements.\n"
            "- Exactly ONE CTA button. No extra badges, tags, or multiple buttons.\n"
            "- No countdowns, timers, fake urgency widgets, or made-up stats.\n"
            "- Use only the provided headline + one description line + one CTA. Do not add extra text.\n"
            "- Do not show product names, filenames, URLs, asset IDs, or placeholder tokens as text.\n"
            "- Include 1 product image for product-specific ads; 2–3 for collaboration ads.\n"
            "- For multiple product images, keep consistent visual size and balanced spacing (grid or row), no overlaps.\n"
            "- Reserve a clear image placement zone (left/right/top/bottom or centered card) and keep text in a separate region.\n"
            "- Product images should appear with transparent backgrounds; add subtle shadows if needed.\n"
            "- Use a full-bleed background in brand colors (solid or subtle gradient), not default white unless brand background is white.\n"
            "- Keep all text within safe margins (~6% padding).\n"
            "- Output only SVG (no markdown)."
        )

    def _build_brand_only_prompt(
        self,
        *,
        headline: str,
        subheading: str,
        cta_text: str,
        body_text: str,
        brand_name: str,
        brand_colors: Dict[str, str],
        style_hint: str,
        width: int,
        height: int,
        ad_type: str,
        market_research: Dict[str, Any],
    ) -> str:
        primary = brand_colors.get("primary", "#1F2937")
        secondary = brand_colors.get("secondary", "#F3F4F6")
        accent = brand_colors.get("accent", primary)
        bg = brand_colors.get("background", "#FFFFFF")
        text = brand_colors.get("text", "#111827")

        style_line = ""
        if style_hint:
            style_line = f"Style hint: {style_hint}\n\n"

        market_line = _format_market_context(market_research)
        market_block = f"{market_line}\n" if market_line else ""

        return (
            "Create a premium static advertisement as a single SVG.\n"
            f"Canvas: {width}x{height} (4:3 landscape), viewBox='0 0 {width} {height}'.\n"
            f"Ad type: {ad_type}.\n"
            f"Brand: {brand_name}\n"
            f"Colors: primary={primary}, secondary={secondary}, accent={accent}, "
            f"background={bg}, text={text}\n"
            f"Headline (tagline): {headline or '[short, punchy tagline]'}\n"
            f"Description: {subheading or body_text or '[single supporting line]'}\n"
            f"CTA (one action): {cta_text or '[short CTA button text]'}\n"
            + market_block +
            "\n"
            + style_line +
            "Design rules:\n"
            "- Clean, modern, high-contrast layout with minimal elements.\n"
            "- Exactly ONE CTA button. No extra badges, tags, or multiple buttons.\n"
            "- No product photos or mockups. Do not invent product images.\n"
            "- Use only the provided headline + one description line + one CTA. Do not add extra text.\n"
            "- Include a logo placeholder slot as a <rect> with id=\"logo-slot\" and data-logo-slot=\"true\".\n"
            "- The logo slot should be in a clean area near the top (left or right), approx 6-10% width and 6-10% height.\n"
            "- Do NOT embed any image data or base64 strings; only create the placeholder rect.\n"
            "- Use the brand name as text elsewhere; do not put logo-slot as visible text.\n"
            "- Use a full-bleed background in brand colors (solid or subtle gradient), not default white unless brand background is white.\n"
            "- Keep all text within safe margins (~6% padding).\n"
            "- Output only SVG (no markdown)."
        )

    def _ensure_logo_slot(self, svg: str, width: int, height: int) -> str:
        if re.search(r'(<[^>]+id="logo-slot"|data-logo-slot="true")', svg, flags=re.I):
            return svg

        slot_w = max(64, int(width * 0.16))
        slot_h = max(24, int(height * 0.08))
        x = int(width * 0.03)
        y = int(height * 0.06)
        rect = (
            f'<rect id="logo-slot" data-logo-slot="true" '
            f'x="{x}" y="{y}" width="{slot_w}" height="{slot_h}" '
            f'fill="none" stroke="none"/>'
        )

        svg_tag = re.search(r"<svg[^>]*>", svg, flags=re.I | re.S)
        if not svg_tag:
            return svg
        return svg.replace(svg_tag.group(0), svg_tag.group(0) + rect, 1)

    def _inject_logo(
        self,
        svg: str,
        logo_svg: str,
        width: int,
        height: int,
        *,
        brand_name: str = "",
        brand_colors: Optional[Dict[str, str]] = None,
    ) -> str:
        if not logo_svg:
            return svg

        try:
            token = self._prepare_logo_token(logo_svg)
        except Exception:
            return svg
        if not token:
            return svg

        info = token.get("LOGO") or {}
        data_uri = info.get("data_uri", "")
        if not data_uri:
            return svg

        rect_match = re.search(
            r'(<rect[^>]*(?:id="logo-slot"|data-logo-slot="true")[^>]*?/?>)',
            svg,
            flags=re.I | re.S,
        )
        if not rect_match:
            return svg

        rect_tag = rect_match.group(1)

        def _attr(tag: str, name: str, fallback: float) -> str:
            m = re.search(rf'{name}="([^"]+)"', tag)
            return m.group(1) if m else str(int(fallback))

        x_raw = _attr(rect_tag, "x", width * 0.03)
        y_raw = _attr(rect_tag, "y", height * 0.06)
        w_raw = _attr(rect_tag, "width", width * 0.16)
        h_raw = _attr(rect_tag, "height", height * 0.08)

        def _num(val: str, fallback: float) -> float:
            try:
                return float(val)
            except Exception:
                return float(fallback)

        x = _num(x_raw, width * 0.04)
        y = _num(y_raw, height * 0.06)
        w = _num(w_raw, width * 0.16)
        h = _num(h_raw, height * 0.08)

        image_tag = (
            f'<image href="{data_uri}" x="{int(x)}" y="{int(y)}" '
            f'width="{int(w)}" height="{int(h)}" '
            f'preserveAspectRatio="xMidYMid meet"/>'
        )

        # Replace the full logo slot rect element (paired first, then self-closing).
        svg, n = re.subn(
            r'<rect[^>]*(?:id="logo-slot"|data-logo-slot="true")[^>]*>.*?</rect>',
            image_tag,
            svg,
            count=1,
            flags=re.I | re.S,
        )
        if n:
            return self._ensure_brand_label(svg, brand_name, x, y, w, h, brand_colors)

        svg, _ = re.subn(
            r'<rect[^>]*(?:id="logo-slot"|data-logo-slot="true")[^>]*?/?>',
            image_tag,
            svg,
            count=1,
            flags=re.I | re.S,
        )
        return self._ensure_brand_label(svg, brand_name, x, y, w, h, brand_colors)

    def _ensure_brand_label(
        self,
        svg: str,
        brand_name: str,
        x: float,
        y: float,
        w: float,
        h: float,
        brand_colors: Optional[Dict[str, str]],
    ) -> str:
        if not brand_name:
            return svg
        if re.search(r'data-brand-name="true"', svg, flags=re.I):
            return svg

        safe_name = html.escape(str(brand_name).strip())
        if not safe_name:
            return svg

        # Remove any existing brand-name-only text nodes to avoid duplicates.
        escaped = re.escape(safe_name)
        svg = re.sub(
            rf'<text[^>]*>\s*(?:<tspan[^>]*>\s*)?{escaped}\s*(?:</tspan>)?\s*</text>',
            "",
            svg,
            flags=re.I | re.S,
        )

        text_color = "#111827"
        if brand_colors:
            text_color = brand_colors.get("text", text_color)

        gap = max(8, int(w * 0.2))
        text_x = int(x + w + gap)
        text_y = int(y + (h / 2))
        font_size = int(min(max(h * 0.6, 14), 28))

        text_tag = (
            f'<text data-brand-name="true" x="{text_x}" y="{text_y}" '
            f'font-size="{font_size}" font-weight="700" '
            f'fill="{text_color}" dominant-baseline="middle" '
            f'font-family="Inter, Arial, sans-serif">{safe_name}</text>'
        )

        svg_tag = re.search(r"<svg[^>]*>", svg, flags=re.I | re.S)
        if not svg_tag:
            return svg
        return svg.replace(svg_tag.group(0), svg_tag.group(0) + text_tag, 1)

    def _prepare_logo_token(self, logo_svg: str) -> Dict[str, Dict[str, str]]:
        src = logo_svg.strip()
        if not src:
            return {}
        try:
            if "<svg" in src:
                data_uri, w, h = self._inline_svg_to_svg_data_uri(src, max_size=256)
            else:
                data_uri, w, h = self._image_to_svg_data_uri(src, max_size=256, pad_to_square=False)
        except Exception:
            return {}
        if not data_uri:
            return {}
        return {
            "LOGO": {
                "name": "Brand Logo",
                "data_uri": data_uri,
                "width": str(w),
                "height": str(h),
            }
        }

    def _extract_svg(self, text: str) -> str:
        match = re.search(r"<svg[^>]*>.*?</svg>", text, flags=re.I | re.S)
        return match.group(0).strip() if match else text.strip()

    def _apply_tokens(self, svg: str, tokens: Dict[str, Dict[str, str]]) -> str:
        out = svg
        for token, info in tokens.items():
            out = out.replace(f"{{{{{token}}}}}", info["data_uri"])
        return out

    def _ensure_svg_root(self, svg: str, width: int, height: int) -> str:
        if "<svg" not in svg.lower():
            return (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
                f"{svg}</svg>"
            )

        def _set_attr(tag: str, attr: str, value: str) -> str:
            if re.search(rf"{attr}=\"[^\"]*\"", tag):
                return re.sub(rf"{attr}=\"[^\"]*\"", f'{attr}="{value}"', tag)
            return tag[:-1] + f' {attr}="{value}">'

        svg_tag = re.search(r"<svg[^>]*>", svg, flags=re.I | re.S)
        if not svg_tag:
            return svg

        tag = svg_tag.group(0)
        tag = _set_attr(tag, "xmlns", "http://www.w3.org/2000/svg")
        tag = _set_attr(tag, "width", str(width))
        tag = _set_attr(tag, "height", str(height))
        tag = _set_attr(tag, "viewBox", f"0 0 {width} {height}")
        return svg.replace(svg_tag.group(0), tag, 1)

    def _ensure_background(self, svg: str, bg_color: str) -> str:
        if not bg_color or 'data-background="base"' in svg:
            return svg
        svg_tag = re.search(r"<svg[^>]*>", svg, flags=re.I | re.S)
        if not svg_tag:
            return svg
        insert = f'<rect width="100%" height="100%" fill="{bg_color}" data-background="base"/>'
        return svg.replace(svg_tag.group(0), svg_tag.group(0) + insert, 1)


def _sanitize_display_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _URL_RE.sub("", text)
    cleaned = _FILENAME_RE.sub("", cleaned)
    cleaned = _strip_garbage_tokens(cleaned)
    return cleaned.strip()


def _sanitize_product_name(name: str, *, idx: int) -> str:
    cleaned = _sanitize_display_text(name)
    if not cleaned:
        return f"Product {idx + 1}"
    return cleaned


def _strip_garbage_tokens(text: str) -> str:
    tokens = text.split()
    cleaned_tokens = []
    for tok in tokens:
        raw = tok.strip(",;:()[]{}<>")
        if not raw:
            continue
        if "/" in raw or "\\" in raw:
            continue
        if _FILENAME_RE.search(raw):
            continue
        if raw.count("_") >= 2 and len(raw) >= 12:
            continue
        if raw.count(".") >= 1 and len(raw) >= 12:
            continue
        if re.match(r"^[A-Za-z0-9]{16,}$", raw):
            continue
        cleaned_tokens.append(tok)
    return " ".join(cleaned_tokens)


def _format_market_context(market_research: Optional[Dict[str, Any]]) -> str:
    if not market_research:
        return ""
    parts: List[str] = []
    saturation = market_research.get("saturation_percent")
    competitive = market_research.get("competitive_edge_percent")
    sentiment = market_research.get("sentiment")
    age_min = market_research.get("target_audience_age_min")
    age_max = market_research.get("target_audience_age_max")
    gender = market_research.get("target_audience_gender")
    trending = market_research.get("trending_keywords") or []

    if isinstance(saturation, (int, float)):
        parts.append(f"saturation {int(saturation)}%")
    if isinstance(competitive, (int, float)):
        parts.append(f"competitive edge {int(competitive)}%")
    if sentiment:
        parts.append(f"sentiment {sentiment}")
    if age_min is not None and age_max is not None:
        parts.append(f"audience {age_min}-{age_max}")
    if gender:
        parts.append(f"gender {gender}")
    if trending:
        parts.append("trends " + ", ".join(trending[:8]))

    if not parts:
        return ""
    return "Market context: " + "; ".join(parts)


def _prepare_product_image(
    img: Image.Image,
    *,
    max_size: int,
    pad_to_square: bool,
) -> Image.Image:
    try:
        img = remove_background_best(img)
    except Exception:
        pass
    try:
        img = trim_transparent(img, padding=6)
    except Exception:
        pass

    if pad_to_square:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        canvas = Image.new("RGBA", (max_size, max_size), (0, 0, 0, 0))
        offset = ((max_size - img.width) // 2, (max_size - img.height) // 2)
        canvas.paste(img, offset, img)
        return canvas

    img.thumbnail((max_size, max_size), Image.LANCZOS)
    return img


def _raster_to_svg_data_uri(
    img: Image.Image,
    *,
    max_size: int,
    pad_to_square: bool,
) -> Tuple[str, int, int]:
    w, h = img.size
    if pad_to_square:
        w = h = max_size
    bio = BytesIO()
    img.save(bio, format="PNG", optimize=True)
    b64_png = base64.b64encode(bio.getvalue()).decode("utf-8")

    # Wrap raster in SVG so we always send SVG data URIs downstream.
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<image href="data:image/png;base64,{b64_png}" '
        f'width="{w}" height="{h}" x="0" y="0" '
        f'preserveAspectRatio="xMidYMid meet"/>'
        f"</svg>"
    )
    b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64_svg}", w, h
