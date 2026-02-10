"""
Pydantic models for product data.
"""

from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# Supported image formats
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
_IMAGE_PATTERN = re.compile(r"https?://.+", re.IGNORECASE)


class ProductInput(BaseModel):
    """Single product as submitted by the caller."""
    product_name: str = Field(..., min_length=1, max_length=256)
    product_image_url: Optional[str] = Field(
        None,
        description="Optional URL to product image (JPG/PNG/WebP, max 10 MB).",
    )
    product_image_urls: Optional[List[str]] = Field(
        None,
        description="Optional list of product image URLs (JPG/PNG/WebP). Used to rotate static ad imagery.",
    )
    product_description: Optional[str] = None
    product_category: Optional[str] = None
    product_features: Optional[Dict[str, str]] = None
    price: Optional[float] = Field(None, ge=0)
    tags: Optional[Dict[str, bool]] = Field(
        None,
        description='E.g. {"is_new": true, "is_bestseller": false}',
    )
    image_url: Optional[str] = Field(
        None,
        description="Optional image URL for static ads (JPG/PNG/WebP). If provided, used as the hero image in static ad templates. Falls back to product_image_url.",
    )
    image_urls: Optional[List[str]] = Field(
        None,
        description="Optional list of static ad hero images (JPG/PNG/WebP). If provided, used for static ads in rotation.",
    )

    @field_validator("product_image_url")
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        if not _IMAGE_PATTERN.match(v):
            raise ValueError("product_image_url must be a valid HTTP(S) URL")
        # Check extension (loose check – actual content type is verified during download)
        lower = v.lower().split("?")[0]  # strip query params
        has_extension = any(lower.endswith(ext) for ext in _IMAGE_EXTENSIONS)
        # Allow URLs without extension (CDNs, dynamic image servers, placeholder services)
        # Actual content-type validation happens at download time
        return v

    @field_validator("product_image_urls", "image_urls")
    @classmethod
    def validate_image_url_list(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned = [u for u in v if u]
        if not cleaned:
            return None
        for url in cleaned:
            if not _IMAGE_PATTERN.match(url):
                raise ValueError("image URL lists must contain valid HTTP(S) URLs")
        return cleaned



class ProductOut(BaseModel):
    """Product as returned by the API."""
    id: uuid.UUID
    product_name: str
    product_image_url: Optional[str] = None
    product_image_urls: Optional[List[str]] = None
    product_description: Optional[str] = None
    product_category: Optional[str] = None
    product_features: Optional[Dict[str, str]] = None
    price: Optional[float] = None
    tags: Optional[Dict[str, bool]] = None
    image_urls: Optional[List[str]] = None
    generation_status: str
    progress: float
    creative_plan: Optional[dict] = None

    model_config = {"from_attributes": True}
