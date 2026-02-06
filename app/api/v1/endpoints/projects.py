"""
Project-scoped endpoints.

GET /projects/{id}/campaigns – list all campaigns for a project
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.campaign import CampaignOut
from app.services.campaign_service import CampaignService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/{project_id}/campaigns", response_model=List[CampaignOut])
async def list_project_campaigns(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List campaigns belonging to *project_id*."""
    svc = CampaignService(db)
    return await svc.list_campaigns(project_id, user.user_id, limit=limit, offset=offset)
