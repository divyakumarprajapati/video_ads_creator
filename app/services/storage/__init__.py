"""
Storage abstraction.

Usage::

    from app.services.storage import get_storage
    storage = get_storage()
    storage.upload_file("/tmp/video.mp4", "campaigns/123/video.mp4")
"""

from __future__ import annotations

from app.core.config import get_settings


def get_storage():
    """Return the configured storage backend (local, S3, or GCS)."""
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.services.storage.s3 import S3Storage
        return S3Storage()
    if settings.storage_backend == "gcs":
        from app.services.storage.gcs import GCSStorage
        return GCSStorage()
    else:
        from app.services.storage.local import LocalStorage
        return LocalStorage()
