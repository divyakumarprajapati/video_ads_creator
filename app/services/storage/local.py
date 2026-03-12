"""
Local Filesystem Storage Service.

Drop-in replacement for the S3 storage service.  Stores all files under
``LOCAL_STORAGE_ROOT`` (default ``./output``) and generates file:// or
HTTP URLs for retrieval.
"""

from __future__ import annotations

import mimetypes
import os
import shutil
from typing import List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LocalStorage:
    """Filesystem-backed storage that mirrors the S3Storage interface."""

    def __init__(self, root: str | None = None, url_prefix: str | None = None):
        self.root = os.path.abspath(root or settings.local_storage_root)
        self.url_prefix = (url_prefix or settings.local_storage_url_prefix).rstrip("/")
        os.makedirs(self.root, exist_ok=True)

    # ── Ensure bucket (no-op for local) ────────────────────

    def ensure_bucket(self) -> None:
        os.makedirs(self.root, exist_ok=True)

    # ── Upload ─────────────────────────────────────────────

    def upload_file(self, local_path: str, key: str) -> str:
        dest = os.path.join(self.root, key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.abspath(local_path) != os.path.abspath(dest):
            shutil.copy2(local_path, dest)
        url = f"{self.url_prefix}/{key}"
        logger.info("local_stored", key=key)
        return url

    def upload_directory(self, local_dir: str, prefix: str) -> List[str]:
        urls: List[str] = []
        for root, _, files in os.walk(local_dir):
            for fname in files:
                full = os.path.join(root, fname)
                relative = os.path.relpath(full, local_dir)
                key = f"{prefix}/{relative}"
                urls.append(self.upload_file(full, key))
        return urls

    # ── Download ───────────────────────────────────────────

    def download_file(self, key: str, local_path: str) -> str:
        src = os.path.join(self.root, key)
        if not os.path.isfile(src):
            raise FileNotFoundError(f"Key not found: {key}")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        shutil.copy2(src, local_path)
        return local_path

    # ── URL ────────────────────────────────────────────────

    def presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """For local storage, just return the static URL."""
        return f"{self.url_prefix}/{key}"

    def public_url(self, key: str) -> str:
        return f"{self.url_prefix}/{key}"

    # ── Delete ─────────────────────────────────────────────

    def delete_key(self, key: str) -> None:
        path = os.path.join(self.root, key)
        if os.path.isfile(path):
            os.unlink(path)

    def delete_prefix(self, prefix: str) -> int:
        target = os.path.join(self.root, prefix)
        if not os.path.isdir(target):
            return 0
        count = sum(len(files) for _, _, files in os.walk(target))
        shutil.rmtree(target, ignore_errors=True)
        return count

    # ── List ───────────────────────────────────────────────

    def list_keys(self, prefix: str) -> List[str]:
        target = os.path.join(self.root, prefix)
        if not os.path.isdir(target):
            return []
        keys: List[str] = []
        for root, _, files in os.walk(target):
            for fname in files:
                full = os.path.join(root, fname)
                keys.append(os.path.relpath(full, self.root))
        return keys
