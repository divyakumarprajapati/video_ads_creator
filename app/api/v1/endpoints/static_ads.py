"""
Single static ad endpoint.

POST /static-ads – generate one static ad synchronously.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import CurrentUser, get_current_user
from app.schemas.static_ad import SingleStaticAdCreate, SingleStaticAdOut
from app.services.asset.paths import get_asset_root, to_relative_asset_path
from app.services.static_ad.single_service import SingleStaticAdService

router = APIRouter(prefix="/static-ads", tags=["Static Ads"])

BASE_OUTPUT = get_asset_root()


@router.post("", response_model=SingleStaticAdOut, status_code=201)
async def create_single_static_ad(
    payload: SingleStaticAdCreate,
    user: CurrentUser = Depends(get_current_user),
):
    """Generate a single static ad from a user prompt and optional image."""
    svc = SingleStaticAdService(output_root=BASE_OUTPUT)
    result = await svc.create_single_ad(payload, user.user_id)
    if not result:
        raise HTTPException(status_code=500, detail="Static ad generation failed")

    return SingleStaticAdOut(
        ad_id=uuid.UUID(result["ad_id"]),
        ad_type=result["ad_type"],
        status=result["status"],
        prompt=result["prompt"],
        headline=result["headline"],
        subheading=result.get("subheading"),
        cta_text=result.get("cta_text"),
        body_text=result.get("body_text"),
        image_url=result.get("image_url"),
        file_path=to_relative_asset_path(result.get("file_path")),
        thumbnail_path=to_relative_asset_path(result.get("thumbnail_path")),
        file_url=result.get("file_url"),
        thumbnail_url=result.get("thumbnail_url"),
        file_size_mb=result.get("file_size_mb"),
        width=result.get("width"),
        height=result.get("height"),
    )
