"""
Pydantic models for product data.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class ProductInput(BaseModel):
    """Single product as submitted by the caller."""
    product_name: str = Field(..., min_length=1, max_length=256)
    product_image_url: str = Field(..., description="URL to product image (JPG/PNG/WebP)")
    product_description: Optional[str] = None
    product_category: Optional[str] = None
    product_features: Optional[Dict[str, str]] = None
    price: Optional[float] = Field(None, ge=0)
    tags: Optional[Dict[str, bool]] = Field(
        None,
        description='E.g. {"is_new": true, "is_bestseller": false}',
    )


class ProductOut(BaseModel):
    """Product as returned by the API."""
    id: uuid.UUID
    product_name: str
    product_image_url: str
    product_description: Optional[str] = None
    product_category: Optional[str] = None
    product_features: Optional[Dict[str, str]] = None
    price: Optional[float] = None
    tags: Optional[Dict[str, bool]] = None
    generation_status: str
    progress: float
    creative_plan: Optional[dict] = None

    model_config = {"from_attributes": True}
