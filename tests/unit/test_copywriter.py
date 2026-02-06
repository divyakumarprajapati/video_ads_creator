"""
Unit tests for the OpenAI copywriter service.

These tests verify the fallback behaviour (returns None when OpenAI is
not configured) and the response parsing logic using mocks.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.strategy.copywriter import (
    BrandCopy,
    ProductCopy,
    generate_brand_copy,
    generate_product_copy,
)


class TestCopywriterDisabled:
    """When OPENAI_API_KEY is empty, all generate_* functions return None."""

    @pytest.mark.asyncio
    async def test_product_copy_returns_none_without_key(self):
        result = await generate_product_copy(
            product_name="Test Serum",
            product_description="A great serum",
            product_category="skincare",
            product_tags={"is_new": True},
            brand_name="TestBrand",
            brand_voice="warm",
            brand_tone="confident",
            message_angle="benefit",
            campaign_goal="awareness",
            num_variants=3,
        )
        # openai_api_key is "" by default → returns None
        assert result is None

    @pytest.mark.asyncio
    async def test_brand_copy_returns_none_without_key(self):
        result = await generate_brand_copy(
            brand_name="TestBrand",
            brand_voice="warm",
            brand_tone="confident",
            brand_industry="skincare",
            product_names=["Product A", "Product B"],
            campaign_goal="awareness",
            message_angles=["benefit", "social_proof", "urgency"],
            num_variants=3,
        )
        assert result is None


class TestCopywriterMocked:
    """Test response parsing with a mocked OpenAI client."""

    @pytest.mark.asyncio
    async def test_product_copy_parses_json_response(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"primary_message": "Glow Up Now", "secondary_message": "Vitamin C that works", "cta_text": "Shop Now"},
            {"primary_message": "New Drop Alert", "secondary_message": "Your skin will thank you", "cta_text": "Get Yours"},
            {"primary_message": "Skin Goals", "secondary_message": "Science meets nature", "cta_text": "Try It"},
        ])

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("app.services.strategy.copywriter.settings") as mock_settings:
            mock_settings.openai_enabled = True
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-5.1-chat-latest"
            mock_settings.openai_max_tokens = 512
            mock_settings.openai_temperature = 0.7
            mock_settings.openai_base_url = ""

            with patch("app.services.strategy.copywriter._get_openai_client", return_value=mock_client):
                result = await generate_product_copy(
                    product_name="Vitamin C Serum",
                    product_description="Brightening serum",
                    product_category="skincare",
                    product_tags={"is_new": True},
                    brand_name="Glow Naturals",
                    brand_voice="warm",
                    brand_tone="confident",
                    message_angle="benefit",
                    campaign_goal="awareness",
                    num_variants=3,
                )

        assert result is not None
        assert len(result) == 3
        assert result[0].primary_message == "Glow Up Now"
        assert result[1].cta_text == "Get Yours"
        assert result[2].secondary_message == "Science meets nature"

    @pytest.mark.asyncio
    async def test_brand_copy_parses_json_response(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"primary_message": "The Full Collection", "secondary_message": "Everything your skin craves", "cta_text": "Explore"},
            {"primary_message": "Curated for You", "secondary_message": "5-star favorites in one place", "cta_text": "Shop All"},
        ])

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("app.services.strategy.copywriter.settings") as mock_settings:
            mock_settings.openai_enabled = True
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-5.1-chat-latest"
            mock_settings.openai_max_tokens = 512
            mock_settings.openai_temperature = 0.7
            mock_settings.openai_base_url = ""

            with patch("app.services.strategy.copywriter._get_openai_client", return_value=mock_client):
                result = await generate_brand_copy(
                    brand_name="Glow Naturals",
                    brand_voice="warm",
                    brand_tone="confident",
                    brand_industry="skincare",
                    product_names=["Serum", "Moisturizer"],
                    campaign_goal="awareness",
                    message_angles=["benefit", "social_proof"],
                    num_variants=2,
                )

        assert result is not None
        assert len(result) == 2
        assert result[0].primary_message == "The Full Collection"
        assert result[1].cta_text == "Shop All"

    @pytest.mark.asyncio
    async def test_product_copy_handles_markdown_fences(self):
        """Model sometimes wraps JSON in ```json ... ``` fences."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n[{"primary_message": "Fresh Drop", "secondary_message": "New season essentials", "cta_text": "Shop"}]\n```'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("app.services.strategy.copywriter.settings") as mock_settings:
            mock_settings.openai_enabled = True
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-5.1-chat-latest"
            mock_settings.openai_max_tokens = 512
            mock_settings.openai_temperature = 0.7
            mock_settings.openai_base_url = ""

            with patch("app.services.strategy.copywriter._get_openai_client", return_value=mock_client):
                result = await generate_product_copy(
                    product_name="Test",
                    product_description=None,
                    product_category=None,
                    product_tags=None,
                    brand_name="Brand",
                    brand_voice="bold",
                    brand_tone="energetic",
                    message_angle="urgency",
                    campaign_goal="conversion",
                    num_variants=1,
                )

        assert result is not None
        assert len(result) == 1
        assert result[0].primary_message == "Fresh Drop"

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self):
        """If OpenAI call throws, return None (fallback to templates)."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with patch("app.services.strategy.copywriter.settings") as mock_settings:
            mock_settings.openai_enabled = True
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-5.1-chat-latest"
            mock_settings.openai_max_tokens = 512
            mock_settings.openai_temperature = 0.7
            mock_settings.openai_base_url = ""

            with patch("app.services.strategy.copywriter._get_openai_client", return_value=mock_client):
                result = await generate_product_copy(
                    product_name="Test",
                    product_description=None,
                    product_category=None,
                    product_tags=None,
                    brand_name="Brand",
                    brand_voice="bold",
                    brand_tone="energetic",
                    message_angle="benefit",
                    campaign_goal="awareness",
                    num_variants=3,
                )

        assert result is None  # graceful fallback


class TestStrategyEngineWithCopywriter:
    """Verify the strategy engine falls back correctly when OpenAI is off."""

    @pytest.mark.asyncio
    async def test_strategy_uses_templates_when_openai_disabled(self):
        from app.core.enums import CampaignGoal, Platform
        from app.schemas.brand import BrandIdentity, MarketResearch
        from app.schemas.product import ProductInput
        from app.services.strategy.engine import generate_campaign_strategy

        brand = BrandIdentity(
            brand_name="Test",
            colors={"primary": "#FF0000", "secondary": "#00FF00",
                    "background": "#FFFFFF", "text": "#000000"},
            fonts={"heading": "Arial", "body": "Helvetica"},
            industry="skincare",
        )
        market = MarketResearch(saturation_percent=70, competitive_edge_percent=80)
        products = [
            ProductInput(
                product_name="Serum",
                product_image_url="https://example.com/serum.png",
                tags={"is_new": True},
            ),
        ]

        strategy = await generate_campaign_strategy(
            brand=brand, market=market, products=products,
            goal=CampaignGoal.AWARENESS,
            platforms=[Platform.INSTAGRAM_FEED],
            duration=15, product_variants=3, brand_variants=3,
            db=None,
        )

        # Should have template fallback messages (not empty)
        for pp in strategy.product_plans:
            for v in pp.variants:
                assert v.primary_message  # not empty
                assert v.cta_text
                assert v.secondary_message

        for v in strategy.brand_plan.variants:
            assert v.primary_message
            assert v.cta_text
