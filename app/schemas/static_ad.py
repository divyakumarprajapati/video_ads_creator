"""
Pydantic models for single static ad generation.
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.brand import BrandIdentity, MarketResearch


class SingleStaticAdCreate(BaseModel):
    """Request payload for generating a single static ad."""
    prompt: str = Field(..., min_length=1, description="User prompt to guide ad copy.")
    image_url: Optional[str] = Field(
        None,
        description="Optional image URL to include in the ad (no background processing).",
    )
    product_name: Optional[str] = Field(None, description="Optional product name for labeling.")
    brand_identity: BrandIdentity
    market_research: MarketResearch
    template_id: Optional[str] = Field(None, description="Optional static ad template ID.")
    style_hint: Optional[str] = Field(None, description="Optional visual style hint.")
    width: Optional[int] = Field(None, ge=100, le=4000)
    height: Optional[int] = Field(None, ge=100, le=4000)


class SingleStaticAdOut(BaseModel):
    """Response payload for a single static ad generation."""
    ad_id: uuid.UUID
    ad_type: str
    status: str
    prompt: str
    headline: str
    subheading: Optional[str] = None
    cta_text: Optional[str] = None
    body_text: Optional[str] = None
    image_url: Optional[str] = None
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    file_size_mb: Optional[float] = None
    width: int
    height: int
