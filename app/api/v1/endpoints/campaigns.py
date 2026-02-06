"""
Campaign endpoints.

POST /campaigns              – create a multi-product campaign
GET  /campaigns/{id}/status  – lightweight progress poll
GET  /campaigns/{id}/results – full results with video links
POST /campaigns/{id}/regenerate – re-run selected videos
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
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

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


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
