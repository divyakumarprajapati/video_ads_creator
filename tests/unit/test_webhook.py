"""
Unit tests for webhook service.
"""

from __future__ import annotations

import pytest

from app.services.webhook import send_webhook_sync


class TestWebhookSync:
    def test_returns_false_for_unreachable_url(self):
        # Should fail gracefully and return False
        result = send_webhook_sync(
            "http://localhost:19999/nonexistent",
            "test.event",
            {"key": "value"},
        )
        assert result is False

    def test_accepts_secret_parameter(self):
        # Should not raise even with secret
        result = send_webhook_sync(
            "http://localhost:19999/webhook",
            "campaign.completed",
            {"campaign_id": "123"},
            secret="test-secret",
        )
        assert result is False
