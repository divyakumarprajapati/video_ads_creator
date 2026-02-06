"""
Unit tests for the local filesystem storage backend.
"""

from __future__ import annotations

import os

import pytest

from app.services.storage.local import LocalStorage


class TestLocalStorage:
    def test_ensure_bucket(self, tmp_path):
        s = LocalStorage(root=str(tmp_path / "store"), url_prefix="http://test")
        s.ensure_bucket()
        assert os.path.isdir(str(tmp_path / "store"))

    def test_upload_and_list(self, tmp_path):
        root = str(tmp_path / "store")
        s = LocalStorage(root=root, url_prefix="http://test")
        s.ensure_bucket()

        # Create a source file
        src = str(tmp_path / "video.mp4")
        with open(src, "w") as f:
            f.write("fake video data")

        url = s.upload_file(src, "campaigns/123/video.mp4")
        assert url == "http://test/campaigns/123/video.mp4"
        assert os.path.isfile(os.path.join(root, "campaigns/123/video.mp4"))

        keys = s.list_keys("campaigns/123")
        assert "campaigns/123/video.mp4" in keys

    def test_download(self, tmp_path):
        root = str(tmp_path / "store")
        s = LocalStorage(root=root, url_prefix="http://test")
        s.ensure_bucket()

        # Upload first
        src = str(tmp_path / "original.mp4")
        with open(src, "w") as f:
            f.write("content")
        s.upload_file(src, "test/file.mp4")

        # Download
        dest = str(tmp_path / "downloaded.mp4")
        s.download_file("test/file.mp4", dest)
        assert os.path.isfile(dest)
        with open(dest) as f:
            assert f.read() == "content"

    def test_delete_key(self, tmp_path):
        root = str(tmp_path / "store")
        s = LocalStorage(root=root, url_prefix="http://test")
        s.ensure_bucket()

        src = str(tmp_path / "x.txt")
        with open(src, "w") as f:
            f.write("data")
        s.upload_file(src, "del/x.txt")
        assert os.path.isfile(os.path.join(root, "del/x.txt"))

        s.delete_key("del/x.txt")
        assert not os.path.isfile(os.path.join(root, "del/x.txt"))

    def test_delete_prefix(self, tmp_path):
        root = str(tmp_path / "store")
        s = LocalStorage(root=root, url_prefix="http://test")
        s.ensure_bucket()

        for name in ("a.mp4", "b.mp4", "c.mp4"):
            src = str(tmp_path / name)
            with open(src, "w") as f:
                f.write("data")
            s.upload_file(src, f"prefix/{name}")

        count = s.delete_prefix("prefix")
        assert count == 3
        assert not os.path.isdir(os.path.join(root, "prefix"))

    def test_presigned_url(self, tmp_path):
        s = LocalStorage(root=str(tmp_path), url_prefix="http://test")
        url = s.presigned_url("campaigns/123/video.mp4")
        assert url == "http://test/campaigns/123/video.mp4"

    def test_upload_directory(self, tmp_path):
        root = str(tmp_path / "store")
        s = LocalStorage(root=root, url_prefix="http://test")
        s.ensure_bucket()

        # Create a directory with files
        src_dir = str(tmp_path / "source")
        os.makedirs(os.path.join(src_dir, "sub"))
        for name in ("a.mp4", "sub/b.mp4"):
            with open(os.path.join(src_dir, name), "w") as f:
                f.write("data")

        urls = s.upload_directory(src_dir, "campaign_1")
        assert len(urls) == 2
        assert os.path.isfile(os.path.join(root, "campaign_1/a.mp4"))
        assert os.path.isfile(os.path.join(root, "campaign_1/sub/b.mp4"))

    def test_download_not_found(self, tmp_path):
        s = LocalStorage(root=str(tmp_path), url_prefix="http://test")
        with pytest.raises(FileNotFoundError):
            s.download_file("nonexistent.mp4", str(tmp_path / "dest.mp4"))
