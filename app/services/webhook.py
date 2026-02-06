"""
Webhook notification service.

Fires HTTP callbacks when campaign events occur (completed, failed,
video available).  Failures are logged but never block the pipeline.
"""

from __future__ import annotations

import json
from typing import Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default timeout for webhook delivery
WEBHOOK_TIMEOUT = 10  # seconds
WEBHOOK_MAX_RETRIES = 3


async def send_webhook(
    url: str,
    event: str,
    payload: dict,
    *,
    secret: Optional[str] = None,
) -> bool:
    """
    POST a JSON payload to *url*.

    Parameters
    ----------
    url : str
        Webhook endpoint URL.
    event : str
        Event type, e.g. ``campaign.completed``, ``video.available``.
    payload : dict
        Event data.
    secret : str, optional
        HMAC secret for signing (sent as ``X-Webhook-Secret`` header).

    Returns
    -------
    bool
        ``True`` if the webhook was delivered successfully.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
    }
    if secret:
        headers["X-Webhook-Secret"] = secret

    body = {"event": event, "data": payload}

    for attempt in range(1, WEBHOOK_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=WEBHOOK_TIMEOUT,
                )
                if resp.status_code < 300:
                    logger.info("webhook_delivered", webhook_event=event, url=url, status_code=resp.status_code)
                    return True
                logger.warning(
                    "webhook_non_2xx",
                    webhook_event=event, url=url,
                    status_code=resp.status_code, attempt=attempt,
                )
        except Exception as exc:
            logger.warning(
                "webhook_delivery_failed",
                webhook_event=event, url=url, error=str(exc), attempt=attempt,
            )

    logger.error("webhook_exhausted_retries", webhook_event=event, url=url)
    return False


def send_webhook_sync(
    url: str,
    event: str,
    payload: dict,
    *,
    secret: Optional[str] = None,
) -> bool:
    """Synchronous variant for use inside Celery workers."""
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
    }
    if secret:
        headers["X-Webhook-Secret"] = secret

    body = {"event": event, "data": payload}

    for attempt in range(1, WEBHOOK_MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                url, json=body, headers=headers, timeout=WEBHOOK_TIMEOUT,
            )
            if resp.status_code < 300:
                logger.info("webhook_delivered", webhook_event=event, url=url, status_code=resp.status_code)
                return True
        except Exception as exc:
            logger.warning("webhook_delivery_failed", webhook_event=event, error=str(exc), attempt=attempt)

    return False
