"""
Unit tests for platform specifications.
"""

from __future__ import annotations

from app.core.enums import Platform
from app.services.strategy.platform_specs import PLATFORM_SPECS, get_platform_spec


class TestPlatformSpecs:
    def test_all_platforms_defined(self):
        for p in Platform:
            assert p in PLATFORM_SPECS

    def test_instagram_feed(self):
        spec = get_platform_spec(Platform.INSTAGRAM_FEED)
        assert spec.width == 1080
        assert spec.height == 1080
        assert spec.aspect_ratio == "1:1"
        assert spec.fps == 30

    def test_tiktok(self):
        spec = get_platform_spec(Platform.TIKTOK)
        assert spec.width == 1080
        assert spec.height == 1920
        assert spec.aspect_ratio == "9:16"

    def test_all_specs_have_h264(self):
        for p in Platform:
            spec = get_platform_spec(p)
            assert spec.codec == "libx264"
