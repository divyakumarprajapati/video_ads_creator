"""
Unit tests for Pydantic schemas – validation logic.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.brand import BrandColors, BrandFonts, BrandIdentity, MarketResearch
from app.schemas.campaign import CampaignCreate
from app.schemas.product import ProductInput


class TestProductInput:
    def test_valid_product(self):
        p = ProductInput(
            product_name="Test",
            product_image_url="https://example.com/img.png",
        )
        assert p.product_name == "Test"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            ProductInput(product_name="", product_image_url="https://x.com/a.png")

    def test_optional_fields_default_none(self):
        p = ProductInput(product_name="X", product_image_url="https://x.com/a.png")
        assert p.product_description is None
        assert p.price is None
        assert p.tags is None


class TestBrandIdentity:
    def test_valid(self):
        bi = BrandIdentity(
            brand_name="Test",
            colors=BrandColors(primary="#000", secondary="#FFF"),
            fonts=BrandFonts(),
        )
        assert bi.brand_name == "Test"

    def test_empty_brand_name_rejected(self):
        with pytest.raises(ValidationError):
            BrandIdentity(
                brand_name="",
                colors=BrandColors(primary="#000", secondary="#FFF"),
                fonts=BrandFonts(),
            )


class TestMarketResearch:
    def test_saturation_level_low(self):
        mr = MarketResearch(saturation_percent=20)
        assert mr.saturation_level.value == "low"

    def test_saturation_level_very_high(self):
        mr = MarketResearch(saturation_percent=85)
        assert mr.saturation_level.value == "very_high"

    def test_bounds(self):
        with pytest.raises(ValidationError):
            MarketResearch(saturation_percent=150)


class TestCampaignCreate:
    def test_valid_campaign(self, campaign_create_data):
        c = CampaignCreate(**campaign_create_data)
        assert len(c.products) == 2
        assert c.campaign_goal.value == "awareness"

    def test_no_products_rejected(self, brand_identity_data, market_research_data):
        with pytest.raises(ValidationError):
            CampaignCreate(
                campaign_name="Empty",
                brand_identity=brand_identity_data,
                market_research=market_research_data,
                products=[],
            )

    def test_duration_bounds(self, campaign_create_data):
        campaign_create_data["duration_preference"] = 3  # below min of 5
        with pytest.raises(ValidationError):
            CampaignCreate(**campaign_create_data)
