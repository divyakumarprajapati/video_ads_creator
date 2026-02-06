"""
Health / readiness probes and Prometheus metrics.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    """Basic readiness – extend to check DB / Redis connectivity."""
    return {"status": "ready"}


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Expose Prometheus-compatible metrics.

    In production, wire this up to ``prometheus_client`` collectors
    for request counts, latencies, queue depth, GPU utilisation, etc.
    """
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return PlainTextResponse(
            content=generate_latest().decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )
    except ImportError:
        # prometheus_client not installed – return stub
        return PlainTextResponse(
            content="# Prometheus client not installed. pip install prometheus-client\n",
            media_type="text/plain",
        )
