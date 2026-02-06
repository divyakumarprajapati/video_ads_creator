"""
Shared test fixtures.
"""

from __future__ import annotations

import os
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

# Ensure test env vars before any app import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/video_ads_test")
os.environ.setdefault("DATABASE_SYNC_URL", "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/video_ads_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/14")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/13")
os.environ.setdefault("APP_ENV", "testing")


@pytest.fixture
def brand_identity_data():
    return {
        "brand_name": "TestBrand",
        "tagline": "Test tagline",
        "colors": {
            "primary": "#FF0000",
            "secondary": "#00FF00",
            "accent": "#0000FF",
            "background": "#FFFFFF",
            "text": "#000000",
        },
        "fonts": {"heading": "Arial", "body": "Helvetica"},
        "voice": "professional",
        "tone": "confident",
        "industry": "skincare",
    }


@pytest.fixture
def market_research_data():
    return {
        "saturation_percent": 65.0,
        "competitive_edge_percent": 75.0,
        "sentiment": "positive",
        "trending_keywords": ["test"],
        "target_audience_age_min": 18,
        "target_audience_age_max": 45,
        "target_audience_gender": "all",
    }


@pytest.fixture
def products_data():
    return [
        {
            "product_name": "Test Product 1",
            "product_image_url": "https://placehold.co/512x512/png",
            "product_category": "skincare",
            "price": 29.99,
            "tags": {"is_new": True, "is_bestseller": False},
        },
        {
            "product_name": "Test Product 2",
            "product_image_url": "https://placehold.co/512x512/png",
            "product_category": "tech",
            "price": 49.99,
            "tags": {"is_new": False, "is_bestseller": True},
        },
    ]


@pytest.fixture
def campaign_create_data(brand_identity_data, market_research_data, products_data):
    return {
        "campaign_name": "Test Campaign",
        "project_id": "test-project",
        "brand_identity": brand_identity_data,
        "market_research": market_research_data,
        "products": products_data,
        "campaign_goal": "awareness",
        "platforms": ["instagram_feed"],
        "duration_preference": 15,
        "product_specific_variants": 3,
        "general_brand_variants": 3,
    }
