"""
Unit tests for the Strategy Engine – pure logic, no DB, no network.
"""

from __future__ import annotations

import pytest

from app.core.enums import (
    CampaignGoal,
    MarketSaturation,
    MessageAngle,
    Platform,
    VisualStyle,
    VideoStyle,
)
from app.schemas.brand import BrandIdentity, MarketResearch
from app.schemas.product import ProductInput
from app.services.strategy.decision_matrices import (
    resolve_brand_primary_message,
    resolve_cta,
    resolve_layout_type,
    resolve_message_angles,
    resolve_pacing,
    resolve_product_primary_message,
    resolve_secondary_message,
    resolve_video_style,
    resolve_visual_style,
)
from app.services.strategy.engine import generate_campaign_strategy


class TestVisualStyleResolution:
    def test_high_saturation_high_edge(self):
        style = resolve_visual_style(MarketSaturation.HIGH, 80.0)
        assert style == VisualStyle.BOLD_VIBRANT

    def test_low_saturation_low_edge(self):
        style = resolve_visual_style(MarketSaturation.LOW, 20.0)
        assert style == VisualStyle.MINIMALIST

    def test_medium_saturation_mid_edge(self):
        style = resolve_visual_style(MarketSaturation.MEDIUM, 55.0)
        assert style == VisualStyle.ELEGANT


class TestMessageAngles:
    def test_awareness_priorities(self):
        angles = resolve_message_angles(CampaignGoal.AWARENESS, 3)
        assert angles[0] == MessageAngle.BENEFIT
        assert len(angles) == 3

    def test_conversion_priorities(self):
        angles = resolve_message_angles(CampaignGoal.CONVERSION, 3)
        assert angles[0] == MessageAngle.URGENCY

    def test_cycling(self):
        angles = resolve_message_angles(CampaignGoal.AWARENESS, 5)
        assert len(angles) == 5


class TestPacing:
    def test_bold_vibrant_is_fast(self):
        label, secs = resolve_pacing(VisualStyle.BOLD_VIBRANT)
        assert label == "fast"
        assert secs == 2.0

    def test_elegant_is_slow(self):
        label, secs = resolve_pacing(VisualStyle.ELEGANT)
        assert label == "slow"
        assert secs == 4.0


class TestCTA:
    def test_awareness_product(self):
        cta = resolve_cta(CampaignGoal.AWARENESS, is_brand=False, variant_idx=0)
        assert "Discover" in cta or "Learn" in cta or "See" in cta

    def test_conversion_brand(self):
        cta = resolve_cta(CampaignGoal.CONVERSION, is_brand=True, variant_idx=0)
        assert len(cta) > 0


class TestVideoStyle:
    def test_skincare_category(self):
        assert resolve_video_style("skincare") == VideoStyle.LIFESTYLE_SCENE

    def test_tech_category(self):
        assert resolve_video_style("tech") == VideoStyle.PRODUCT_HERO

    def test_unknown_category(self):
        assert resolve_video_style("unknown") == VideoStyle.PRODUCT_HERO

    def test_none_category(self):
        assert resolve_video_style(None) == VideoStyle.PRODUCT_HERO


class TestProductMessage:
    def test_new_product(self):
        msg = resolve_product_primary_message({"is_new": True}, 0)
        assert msg in ("Just Dropped", "New Arrival", "Fresh In")

    def test_bestseller(self):
        msg = resolve_product_primary_message({"is_bestseller": True}, 0)
        assert msg in ("Fan Favorite", "#1 Bestseller", "Most Loved")

    def test_default(self):
        msg = resolve_product_primary_message({}, 0)
        assert msg in ("Check This Out", "Spotlight", "Featured")


class TestLayoutType:
    def test_single_product(self):
        layout = resolve_layout_type(1, 0)
        assert layout.value == "hero_supporting"

    def test_many_products(self):
        layout = resolve_layout_type(20, 0)
        assert layout.value in ("sequential_carousel", "lifestyle_montage", "hero_supporting")


class TestStrategyEngineIntegration:
    @pytest.mark.asyncio
    async def test_full_strategy_no_db(self):
        brand = BrandIdentity(
            brand_name="Test",
            colors={"primary": "#FF0000", "secondary": "#00FF00",
                    "background": "#FFFFFF", "text": "#000000"},
            fonts={"heading": "Arial", "body": "Helvetica"},
            industry="skincare",
        )
        market = MarketResearch(
            saturation_percent=70, competitive_edge_percent=80, sentiment="positive",
        )
        products = [
            ProductInput(
                product_name=f"Product {i}",
                product_image_url=f"https://example.com/{i}.png",
                product_category="skincare",
                tags={"is_new": i % 2 == 0},
            )
            for i in range(5)
        ]

        strategy = await generate_campaign_strategy(
            brand=brand, market=market, products=products,
            goal=CampaignGoal.AWARENESS,
            platforms=[Platform.INSTAGRAM_FEED, Platform.TIKTOK],
            duration=15, product_variants=3, brand_variants=3,
            db=None,
        )

        # Verify structure
        assert strategy.visual_style is not None
        assert strategy.pacing in ("fast", "medium", "slow")
        assert len(strategy.product_plans) == 5
        assert len(strategy.brand_plan.variants) == 3
        assert strategy.total_videos == 5 * 3 + 3  # 18

        # Verify each product plan
        for pp in strategy.product_plans:
            assert len(pp.variants) == 3
            for v in pp.variants:
                assert v.primary_message
                assert v.cta_text
                assert v.message_angle

        # Verify brand plan
        assert len(strategy.brand_plan.layout_types) == 3
        assert len(strategy.brand_plan.products_shown) == 5

    @pytest.mark.asyncio
    async def test_single_product_campaign(self):
        brand = BrandIdentity(
            brand_name="Solo",
            colors={"primary": "#000", "secondary": "#FFF",
                    "background": "#FFF", "text": "#000"},
            fonts={"heading": "Mono", "body": "Mono"},
        )
        market = MarketResearch(saturation_percent=20, competitive_edge_percent=30)
        products = [
            ProductInput(product_name="Solo Item", product_image_url="https://example.com/solo.png"),
        ]

        strategy = await generate_campaign_strategy(
            brand=brand, market=market, products=products,
            goal=CampaignGoal.CONVERSION,
            platforms=[Platform.INSTAGRAM_FEED],
            duration=10, product_variants=2, brand_variants=2,
            db=None,
        )

        assert strategy.total_videos == 1 * 2 + 2  # 4
        assert len(strategy.product_plans) == 1
        assert strategy.product_plans[0].variants[0].message_angle == "urgency"

    @pytest.mark.asyncio
    async def test_large_campaign_100_products(self):
        brand = BrandIdentity(
            brand_name="Mega",
            colors={"primary": "#123", "secondary": "#456",
                    "background": "#FFF", "text": "#000"},
            fonts={"heading": "Big", "body": "Small"},
        )
        market = MarketResearch(saturation_percent=90, competitive_edge_percent=50)
        products = [
            ProductInput(
                product_name=f"Product {i}",
                product_image_url=f"https://example.com/{i}.png",
            )
            for i in range(100)
        ]

        strategy = await generate_campaign_strategy(
            brand=brand, market=market, products=products,
            goal=CampaignGoal.AWARENESS,
            platforms=[Platform.INSTAGRAM_FEED, Platform.TIKTOK, Platform.YOUTUBE_SHORTS],
            duration=15, product_variants=3, brand_variants=3,
            db=None,
        )

        assert strategy.total_videos == 100 * 3 + 3  # 303
        assert len(strategy.product_plans) == 100
