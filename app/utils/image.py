"""
Image processing utilities built on Pillow and OpenCV.
"""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

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


def _estimate_background_color(arr: np.ndarray, sample: int = 12) -> Tuple[int, int, int]:
    """Estimate background color by sampling the image borders."""
    h, w = arr.shape[:2]
    if h == 0 or w == 0:
        return (255, 255, 255)

    coords = [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]
    step = max(1, min(h, w) // sample)
    for x in range(0, w, step):
        coords.append((0, x))
        coords.append((h - 1, x))
    for y in range(0, h, step):
        coords.append((y, 0))
        coords.append((y, w - 1))

    colors = [arr[y, x, :3] for (y, x) in coords]
    median = np.median(np.array(colors), axis=0)
    return (int(median[0]), int(median[1]), int(median[2]))


def trim_transparent(img: Image.Image, padding: int = 8, min_alpha: int = 12) -> Image.Image:
    """Trim transparent borders with optional padding."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.getchannel("A")
    mask = alpha.point(lambda a: 255 if a > min_alpha else 0)
    bbox = mask.getbbox()
    if not bbox:
        return img
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(img.width, x2 + padding)
    y2 = min(img.height, y2 + padding)
    return img.crop((x1, y1, x2, y2))


def extract_subject_rgba(
    img: Image.Image,
    *,
    bg_threshold: int = 28,
    min_alpha: int = 12,
) -> Image.Image:
    """
    Heuristic background removal with edge sampling + crop.
    Uses alpha if present; otherwise estimates background from borders.
    """
    img = img.convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]

    if alpha.min() < 250:
        alpha = np.where(alpha > min_alpha, alpha, 0)
    else:
        bg = _estimate_background_color(arr)
        diff = np.sqrt(((arr[:, :, :3].astype("int32") - np.array(bg)) ** 2).sum(axis=2))
        thresholds = [bg_threshold, 18, 35, 45]
        mask = diff > thresholds[0]
        coverage = mask.mean()
        for t in thresholds[1:]:
            if 0.02 < coverage < 0.98:
                break
            mask = diff > t
            coverage = mask.mean()

        mask_img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        mask_img = mask_img.filter(ImageFilter.MaxFilter(5))
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(1))
        alpha = np.array(mask_img)

    # Apply alpha and crop
    out = img.copy()
    out.putalpha(Image.fromarray(alpha.astype(np.uint8), mode="L"))
    out = trim_transparent(out, padding=6, min_alpha=min_alpha)

    # Safety: if crop is too tiny, return original
    if out.width < img.width * 0.25 or out.height < img.height * 0.25:
        return img
    return out


def enhance_image(
    img: Image.Image,
    *,
    brightness: float = 1.02,
    contrast: float = 1.08,
    color: float = 1.06,
    sharpness: float = 1.08,
) -> Image.Image:
    """Subtle enhancement for product imagery."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(color)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    return img
