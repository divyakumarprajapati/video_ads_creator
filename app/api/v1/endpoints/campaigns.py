"""
Campaign endpoints.

POST /campaigns                  – create a multi-product campaign
GET  /campaigns/{id}/status      – lightweight progress poll
GET  /campaigns/{id}/results     – full results with video links
GET  /campaigns/{id}/download    – download campaign archive (ZIP)
POST /campaigns/{id}/regenerate  – re-run selected videos
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.campaign import (
    CampaignCreate,
    CampaignOut,
    CampaignResultsOut,
    CampaignStatusOut,
    RegenerateRequest,
)
from app.services.campaign_service import CampaignService
from app.services.download import create_campaign_archive

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

BASE_OUTPUT = os.environ.get("VIDEO_OUTPUT_DIR", "/tmp/video_ads_output")


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Create a new multi-product video campaign.

    Accepts brand identity, market research, and 1–N products.
    Returns immediately with campaign metadata; video generation
    proceeds asynchronously in the background.
    """
    svc = CampaignService(db)
    return await svc.create_campaign(payload, user.user_id)


@router.get("/{campaign_id}/status", response_model=CampaignStatusOut)
async def get_campaign_status(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Poll campaign generation progress.  Light endpoint for frequent calls."""
    svc = CampaignService(db)
    return await svc.get_campaign_status(campaign_id, user.user_id)


@router.get("/{campaign_id}/results", response_model=CampaignResultsOut)
async def get_campaign_results(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Retrieve completed videos, exports, quality scores, and download links."""
    svc = CampaignService(db)
    return await svc.get_campaign_results(campaign_id, user.user_id)


@router.get("/{campaign_id}/download")
async def download_campaign(
    campaign_id: uuid.UUID,
    type: str = Query(None, description="Filter: product_specific | general_brand"),
    platform: str = Query(None, description="Filter: instagram_feed | tiktok | etc."),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Download a ZIP archive of the campaign's generated videos.

    Supports filtering:
    - ``?type=product_specific`` – only product-specific videos
    - ``?type=general_brand``    – only general brand videos
    - ``?platform=tiktok``       – only TikTok exports
    - Combine filters: ``?type=product_specific&platform=instagram_feed``
    """
    # Verify campaign ownership
    svc = CampaignService(db)
    await svc._get_campaign(campaign_id, user.user_id)

    zip_path = create_campaign_archive(
        BASE_OUTPUT,
        str(campaign_id),
        filter_type=type,
        filter_platform=platform,
    )
    if not zip_path or not os.path.isfile(zip_path):
        raise HTTPException(
            status_code=404,
            detail="No videos available for download yet. Check campaign status.",
        )

    filename = os.path.basename(zip_path)
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{campaign_id}/regenerate")
async def regenerate_videos(
    campaign_id: uuid.UUID,
    payload: RegenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Re-queue specific videos for regeneration (e.g. after QA failure)."""
    svc = CampaignService(db)
    return await svc.regenerate_videos(campaign_id, payload.video_ids, user.user_id)
