"""
Pydantic models for video templates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    compatible_visual_styles: List[str] = []
    compatible_video_styles: List[str] = []
    compatible_industries: List[str] = []
    requires_product_image: bool = True
    requires_background: bool = False
    min_duration: int = 5
    max_duration: int = 30
    supported_aspect_ratios: List[str] = []
    performance_score: float = 50.0
    usage_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateListOut(BaseModel):
    templates: List[TemplateOut]
    total: int


class TemplateFilter(BaseModel):
    """Query parameters for filtering templates."""
    category: Optional[str] = None
    visual_style: Optional[str] = None
    video_style: Optional[str] = None
    industry: Optional[str] = None
    min_duration: Optional[int] = None
    max_duration: Optional[int] = None
    aspect_ratio: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
