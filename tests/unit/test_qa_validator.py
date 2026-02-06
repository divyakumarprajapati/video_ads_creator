"""
Unit tests for the QA validator.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from app.services.qa.validator import QAResult, QAValidator


class TestQAValidator:
    def test_missing_file(self):
        qa = QAValidator()
        result = qa.validate("/nonexistent/video.mp4")
        assert not result.passed
        assert result.overall_score == 0.0

    def test_empty_file(self, tmp_path):
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        qa = QAValidator()
        result = qa.validate(str(empty))
        assert not result.passed

    def test_result_serialisation(self):
        result = QAResult(
            video_path="/test.mp4",
            overall_score=85.0,
            passed=True,
            checks=[],
        )
        d = result.to_dict()
        assert d["overall_score"] == 85.0
        assert d["passed"] is True
