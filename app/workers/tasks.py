"""
Celery task definitions.

Three task types:
  1. ``run_campaign_pipeline`` – orchestrator that fans-out to product + brand tasks
  2. ``process_product_video``  – generates all variants for one product
  3. ``process_brand_video``    – generates all variants for general-brand videos
"""

from __future__ import annotations

import json
import os
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from celery import chord, group
from celery.utils.log import get_task_logger

from app.core.config import get_settings
from app.core.enums import (
    CampaignStatus,
    Platform,
    ProductGenerationStatus,
    VideoStatus,
    VideoType,
)
from app.services.asset.processor import AssetProcessor
from app.services.export.encoder import PlatformEncoder
from app.services.qa.validator import QAValidator
from app.services.video.generator import VideoGenerator
from app.utils.file_utils import (
    brand_variant_dir,
    campaign_dir,
    ensure_dir,
    file_size_mb,
    tmp_dir,
    variant_dir,
)
from app.workers.celery_app import celery_app
from app.workers.progress import (
    update_campaign_progress,
    update_video_progress,
)

logger = get_task_logger(__name__)
settings = get_settings()

BASE_OUTPUT = os.environ.get("VIDEO_OUTPUT_DIR", "/tmp/video_ads_output")


# ────────────────────────────────────────────────────────────
#  Helpers – synchronous DB access (workers run outside async)
# ────────────────────────────────────────────────────────────

def _sync_engine():
    from sqlalchemy import create_engine
    return create_engine(settings.database_sync_url)


def _update_video_record(video_id: str, **kwargs) -> None:
    """Update a CampaignVideo row via synchronous connection."""
    from sqlalchemy import text
    eng = _sync_engine()
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    with eng.connect() as conn:
        conn.execute(
            text(f"UPDATE campaign_videos SET {sets}, updated_at = now() WHERE id = :vid"),
            {"vid": video_id, **kwargs},
        )
        conn.commit()


def _update_product_record(product_id: str, **kwargs) -> None:
    from sqlalchemy import text
    eng = _sync_engine()
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    with eng.connect() as conn:
        conn.execute(
            text(f"UPDATE campaign_products SET {sets}, updated_at = now() WHERE id = :pid"),
            {"pid": product_id, **kwargs},
        )
        conn.commit()


def _update_campaign_record(campaign_id: str, **kwargs) -> None:
    from sqlalchemy import text
    eng = _sync_engine()
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    with eng.connect() as conn:
        conn.execute(
            text(f"UPDATE campaigns SET {sets}, updated_at = now() WHERE id = :cid"),
            {"cid": campaign_id, **kwargs},
        )
        conn.commit()


def _insert_platform_export(video_id: str, platform: str, file_path: str,
                            file_size: float, resolution: str, aspect_ratio: str,
                            public_url: str = "") -> None:
    from sqlalchemy import text
    eng = _sync_engine()
    with eng.connect() as conn:
        conn.execute(text(
            "INSERT INTO campaign_platform_exports "
            "(id, video_id, platform, file_path, file_size_mb, resolution, aspect_ratio, public_url, created_at, updated_at) "
            "VALUES (:id, :vid, :plat, :fp, :fs, :res, :ar, :url, now(), now())"
        ), {
            "id": str(uuid.uuid4()), "vid": video_id, "plat": platform,
            "fp": file_path, "fs": file_size, "res": resolution,
            "ar": aspect_ratio, "url": public_url,
        })
        conn.commit()


def _get_campaign_data(campaign_id: str) -> Dict[str, Any]:
    """Load campaign + products + videos as plain dicts."""
    from sqlalchemy import text
    eng = _sync_engine()
    with eng.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM campaigns WHERE id = :cid"), {"cid": campaign_id}
        ).mappings().first()
        if not row:
            raise ValueError(f"Campaign {campaign_id} not found")
        campaign = dict(row)

        products = [dict(r) for r in conn.execute(
            text("SELECT * FROM campaign_products WHERE campaign_id = :cid ORDER BY created_at"),
            {"cid": campaign_id},
        ).mappings().all()]

        videos = [dict(r) for r in conn.execute(
            text("SELECT * FROM campaign_videos WHERE campaign_id = :cid ORDER BY created_at"),
            {"cid": campaign_id},
        ).mappings().all()]

    campaign["products"] = products
    campaign["videos"] = videos
    return campaign


# ────────────────────────────────────────────────────────────
#  Task 1: Process one product's videos
# ────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_product_video",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def process_product_video(
    self,
    campaign_id: str,
    product_id: str,
    product_data: Dict,
    video_records: List[Dict],
    brand_identity: Dict,
    platforms: List[str],
    duration: int,
) -> Dict:
    """
    Generate all variant videos for a single product.

    Steps: asset prep → video gen → QA → platform export → upload
    """
    cid = campaign_id
    pid = product_id
    product_idx = product_data.get("product_index", 0)
    product_name = product_data.get("product_name", f"product_{product_idx}")
    work = tmp_dir(prefix=f"prod_{product_idx}_")

    try:
        # ── 1. Asset Preparation ───────────────────────────
        _update_product_record(pid, generation_status="processing", progress=10)

        asset_proc = AssetProcessor(work)
        bg_primary = brand_identity.get("colors", {}).get("background", "#FFFFFF")
        bg_secondary = brand_identity.get("colors", {}).get("secondary", "#F0F0F0")

        assets = asset_proc.prepare_product_assets(
            image_url=product_data["product_image_url"],
            product_idx=product_idx,
            bg_primary=bg_primary,
            bg_secondary=bg_secondary,
        )
        _update_product_record(
            pid, progress=30,
            processed_image_path=assets["composite"],
            background_removed_path=assets["no_bg"],
            upscaled_image_path=assets["upscaled"],
        )

        # ── 2. Generate video variants ─────────────────────
        vid_gen = VideoGenerator(work)
        qa = QAValidator()
        encoder = PlatformEncoder()
        platform_enums = [Platform(p) for p in platforms]

        results = []
        for vr in video_records:
            video_id = str(vr["id"])
            variant_id = vr["variant_id"]
            creative = vr.get("creative", {})

            update_video_progress(cid, video_id, 10, "generating")
            _update_video_record(video_id, status="generating", generation_progress=10)

            # Generate master video
            master = vid_gen.generate_product_video(
                composite_path=assets["composite"],
                video_style=creative.get("video_style", "product_hero"),
                variant_id=variant_id,
                primary_message=vr.get("primary_message", ""),
                secondary_message=vr.get("secondary_message", ""),
                cta_text=vr.get("cta_text", ""),
                pacing=creative.get("pacing", "medium"),
                duration=duration,
            )
            update_video_progress(cid, video_id, 50, "compositing")
            _update_video_record(video_id, status="compositing", generation_progress=50)

            # QA check
            qa_result = qa.validate(master)
            update_video_progress(cid, video_id, 70, "qa",
                                  quality_score=qa_result.overall_score)

            if not qa_result.passed and self.request.retries < self.max_retries:
                logger.warning("QA failed for video %s, retrying", video_id)
                _update_video_record(video_id, status="retrying",
                                     quality_score=qa_result.overall_score)
                raise self.retry(countdown=30)

            # Platform exports
            out_dir = variant_dir(
                BASE_OUTPUT, cid, product_name, product_idx,
                variant_id, vr.get("message_angle", "benefit"),
            )
            exports = encoder.encode_all(master, out_dir, platform_enums, max_duration=duration)

            # Record exports in DB
            for exp in exports:
                if exp.file_path:
                    _insert_platform_export(
                        video_id, exp.platform, exp.file_path,
                        exp.file_size_mb, exp.resolution, exp.aspect_ratio,
                    )

            # Update video record
            _update_video_record(
                video_id,
                status="completed",
                generation_progress=100,
                quality_score=qa_result.overall_score,
                file_path=master,
                file_size_mb=file_size_mb(master),
                thumbnail_path=exports[0].thumbnail_path if exports else None,
                duration_seconds=float(duration),
            )
            update_video_progress(cid, video_id, 100, "completed",
                                  quality_score=qa_result.overall_score)
            results.append({"video_id": video_id, "status": "completed",
                            "quality_score": qa_result.overall_score})

        _update_product_record(pid, generation_status="completed", progress=100)
        return {"product_id": pid, "videos": results}

    except Exception as exc:
        logger.error("Product video generation failed: %s", traceback.format_exc())
        _update_product_record(pid, generation_status="failed", progress=0)
        for vr in video_records:
            _update_video_record(str(vr["id"]), status="failed", generation_progress=0)
            update_video_progress(cid, str(vr["id"]), 0, "failed")
        raise


# ────────────────────────────────────────────────────────────
#  Task 2: Process general-brand videos
# ────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_brand_video",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def process_brand_video(
    self,
    campaign_id: str,
    product_composites: List[str],
    video_records: List[Dict],
    brand_identity: Dict,
    platforms: List[str],
    duration: int,
) -> Dict:
    """Generate all general-brand video variants."""
    cid = campaign_id
    work = tmp_dir(prefix="brand_")

    try:
        vid_gen = VideoGenerator(work)
        qa = QAValidator()
        encoder = PlatformEncoder()
        platform_enums = [Platform(p) for p in platforms]
        results = []

        for vr in video_records:
            video_id = str(vr["id"])
            variant_id = vr["variant_id"]
            layout = vr.get("layout_type", "sequential_carousel")

            update_video_progress(cid, video_id, 10, "generating")
            _update_video_record(video_id, status="generating", generation_progress=10)

            master = vid_gen.generate_brand_video(
                product_composites=product_composites,
                layout_type=layout,
                variant_id=variant_id,
                primary_message=vr.get("primary_message", ""),
                secondary_message=vr.get("secondary_message", ""),
                cta_text=vr.get("cta_text", ""),
                pacing=vr.get("pacing", "medium"),
                duration=duration,
            )

            qa_result = qa.validate(master)
            update_video_progress(cid, video_id, 70, "qa",
                                  quality_score=qa_result.overall_score)

            if not qa_result.passed and self.request.retries < self.max_retries:
                _update_video_record(video_id, status="retrying",
                                     quality_score=qa_result.overall_score)
                raise self.retry(countdown=30)

            out_dir = brand_variant_dir(
                BASE_OUTPUT, cid, variant_id,
                vr.get("message_angle", "benefit"),
            )
            exports = encoder.encode_all(master, out_dir, platform_enums, max_duration=duration)

            for exp in exports:
                if exp.file_path:
                    _insert_platform_export(
                        video_id, exp.platform, exp.file_path,
                        exp.file_size_mb, exp.resolution, exp.aspect_ratio,
                    )

            _update_video_record(
                video_id,
                status="completed",
                generation_progress=100,
                quality_score=qa_result.overall_score,
                file_path=master,
                file_size_mb=file_size_mb(master),
                thumbnail_path=exports[0].thumbnail_path if exports else None,
                duration_seconds=float(duration),
            )
            update_video_progress(cid, video_id, 100, "completed",
                                  quality_score=qa_result.overall_score)
            results.append({"video_id": video_id, "status": "completed",
                            "quality_score": qa_result.overall_score})

        return {"campaign_id": cid, "brand_videos": results}

    except Exception as exc:
        logger.error("Brand video generation failed: %s", traceback.format_exc())
        for vr in video_records:
            _update_video_record(str(vr["id"]), status="failed", generation_progress=0)
            update_video_progress(cid, str(vr["id"]), 0, "failed")
        raise


# ────────────────────────────────────────────────────────────
#  Task 3: Campaign orchestrator
# ────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.run_campaign_pipeline",
    max_retries=1,
    acks_late=True,
)
def run_campaign_pipeline(self, campaign_id: str) -> Dict:
    """
    Top-level orchestrator.

    1. Load campaign data from DB
    2. Fan-out product tasks + brand task as a Celery group
    3. On completion, finalise campaign status
    """
    cid = campaign_id
    try:
        _update_campaign_record(cid, status="generating", overall_progress=5)
        update_campaign_progress(cid, 5, "generating")

        data = _get_campaign_data(cid)
        products = data["products"]
        videos = data["videos"]
        brand_identity = data.get("brand_identity") or {}
        strategy = data.get("strategy_plan") or {}
        platforms = data.get("platforms") or ["instagram_feed"]
        duration = data.get("duration_preference", 15)

        # ── Prepare asset processor for product composites ──
        work = tmp_dir(prefix="campaign_assets_")
        asset_proc = AssetProcessor(work)
        bg_primary = brand_identity.get("colors", {}).get("background", "#FFFFFF")
        bg_secondary = brand_identity.get("colors", {}).get("secondary", "#F0F0F0")

        # Group videos by product
        product_video_map: Dict[str, List[Dict]] = {}
        brand_video_list: List[Dict] = []
        for v in videos:
            v_dict = dict(v)
            # Enrich with creative plan from strategy
            product_plans = strategy.get("product_plans", [])
            if v.get("video_type") == "product_specific" and v.get("product_id"):
                pid = str(v["product_id"])
                if pid not in product_video_map:
                    product_video_map[pid] = []
                # Find matching variant in strategy
                for pp in product_plans:
                    for var in pp.get("variants", []):
                        if var.get("variant_id") == v.get("variant_id"):
                            v_dict["creative"] = {
                                "video_style": pp.get("video_style", "product_hero"),
                                "pacing": var.get("pacing", "medium"),
                            }
                product_video_map[pid].append(v_dict)
            else:
                # Brand video
                brand_plan = strategy.get("brand_plan", {})
                layouts = brand_plan.get("layout_types", ["sequential_carousel"])
                v_idx = v.get("variant_id", 1) - 1
                v_dict["layout_type"] = layouts[v_idx % len(layouts)] if layouts else "sequential_carousel"
                v_dict["pacing"] = "medium"
                for bv in brand_plan.get("variants", []):
                    if bv.get("variant_id") == v.get("variant_id"):
                        v_dict["pacing"] = bv.get("pacing", "medium")
                brand_video_list.append(v_dict)

        # Pre-download and composite all product images (needed for brand video)
        product_composites: List[str] = []
        product_data_map: Dict[str, Dict] = {}
        for idx, prod in enumerate(products):
            prod_dict = dict(prod)
            prod_dict["product_index"] = idx
            product_data_map[str(prod["id"])] = prod_dict
            try:
                assets = asset_proc.prepare_product_assets(
                    image_url=prod["product_image_url"],
                    product_idx=idx,
                    bg_primary=bg_primary,
                    bg_secondary=bg_secondary,
                )
                product_composites.append(assets["composite"])
            except Exception as exc:
                logger.warning("Asset prep failed for product %s: %s", prod["id"], exc)

        update_campaign_progress(cid, 15, "generating")
        _update_campaign_record(cid, overall_progress=15)

        # ── Fan-out tasks ──────────────────────────────────
        task_group = []

        for pid, vid_records in product_video_map.items():
            prod_data = product_data_map.get(pid, {"product_image_url": "", "product_name": "unknown", "product_index": 0})
            task_group.append(
                process_product_video.s(
                    cid, pid, prod_data, vid_records,
                    brand_identity, platforms, duration,
                )
            )

        if brand_video_list and product_composites:
            task_group.append(
                process_brand_video.s(
                    cid, product_composites, brand_video_list,
                    brand_identity, platforms, duration,
                )
            )

        if task_group:
            job = group(task_group)
            result = job.apply_async()
            result.get(timeout=3600, propagate=False)  # Wait up to 1 hour

        # ── Finalise ───────────────────────────────────────
        # Recount statuses
        final_data = _get_campaign_data(cid)
        total = len(final_data["videos"])
        completed = sum(1 for v in final_data["videos"] if v.get("status") == "completed")
        failed = sum(1 for v in final_data["videos"] if v.get("status") == "failed")

        if failed == total:
            final_status = "failed"
        elif completed == total:
            final_status = "completed"
        elif completed > 0:
            final_status = "completed"  # Partial success counts as completed
        else:
            final_status = "failed"

        progress = round((completed / total) * 100, 1) if total else 0
        _update_campaign_record(cid, status=final_status, overall_progress=progress)
        update_campaign_progress(cid, progress, final_status)

        # ── Generate campaign_summary.json ─────────────────
        try:
            from app.services.download import generate_campaign_summary
            generate_campaign_summary(BASE_OUTPUT, cid, final_data)
        except Exception as exc:
            logger.warning("Failed to write campaign summary: %s", exc)

        # ── Upload to S3 ───────────────────────────────────
        try:
            from app.services.storage.s3 import S3Storage
            s3 = S3Storage()
            s3.ensure_bucket()
            camp_dir_path = os.path.join(BASE_OUTPUT, f"campaign_{cid}")
            if os.path.isdir(camp_dir_path):
                s3.upload_directory(camp_dir_path, f"campaigns/{cid}")
                logger.info("campaign_uploaded_to_s3", campaign_id=cid)
        except Exception as exc:
            logger.warning("S3 upload failed (non-fatal): %s", exc)

        # ── Fire webhook notifications ─────────────────────
        webhook_config = data.get("brand_identity", {}).get("_webhook") or data.get("_webhook")
        # Webhook URL is stored at campaign level if provided
        _fire_campaign_webhook(cid, final_status, {
            "campaign_id": cid,
            "status": final_status,
            "total_videos": total,
            "completed": completed,
            "failed": failed,
            "progress": progress,
        })

        return {
            "campaign_id": cid,
            "status": final_status,
            "total_videos": total,
            "completed": completed,
            "failed": failed,
        }

    except Exception as exc:
        logger.error("Campaign pipeline failed: %s", traceback.format_exc())
        _update_campaign_record(cid, status="failed", error_message=str(exc))
        update_campaign_progress(cid, 0, "failed")
        _fire_campaign_webhook(cid, "failed", {
            "campaign_id": cid,
            "status": "failed",
            "error": str(exc),
        })
        raise


def _fire_campaign_webhook(campaign_id: str, status: str, payload: dict) -> None:
    """Fire webhook if campaign has a webhook_url configured."""
    try:
        from sqlalchemy import text
        eng = _sync_engine()
        with eng.connect() as conn:
            row = conn.execute(
                text("SELECT brand_identity FROM campaigns WHERE id = :cid"),
                {"cid": campaign_id},
            ).mappings().first()
        if not row:
            return
        bi = row.get("brand_identity") or {}
        webhook_url = bi.get("_webhook_url")
        webhook_secret = bi.get("_webhook_secret")
        if not webhook_url:
            return

        from app.services.webhook import send_webhook_sync
        event = f"campaign.{status}"
        send_webhook_sync(webhook_url, event, payload, secret=webhook_secret)
    except Exception as exc:
        logger.warning("Webhook fire failed: %s", exc)
