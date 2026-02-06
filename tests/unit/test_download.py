"""
Unit tests for the download / archive service.
"""

from __future__ import annotations

import json
import os

import pytest

from app.services.download import create_campaign_archive, generate_campaign_summary


class TestCampaignSummary:
    def test_generates_summary_json(self, tmp_path):
        base = str(tmp_path)
        cid = "test-campaign-123"
        data = {
            "campaign_name": "Test Campaign",
            "status": "completed",
            "campaign_goal": "awareness",
            "platforms": ["instagram_feed", "tiktok"],
            "products": [
                {"product_name": "Product A", "product_category": "skincare", "generation_status": "completed"},
                {"product_name": "Product B", "product_category": "tech", "generation_status": "completed"},
            ],
            "videos": [
                {"id": "v1", "video_type": "product_specific", "variant_id": 1, "status": "completed", "quality_score": 92.0, "file_path": "/test.mp4", "duration_seconds": 15},
                {"id": "v2", "video_type": "product_specific", "variant_id": 2, "status": "completed", "quality_score": 88.0, "file_path": "/test2.mp4", "duration_seconds": 15},
                {"id": "v3", "video_type": "general_brand", "variant_id": 1, "status": "failed", "quality_score": None, "file_path": None, "duration_seconds": None},
            ],
        }

        path = generate_campaign_summary(base, cid, data)
        assert os.path.isfile(path)

        with open(path) as f:
            summary = json.load(f)

        assert summary["campaign_id"] == cid
        assert summary["total_products"] == 2
        assert summary["total_videos"] == 3
        assert summary["completed_videos"] == 2
        assert summary["failed_videos"] == 1
        assert summary["average_quality_score"] == 90.0
        assert summary["product_specific_videos"] == 2
        assert summary["general_brand_videos"] == 1
        assert len(summary["video_manifest"]) == 3


class TestCampaignArchive:
    def test_returns_none_for_nonexistent(self, tmp_path):
        result = create_campaign_archive(str(tmp_path), "nonexistent")
        assert result is None

    def test_creates_zip(self, tmp_path):
        base = str(tmp_path)
        cid = "zip-test"
        camp_dir = os.path.join(base, f"campaign_{cid}", "product_specific")
        os.makedirs(camp_dir)
        # Create a dummy file
        with open(os.path.join(camp_dir, "test.mp4"), "w") as f:
            f.write("fake video data")

        result = create_campaign_archive(base, cid)
        assert result is not None
        assert result.endswith(".zip")
        assert os.path.isfile(result)

    def test_filter_by_type(self, tmp_path):
        base = str(tmp_path)
        cid = "filter-test"
        # Create both types
        for subdir in ("product_specific/p1", "general_brand/v1"):
            d = os.path.join(base, f"campaign_{cid}", subdir)
            os.makedirs(d)
            with open(os.path.join(d, "video.mp4"), "w") as f:
                f.write("data")

        # Filter product_specific only
        result = create_campaign_archive(base, cid, filter_type="product_specific")
        assert result is not None
        assert "product_specific" in result
