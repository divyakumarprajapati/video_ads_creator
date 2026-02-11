"""
Aggregate all v1 routers into a single APIRouter that the main app mounts.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.assets import router as assets_router
from app.api.v1.endpoints.campaigns import router as campaigns_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.images import router as images_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.static_ads import router as static_ads_router
from app.api.v1.endpoints.templates import router as templates_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(assets_router)
api_router.include_router(campaigns_router)
api_router.include_router(templates_router)
api_router.include_router(projects_router)
api_router.include_router(images_router)
api_router.include_router(static_ads_router)
