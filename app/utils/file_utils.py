"""
File and path utilities.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from python_slugify import slugify


def campaign_dir(base: str, campaign_id: str) -> str:
    return os.path.join(base, f"campaign_{campaign_id}")


def product_dir(base: str, campaign_id: str, product_name: str, product_idx: int) -> str:
    safe_name = slugify(product_name, max_length=40) or f"product_{product_idx}"
    return os.path.join(
        campaign_dir(base, campaign_id),
        "product_specific",
        f"product_{product_idx + 1}_{safe_name}",
    )


def variant_dir(base: str, campaign_id: str, product_name: str, product_idx: int,
                variant_id: int, angle: str) -> str:
    return os.path.join(
        product_dir(base, campaign_id, product_name, product_idx),
        f"variant_{variant_id}_{angle}",
    )


def brand_variant_dir(base: str, campaign_id: str, variant_id: int, angle: str) -> str:
    return os.path.join(
        campaign_dir(base, campaign_id),
        "general_brand",
        f"variant_{variant_id}_{angle}",
    )


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def tmp_dir(prefix: str = "vae_") -> str:
    return tempfile.mkdtemp(prefix=prefix)


def safe_filename(name: str, ext: str = ".mp4") -> str:
    return slugify(name, max_length=60) + ext


def cleanup_dir(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def file_size_mb(path: str) -> float:
    if not os.path.exists(path):
        return 0.0
    return round(os.path.getsize(path) / (1024 * 1024), 2)
