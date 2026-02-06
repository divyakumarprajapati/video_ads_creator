"""
Synchronous / in-process campaign runner.

When ``USE_CELERY=false`` (the default), campaign generation runs in a
background thread inside the API process.  This avoids requiring Redis
and Celery for development or small-scale deployments.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def dispatch_campaign(campaign_id: str) -> None:
    """
    Start campaign generation in a daemon thread.

    The thread runs ``pipeline.run_campaign`` which is the same function
    that Celery tasks wrap, ensuring identical behaviour in both modes.
    """
    t = threading.Thread(
        target=_run_in_thread,
        args=(campaign_id,),
        name=f"campaign-{campaign_id[:8]}",
        daemon=True,
    )
    t.start()
    logger.info("Campaign %s dispatched to background thread", campaign_id)


def _run_in_thread(campaign_id: str) -> None:
    try:
        from app.workers.pipeline import run_campaign
        result = run_campaign(campaign_id)
        logger.info("Campaign %s finished: %s", campaign_id, result.get("status"))
    except Exception:
        logger.exception("Campaign %s failed in background thread", campaign_id)
