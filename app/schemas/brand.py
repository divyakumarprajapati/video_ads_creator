"""
Pydantic models for brand identity and market research data.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.enums import MarketSaturation, Sentiment


class BrandColors(BaseModel):
    primary: str = Field(..., description="Primary hex colour, e.g. '#FF5733'")
    secondary: str = Field(..., description="Secondary hex colour")
    accent: Optional[str] = Field(None, description="Optional accent colour")
    background: str = Field("#FFFFFF", description="Background colour")
    text: str = Field("#000000", description="Text colour")


class BrandFonts(BaseModel):
    heading: str = Field("Montserrat", description="Font family for headings")
    body: str = Field("Open Sans", description="Font family for body text")
    accent: Optional[str] = Field(None, description="Optional accent font")


class BrandIdentity(BaseModel):
    """Everything we need to keep video output on-brand."""
    brand_name: str = Field(..., min_length=1, max_length=256)
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    colors: BrandColors
    fonts: BrandFonts
    voice: str = Field("professional", description="Brand voice: professional, playful, bold, etc.")
    tone: str = Field("confident", description="Brand tone: confident, warm, urgent, etc.")
    industry: Optional[str] = Field(None, description="E.g. skincare, tech, fashion")


class MarketResearch(BaseModel):
    """Market context that drives creative decisions."""
    saturation_percent: float = Field(
        50.0, ge=0, le=100, description="Market saturation percentage"
    )
    competitive_edge_percent: float = Field(
        50.0, ge=0, le=100, description="Competitive edge score"
    )
    sentiment: Sentiment = Sentiment.NEUTRAL
    trending_keywords: List[str] = Field(default_factory=list)
    target_audience_age_min: int = Field(18, ge=13)
    target_audience_age_max: int = Field(65, le=100)
    target_audience_gender: str = Field("all", description="all | male | female")

    @property
    def saturation_level(self) -> MarketSaturation:
        if self.saturation_percent < 30:
            return MarketSaturation.LOW
        if self.saturation_percent < 60:
            return MarketSaturation.MEDIUM
        if self.saturation_percent < 80:
            return MarketSaturation.HIGH
        return MarketSaturation.VERY_HIGH
