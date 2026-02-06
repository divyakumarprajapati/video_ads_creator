"""
Unit tests for domain enums.
"""

from __future__ import annotations

from app.core.enums import (
    CampaignGoal,
    CampaignStatus,
    LayoutType,
    MarketSaturation,
    MessageAngle,
    Platform,
    TemplateCategory,
    VariantType,
    VideoStatus,
    VideoStyle,
    VideoType,
    VisualStyle,
)


class TestEnumValues:
    def test_campaign_status_values(self):
        assert CampaignStatus.DRAFT.value == "draft"
        assert CampaignStatus.COMPLETED.value == "completed"

    def test_platform_values(self):
        assert len(Platform) == 5
        assert Platform.INSTAGRAM_FEED.value == "instagram_feed"

    def test_video_type(self):
        assert VideoType.PRODUCT_SPECIFIC.value == "product_specific"
        assert VideoType.GENERAL_BRAND.value == "general_brand"

    def test_visual_styles(self):
        assert len(VisualStyle) == 6

    def test_layout_types(self):
        assert len(LayoutType) == 4

    def test_message_angles(self):
        assert len(MessageAngle) == 3
