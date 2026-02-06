"""
Template selection service.

Given a creative brief (visual style, video style, duration, aspect ratios),
score all compatible templates and return the top-N candidates.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VideoStyle, VisualStyle
from app.models.campaign import VideoTemplate


async def select_templates(
    db: AsyncSession,
    *,
    visual_style: VisualStyle,
    video_style: VideoStyle,
    duration: int,
    aspect_ratios: List[str],
    industry: Optional[str] = None,
    limit: int = 3,
) -> List[VideoTemplate]:
    """
    Return the best-matching active templates sorted by composite score.

    Scoring (deterministic, no ML):
      +30  visual style match
      +30  video style match
      +10  industry match
      +10  aspect ratio overlap
      +20  performance_score (normalised to 0-20)
    """

    stmt = (
        select(VideoTemplate)
        .where(VideoTemplate.is_active.is_(True))
        .where(VideoTemplate.min_duration <= duration)
        .where(VideoTemplate.max_duration >= duration)
    )
    result = await db.execute(stmt)
    candidates: List[VideoTemplate] = list(result.scalars().all())

    if not candidates:
        # Fallback: relax duration filter
        stmt = select(VideoTemplate).where(VideoTemplate.is_active.is_(True))
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())

    scored: list[tuple[float, VideoTemplate]] = []
    for tpl in candidates:
        score = 0.0
        # Visual style
        if visual_style.value in (tpl.compatible_visual_styles or []):
            score += 30
        # Video style
        if video_style.value in (tpl.compatible_video_styles or []):
            score += 30
        # Industry
        if industry and industry.lower() in [i.lower() for i in (tpl.compatible_industries or [])]:
            score += 10
        # Aspect ratio overlap
        tpl_ratios = set(tpl.supported_aspect_ratios or [])
        if tpl_ratios.intersection(set(aspect_ratios)):
            score += 10
        # Performance
        score += (tpl.performance_score or 0) / 5.0  # 0-100 → 0-20
        scored.append((score, tpl))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [tpl for _, tpl in scored[:limit]]
