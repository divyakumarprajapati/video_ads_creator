"""
Celery task definitions.

These are **thin wrappers** around the functions in ``pipeline.py``.
Only loaded when ``USE_CELERY=true``.
"""

from __future__ import annotations

from typing import Dict, List

from app.core.config import get_settings
from app.workers.celery_app import celery_app

settings = get_settings()

if celery_app is not None:
    # ── Celery mode ────────────────────────────────────────

    from celery import group as celery_group

    @celery_app.task(bind=True, name="app.workers.tasks.process_product_video",
                     max_retries=2, default_retry_delay=30, acks_late=True)
    def process_product_video(self, campaign_id, product_id, product_data,
                              video_records, brand_identity, platforms, duration):
        from app.workers.pipeline import process_product_videos
        return process_product_videos(
            campaign_id, product_id, product_data,
            video_records, brand_identity, platforms, duration,
        )

    @celery_app.task(bind=True, name="app.workers.tasks.process_brand_video",
                     max_retries=2, default_retry_delay=30, acks_late=True)
    def process_brand_video(self, campaign_id, product_composites,
                            video_records, brand_identity, platforms, duration):
        from app.workers.pipeline import process_brand_videos
        return process_brand_videos(
            campaign_id, product_composites,
            video_records, brand_identity, platforms, duration,
        )

    @celery_app.task(bind=True, name="app.workers.tasks.run_campaign_pipeline",
                     max_retries=1, acks_late=True)
    def run_campaign_pipeline(self, campaign_id: str) -> Dict:
        from app.workers.pipeline import run_campaign
        return run_campaign(campaign_id)
