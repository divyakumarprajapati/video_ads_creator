"""
Asset serving endpoints.

Clients receive relative asset paths in API responses (e.g. thumbnail_path).
This router serves those files from the local asset root.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.services.asset.paths import (
    extract_campaign_id_from_relative_path,
    resolve_local_asset_path,
)
from app.services.campaign_service import CampaignService


router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get("/{relative_path:path}")
async def get_asset(
    relative_path: str,
    download: bool = Query(False, description="Force Content-Disposition: attachment"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Serve an asset file by relative path.

    The *relative_path* must start with one of:
    - ``campaign_<uuid>/...``
    - ``campaigns/<uuid>/...``
    """
    campaign_id = extract_campaign_id_from_relative_path(relative_path)
    if not campaign_id:
        raise HTTPException(
            status_code=400,
            detail="relative_path must start with campaign_<uuid>/... or campaigns/<uuid>/...",
        )

    # Enforce ownership: user can only fetch assets for their campaigns.
    svc = CampaignService(db)
    await svc._get_campaign(campaign_id, user.user_id)

    try:
        path: Path = resolve_local_asset_path(relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")

    media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    # Starlette's FileResponse sets Content-Disposition to attachment when filename is set,
    # so only set it when the client explicitly requests download=true.
    if download:
        filename = path.name
        return FileResponse(
            str(path),
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return FileResponse(str(path), media_type=media_type)
