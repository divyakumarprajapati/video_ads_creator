"""
Asset path helpers.

We store and generate assets on disk (local backend) and sometimes persist
absolute filesystem paths in the DB. API responses should expose *relative*
paths so clients can request files via the assets endpoint without leaking
server filesystem layout.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Optional

from app.core.config import get_settings


_CAMPAIGN_PREFIX_RE = re.compile(
    r"^(?:campaign_(?P<a>[0-9a-fA-F-]{36})(?:/|$)|campaigns/(?P<b>[0-9a-fA-F-]{36})(?:/|$))"
)


def get_asset_root() -> str:
    """
    Root directory that contains generated output on disk.

    Mirrors the worker/pipeline defaulting logic:
    - VIDEO_OUTPUT_DIR env overrides everything
    - local backend uses settings.local_storage_root
    - otherwise fall back to /tmp/video_ads_output
    """
    settings = get_settings()
    env = os.environ.get("VIDEO_OUTPUT_DIR")
    if env:
        return os.path.abspath(env)
    if settings.storage_backend == "local":
        return os.path.abspath(settings.local_storage_root)
    return os.path.abspath("/tmp/video_ads_output")


def extract_campaign_id_from_relative_path(relative_path: str) -> Optional[uuid.UUID]:
    """
    If *relative_path* begins with campaign-scoped prefixes, return the campaign UUID.

    Supports:
    - campaign_<uuid>/...
    - campaigns/<uuid>/...
    """
    p = (relative_path or "").lstrip("/").replace("\\", "/")
    m = _CAMPAIGN_PREFIX_RE.match(p)
    if not m:
        return None
    raw = m.group("a") or m.group("b")
    try:
        return uuid.UUID(str(raw))
    except Exception:
        return None


def to_relative_asset_path(path: str | None) -> str | None:
    """
    Convert an absolute filesystem path into a safe relative asset path.

    If conversion isn't possible, returns a best-effort relative fallback.
    """
    if not path:
        return None

    # Normalize for output (API), keep it simple and URL-friendly.
    p = str(path).replace("\\", "/")
    if not os.path.isabs(p):
        return p.lstrip("/")

    root = get_asset_root().replace("\\", "/")
    try:
        rel = os.path.relpath(p, root).replace("\\", "/")
        # Only accept if it stays within root.
        if rel != "." and not rel.startswith("../") and not rel.startswith("..\\") and ".." not in rel.split("/"):
            return rel.lstrip("/")
    except Exception:
        pass

    # Fallback: strip everything before known campaign prefixes.
    for marker in ("/campaign_", "/campaigns/"):
        idx = p.rfind(marker)
        if idx != -1:
            return p[idx + 1 :].lstrip("/")

    # Last resort: just return the filename (still relative).
    return os.path.basename(p)


def resolve_local_asset_path(relative_path: str) -> Path:
    """
    Resolve a relative asset path to an absolute on-disk path under asset root.

    Raises ValueError for invalid/traversal attempts.
    """
    if not relative_path:
        raise ValueError("Missing relative_path")

    rel = str(relative_path).replace("\\", "/").lstrip("/")
    if "\x00" in rel:
        raise ValueError("Invalid path")

    # Quick reject obvious traversal attempts before resolve().
    parts = [p for p in rel.split("/") if p]
    if any(p in (".", "..") for p in parts):
        raise ValueError("Path traversal not allowed")

    root = Path(get_asset_root()).resolve()
    candidate = (root / rel).resolve()

    # Ensure candidate is within root
    if candidate == root or root not in candidate.parents:
        raise ValueError("Path is outside asset root")

    return candidate
