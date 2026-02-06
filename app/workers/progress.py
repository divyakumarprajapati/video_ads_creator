"""
Progress tracking via Redis.

Workers publish progress updates; the API layer reads them for real-time
status polling.  All data is stored in Redis hashes with campaign-scoped keys.
"""

from __future__ import annotations

import json
from typing import Dict, Optional

import redis

from app.core.config import get_settings

settings = get_settings()

_redis: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _campaign_key(campaign_id: str) -> str:
    return f"campaign:{campaign_id}:progress"


def _video_key(campaign_id: str, video_id: str) -> str:
    return f"campaign:{campaign_id}:video:{video_id}"


# ── Write (from workers) ──────────────────────────────────

def update_campaign_progress(campaign_id: str, progress: float, status: str) -> None:
    r = _get_redis()
    r.hset(_campaign_key(campaign_id), mapping={
        "progress": str(progress),
        "status": status,
    })
    r.expire(_campaign_key(campaign_id), 86400)


def update_video_progress(
    campaign_id: str,
    video_id: str,
    progress: float,
    status: str,
    quality_score: Optional[float] = None,
) -> None:
    r = _get_redis()
    data: Dict[str, str] = {
        "progress": str(progress),
        "status": status,
    }
    if quality_score is not None:
        data["quality_score"] = str(quality_score)
    r.hset(_video_key(campaign_id, video_id), mapping=data)
    r.expire(_video_key(campaign_id, video_id), 86400)


# ── Read (from API) ───────────────────────────────────────

def get_campaign_progress(campaign_id: str) -> Dict:
    r = _get_redis()
    data = r.hgetall(_campaign_key(campaign_id))
    return {
        "progress": float(data.get("progress", 0)),
        "status": data.get("status", "unknown"),
    }


def get_video_progress(campaign_id: str, video_id: str) -> Dict:
    r = _get_redis()
    data = r.hgetall(_video_key(campaign_id, video_id))
    return {
        "progress": float(data.get("progress", 0)),
        "status": data.get("status", "unknown"),
        "quality_score": float(data["quality_score"]) if "quality_score" in data else None,
    }
