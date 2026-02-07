"""
Asset serving endpoints.

Clients receive relative asset paths in API responses (e.g. thumbnail_path).
This router serves those files from the local asset root.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.services.asset.paths import resolve_local_asset_path


router = APIRouter(prefix="/assets", tags=["Assets"])

def _serve_asset(relative_path: str, *, download: bool) -> FileResponse:
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


@router.get("")
async def get_asset_by_query(
    relative_path: str = Query(..., description="Relative path under the asset root"),
    download: bool = Query(False, description="Force Content-Disposition: attachment"),
):
    """Serve an asset by query parameter (no authentication required)."""
    return _serve_asset(relative_path, download=download)


@router.get("/{relative_path:path}")
async def get_asset(
    relative_path: str,
    download: bool = Query(False, description="Force Content-Disposition: attachment"),
):
    """Serve an asset by path parameter (no authentication required)."""
    return _serve_asset(relative_path, download=download)
