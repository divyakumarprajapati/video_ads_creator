"""
Progress tracking.

Two backends:
  - **In-memory dict** (default) – zero dependencies, works everywhere.
  - **Redis**          – when ``REDIS_ENABLED=true``, uses Redis hashes for
                         cross-process visibility.

Workers write updates; the API layer reads them for real-time polling.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional

from app.core.config import get_settings

settings = get_settings()

# ────────────────────────────────────────────────────────────
#  In-memory store (thread-safe)
# ────────────────────────────────────────────────────────────

_lock = threading.Lock()
_campaigns: Dict[str, Dict[str, str]] = {}
_videos: Dict[str, Dict[str, str]] = {}


def _campaign_mem_key(campaign_id: str) -> str:
    return campaign_id


def _video_mem_key(campaign_id: str, video_id: str) -> str:
    return f"{campaign_id}:{video_id}"


# ────────────────────────────────────────────────────────────
#  Optional Redis
# ────────────────────────────────────────────────────────────

_redis = None


def _get_redis():
    global _redis
    if not settings.redis_enabled:
        return None
    if _redis is None:
        try:
            import redis as _r
            _redis = _r.from_url(settings.redis_url, decode_responses=True)
            _redis.ping()
        except Exception:
            _redis = None
    return _redis


def _campaign_redis_key(campaign_id: str) -> str:
    return f"campaign:{campaign_id}:progress"


def _video_redis_key(campaign_id: str, video_id: str) -> str:
    return f"campaign:{campaign_id}:video:{video_id}"


# ────────────────────────────────────────────────────────────
#  Write (from workers)
# ────────────────────────────────────────────────────────────

def update_campaign_progress(
    campaign_id: str,
    progress: float,
    status: str,
    eta_seconds: Optional[float] = None,
) -> None:
    data = {"progress": str(progress), "status": status}
    if eta_seconds is not None:
        data["eta_seconds"] = str(eta_seconds)

    r = _get_redis()
    if r is not None:
        try:
            r.hset(_campaign_redis_key(campaign_id), mapping=data)
            r.expire(_campaign_redis_key(campaign_id), 86400)
            return
        except Exception:
            pass

    with _lock:
        _campaigns[_campaign_mem_key(campaign_id)] = data


def update_video_progress(
    campaign_id: str,
    video_id: str,
    progress: float,
    status: str,
    quality_score: Optional[float] = None,
) -> None:
    data: Dict[str, str] = {"progress": str(progress), "status": status}
    if quality_score is not None:
        data["quality_score"] = str(quality_score)

    r = _get_redis()
    if r is not None:
        try:
            r.hset(_video_redis_key(campaign_id, video_id), mapping=data)
            r.expire(_video_redis_key(campaign_id, video_id), 86400)
            return
        except Exception:
            pass

    with _lock:
        _videos[_video_mem_key(campaign_id, video_id)] = data


# ────────────────────────────────────────────────────────────
#  Read (from API)
# ────────────────────────────────────────────────────────────

def get_campaign_progress(campaign_id: str) -> Dict:
    r = _get_redis()
    if r is not None:
        try:
            data = r.hgetall(_campaign_redis_key(campaign_id))
            if data:
                return {
                    "progress": float(data.get("progress", 0)),
                    "status": data.get("status", "unknown"),
                }
        except Exception:
            pass

    with _lock:
        data = _campaigns.get(_campaign_mem_key(campaign_id), {})
    return {
        "progress": float(data.get("progress", 0)),
        "status": data.get("status", "unknown"),
    }


def get_video_progress(campaign_id: str, video_id: str) -> Dict:
    r = _get_redis()
    if r is not None:
        try:
            data = r.hgetall(_video_redis_key(campaign_id, video_id))
            if data:
                return {
                    "progress": float(data.get("progress", 0)),
                    "status": data.get("status", "unknown"),
                    "quality_score": float(data["quality_score"]) if "quality_score" in data else None,
                }
        except Exception:
            pass

    with _lock:
        data = _videos.get(_video_mem_key(campaign_id, video_id), {})
    return {
        "progress": float(data.get("progress", 0)),
        "status": data.get("status", "unknown"),
        "quality_score": float(data["quality_score"]) if "quality_score" in data else None,
    }
