"""
Celery application factory.

Configures Celery with Redis broker/backend, task routing, retry
behaviour, and serialisation.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "video_ads_engine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Concurrency
    worker_concurrency=settings.worker_concurrency,
    worker_prefetch_multiplier=1,

    # Retry
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Result expiry
    result_expires=86400,  # 24 hours

    # Routing
    task_routes={
        "app.workers.tasks.process_product_video": {"queue": "video_gen"},
        "app.workers.tasks.process_brand_video": {"queue": "video_gen"},
        "app.workers.tasks.run_campaign_pipeline": {"queue": "orchestrator"},
    },

    # Autodiscover
    include=["app.workers.tasks"],
)
