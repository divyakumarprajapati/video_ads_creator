"""
Campaign domain service.

Orchestrates the lifecycle of a campaign: creation, strategy generation,
video record insertion, task dispatch, status queries, and result assembly.
"""

from __future__ import annotations

import os
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    CampaignGoal,
    CampaignStatus,
    LayoutType,
    MessageAngle,
    Platform,
    ProductGenerationStatus,
    StaticAdStatus,
    StaticAdType,
    VariantType,
    VideoStatus,
    VideoType,
)
from app.core.logging import get_logger
from app.models.campaign import (
    Campaign,
    CampaignPlatformExport,
    CampaignProduct,
    CampaignStaticAd,
    CampaignVideo,
)
from app.schemas.brand import BrandIdentity, MarketResearch
from app.schemas.campaign import (
    CampaignCreate,
    CampaignOut,
    CampaignResultsOut,
    CampaignStatusOut,
    PlatformExportOut,
    ProductInput,
    StaticAdResultOut,
    StaticAdStatusItem,
    VideoResultOut,
    VideoStatusItem,
)
from app.schemas.product import ProductOut
from app.services.strategy.engine import generate_campaign_strategy
from app.services.asset.paths import resolve_local_asset_path, to_relative_asset_path

logger = get_logger(__name__)


class CampaignService:
    """All campaign operations in one place."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ─────────────────────────────────────────────

    async def create_campaign(
        self, payload: CampaignCreate, user_id: str
    ) -> CampaignOut:
        """
        Create campaign → run strategy → insert video records → dispatch workers.
        """
        # 1. Insert campaign row
        # Store webhook config inside brand_identity for worker access
        brand_data = payload.brand_identity.model_dump()
        if payload.webhook:
            brand_data["_webhook_url"] = payload.webhook.url
            brand_data["_webhook_secret"] = payload.webhook.secret
            brand_data["_webhook_events"] = payload.webhook.events

        campaign = Campaign(
            project_id=payload.project_id,
            user_id=user_id,
            campaign_name=payload.campaign_name,
            campaign_goal=payload.campaign_goal,
            platforms=[p.value for p in payload.platforms],
            duration_preference=payload.duration_preference,
            brand_identity=brand_data,
            market_research=payload.market_research.model_dump(),
            product_specific_variants=payload.product_specific_variants,
            general_brand_variants=payload.general_brand_variants,
            status=CampaignStatus.STRATEGISING,
        )
        self.db.add(campaign)
        await self.db.flush()

        # 2. Insert product rows
        product_models: List[CampaignProduct] = []
        for prod in payload.products:
            pm = CampaignProduct(
                campaign_id=campaign.id,
                product_name=prod.product_name,
                product_image_url=prod.product_image_url,
                product_description=prod.product_description,
                product_category=prod.product_category,
                product_features=prod.product_features,
                price=prod.price,
                tags=prod.tags,
            )
            self.db.add(pm)
            product_models.append(pm)
        await self.db.flush()

        # 3. Generate strategy
        strategy = await generate_campaign_strategy(
            brand=payload.brand_identity,
            market=payload.market_research,
            products=payload.products,
            goal=payload.campaign_goal,
            platforms=payload.platforms,
            duration=payload.duration_preference,
            product_variants=payload.product_specific_variants,
            brand_variants=payload.general_brand_variants,
            db=self.db,
        )
        campaign.strategy_plan = strategy.to_dict()

        # 4. Create video records for product-specific videos
        video_models: List[CampaignVideo] = []
        for plan, prod_model in zip(strategy.product_plans, product_models):
            for var in plan.variants:
                vm = CampaignVideo(
                    campaign_id=campaign.id,
                    product_id=prod_model.id,
                    video_type=VideoType.PRODUCT_SPECIFIC,
                    variant_id=var.variant_id,
                    variant_type=VariantType(var.variant_type),
                    message_angle=MessageAngle(var.message_angle),
                    primary_message=var.primary_message,
                    secondary_message=var.secondary_message,
                    cta_text=var.cta_text,
                    template_id=uuid.UUID(var.template_id) if var.template_id else None,
                )
                self.db.add(vm)
                video_models.append(vm)

        # 5. Create video records for general-brand videos
        if strategy.brand_plan:
            bp = strategy.brand_plan
            for vi, var in enumerate(bp.variants):
                layout = bp.layout_types[vi] if vi < len(bp.layout_types) else "sequential_carousel"
                vm = CampaignVideo(
                    campaign_id=campaign.id,
                    product_id=None,
                    video_type=VideoType.GENERAL_BRAND,
                    variant_id=var.variant_id,
                    variant_type=VariantType(var.variant_type),
                    message_angle=MessageAngle(var.message_angle),
                    primary_message=var.primary_message,
                    secondary_message=var.secondary_message,
                    cta_text=var.cta_text,
                    template_id=uuid.UUID(var.template_id) if var.template_id else None,
                    layout_type=LayoutType(layout),
                    products_shown=bp.products_shown,
                )
                self.db.add(vm)
                video_models.append(vm)

        # 5b. Create static ad records for product-specific static ads
        static_ad_models: List[CampaignStaticAd] = []
        for plan, prod_model, prod_input in zip(strategy.product_plans, product_models, payload.products):
            for sa_var in plan.static_ad_variants:
                sa = CampaignStaticAd(
                    campaign_id=campaign.id,
                    product_id=prod_model.id,
                    ad_type=StaticAdType.PRODUCT_SPECIFIC,
                    variant_id=sa_var.variant_id,
                    variant_type=VariantType(sa_var.variant_type),
                    message_angle=MessageAngle(sa_var.message_angle),
                    static_template_id=sa_var.static_template_id,
                    static_template_name=sa_var.static_template_name,
                    headline=sa_var.headline,
                    subheading=sa_var.subheading,
                    cta_text=sa_var.cta_text,
                    body_text=sa_var.body_text,
                    image_url=sa_var.image_url or getattr(prod_input, "image_url", None) or "",
                )
                self.db.add(sa)
                static_ad_models.append(sa)

        # 5c. Create static ad records for general-brand static ads
        if strategy.brand_plan:
            bp = strategy.brand_plan
            for sa_var in bp.static_ad_variants:
                sa = CampaignStaticAd(
                    campaign_id=campaign.id,
                    product_id=None,
                    ad_type=StaticAdType.GENERAL_BRAND,
                    variant_id=sa_var.variant_id,
                    variant_type=VariantType(sa_var.variant_type),
                    message_angle=MessageAngle(sa_var.message_angle),
                    static_template_id=sa_var.static_template_id,
                    static_template_name=sa_var.static_template_name,
                    headline=sa_var.headline,
                    subheading=sa_var.subheading,
                    cta_text=sa_var.cta_text,
                    body_text=sa_var.body_text,
                    image_url="",
                )
                self.db.add(sa)
                static_ad_models.append(sa)

        await self.db.flush()

        # 6. Update campaign status to "generating" with ETA
        campaign.status = CampaignStatus.GENERATING
        total_videos = len(video_models)
        total_static_ads = len(static_ad_models)

        # Estimate completion: ~3 min per product + 3 min for brand videos
        # (conservative; parallel processing makes this faster on multi-GPU)
        num_products = len(product_models)
        estimated_minutes = max(3, (num_products * 3 + 3) / max(1, 2))  # assume 2 workers
        campaign.estimated_completion = datetime.now(timezone.utc) + timedelta(minutes=estimated_minutes)

        # 7. Dispatch worker (Celery or background thread)
        from app.core.config import get_settings as _gs
        if _gs().use_celery:
            from app.workers.tasks import run_campaign_pipeline
            run_campaign_pipeline.delay(str(campaign.id))
        else:
            from app.workers.sync_runner import dispatch_campaign
            dispatch_campaign(str(campaign.id))

        logger.info(
            "campaign_created",
            campaign_id=str(campaign.id),
            products=len(product_models),
            videos=total_videos,
            static_ads=total_static_ads,
        )

        return CampaignOut(
            id=campaign.id,
            project_id=campaign.project_id,
            campaign_name=campaign.campaign_name,
            campaign_goal=campaign.campaign_goal,
            platforms=campaign.platforms,
            duration_preference=campaign.duration_preference,
            product_specific_variants=campaign.product_specific_variants,
            general_brand_variants=campaign.general_brand_variants,
            status=campaign.status,
            overall_progress=campaign.overall_progress,
            estimated_completion=campaign.estimated_completion,
            total_products=len(product_models),
            total_videos=total_videos,
            total_static_ads=total_static_ads,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    # ── Get status ─────────────────────────────────────────

    async def get_campaign_status(
        self, campaign_id: uuid.UUID, user_id: str
    ) -> CampaignStatusOut:
        campaign = await self._get_campaign(campaign_id, user_id)
        videos = campaign.videos

        video_items = []
        for v in videos:
            product_name = v.product.product_name if v.product else None
            video_items.append(VideoStatusItem(
                video_id=v.id,
                video_type=v.video_type,
                product_name=product_name,
                variant_id=v.variant_id,
                status=v.status,
                generation_progress=v.generation_progress,
                quality_score=v.quality_score,
            ))

        completed = sum(1 for v in videos if v.status == VideoStatus.COMPLETED)
        failed = sum(1 for v in videos if v.status == VideoStatus.FAILED)

        # Static ads status
        static_ads = campaign.static_ads
        sa_items = []
        for sa in static_ads:
            product_name = sa.product.product_name if sa.product else None
            sa_items.append(StaticAdStatusItem(
                ad_id=sa.id,
                ad_type=sa.ad_type,
                product_name=product_name,
                variant_id=sa.variant_id,
                status=sa.status,
                quality_score=sa.quality_score,
            ))

        sa_completed = sum(1 for sa in static_ads if sa.status == StaticAdStatus.COMPLETED)
        sa_failed = sum(1 for sa in static_ads if sa.status == StaticAdStatus.FAILED)

        return CampaignStatusOut(
            campaign_id=campaign.id,
            status=campaign.status,
            overall_progress=campaign.overall_progress,
            estimated_completion=campaign.estimated_completion,
            total_videos=len(videos),
            completed_videos=completed,
            failed_videos=failed,
            videos=video_items,
            total_static_ads=len(static_ads),
            completed_static_ads=sa_completed,
            failed_static_ads=sa_failed,
            static_ads=sa_items,
        )

    # ── Get results ────────────────────────────────────────

    async def get_campaign_results(
        self, campaign_id: uuid.UUID, user_id: str
    ) -> CampaignResultsOut:
        campaign = await self._get_campaign(campaign_id, user_id)

        products_out = [
            ProductOut.model_validate(p) for p in campaign.products
        ]

        videos_out = []
        for v in campaign.videos:
            exports: List[PlatformExportOut] = []
            for e in v.exports:
                out = PlatformExportOut.model_validate(e)
                out.file_path = to_relative_asset_path(out.file_path)
                exports.append(out)

            thumb_rel = to_relative_asset_path(v.thumbnail_path)
            file_rel = to_relative_asset_path(v.file_path)
            if file_rel is None and thumb_rel:
                # Prefer a stable master path colocated with the thumbnail.
                candidate = f"{os.path.dirname(thumb_rel)}/master.mp4"
                try:
                    if resolve_local_asset_path(candidate).is_file():
                        file_rel = candidate
                except Exception:
                    pass
            if file_rel is None and exports:
                # Fall back to first available export file (already normalized above).
                file_rel = exports[0].file_path

            videos_out.append(VideoResultOut(
                video_id=v.id,
                video_type=v.video_type,
                product_id=v.product_id,
                product_name=v.product.product_name if v.product else None,
                variant_id=v.variant_id,
                variant_type=v.variant_type.value if v.variant_type else "",
                message_angle=v.message_angle.value if v.message_angle else "",
                primary_message=v.primary_message,
                secondary_message=v.secondary_message,
                cta_text=v.cta_text,
                template_id=v.template_id,
                layout_type=v.layout_type.value if v.layout_type else None,
                status=v.status,
                quality_score=v.quality_score,
                file_path=file_rel,
                thumbnail_path=thumb_rel,
                file_size_mb=v.file_size_mb,
                duration_seconds=v.duration_seconds,
                exports=exports,
                metadata=v.extra_metadata,
            ))

        # Static ads results
        static_ads_out = []
        for sa in campaign.static_ads:
            sa_file_rel = to_relative_asset_path(sa.file_path)
            sa_thumb_rel = to_relative_asset_path(sa.thumbnail_path)
            static_ads_out.append(StaticAdResultOut(
                ad_id=sa.id,
                ad_type=sa.ad_type,
                product_id=sa.product_id,
                product_name=sa.product.product_name if sa.product else None,
                variant_id=sa.variant_id,
                variant_type=sa.variant_type.value if sa.variant_type else "",
                message_angle=sa.message_angle.value if sa.message_angle else "",
                headline=sa.headline,
                subheading=sa.subheading,
                cta_text=sa.cta_text,
                body_text=sa.body_text,
                image_url=sa.image_url,
                static_template_id=sa.static_template_id,
                static_template_name=sa.static_template_name,
                status=sa.status,
                quality_score=sa.quality_score,
                file_path=sa_file_rel,
                thumbnail_path=sa_thumb_rel,
                file_size_mb=sa.file_size_mb,
                width=sa.width,
                height=sa.height,
                metadata=sa.extra_metadata,
            ))

        total = len(campaign.videos)
        completed = sum(1 for v in campaign.videos if v.status == VideoStatus.COMPLETED)
        failed = sum(1 for v in campaign.videos if v.status == VideoStatus.FAILED)
        avg_quality = 0.0
        scored = [v.quality_score for v in campaign.videos if v.quality_score is not None]
        if scored:
            avg_quality = round(sum(scored) / len(scored), 1)

        sa_total = len(campaign.static_ads)
        sa_completed = sum(1 for sa in campaign.static_ads if sa.status == StaticAdStatus.COMPLETED)
        sa_failed = sum(1 for sa in campaign.static_ads if sa.status == StaticAdStatus.FAILED)

        summary = {
            "total_products": len(campaign.products),
            "total_videos": total,
            "completed_videos": completed,
            "failed_videos": failed,
            "average_quality_score": avg_quality,
            "platforms": campaign.platforms,
            "total_static_ads": sa_total,
            "completed_static_ads": sa_completed,
            "failed_static_ads": sa_failed,
        }

        return CampaignResultsOut(
            campaign_id=campaign.id,
            campaign_name=campaign.campaign_name,
            status=campaign.status,
            overall_progress=campaign.overall_progress,
            products=products_out,
            videos=videos_out,
            static_ads=static_ads_out,
            summary=summary,
        )

    # ── Regenerate specific videos ─────────────────────────

    async def regenerate_videos(
        self, campaign_id: uuid.UUID, video_ids: List[uuid.UUID], user_id: str
    ) -> Dict:
        campaign = await self._get_campaign(campaign_id, user_id)

        # Reset selected videos to QUEUED
        reset_count = 0
        for v in campaign.videos:
            if v.id in video_ids:
                v.status = VideoStatus.QUEUED
                v.generation_progress = 0.0
                v.quality_score = None
                v.retry_count += 1
                reset_count += 1

        campaign.status = CampaignStatus.GENERATING
        await self.db.flush()

        # Dispatch orchestrator again
        from app.core.config import get_settings as _gs
        if _gs().use_celery:
            from app.workers.tasks import run_campaign_pipeline
            run_campaign_pipeline.delay(str(campaign.id))
        else:
            from app.workers.sync_runner import dispatch_campaign
            dispatch_campaign(str(campaign.id))

        return {"campaign_id": str(campaign_id), "videos_reset": reset_count}

    # ── List campaigns for a project ───────────────────────

    async def list_campaigns(
        self, project_id: str, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[CampaignOut]:
        stmt = (
            select(Campaign)
            .where(Campaign.project_id == project_id, Campaign.user_id == user_id)
            .order_by(Campaign.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        campaigns = result.scalars().all()

        return [
            CampaignOut(
                id=c.id,
                project_id=c.project_id,
                campaign_name=c.campaign_name,
                campaign_goal=c.campaign_goal,
                platforms=c.platforms,
                duration_preference=c.duration_preference,
                product_specific_variants=c.product_specific_variants,
                general_brand_variants=c.general_brand_variants,
                status=c.status,
                overall_progress=c.overall_progress,
                estimated_completion=c.estimated_completion,
                total_products=len(c.products),
                total_videos=len(c.videos),
                total_static_ads=len(c.static_ads),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in campaigns
        ]

    # ── Internal ───────────────────────────────────────────

    async def _get_campaign(self, campaign_id: uuid.UUID, user_id: str) -> Campaign:
        stmt = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        campaign = result.scalar_one_or_none()
        if not campaign:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign {campaign_id} not found",
            )
        return campaign
