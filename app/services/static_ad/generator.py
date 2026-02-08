"""
Static Ad Image Generator.

Generates professional static advertisement images using Pillow.
Each template from template.json is rendered into a polished ad image
by composing backgrounds, product images, text overlays, shapes, and
brand elements according to the template's visual_structure spec.

Supports:
- Product images provided via image_url or pre-processed composites
- Gradient and solid backgrounds using brand colors
- Headline, subheading, CTA, and body text with proper typography
- Logo placement (when logo_url is provided)
- Multiple layout variations (hero, grid, split, minimal, etc.)
"""

from __future__ import annotations

import math
import os
import textwrap
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.core.logging import get_logger
from app.services.static_ad.template_registry import StaticAdTemplate
from app.utils.image import download_image, _hex_to_rgb

logger = get_logger(__name__)

# ── Font helpers ──────────────────────────────────────────

_FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}

# Common font paths on Linux
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "arial.ttf",
    "Arial.ttf",
]

_BOLD_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a font at the given size, with caching."""
    key = (str(bold), size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    paths = _BOLD_FONT_PATHS if bold else _FONT_PATHS
    for p in paths:
        try:
            font = ImageFont.truetype(p, size)
            _FONT_CACHE[key] = font
            return font
        except (OSError, IOError):
            continue

    font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    """Calculate text size using textbbox."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Word-wrap text to fit within max_width pixels."""
    if not text:
        return []
    # Start with a reasonable character estimate
    avg_char_width = font.getlength("M") if hasattr(font, "getlength") else 12
    chars_per_line = max(10, int(max_width / max(avg_char_width, 1)))
    lines = textwrap.wrap(text, width=chars_per_line)

    # Refine: check each line actually fits
    result = []
    for line in lines:
        dummy_img = Image.new("RGB", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        w, _ = _text_size(dummy_draw, line, font)
        if w > max_width and len(line) > 5:
            # Re-wrap with fewer characters
            sub_lines = textwrap.wrap(line, width=max(5, chars_per_line - 5))
            result.extend(sub_lines)
        else:
            result.append(line)
    return result


# ── Color helpers ─────────────────────────────────────────

def _parse_color(color_str: str) -> Tuple[int, int, int]:
    """Parse hex color string to RGB tuple."""
    try:
        return _hex_to_rgb(color_str)
    except (ValueError, IndexError):
        return (0, 0, 0)


def _luminance(r: int, g: int, b: int) -> float:
    """Relative luminance of an RGB color."""
    return 0.299 * r + 0.587 * g + 0.114 * b


def _contrast_color(bg_color: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Choose black or white text for best readability on bg_color."""
    if _luminance(*bg_color) > 128:
        return (20, 20, 20)
    return (255, 255, 255)


def _darken(color: Tuple[int, int, int], factor: float = 0.7) -> Tuple[int, int, int]:
    """Darken a color by a factor."""
    return tuple(max(0, int(c * factor)) for c in color)  # type: ignore[return-value]


def _lighten(color: Tuple[int, int, int], factor: float = 0.3) -> Tuple[int, int, int]:
    """Lighten a color by a factor."""
    return tuple(min(255, int(c + (255 - c) * factor)) for c in color)  # type: ignore[return-value]


def _with_alpha(color: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int, int]:
    """Add alpha channel to RGB color."""
    return (color[0], color[1], color[2], alpha)


# ── Drawing helpers ───────────────────────────────────────

def _draw_gradient_rect(
    img: Image.Image,
    xy: Tuple[int, int, int, int],
    color_top: Tuple[int, int, int],
    color_bottom: Tuple[int, int, int],
    direction: str = "vertical",
) -> None:
    """Draw a gradient-filled rectangle."""
    x1, y1, x2, y2 = xy
    draw = ImageDraw.Draw(img)
    if direction == "vertical":
        for y in range(y1, y2):
            ratio = (y - y1) / max(1, y2 - y1)
            r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
            g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
            b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
            draw.line([(x1, y), (x2, y)], fill=(r, g, b))
    else:
        for x in range(x1, x2):
            ratio = (x - x1) / max(1, x2 - x1)
            r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
            g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
            b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
            draw.line([(x, y1), (x, y2)], fill=(r, g, b))


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int, int, int],
    fill: Any,
    radius: int = 12,
) -> None:
    """Draw a rounded rectangle."""
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
    except AttributeError:
        # Fallback for older Pillow versions
        draw.rectangle(xy, fill=fill)


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    color: Tuple[int, ...],
    max_width: int,
    align: str = "left",
    line_spacing: int = 8,
) -> int:
    """Draw wrapped text and return total height used."""
    lines = _wrap_text(text, font, max_width)
    x, y = position
    total_height = 0
    for line in lines:
        w, h = _text_size(draw, line, font)
        if align == "center":
            draw.text((x + (max_width - w) // 2, y), line, fill=color, font=font)
        elif align == "right":
            draw.text((x + max_width - w, y), line, fill=color, font=font)
        else:
            draw.text((x, y), line, fill=color, font=font)
        y += h + line_spacing
        total_height += h + line_spacing
    return total_height


def _load_and_fit_image(
    path_or_url: str,
    work_dir: str,
    target_size: Tuple[int, int],
    name: str = "img",
) -> Optional[Image.Image]:
    """Load an image from path or URL and resize to fit target_size."""
    try:
        if path_or_url.startswith(("http://", "https://")):
            dest = os.path.join(work_dir, f"_dl_{name}.png")
            if not os.path.exists(dest):
                download_image(path_or_url, dest)
            img = Image.open(dest)
        else:
            img = Image.open(path_or_url)

        img = img.convert("RGBA")
        img.thumbnail(target_size, Image.LANCZOS)
        return img
    except Exception as exc:
        logger.warning("image_load_failed", error=str(exc), source=path_or_url[:80])
        return None


def _add_drop_shadow(
    img: Image.Image,
    offset: Tuple[int, int] = (8, 8),
    blur_radius: int = 15,
    shadow_color: Tuple[int, int, int, int] = (0, 0, 0, 80),
) -> Image.Image:
    """Add a soft drop shadow behind a product image for depth."""
    shadow_size = (
        img.width + abs(offset[0]) + blur_radius * 2,
        img.height + abs(offset[1]) + blur_radius * 2,
    )
    shadow = Image.new("RGBA", shadow_size, (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", img.size, shadow_color)
    shadow.paste(shadow_layer, (blur_radius + max(0, offset[0]), blur_radius + max(0, offset[1])))
    try:
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
    except Exception:
        pass

    # Composite: shadow + original
    result = Image.new("RGBA", shadow_size, (0, 0, 0, 0))
    result = Image.alpha_composite(result, shadow)
    paste_x = blur_radius + max(0, -offset[0])
    paste_y = blur_radius + max(0, -offset[1])
    result.paste(img, (paste_x, paste_y), img if img.mode == "RGBA" else None)
    return result


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    position: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, ...],
    shadow_color: Tuple[int, ...] = (0, 0, 0, 60),
    shadow_offset: int = 2,
) -> None:
    """Draw text with a subtle shadow for readability over images."""
    x, y = position
    # Shadow
    draw.text((x + shadow_offset, y + shadow_offset), text,
              fill=shadow_color[:3], font=font)
    # Main text
    draw.text((x, y), text, fill=fill, font=font)


def _draw_radial_gradient(
    img: Image.Image,
    center: Tuple[int, int],
    radius: int,
    color_center: Tuple[int, int, int],
    color_edge: Tuple[int, int, int],
) -> None:
    """Draw a radial gradient emanating from center."""
    for y in range(max(0, center[1] - radius), min(img.height, center[1] + radius)):
        for x in range(max(0, center[0] - radius), min(img.width, center[0] + radius)):
            dist = math.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)
            if dist > radius:
                continue
            ratio = dist / radius
            r = int(color_center[0] + (color_edge[0] - color_center[0]) * ratio)
            g = int(color_center[1] + (color_edge[1] - color_center[1]) * ratio)
            b = int(color_center[2] + (color_edge[2] - color_center[2]) * ratio)
            img.putpixel((x, y), (r, g, b))


def _apply_subtle_texture(img: Image.Image, intensity: float = 0.03) -> Image.Image:
    """Add subtle noise texture for a premium printed feel."""
    import random
    pixels = img.load()
    w, h = img.size
    noise_range = int(255 * intensity)
    for y in range(0, h, 2):  # Skip every other pixel for performance
        for x in range(0, w, 2):
            try:
                r, g, b = pixels[x, y][:3]
                n = random.randint(-noise_range, noise_range)
                pixels[x, y] = (
                    max(0, min(255, r + n)),
                    max(0, min(255, g + n)),
                    max(0, min(255, b + n)),
                )
            except (IndexError, TypeError):
                pass
    return img


# ────────────────────────────────────────────────────────────
#  Static Ad Generator
# ────────────────────────────────────────────────────────────

class StaticAdGenerator:
    """
    Generates professional static ad images based on template definitions.

    The generator reads the template's visual_structure and description
    to compose a layout-appropriate advertisement image using brand colors,
    product images, and messaging text.
    """

    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

    def generate(
        self,
        *,
        template: StaticAdTemplate,
        headline: str,
        subheading: str = "",
        cta_text: str = "",
        body_text: str = "",
        brand_colors: Dict[str, str],
        brand_name: str = "",
        logo_url: Optional[str] = None,
        product_image_url: Optional[str] = None,
        image_url: Optional[str] = None,
        width: int = 1080,
        height: int = 1080,
        variant_id: int = 1,
    ) -> str:
        """
        Generate a static ad image.

        Parameters
        ----------
        template : StaticAdTemplate
            The template definition to use.
        headline : str
            Primary headline text.
        subheading : str
            Secondary text.
        cta_text : str
            Call-to-action text.
        body_text : str
            Optional body / benefit text.
        brand_colors : dict
            Brand color dict with keys: primary, secondary, accent, background, text.
        brand_name : str
            Brand name for logo/text placement.
        logo_url : str, optional
            URL to the brand logo image.
        product_image_url : str, optional
            URL to the product image.
        image_url : str, optional
            User-provided image URL (takes priority over product_image_url).
        width : int
            Output image width in pixels.
        height : int
            Output image height in pixels.
        variant_id : int
            Variant number for output filename.

        Returns
        -------
        str
            Path to the generated PNG image file.
        """
        out_name = f"static_ad_v{variant_id}_{template.template_id}.png"
        output_path = os.path.join(self.work_dir, out_name)
        if os.path.exists(output_path):
            return output_path

        # Resolve the image to use (image_url takes priority)
        img_source = image_url or product_image_url

        # Parse brand colors
        primary = _parse_color(brand_colors.get("primary", "#2E8B57"))
        secondary = _parse_color(brand_colors.get("secondary", "#F0F8FF"))
        accent = _parse_color(brand_colors.get("accent", "") or brand_colors.get("primary", "#FF6B35"))
        bg_color = _parse_color(brand_colors.get("background", "#FFFFFF"))
        text_color = _parse_color(brand_colors.get("text", "#000000"))

        # Route to category-specific renderer
        category = template.category
        try:
            if category.startswith("hero_product_showcase"):
                img = self._render_hero_product(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, logo_url, img_source,
                )
            elif category.startswith("benefit_grid"):
                img = self._render_benefit_grid(
                    template, width, height, headline, subheading, cta_text, body_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, logo_url,
                )
            elif category.startswith("before_after"):
                img = self._render_before_after(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, img_source,
                )
            elif category.startswith("testimonial_trust"):
                img = self._render_testimonial(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, logo_url, img_source,
                )
            elif category.startswith("urgency_countdown"):
                img = self._render_urgency(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, img_source,
                )
            elif category.startswith("lifestyle_context"):
                img = self._render_lifestyle(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, img_source,
                )
            elif category.startswith("stat_impact_dashboard"):
                img = self._render_stat_dashboard(
                    template, width, height, headline, subheading, cta_text, body_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name,
                )
            elif category.startswith("minimalist_luxury"):
                img = self._render_minimalist(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, logo_url, img_source,
                )
            elif category.startswith("problem_agitation_solution"):
                img = self._render_pas(
                    template, width, height, headline, subheading, cta_text, body_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, img_source,
                )
            elif category.startswith("social_proof_carousel"):
                img = self._render_social_proof(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, logo_url,
                )
            elif category.startswith("feature_highlight"):
                img = self._render_feature_highlight(
                    template, width, height, headline, subheading, cta_text, body_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, img_source,
                )
            elif category.startswith("comparison_table"):
                img = self._render_comparison(
                    template, width, height, headline, subheading, cta_text, body_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name,
                )
            elif category.startswith("ugc_authenticity"):
                img = self._render_ugc(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, img_source,
                )
            elif category.startswith("seasonal_themed"):
                img = self._render_seasonal(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, img_source,
                )
            elif category.startswith("how_it_works"):
                img = self._render_how_it_works(
                    template, width, height, headline, subheading, cta_text, body_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name,
                )
            else:
                # Fallback: generic hero layout
                img = self._render_hero_product(
                    template, width, height, headline, subheading, cta_text,
                    primary, secondary, accent, bg_color, text_color,
                    brand_name, logo_url, img_source,
                )
        except Exception as exc:
            logger.error("static_ad_render_failed", template=template.template_id, error=str(exc))
            # Fallback: generate a clean branded image
            img = self._render_fallback(
                width, height, headline, cta_text,
                primary, bg_color, text_color, brand_name,
            )

        img.convert("RGB").save(output_path, quality=95)
        logger.info("static_ad_generated", template=template.template_id, variant=variant_id)
        return output_path

    # ── Hero Product Showcase ─────────────────────────────

    def _render_hero_product(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, logo_url, img_source,
    ) -> Image.Image:
        """Hero product layout: product on one side, text on the other."""
        img = Image.new("RGBA", (w, h), bg + (255,))

        # Left side: rich gradient with subtle secondary blend
        _draw_gradient_rect(img, (0, 0, int(w * 0.45), h), _darken(primary, 0.85), primary)

        # Soft transition zone between sides
        draw = ImageDraw.Draw(img)
        trans_start = int(w * 0.43)
        trans_end = int(w * 0.50)
        for x in range(trans_start, trans_end):
            ratio = (x - trans_start) / max(1, trans_end - trans_start)
            left_r, left_g, left_b = primary
            right_r, right_g, right_b = _lighten(bg, 0.05)
            r = int(left_r + (right_r - left_r) * ratio)
            g = int(left_g + (right_g - left_g) * ratio)
            b = int(left_b + (right_b - left_b) * ratio)
            draw.line([(x, 0), (x, h)], fill=(r, g, b))

        # Right side: clean background
        draw.rectangle([(trans_end, 0), (w, h)], fill=_lighten(bg, 0.05))

        # Product image with drop shadow (right 55%)
        if img_source:
            prod_img = _load_and_fit_image(img_source, self.work_dir, (int(w * 0.48), int(h * 0.70)), "hero_prod")
            if prod_img:
                prod_with_shadow = _add_drop_shadow(prod_img, offset=(6, 6), blur_radius=12)
                px = int(w * 0.50) + (int(w * 0.50) - prod_with_shadow.width) // 2
                py = (h - prod_with_shadow.height) // 2
                img.paste(prod_with_shadow, (px, py), prod_with_shadow)

        # Text on left side
        left_text_color = _contrast_color(primary)
        margin = int(w * 0.05)
        text_w = int(w * 0.38)

        # Logo or brand name at top
        y_cursor = int(h * 0.06)
        if logo_url:
            logo_img = _load_and_fit_image(logo_url, self.work_dir, (100, 40), "logo")
            if logo_img:
                img.paste(logo_img, (margin, y_cursor), logo_img if logo_img.mode == "RGBA" else None)
                y_cursor += 50
        if brand_name:
            brand_font = _get_font(20, bold=False)
            _draw_text_with_shadow(draw, (margin, y_cursor), brand_name.upper(),
                                   brand_font, _lighten(left_text_color, 0.2))
            y_cursor += 36

        # Decorative accent line
        draw.rectangle([(margin, y_cursor), (margin + 50, y_cursor + 3)], fill=accent)
        y_cursor += 24

        # Headline
        head_font = _get_font(min(48, w // 20), bold=True)
        head_h = _draw_text_block(draw, headline, (margin, y_cursor), head_font, left_text_color, text_w, "left", 8)
        y_cursor += head_h + 16

        # Subheading
        if subheading:
            sub_font = _get_font(min(24, w // 36), bold=False)
            sub_color = _lighten(left_text_color, 0.25) if _luminance(*left_text_color) < 128 else _darken(left_text_color, 0.65)
            _draw_text_block(draw, subheading, (margin, y_cursor), sub_font, sub_color, text_w, "left", 6)

        # CTA Button with shadow
        if cta:
            cta_font = _get_font(min(24, w // 38), bold=True)
            cta_w, cta_h = _text_size(draw, cta, cta_font)
            btn_w = cta_w + 52
            btn_h = cta_h + 28
            btn_x = margin
            btn_y = h - int(h * 0.10) - btn_h
            # Button shadow
            _draw_rounded_rect(draw, (btn_x + 2, btn_y + 2, btn_x + btn_w + 2, btn_y + btn_h + 2),
                               fill=_darken(accent, 0.5), radius=btn_h // 2)
            _draw_rounded_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
                               fill=accent, radius=btn_h // 2)
            draw.text((btn_x + 26, btn_y + 14), cta, fill=_contrast_color(accent), font=cta_font)

        return img.convert("RGB")

    # ── Benefit Grid ──────────────────────────────────────

    def _render_benefit_grid(
        self, template, w, h, headline, subheading, cta, body_text,
        primary, secondary, accent, bg, text_color,
        brand_name, logo_url,
    ) -> Image.Image:
        """Benefit grid: header + benefit cards + CTA footer."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)

        margin = int(w * 0.06)
        header_h = int(h * 0.18)
        footer_h = int(h * 0.14)
        grid_h = h - header_h - footer_h

        # Header gradient
        _draw_gradient_rect(img, (0, 0, w, header_h), primary, _darken(primary, 0.85))
        header_text_color = _contrast_color(primary)

        # Brand name in header
        if brand_name:
            bf = _get_font(18, bold=False)
            draw.text((margin, int(header_h * 0.15)), brand_name.upper(), fill=header_text_color, font=bf)

        # Headline
        hf = _get_font(min(40, w // 22), bold=True)
        _draw_text_block(draw, headline, (margin, int(header_h * 0.45)), hf, header_text_color, w - margin * 2, "left")

        # Benefits grid (3 columns)
        benefits = [s.strip() for s in (body_text or subheading or "").split(".") if s.strip()]
        if not benefits:
            benefits = [subheading or "Premium Quality", "Expert Crafted", "Satisfaction Guaranteed"]
        benefits = benefits[:6]  # cap at 6

        cols = 3 if len(benefits) >= 3 else max(1, len(benefits))
        rows = math.ceil(len(benefits) / cols)
        gutter = int(w * 0.03)
        cell_w = (w - margin * 2 - gutter * (cols - 1)) // cols
        cell_h = (grid_h - gutter * (rows + 1)) // max(1, rows)

        benefit_font = _get_font(min(22, w // 42), bold=True)
        desc_font = _get_font(min(16, w // 58), bold=False)

        for idx, benefit in enumerate(benefits):
            col = idx % cols
            row = idx // cols
            cx = margin + col * (cell_w + gutter)
            cy = header_h + gutter + row * (cell_h + gutter)

            # Card background
            card_bg = _lighten(bg, 0.05) if _luminance(*bg) < 200 else _darken(bg, 0.03)
            _draw_rounded_rect(draw, (cx, cy, cx + cell_w, cy + cell_h), fill=card_bg, radius=12)

            # Accent bar top of card
            draw.rectangle([(cx, cy), (cx + cell_w, cy + 4)], fill=accent)

            # Benefit number circle
            circle_r = 18
            circle_x = cx + cell_w // 2
            circle_y = cy + 30
            draw.ellipse(
                [circle_x - circle_r, circle_y - circle_r, circle_x + circle_r, circle_y + circle_r],
                fill=primary,
            )
            num_font = _get_font(18, bold=True)
            num_text = str(idx + 1)
            nw, nh = _text_size(draw, num_text, num_font)
            draw.text((circle_x - nw // 2, circle_y - nh // 2), num_text, fill=_contrast_color(primary), font=num_font)

            # Benefit text
            _draw_text_block(
                draw, benefit,
                (cx + 12, circle_y + circle_r + 16), benefit_font, text_color,
                cell_w - 24, "center", 6,
            )

        # Footer CTA bar
        draw.rectangle([(0, h - footer_h), (w, h)], fill=accent)
        if cta:
            cta_font = _get_font(min(30, w // 30), bold=True)
            cta_color = _contrast_color(accent)
            cw, ch = _text_size(draw, cta, cta_font)
            draw.text(((w - cw) // 2, h - footer_h + (footer_h - ch) // 2), cta, fill=cta_color, font=cta_font)

        return img

    # ── Before / After ────────────────────────────────────

    def _render_before_after(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, img_source,
    ) -> Image.Image:
        """Before/After split layout."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)

        # Header
        header_h = int(h * 0.12)
        hf = _get_font(min(36, w // 24), bold=True)
        _draw_text_block(draw, headline, (int(w * 0.05), int(header_h * 0.25)), hf, text_color, int(w * 0.9), "center")

        # Split area
        split_y = header_h
        split_h = int(h * 0.72)
        mid_x = w // 2

        # Before side (left) - muted/gray overlay
        draw.rectangle([(0, split_y), (mid_x - 2, split_y + split_h)], fill=_darken(secondary, 0.6))
        before_font = _get_font(min(20, w // 44), bold=True)
        draw.text((int(w * 0.05), split_y + 12), "BEFORE", fill=(180, 60, 60), font=before_font)

        # After side (right) - vibrant
        _draw_gradient_rect(img, (mid_x + 2, split_y, w, split_y + split_h), _lighten(primary, 0.4), primary)
        draw.text((mid_x + int(w * 0.05), split_y + 12), "AFTER", fill=_contrast_color(primary), font=before_font)

        # Product image on after side
        if img_source:
            prod_img = _load_and_fit_image(
                img_source, self.work_dir,
                (int(w * 0.4), int(split_h * 0.7)), "ba_prod",
            )
            if prod_img:
                px = mid_x + (w // 2 - prod_img.width) // 2
                py = split_y + (split_h - prod_img.height) // 2 + 20
                img.paste(prod_img, (px, py), prod_img if prod_img.mode == "RGBA" else None)

        # Center divider
        draw.rectangle([(mid_x - 2, split_y), (mid_x + 2, split_y + split_h)], fill=accent)

        # Subheading
        if subheading:
            sub_font = _get_font(min(22, w // 40), bold=False)
            sw, sh = _text_size(draw, subheading, sub_font)
            draw.text(((w - sw) // 2, split_y + split_h + 10), subheading, fill=text_color, font=sub_font)

        # CTA button
        if cta:
            self._draw_cta_button(draw, cta, w, h, accent, int(h * 0.90))

        return img

    # ── Testimonial Trust ─────────────────────────────────

    def _render_testimonial(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, logo_url, img_source,
    ) -> Image.Image:
        """Testimonial layout with quote and trust elements."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)

        margin = int(w * 0.08)

        # Decorative accent bar top
        draw.rectangle([(0, 0), (w, 6)], fill=primary)

        # Large quotation mark
        quote_font = _get_font(min(120, w // 8), bold=True)
        draw.text((margin, int(h * 0.08)), "\u201C", fill=_lighten(primary, 0.5), font=quote_font)

        # Quote text (headline as the testimonial)
        quote_font_text = _get_font(min(32, w // 28), bold=False)
        _draw_text_block(
            draw, f'"{headline}"',
            (margin, int(h * 0.25)), quote_font_text, text_color,
            w - margin * 2, "center", 12,
        )

        # Stars
        star_y = int(h * 0.58)
        star_font = _get_font(28, bold=False)
        stars = "\u2605" * 5
        sw, sh = _text_size(draw, stars, star_font)
        draw.text(((w - sw) // 2, star_y), stars, fill=(255, 193, 7), font=star_font)

        # Attribution line (subheading)
        if subheading:
            attr_font = _get_font(min(20, w // 44), bold=True)
            aw, ah = _text_size(draw, subheading, attr_font)
            draw.text(((w - aw) // 2, star_y + 50), subheading, fill=_darken(text_color, 0.7), font=attr_font)

        # Brand name bottom
        if brand_name:
            bf = _get_font(20, bold=True)
            bw, bh = _text_size(draw, brand_name, bf)
            draw.text(((w - bw) // 2, h - int(h * 0.18)), brand_name, fill=primary, font=bf)

        # CTA button
        if cta:
            self._draw_cta_button(draw, cta, w, h, accent, int(h * 0.88))

        return img

    # ── Urgency Countdown ─────────────────────────────────

    def _render_urgency(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, img_source,
    ) -> Image.Image:
        """Urgency/countdown layout with bold offer."""
        img = Image.new("RGB", (w, h))

        # Dark/dramatic gradient background
        _draw_gradient_rect(img, (0, 0, w, h), (30, 0, 0), (80, 0, 0))
        draw = ImageDraw.Draw(img)

        # Urgency badge
        badge_font = _get_font(min(18, w // 50), bold=True)
        badge_text = "LIMITED TIME"
        bw, bh = _text_size(draw, badge_text, badge_font)
        badge_x = w - bw - 30
        _draw_rounded_rect(draw, (badge_x - 12, 20, badge_x + bw + 12, 20 + bh + 16), fill=(220, 50, 50), radius=4)
        draw.text((badge_x, 28), badge_text, fill=(255, 255, 255), font=badge_font)

        # Large offer headline
        offer_font = _get_font(min(72, w // 12), bold=True)
        _draw_text_block(draw, headline, (int(w * 0.06), int(h * 0.12)), offer_font, (255, 255, 255), int(w * 0.88), "center")

        # Timer display
        timer_y = int(h * 0.40)
        timer_font = _get_font(min(48, w // 18), bold=True)
        timer_text = "23:59:47"
        tw, th = _text_size(draw, timer_text, timer_font)
        tx = (w - tw) // 2
        _draw_rounded_rect(draw, (tx - 20, timer_y - 10, tx + tw + 20, timer_y + th + 10), fill=(0, 0, 0, 150)[:3], radius=8)
        draw.text((tx, timer_y), timer_text, fill=(255, 220, 50), font=timer_font)

        # Product image
        if img_source:
            prod_img = _load_and_fit_image(img_source, self.work_dir, (int(w * 0.45), int(h * 0.35)), "urg_prod")
            if prod_img:
                px = (w - prod_img.width) // 2
                py = int(h * 0.52)
                img.paste(prod_img, (px, py), prod_img if prod_img.mode == "RGBA" else None)

        # CTA button (bright accent)
        if cta:
            cta_font = _get_font(min(28, w // 32), bold=True)
            cw, ch = _text_size(draw, cta, cta_font)
            btn_w = cw + 60
            btn_h = ch + 30
            btn_x = (w - btn_w) // 2
            btn_y = h - int(h * 0.10) - btn_h
            _draw_rounded_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), fill=accent, radius=btn_h // 2)
            draw.text((btn_x + 30, btn_y + 15), cta, fill=_contrast_color(accent), font=cta_font)

        return img

    # ── Lifestyle Context ─────────────────────────────────

    def _render_lifestyle(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, img_source,
    ) -> Image.Image:
        """Lifestyle integration layout."""
        img = Image.new("RGB", (w, h), bg)

        # Use image as full background if available
        if img_source:
            bg_img = _load_and_fit_image(img_source, self.work_dir, (w, h), "lifestyle_bg")
            if bg_img:
                bg_img = bg_img.convert("RGB").resize((w, h), Image.LANCZOS)
                img = bg_img.copy()

        # Dark gradient overlay from bottom
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for y in range(h // 3, h):
            alpha = int(200 * (y - h // 3) / (h - h // 3))
            overlay_draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")

        draw = ImageDraw.Draw(img)
        margin = int(w * 0.06)

        # Brand name top
        if brand_name:
            bf = _get_font(22, bold=True)
            draw.text((margin, int(h * 0.05)), brand_name, fill=(255, 255, 255), font=bf)

        # Headline (bottom third)
        hf = _get_font(min(44, w // 20), bold=True)
        _draw_text_block(draw, headline, (margin, int(h * 0.62)), hf, (255, 255, 255), w - margin * 2, "left", 10)

        # Subheading
        if subheading:
            sf = _get_font(min(24, w // 36), bold=False)
            _draw_text_block(draw, subheading, (margin, int(h * 0.78)), sf, (220, 220, 220), w - margin * 2, "left")

        # CTA card
        if cta:
            cta_font = _get_font(min(24, w // 36), bold=True)
            cw, ch = _text_size(draw, cta, cta_font)
            card_w = cw + 48
            card_h = ch + 28
            card_x = margin
            card_y = h - int(h * 0.08) - card_h
            _draw_rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h), fill=accent, radius=card_h // 2)
            draw.text((card_x + 24, card_y + 14), cta, fill=_contrast_color(accent), font=cta_font)

        return img

    # ── Stat Impact Dashboard ─────────────────────────────

    def _render_stat_dashboard(
        self, template, w, h, headline, subheading, cta, body_text,
        primary, secondary, accent, bg, text_color,
        brand_name,
    ) -> Image.Image:
        """Data-driven dashboard layout with stat cards."""
        img = Image.new("RGB", (w, h))
        _draw_gradient_rect(img, (0, 0, w, h), _darken(primary, 0.8), primary)
        draw = ImageDraw.Draw(img)
        tc = _contrast_color(primary)

        margin = int(w * 0.06)

        # Headline
        hf = _get_font(min(36, w // 24), bold=True)
        _draw_text_block(draw, headline, (margin, int(h * 0.06)), hf, tc, w - margin * 2, "center")

        # Stat cards (2x2 grid)
        stats = [s.strip() for s in (body_text or "").split(",") if s.strip()]
        if not stats:
            stats = ["10K+", "4.9/5.0", "98%", "50+"]
        stat_labels = ["Users", "Rating", "Satisfaction", "Countries"]

        card_margin = int(w * 0.08)
        gutter = int(w * 0.04)
        card_w = (w - card_margin * 2 - gutter) // 2
        card_h = (int(h * 0.55) - gutter) // 2

        stat_font = _get_font(min(48, w // 16), bold=True)
        label_font = _get_font(min(18, w // 50), bold=False)

        for idx in range(min(4, len(stats))):
            col = idx % 2
            row = idx // 2
            cx = card_margin + col * (card_w + gutter)
            cy = int(h * 0.22) + row * (card_h + gutter)

            card_bg = _with_alpha(tc, 25)[:3]
            _draw_rounded_rect(draw, (cx, cy, cx + card_w, cy + card_h), fill=card_bg, radius=16)

            # Stat number
            stat_text = stats[idx] if idx < len(stats) else "--"
            sw, sh = _text_size(draw, stat_text, stat_font)
            draw.text((cx + (card_w - sw) // 2, cy + card_h // 4), stat_text, fill=accent, font=stat_font)

            # Label
            label = stat_labels[idx] if idx < len(stat_labels) else ""
            lw, lh = _text_size(draw, label, label_font)
            draw.text((cx + (card_w - lw) // 2, cy + card_h * 2 // 3), label, fill=tc, font=label_font)

        # CTA
        if cta:
            self._draw_cta_button(draw, cta, w, h, accent, int(h * 0.88))

        return img

    # ── Minimalist Luxury ─────────────────────────────────

    def _render_minimalist(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, logo_url, img_source,
    ) -> Image.Image:
        """Premium minimalist layout with generous white space."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        margin = int(w * 0.12)

        # Product image centered (30% canvas)
        if img_source:
            target = int(min(w, h) * 0.35)
            prod_img = _load_and_fit_image(img_source, self.work_dir, (target, target), "min_prod")
            if prod_img:
                px = (w - prod_img.width) // 2
                py = (h - prod_img.height) // 2 - int(h * 0.02)
                img.paste(prod_img, (px, py), prod_img if prod_img.mode == "RGBA" else None)

        # Headline above product (serif-like, letter-spaced)
        hf = _get_font(min(38, w // 24), bold=True)
        hw, hh = _text_size(draw, headline, hf)
        draw.text(((w - hw) // 2, int(h * 0.12)), headline, fill=text_color, font=hf)

        # Thin divider line
        line_y = int(h * 0.12) + hh + 16
        draw.line([(w // 4, line_y), (3 * w // 4, line_y)], fill=_lighten(text_color, 0.6), width=1)

        # Tagline/subheading below product
        if subheading:
            sf = _get_font(min(18, w // 50), bold=False)
            sw, sh = _text_size(draw, subheading, sf)
            draw.text(((w - sw) // 2, int(h * 0.78)), subheading, fill=_darken(text_color, 0.5), font=sf)

        # Brand name small at bottom
        if brand_name:
            bf = _get_font(16, bold=False)
            bw, bh = _text_size(draw, brand_name.upper(), bf)
            draw.text(((w - bw) // 2, h - int(h * 0.06)), brand_name.upper(), fill=_darken(text_color, 0.4), font=bf)

        # CTA as understated text link
        if cta:
            cf = _get_font(min(18, w // 50), bold=False)
            cw, ch = _text_size(draw, cta, cf)
            cx = (w - cw) // 2
            cy = int(h * 0.85)
            draw.text((cx, cy), cta, fill=primary, font=cf)
            draw.line([(cx, cy + ch + 2), (cx + cw, cy + ch + 2)], fill=primary, width=1)

        return img

    # ── Problem-Agitation-Solution ────────────────────────

    def _render_pas(
        self, template, w, h, headline, subheading, cta, body_text,
        primary, secondary, accent, bg, text_color,
        brand_name, img_source,
    ) -> Image.Image:
        """Problem → Agitation → Solution three-section layout."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)

        # Problem zone (top 30%) - dark
        prob_h = int(h * 0.30)
        draw.rectangle([(0, 0), (w, prob_h)], fill=(60, 30, 30))
        pf = _get_font(min(28, w // 32), bold=True)
        _draw_text_block(draw, headline, (int(w * 0.06), int(prob_h * 0.3)), pf, (220, 80, 80), int(w * 0.88), "center")

        # Agitation zone (middle 20%) - red accent
        agit_y = prob_h
        agit_h = int(h * 0.20)
        draw.rectangle([(0, agit_y), (w, agit_y + agit_h)], fill=(100, 30, 30))

        pain_points = [s.strip() for s in (body_text or subheading or "").split(".") if s.strip()]
        if not pain_points:
            pain_points = ["Wasted time", "Lost revenue", "Constant stress"]
        pf2 = _get_font(min(20, w // 44), bold=False)
        y = agit_y + 16
        for pp in pain_points[:3]:
            draw.text((int(w * 0.08), y), f"\u2717  {pp}", fill=(255, 150, 150), font=pf2)
            y += 32

        # Solution zone (bottom 50%) - bright
        sol_y = agit_y + agit_h
        sol_h = h - sol_y
        _draw_gradient_rect(img, (0, sol_y, w, h), _lighten(primary, 0.3), primary)
        sol_tc = _contrast_color(primary)

        # Product image
        if img_source:
            prod_img = _load_and_fit_image(img_source, self.work_dir, (int(w * 0.35), int(sol_h * 0.6)), "pas_prod")
            if prod_img:
                px = int(w * 0.06)
                py = sol_y + (sol_h - prod_img.height) // 2
                img.paste(prod_img, (px, py), prod_img if prod_img.mode == "RGBA" else None)

        # Solution text
        sf = _get_font(min(28, w // 32), bold=True)
        sol_text = cta or "The Solution"
        _draw_text_block(draw, sol_text, (int(w * 0.5), sol_y + int(sol_h * 0.2)), sf, sol_tc, int(w * 0.44), "left")

        # Checkmark benefits
        check_font = _get_font(min(18, w // 50), bold=False)
        check_y = sol_y + int(sol_h * 0.45)
        for pp in pain_points[:3]:
            draw.text((int(w * 0.5), check_y), f"\u2713  {pp}", fill=sol_tc, font=check_font)
            check_y += 28

        return img

    # ── Social Proof ──────────────────────────────────────

    def _render_social_proof(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, logo_url,
    ) -> Image.Image:
        """Social proof layout with trust signals."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        margin = int(w * 0.06)

        # Headline
        hf = _get_font(min(34, w // 26), bold=True)
        _draw_text_block(draw, headline, (margin, int(h * 0.06)), hf, text_color, w - margin * 2, "center")

        # Trust metric area
        metrics = [
            ("50,000+", "Happy Customers"),
            ("4.9/5.0", "Average Rating"),
            ("98%", "Satisfaction"),
        ]
        metric_y = int(h * 0.22)
        metric_w = (w - margin * 2) // 3
        num_font = _get_font(min(40, w // 20), bold=True)
        label_font = _get_font(min(16, w // 56), bold=False)

        for idx, (num, label) in enumerate(metrics):
            mx = margin + idx * metric_w
            nw, nh = _text_size(draw, num, num_font)
            draw.text((mx + (metric_w - nw) // 2, metric_y), num, fill=primary, font=num_font)
            lw, lh = _text_size(draw, label, label_font)
            draw.text((mx + (metric_w - lw) // 2, metric_y + nh + 8), label, fill=_darken(text_color, 0.6), font=label_font)

        # Divider
        draw.line([(margin, int(h * 0.48)), (w - margin, int(h * 0.48))], fill=_lighten(text_color, 0.8), width=1)

        # Stars and subheading
        star_font = _get_font(32, bold=False)
        stars = "\u2605" * 5
        sw, sh = _text_size(draw, stars, star_font)
        draw.text(((w - sw) // 2, int(h * 0.54)), stars, fill=(255, 193, 7), font=star_font)

        if subheading:
            sf = _get_font(min(22, w // 40), bold=False)
            _draw_text_block(draw, subheading, (margin, int(h * 0.64)), sf, text_color, w - margin * 2, "center")

        # Brand name
        if brand_name:
            bf = _get_font(20, bold=True)
            bw, bh = _text_size(draw, brand_name, bf)
            draw.text(((w - bw) // 2, int(h * 0.78)), brand_name, fill=primary, font=bf)

        # CTA
        if cta:
            self._draw_cta_button(draw, cta, w, h, accent, int(h * 0.88))

        return img

    # ── Feature Highlight ─────────────────────────────────

    def _render_feature_highlight(
        self, template, w, h, headline, subheading, cta, body_text,
        primary, secondary, accent, bg, text_color,
        brand_name, img_source,
    ) -> Image.Image:
        """Feature spotlight with annotation."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)

        # Left half: product/feature image
        if img_source:
            prod_img = _load_and_fit_image(img_source, self.work_dir, (w // 2 - 20, int(h * 0.7)), "feat_prod")
            if prod_img:
                px = (w // 2 - prod_img.width) // 2
                py = (h - prod_img.height) // 2
                img.paste(prod_img, (px, py), prod_img if prod_img.mode == "RGBA" else None)

                # Spotlight glow circle
                glow_r = min(prod_img.width, prod_img.height) // 3
                glow_x = px + prod_img.width // 2
                glow_y = py + prod_img.height // 2
                for r in range(glow_r, 0, -2):
                    alpha = max(0, 40 - int(40 * r / glow_r))
                    draw.ellipse(
                        [glow_x - r, glow_y - r, glow_x + r, glow_y + r],
                        outline=_lighten(accent, 0.5),
                    )

        # Right half: text content
        text_x = w // 2 + int(w * 0.04)
        text_w = w // 2 - int(w * 0.08)

        # Headline
        hf = _get_font(min(36, w // 24), bold=True)
        y = int(h * 0.15)
        head_h = _draw_text_block(draw, headline, (text_x, y), hf, text_color, text_w, "left", 10)
        y += head_h + 20

        # Benefits
        benefits = [s.strip() for s in (body_text or subheading or "").split(".") if s.strip()]
        if not benefits:
            benefits = [subheading or "Key benefit"]
        bf = _get_font(min(20, w // 44), bold=False)
        for b in benefits[:4]:
            draw.text((text_x, y), f"\u2022  {b}", fill=_darken(text_color, 0.8), font=bf)
            y += 32

        # CTA
        if cta:
            cta_font = _get_font(min(22, w // 40), bold=True)
            cw, ch = _text_size(draw, cta, cta_font)
            btn_w = cw + 40
            btn_h = ch + 24
            btn_y = h - int(h * 0.12) - btn_h
            _draw_rounded_rect(draw, (text_x, btn_y, text_x + btn_w, btn_y + btn_h), fill=accent, radius=btn_h // 2)
            draw.text((text_x + 20, btn_y + 12), cta, fill=_contrast_color(accent), font=cta_font)

        return img

    # ── Comparison Table ──────────────────────────────────

    def _render_comparison(
        self, template, w, h, headline, subheading, cta, body_text,
        primary, secondary, accent, bg, text_color,
        brand_name,
    ) -> Image.Image:
        """Comparison table layout."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        margin = int(w * 0.06)

        # Headline
        hf = _get_font(min(32, w // 28), bold=True)
        _draw_text_block(draw, headline, (margin, int(h * 0.04)), hf, text_color, w - margin * 2, "center")

        # Table area
        table_y = int(h * 0.15)
        table_h = int(h * 0.68)
        col_w = (w - margin * 2) // 3

        # Column headers
        headers = ["Others", brand_name or "Us", "Premium"]
        header_font = _get_font(min(22, w // 40), bold=True)
        for i, header in enumerate(headers):
            hx = margin + i * col_w
            col_bg = accent if i == 1 else _lighten(bg, 0.05)
            draw.rectangle([(hx, table_y), (hx + col_w - 2, table_y + 50)], fill=col_bg)
            hc = _contrast_color(accent) if i == 1 else text_color
            hw2, hh2 = _text_size(draw, header, header_font)
            draw.text((hx + (col_w - hw2) // 2, table_y + (50 - hh2) // 2), header, fill=hc, font=header_font)

        # Feature rows
        features = ["Quality", "Support", "Price", "Speed", "Features"]
        row_font = _get_font(min(18, w // 50), bold=False)
        check = "\u2713"
        cross = "\u2717"

        for ri, feature in enumerate(features):
            ry = table_y + 55 + ri * (table_h - 55) // len(features)
            row_bg = _lighten(bg, 0.02) if ri % 2 == 0 else bg
            draw.rectangle([(margin, ry), (w - margin, ry + (table_h - 55) // len(features))], fill=row_bg)

            # Feature name
            draw.text((margin + 10, ry + 10), feature, fill=text_color, font=row_font)

            # Marks per column
            marks = [cross, check, check] if ri % 2 == 0 else [check, check, cross]
            for ci, mark in enumerate(marks):
                mx = margin + ci * col_w + col_w // 2
                color = (0, 180, 0) if mark == check else (200, 50, 50)
                mf = _get_font(22, bold=True)
                mw, mh = _text_size(draw, mark, mf)
                draw.text((mx - mw // 2, ry + 8), mark, fill=color, font=mf)

        # CTA
        if cta:
            self._draw_cta_button(draw, cta, w, h, accent, int(h * 0.88))

        return img

    # ── UGC Authenticity ──────────────────────────────────

    def _render_ugc(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, img_source,
    ) -> Image.Image:
        """UGC-style layout with authentic photo collage aesthetic."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        margin = int(w * 0.05)

        # Headline
        hf = _get_font(min(30, w // 30), bold=True)
        _draw_text_block(draw, headline, (margin, int(h * 0.04)), hf, text_color, w - margin * 2, "center")

        # Photo cards area (2x2 grid style with rotation effect)
        card_area_y = int(h * 0.16)
        card_area_h = int(h * 0.60)
        card_w = (w - margin * 3) // 2
        card_h = (card_area_h - margin) // 2

        card_colors = [_lighten(primary, 0.6), _lighten(secondary, 0.2), _lighten(accent, 0.5), _lighten(primary, 0.4)]
        for idx in range(4):
            col = idx % 2
            row = idx // 2
            cx = margin + col * (card_w + margin)
            cy = card_area_y + row * (card_h + margin)

            # Card shadow
            draw.rectangle([(cx + 3, cy + 3), (cx + card_w + 3, cy + card_h + 3)], fill=_darken(bg, 0.85))
            # Card body
            draw.rectangle([(cx, cy), (cx + card_w, cy + card_h)], fill=(255, 255, 255))
            # Inner colored area (simulating a photo)
            inner_m = 8
            draw.rectangle([(cx + inner_m, cy + inner_m), (cx + card_w - inner_m, cy + card_h - 35)], fill=card_colors[idx])

            # Small heart icon
            heart_font = _get_font(16, bold=False)
            draw.text((cx + inner_m, cy + card_h - 28), "\u2665 " + str(120 + idx * 37), fill=(220, 50, 50), font=heart_font)

        # If we have an image, paste it into the first card
        if img_source:
            prod_img = _load_and_fit_image(img_source, self.work_dir, (card_w - 20, card_h - 50), "ugc_prod")
            if prod_img:
                img.paste(prod_img, (margin + 10, card_area_y + 10), prod_img if prod_img.mode == "RGBA" else None)

        # Hashtag
        if brand_name:
            tag_font = _get_font(min(22, w // 40), bold=True)
            tag = f"#{brand_name.replace(' ', '')}Love"
            tw, th = _text_size(draw, tag, tag_font)
            draw.text(((w - tw) // 2, int(h * 0.80)), tag, fill=primary, font=tag_font)

        # CTA
        if cta:
            self._draw_cta_button(draw, cta, w, h, accent, int(h * 0.89))

        return img

    # ── Seasonal ──────────────────────────────────────────

    def _render_seasonal(
        self, template, w, h, headline, subheading, cta,
        primary, secondary, accent, bg, text_color,
        brand_name, img_source,
    ) -> Image.Image:
        """Seasonal campaign with festive elements."""
        img = Image.new("RGB", (w, h))
        _draw_gradient_rect(img, (0, 0, w, h), primary, _darken(primary, 0.7))
        draw = ImageDraw.Draw(img)
        tc = _contrast_color(primary)
        margin = int(w * 0.06)

        # Decorative top border
        for i in range(0, w, 40):
            draw.ellipse([(i, -10), (i + 20, 10)], fill=accent)

        # Season badge
        badge_font = _get_font(min(16, w // 56), bold=True)
        badge_text = "SEASONAL OFFER"
        bw, bh = _text_size(draw, badge_text, badge_font)
        badge_x = (w - bw - 24) // 2
        _draw_rounded_rect(draw, (badge_x, 30, badge_x + bw + 24, 30 + bh + 16), fill=accent, radius=4)
        draw.text((badge_x + 12, 38), badge_text, fill=_contrast_color(accent), font=badge_font)

        # Headline
        hf = _get_font(min(42, w // 20), bold=True)
        _draw_text_block(draw, headline, (margin, int(h * 0.12)), hf, tc, w - margin * 2, "center")

        # Product image
        if img_source:
            prod_img = _load_and_fit_image(img_source, self.work_dir, (int(w * 0.45), int(h * 0.35)), "season_prod")
            if prod_img:
                px = (w - prod_img.width) // 2
                py = int(h * 0.35)
                img.paste(prod_img, (px, py), prod_img if prod_img.mode == "RGBA" else None)

        # Subheading
        if subheading:
            sf = _get_font(min(24, w // 36), bold=False)
            _draw_text_block(draw, subheading, (margin, int(h * 0.75)), sf, tc, w - margin * 2, "center")

        # CTA
        if cta:
            cta_font = _get_font(min(26, w // 34), bold=True)
            cw, ch = _text_size(draw, cta, cta_font)
            btn_w = cw + 56
            btn_h = ch + 28
            btn_x = (w - btn_w) // 2
            btn_y = h - int(h * 0.10) - btn_h
            _draw_rounded_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), fill=(255, 255, 255), radius=btn_h // 2)
            draw.text((btn_x + 28, btn_y + 14), cta, fill=primary, font=cta_font)

        # Decorative bottom border
        for i in range(0, w, 40):
            draw.ellipse([(i, h - 10), (i + 20, h + 10)], fill=accent)

        return img

    # ── How It Works ──────────────────────────────────────

    def _render_how_it_works(
        self, template, w, h, headline, subheading, cta, body_text,
        primary, secondary, accent, bg, text_color,
        brand_name,
    ) -> Image.Image:
        """Step-by-step process layout."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        margin = int(w * 0.06)

        # Headline
        hf = _get_font(min(34, w // 26), bold=True)
        _draw_text_block(draw, headline, (margin, int(h * 0.05)), hf, text_color, w - margin * 2, "center")

        # Steps
        steps = [s.strip() for s in (body_text or subheading or "").split(".") if s.strip()]
        if not steps:
            steps = ["Sign Up", "Choose Plan", "Get Started"]
        steps = steps[:3]

        step_y_start = int(h * 0.18)
        step_h = (int(h * 0.65)) // max(1, len(steps))
        circle_r = 30
        num_font = _get_font(24, bold=True)
        step_title_font = _get_font(min(24, w // 36), bold=True)
        connector_x = margin + circle_r

        for idx, step in enumerate(steps):
            sy = step_y_start + idx * step_h

            # Connector line (between steps)
            if idx > 0:
                draw.line(
                    [(connector_x, sy - step_h + circle_r * 2 + 10), (connector_x, sy - 10)],
                    fill=_lighten(primary, 0.5), width=2,
                )

            # Step circle
            draw.ellipse(
                [margin, sy, margin + circle_r * 2, sy + circle_r * 2],
                fill=primary,
            )
            num_text = str(idx + 1)
            nw, nh = _text_size(draw, num_text, num_font)
            draw.text(
                (margin + circle_r - nw // 2, sy + circle_r - nh // 2),
                num_text, fill=_contrast_color(primary), font=num_font,
            )

            # Step text
            draw.text(
                (margin + circle_r * 2 + 20, sy + circle_r - 12),
                step, fill=text_color, font=step_title_font,
            )

        # CTA
        if cta:
            self._draw_cta_button(draw, cta, w, h, accent, int(h * 0.88))

        return img

    # ── Fallback ──────────────────────────────────────────

    def _render_fallback(
        self, w, h, headline, cta,
        primary, bg, text_color, brand_name,
    ) -> Image.Image:
        """Simple branded fallback for any render errors."""
        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)

        # Accent bar top
        draw.rectangle([(0, 0), (w, 8)], fill=primary)

        # Headline centered
        hf = _get_font(min(40, w // 22), bold=True)
        _draw_text_block(draw, headline, (int(w * 0.08), int(h * 0.35)), hf, text_color, int(w * 0.84), "center")

        # Brand name
        if brand_name:
            bf = _get_font(24, bold=True)
            bw, bh = _text_size(draw, brand_name, bf)
            draw.text(((w - bw) // 2, int(h * 0.12)), brand_name, fill=primary, font=bf)

        # CTA
        if cta:
            self._draw_cta_button(draw, cta, w, h, primary, int(h * 0.75))

        return img

    # ── Shared helpers ────────────────────────────────────

    def _draw_cta_button(
        self,
        draw: ImageDraw.ImageDraw,
        cta: str,
        canvas_w: int,
        canvas_h: int,
        color: Tuple[int, int, int],
        y_pos: int,
    ) -> None:
        """Draw a centered CTA button at y_pos."""
        cta_font = _get_font(min(24, canvas_w // 38), bold=True)
        cw, ch = _text_size(draw, cta, cta_font)
        btn_w = cw + 48
        btn_h = ch + 24
        btn_x = (canvas_w - btn_w) // 2
        _draw_rounded_rect(draw, (btn_x, y_pos, btn_x + btn_w, y_pos + btn_h), fill=color, radius=btn_h // 2)
        draw.text((btn_x + 24, y_pos + 12), cta, fill=_contrast_color(color), font=cta_font)
