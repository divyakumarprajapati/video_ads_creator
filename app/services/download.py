"""
Download / archive service.

Creates ZIP archives of campaign output for bulk download, with filtering
by video type or platform.
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import List, Optional

from app.core.logging import get_logger
from app.utils.file_utils import campaign_dir, ensure_dir

logger = get_logger(__name__)


def create_campaign_archive(
    base_output: str,
    campaign_id: str,
    *,
    filter_type: Optional[str] = None,
    filter_platform: Optional[str] = None,
) -> Optional[str]:
    """
    Create a ZIP archive of campaign videos.

    Parameters
    ----------
    base_output : str
        Root output directory.
    campaign_id : str
        Campaign UUID string.
    filter_type : str, optional
        ``product_specific`` or ``general_brand`` to include only one type.
    filter_platform : str, optional
        E.g. ``instagram_feed`` to include only that platform's exports.

    Returns
    -------
    str or None
        Path to the generated ZIP file, or None if no files found.
    """
    camp_dir = campaign_dir(base_output, campaign_id)
    if not os.path.isdir(camp_dir):
        return None

    zip_name = f"campaign_{campaign_id}"
    if filter_type:
        zip_name += f"_{filter_type}"
    if filter_platform:
        zip_name += f"_{filter_platform}"
    zip_path = os.path.join(base_output, f"{zip_name}.zip")

    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(camp_dir):
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, base_output)

                # Apply type filter
                if filter_type:
                    if filter_type == "product_specific" and "/general_brand/" in rel:
                        continue
                    if filter_type == "general_brand" and "/product_specific/" in rel:
                        continue

                # Apply platform filter
                if filter_platform:
                    # Only include files that match the platform name or are metadata
                    base = os.path.basename(fname)
                    is_platform_match = base.startswith(filter_platform)
                    is_metadata = base == "metadata.json"
                    is_thumbnail = base.endswith("_thumb.jpg") and filter_platform in base
                    if not (is_platform_match or is_metadata or is_thumbnail):
                        continue

                zf.write(full, rel)
                count += 1

    if count == 0:
        os.unlink(zip_path)
        return None

    logger.info("archive_created", path=zip_path, files=count)
    return zip_path


def generate_campaign_summary(
    base_output: str,
    campaign_id: str,
    campaign_data: dict,
) -> str:
    """
    Write ``campaign_summary.json`` into the campaign output directory.

    Contains high-level stats: products, videos, quality scores, platforms.
    """
    camp_dir = campaign_dir(base_output, campaign_id)
    ensure_dir(camp_dir)
    summary_path = os.path.join(camp_dir, "campaign_summary.json")

    products = campaign_data.get("products", [])
    videos = campaign_data.get("videos", [])

    completed = [v for v in videos if v.get("status") == "completed"]
    failed = [v for v in videos if v.get("status") == "failed"]

    scores = [v.get("quality_score", 0) for v in completed if v.get("quality_score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    product_specific = [v for v in videos if v.get("video_type") == "product_specific"]
    general_brand = [v for v in videos if v.get("video_type") == "general_brand"]

    # Static ads
    static_ads = campaign_data.get("static_ads", [])
    completed_static = [sa for sa in static_ads if sa.get("status") == "completed"]
    failed_static = [sa for sa in static_ads if sa.get("status") == "failed"]

    summary = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_data.get("campaign_name", ""),
        "status": campaign_data.get("status", "unknown"),
        "total_products": len(products),
        "total_videos": len(videos),
        "product_specific_videos": len(product_specific),
        "general_brand_videos": len(general_brand),
        "completed_videos": len(completed),
        "failed_videos": len(failed),
        "average_quality_score": avg_score,
        "total_static_ads": len(static_ads),
        "completed_static_ads": len(completed_static),
        "failed_static_ads": len(failed_static),
        "platforms": campaign_data.get("platforms", []),
        "campaign_goal": campaign_data.get("campaign_goal", ""),
        "products": [
            {
                "product_name": p.get("product_name"),
                "product_category": p.get("product_category"),
                "status": p.get("generation_status"),
            }
            for p in products
        ],
        "video_manifest": [
            {
                "video_id": str(v.get("id", "")),
                "video_type": v.get("video_type"),
                "variant_id": v.get("variant_id"),
                "status": v.get("status"),
                "quality_score": v.get("quality_score"),
                "file_path": v.get("file_path"),
                "duration_seconds": v.get("duration_seconds"),
            }
            for v in videos
        ],
        "static_ad_manifest": [
            {
                "ad_id": str(sa.get("id", "")),
                "ad_type": sa.get("ad_type"),
                "variant_id": sa.get("variant_id"),
                "static_template_id": sa.get("static_template_id"),
                "status": sa.get("status"),
                "quality_score": sa.get("quality_score"),
                "file_path": sa.get("file_path"),
            }
            for sa in static_ads
        ],
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info("campaign_summary_written", path=summary_path)
    return summary_path
