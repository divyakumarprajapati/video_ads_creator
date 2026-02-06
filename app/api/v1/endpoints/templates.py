"""
Template endpoints.

GET /templates       – list / filter templates
GET /templates/{id}  – template detail
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.models.campaign import VideoTemplate
from app.schemas.template import TemplateListOut, TemplateOut

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=TemplateListOut)
async def list_templates(
    category: Optional[str] = Query(None),
    visual_style: Optional[str] = Query(None),
    video_style: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    min_duration: Optional[int] = Query(None),
    max_duration: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List available video templates with optional filters."""
    stmt = select(VideoTemplate).where(VideoTemplate.is_active.is_(True))

    if category:
        stmt = stmt.where(VideoTemplate.category == category)
    if min_duration is not None:
        stmt = stmt.where(VideoTemplate.max_duration >= min_duration)
    if max_duration is not None:
        stmt = stmt.where(VideoTemplate.min_duration <= max_duration)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(VideoTemplate.performance_score.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    templates = result.scalars().all()

    # Post-filter for JSONB array fields (visual_style, video_style, industry)
    items: List[TemplateOut] = []
    for t in templates:
        if visual_style and visual_style not in (t.compatible_visual_styles or []):
            continue
        if video_style and video_style not in (t.compatible_video_styles or []):
            continue
        if industry and industry.lower() not in [i.lower() for i in (t.compatible_industries or [])]:
            continue
        items.append(TemplateOut.model_validate(t))

    return TemplateListOut(templates=items, total=total)


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get full details for a single template."""
    result = await db.execute(
        select(VideoTemplate).where(VideoTemplate.id == template_id)
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateOut.model_validate(tpl)
