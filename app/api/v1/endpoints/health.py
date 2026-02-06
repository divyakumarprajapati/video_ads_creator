"""
Health / readiness probes.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    """Basic readiness – extend to check DB / Redis connectivity."""
    return {"status": "ready"}
