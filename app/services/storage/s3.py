"""
S3-Compatible Storage Service.

Wraps boto3 for uploading, downloading, generating presigned URLs,
and managing campaign file trees in object storage.
"""

from __future__ import annotations

import mimetypes
import os
from typing import List, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class S3Storage:
    """Thin wrapper around boto3 S3 client."""

    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )
        self.bucket = settings.s3_bucket_name

    # ── Ensure bucket ──────────────────────────────────────

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self.bucket)
            logger.info("s3_bucket_created", bucket=self.bucket)

    # ── Upload ─────────────────────────────────────────────

    def upload_file(self, local_path: str, s3_key: str) -> str:
        content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
        self._client.upload_file(
            local_path,
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        url = f"{settings.s3_public_url}/{s3_key}"
        logger.info("s3_uploaded", key=s3_key)
        return url

    def upload_directory(self, local_dir: str, s3_prefix: str) -> List[str]:
        """Upload an entire directory tree, preserving structure."""
        urls: List[str] = []
        for root, _, files in os.walk(local_dir):
            for fname in files:
                local = os.path.join(root, fname)
                relative = os.path.relpath(local, local_dir)
                key = f"{s3_prefix}/{relative}"
                urls.append(self.upload_file(local, key))
        return urls

    # ── Download ───────────────────────────────────────────

    def download_file(self, s3_key: str, local_path: str) -> str:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self._client.download_file(self.bucket, s3_key, local_path)
        return local_path

    # ── Presigned URLs ─────────────────────────────────────

    def presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": s3_key},
            ExpiresIn=expires_in,
        )

    # ── Delete ─────────────────────────────────────────────

    def delete_key(self, s3_key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=s3_key)

    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects under *prefix*.  Returns count deleted."""
        paginator = self._client.get_paginator("list_objects_v2")
        count = 0
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                self._client.delete_object(Bucket=self.bucket, Key=obj["Key"])
                count += 1
        return count

    # ── List ───────────────────────────────────────────────

    def list_keys(self, prefix: str) -> List[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: List[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys
