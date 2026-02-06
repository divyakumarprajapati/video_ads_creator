"""
Image processing utilities built on Pillow and OpenCV.
"""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.logging import get_logger

logger = get_logger(__name__)


def download_image(url: str, dest: str) -> str:
    """Download an image from *url* and save to *dest*.  Returns *dest*."""
    import httpx

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest


def resize_image(
    src: str,
    dest: str,
    size: Tuple[int, int] = (1080, 1080),
    keep_aspect: bool = True,
) -> str:
    """Resize to *size*.  If *keep_aspect*, use thumbnail (no crop)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    img = Image.open(src).convert("RGBA")
    if keep_aspect:
        img.thumbnail(size, Image.LANCZOS)
        # Paste onto a canvas of exact *size*
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
        canvas.paste(img, offset, img)
        canvas.save(dest)
    else:
        img.resize(size, Image.LANCZOS).save(dest)
    return dest


def create_solid_background(
    dest: str,
    size: Tuple[int, int] = (1080, 1080),
    color: str = "#FFFFFF",
) -> str:
    """Generate a solid-colour background image."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    img = Image.new("RGB", size, color)
    img.save(dest)
    return dest


def create_gradient_background(
    dest: str,
    size: Tuple[int, int] = (1080, 1080),
    color_top: str = "#000000",
    color_bottom: str = "#333333",
) -> str:
    """Generate a vertical-gradient background."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    w, h = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)

    r1, g1, b1 = _hex_to_rgb(color_top)
    r2, g2, b2 = _hex_to_rgb(color_bottom)

    for y in range(h):
        ratio = y / h
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    img.save(dest)
    return dest


def composite_product_on_background(
    product_path: str,
    background_path: str,
    dest: str,
    product_scale: float = 0.7,
) -> str:
    """Place a (possibly transparent) product image centred on a background."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    bg = Image.open(background_path).convert("RGBA")
    prod = Image.open(product_path).convert("RGBA")

    # Scale product
    target_w = int(bg.width * product_scale)
    target_h = int(bg.height * product_scale)
    prod.thumbnail((target_w, target_h), Image.LANCZOS)

    offset = ((bg.width - prod.width) // 2, (bg.height - prod.height) // 2)
    bg.paste(prod, offset, prod)
    bg.convert("RGB").save(dest)
    return dest


def render_text_image(
    dest: str,
    text: str,
    size: Tuple[int, int] = (1080, 200),
    fontsize: int = 64,
    color: str = "#FFFFFF",
    bg_color: Optional[str] = None,
) -> str:
    """Render text to a PNG image (useful for overlays that need exact fonts)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    bg = (0, 0, 0, 0) if bg_color is None else _hex_to_rgb(bg_color)
    img = Image.new("RGBA", size, bg)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", fontsize)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size[0] - tw) // 2
    y = (size[1] - th) // 2
    draw.text((x, y), text, fill=color, font=font)
    img.save(dest)
    return dest


# ── Helpers ─────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i: i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
