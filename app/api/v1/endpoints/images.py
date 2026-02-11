"""
Image processing endpoints.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
import numpy as np
from PIL import Image, ImageOps

from app.core.config import get_settings
from app.utils.image import remove_background_best, trim_transparent


router = APIRouter(prefix="/images", tags=["Images"])
settings = get_settings()


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
        img = _force_remove_border_bg(img)
    except Exception:
        pass
    try:
        img = _trim_alpha(img, padding=0, min_alpha=1)
    except Exception:
        pass
    # Enforce a consistent transparent border after trimming.
    img = ImageOps.expand(img, border=10, fill=(0, 0, 0, 0))

    if pad_to_square:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        canvas = Image.new("RGBA", (max_size, max_size), (0, 0, 0, 0))
        offset = ((max_size - img.width) // 2, (max_size - img.height) // 2)
        canvas.paste(img, offset, img)
        return canvas

    img.thumbnail((max_size, max_size), Image.LANCZOS)
    return img


def _png_bytes(img: Image.Image) -> bytes:
    bio = BytesIO()
    img.save(bio, format="PNG", optimize=True)
    return bio.getvalue()


def _estimate_background_color(arr: np.ndarray, sample: int = 12) -> tuple[int, int, int]:
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


def _force_remove_border_bg(
    img: Image.Image,
    *,
    bg_threshold: int = 28,
) -> Image.Image:
    """
    If the image has no transparency, attempt background keying using
    the estimated border color.
    """
    img = img.convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    if alpha.min() < 250:
        return img

    bg = _estimate_background_color(arr)
    diff = np.sqrt(((arr[:, :, :3].astype("int32") - np.array(bg)) ** 2).sum(axis=2))
    mask = diff > bg_threshold
    new_alpha = (mask * 255).astype(np.uint8)

    out = img.copy()
    out.putalpha(Image.fromarray(new_alpha, mode="L"))
    return out


def _trim_alpha(
    img: Image.Image,
    *,
    padding: int = 0,
    min_alpha: int = 1,
) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = np.array(img.getchannel("A"))
    mask = alpha > min_alpha
    if not mask.any():
        return img

    rows, cols = np.where(mask)
    row_start, row_end = rows.min(), rows.max() + 1
    col_start, col_end = cols.min(), cols.max() + 1
    row_start = max(0, row_start - padding)
    col_start = max(0, col_start - padding)
    row_end = min(img.height, row_end + padding)
    col_end = min(img.width, col_end + padding)
    img = img.crop((col_start, row_start, col_end, row_end))
    return img


@router.post("/process")
async def process_image(
    image_url: Optional[str] = Query(
        None,
        description="Image URL to fetch and process (use instead of file upload).",
    ),
    max_size: int = Query(512, ge=64, le=2048, description="Max size for output image."),
    pad_to_square: bool = Query(False, description="Pad result to a square canvas."),
    response_format: str = Query(
        "png",
        description="Response format: png or json (data_uri + dimensions).",
    ),
    file: Optional[UploadFile] = File(
        None,
        description="Image file upload (use instead of image_url).",
    ),
):
    if not file and not image_url:
        raise HTTPException(status_code=400, detail="Provide file or image_url.")
    if file and image_url:
        raise HTTPException(status_code=400, detail="Provide only one of file or image_url.")

    if response_format not in {"png", "json"}:
        raise HTTPException(status_code=400, detail="response_format must be png or json.")

    if file:
        content = await file.read()
    else:
        try:
            resp = httpx.get(image_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            content = resp.content
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download image: {exc}")

    max_bytes = settings.max_image_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {settings.max_image_size_mb} MB limit.",
        )

    try:
        img = Image.open(BytesIO(content)).convert("RGBA")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    img = _prepare_product_image(img, max_size=max_size, pad_to_square=pad_to_square)
    png = _png_bytes(img)

    if response_format == "json":
        b64 = base64.b64encode(png).decode("utf-8")
        return JSONResponse(
            {
                "data_uri": f"data:image/png;base64,{b64}",
                "width": img.width,
                "height": img.height,
            }
        )

    return StreamingResponse(BytesIO(png), media_type="image/png")
