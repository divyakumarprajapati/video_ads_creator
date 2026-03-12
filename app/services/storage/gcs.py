"""
GCS Storage Service.

Wraps google-cloud-storage for uploading, downloading, generating signed URLs,
and managing campaign file trees in Google Cloud Storage.
"""

from __future__ import annotations

import json
import mimetypes
import os
from datetime import timedelta
from typing import List

from google.cloud import storage
from google.oauth2 import service_account

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GCSStorage:
    """Thin wrapper around google-cloud-storage client."""

    def __init__(self):
        creds = None
        if settings.gcs_credentials_json:
            info = json.loads(settings.gcs_credentials_json)
            creds = service_account.Credentials.from_service_account_info(info)

        self._client = storage.Client(
            project=settings.gcs_project or None,
            credentials=creds,
        )
        self.bucket = settings.gcs_bucket_name
        self._bucket = self._client.bucket(self.bucket)

    # ── Ensure bucket ──────────────────────────────────────

    def ensure_bucket(self) -> None:
        existing = self._client.lookup_bucket(self.bucket)
        if existing is None:
            self._client.create_bucket(self.bucket, location=settings.gcs_location)
            logger.info("gcs_bucket_created", bucket=self.bucket, location=settings.gcs_location)
        else:
            self._bucket = existing

    # ── Upload ─────────────────────────────────────────────

    def upload_file(self, local_path: str, key: str) -> str:
        content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
        blob = self._bucket.blob(key)
        blob.upload_from_filename(local_path, content_type=content_type)
        if settings.gcs_make_public:
            blob.make_public()
        url = self.public_url(key)
        logger.info("gcs_uploaded", key=key)
        return url

    def upload_directory(self, local_dir: str, prefix: str) -> List[str]:
        urls: List[str] = []
        for root, _, files in os.walk(local_dir):
            for fname in files:
                local = os.path.join(root, fname)
                relative = os.path.relpath(local, local_dir)
                key = f"{prefix}/{relative}"
                urls.append(self.upload_file(local, key))
        return urls

    # ── Download ───────────────────────────────────────────

    def download_file(self, key: str, local_path: str) -> str:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob = self._bucket.blob(key)
        blob.download_to_filename(local_path)
        return local_path

    # ── URLs ───────────────────────────────────────────────

    def presigned_url(self, key: str, expires_in: int = 3600) -> str:
        blob = self._bucket.blob(key)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_in),
            method="GET",
        )

    def public_url(self, key: str) -> str:
        base = (settings.gcs_public_url or f"https://storage.googleapis.com/{self.bucket}").rstrip("/")
        return f"{base}/{key}"

    # ── Delete ─────────────────────────────────────────────

    def delete_key(self, key: str) -> None:
        blob = self._bucket.blob(key)
        blob.delete()

    def delete_prefix(self, prefix: str) -> int:
        count = 0
        for blob in self._client.list_blobs(self.bucket, prefix=prefix):
            blob.delete()
            count += 1
        return count

    # ── List ───────────────────────────────────────────────

    def list_keys(self, prefix: str) -> List[str]:
        return [blob.name for blob in self._client.list_blobs(self.bucket, prefix=prefix)]
