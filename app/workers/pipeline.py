"""
Core pipeline logic – pure functions with no Celery dependency.

These functions contain the actual video generation workflow.
They are called by:
  - ``sync_runner.py``  (default – runs in a background thread)
  - ``tasks.py``        (when USE_CELERY=true – runs in Celery workers)
"""

from __future__ import annotations

import logging
import os
import shutil
import traceback
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.enums import Platform
from app.services.asset.processor import AssetProcessor
from app.services.export.encoder import PlatformEncoder
from app.services.qa.validator import QAValidator
from app.services.static_ad.generator import StaticAdGenerator
from app.services.static_ad.anthropic_svg_generator import AnthropicSvgGenerator
from app.services.static_ad.template_registry import get_template_by_id
from app.services.static_ad.validator import StaticAdValidator
from app.services.video.generator import VideoGenerator
from app.utils.file_utils import (
    brand_variant_dir,
    ensure_dir,
    file_size_mb,
    tmp_dir,
    variant_dir,
)
from app.workers.progress import update_campaign_progress, update_video_progress

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_OUTPUT = os.environ.get("VIDEO_OUTPUT_DIR", os.path.abspath(
    settings.local_storage_root if settings.storage_backend == "local" else "/tmp/video_ads_output"
))


# ────────────────────────────────────────────────────────────
#  Helpers: static ads (Anthropic SVG)
# ────────────────────────────────────────────────────────────

def _resolve_product_image_source(
    product_id: Optional[str],
    product_map: Dict[str, Dict],
    product_assets_map: Optional[Dict[str, Dict]] = None,
    *,
    prefer_no_bg: bool = False,
) -> str:
    if not product_id:
        return ""
    if product_assets_map and product_id in product_assets_map:
        assets = product_assets_map[product_id]
        if prefer_no_bg:
            return (
                assets.get("no_bg")
                or assets.get("upscaled")
                or assets.get("original")
                or assets.get("composite")
                or ""
            )
        return (
            assets.get("upscaled")
            or assets.get("no_bg")
            or assets.get("composite")
            or assets.get("original")
            or ""
        )
    return product_map.get(product_id, {}).get("product_image_url", "")


def _select_collab_products(
    products: List[Dict],
    variant_id: int,
) -> List[Dict]:
    if not products:
        return []
    count = 2 if variant_id % 2 == 0 else 3
    count = min(count, len(products))
    start = variant_id % len(products)
    selected = []
    for i in range(count):
        selected.append(products[(start + i) % len(products)])
    return selected


def _build_style_hint(static_ad: Dict) -> str:
    template_name = (static_ad.get("static_template_name") or "").lower()

    if "minimal" in template_name or "luxury" in template_name:
        return "minimalist luxury, lots of white space, elegant typography"
    if "ugc" in template_name or "authentic" in template_name:
        return "authentic, UGC-inspired, casual, natural lighting"
    if "before_after" in template_name:
        return "split layout, clear before/after labels, clinical clarity"
    if "urgency" in template_name:
        return "bold urgency, high contrast, offer emphasis (no timers)"
    if "social_proof" in template_name or "testimonial" in template_name:
        return "trust-building, social proof elements, clean badges"
    return ""


def _try_rasterize_svg(svg_path: str, png_path: str) -> bool:
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path)
        return os.path.exists(png_path)
    except Exception:
        return False


# ────────────────────────────────────────────────────────────
#  Synchronous DB helpers
# ────────────────────────────────────────────────────────────

def _sync_engine():
    from sqlalchemy import create_engine
    return create_engine(settings.database_sync_url)


def _update_video_record(video_id: str, **kwargs) -> None:
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


def _update_static_ad_record(ad_id: str, **kwargs) -> None:
    from sqlalchemy import text
    eng = _sync_engine()
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    with eng.connect() as conn:
        conn.execute(
            text(f"UPDATE campaign_static_ads SET {sets}, updated_at = now() WHERE id = :aid"),
            {"aid": ad_id, **kwargs},
        )
        conn.commit()


def _get_campaign_data(campaign_id: str) -> Dict[str, Any]:
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
        static_ads = [dict(r) for r in conn.execute(
            text("SELECT * FROM campaign_static_ads WHERE campaign_id = :cid ORDER BY created_at"),
            {"cid": campaign_id},
        ).mappings().all()]
    campaign["products"] = products
    campaign["videos"] = videos
    campaign["static_ads"] = static_ads
    return campaign


# ────────────────────────────────────────────────────────────
#  Pipeline: process one product's videos
# ────────────────────────────────────────────────────────────

def process_product_videos(
    campaign_id: str,
    product_id: str,
    product_data: Dict,
    video_records: List[Dict],
    brand_identity: Dict,
    platforms: List[str],
    duration: int,
    max_retries: int = 2,
) -> Dict:
    cid = campaign_id
    pid = product_id
    product_idx = product_data.get("product_index", 0)
    product_name = product_data.get("product_name", f"product_{product_idx}")
    work = tmp_dir(prefix=f"prod_{product_idx}_")

    try:
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

            qa_result = qa.validate(master)
            update_video_progress(cid, video_id, 70, "qa",
                                  quality_score=qa_result.overall_score)

            out_dir = variant_dir(
                BASE_OUTPUT, cid, product_name, product_idx,
                variant_id, vr.get("message_angle", "benefit"),
            )
            exports = encoder.encode_all(master, out_dir, platform_enums, max_duration=duration)

            # Persist a copy of the master into the campaign output dir so it can be served/downloaded.
            master_out = os.path.join(out_dir, "master.mp4")
            try:
                if os.path.isfile(master) and not os.path.exists(master_out):
                    shutil.copy2(master, master_out)
            except Exception:
                master_out = master

            for exp in exports:
                if exp.file_path:
                    _insert_platform_export(
                        video_id, exp.platform, exp.file_path,
                        exp.file_size_mb, exp.resolution, exp.aspect_ratio,
                    )

            _update_video_record(
                video_id, status="completed", generation_progress=100,
                quality_score=qa_result.overall_score, file_path=master_out,
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
#  Pipeline: process general-brand videos
# ────────────────────────────────────────────────────────────

def process_brand_videos(
    campaign_id: str,
    product_composites: List[str],
    video_records: List[Dict],
    brand_identity: Dict,
    platforms: List[str],
    duration: int,
    max_retries: int = 2,
) -> Dict:
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

            out_dir = brand_variant_dir(
                BASE_OUTPUT, cid, variant_id,
                vr.get("message_angle", "benefit"),
            )
            exports = encoder.encode_all(master, out_dir, platform_enums, max_duration=duration)

            # Persist a copy of the master into the campaign output dir so it can be served/downloaded.
            master_out = os.path.join(out_dir, "master.mp4")
            try:
                if os.path.isfile(master) and not os.path.exists(master_out):
                    shutil.copy2(master, master_out)
            except Exception:
                master_out = master

            for exp in exports:
                if exp.file_path:
                    _insert_platform_export(
                        video_id, exp.platform, exp.file_path,
                        exp.file_size_mb, exp.resolution, exp.aspect_ratio,
                    )

            _update_video_record(
                video_id, status="completed", generation_progress=100,
                quality_score=qa_result.overall_score, file_path=master_out,
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
#  Pipeline: process static ads
# ────────────────────────────────────────────────────────────

def process_static_ads(
    campaign_id: str,
    static_ad_records: List[Dict],
    brand_identity: Dict,
    products: List[Dict],
    product_assets_map: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """
    Generate static ad images for all static ad records in the campaign.

    Each record references a template from template.json and contains
    messaging text.  The generator composes the final image using brand
    colors, product images, and the template layout.

    When ``product_composites`` are passed (from video pipeline), these
    pre-processed images (bg removed, brand bg applied, upscaled) are
    used instead of raw product URLs, producing much cleaner static ads.
    """
    cid = campaign_id
    work = tmp_dir(prefix="static_ads_")
    ad_width = 768
    ad_height = 1024

    try:
        generator = StaticAdGenerator(work)
        svg_generator = AnthropicSvgGenerator(work)
        qa = StaticAdValidator()
        use_anthropic = bool(settings.use_anthropic_svg_ads and settings.anthropic_api_key)

        # Build product lookup
        product_map: Dict[str, Dict] = {}
        for prod in products:
            product_map[str(prod["id"])] = prod

        brand_colors = brand_identity.get("colors", {})
        brand_name = brand_identity.get("brand_name", "")
        logo_url = brand_identity.get("logo_url")

        results = []
        for sa in static_ad_records:
            ad_id = str(sa["id"])
            template_id = sa.get("static_template_id", "")
            variant_id = sa.get("variant_id", 1)

            try:
                _update_static_ad_record(ad_id, status="generating")

                # Look up the template
                template = get_template_by_id(template_id) if template_id else None
                if not template:
                    from app.services.static_ad.template_registry import get_all_templates
                    all_tpls = get_all_templates()
                    template = all_tpls[0] if all_tpls else None

                if not template and not use_anthropic:
                    logger.warning("No static ad templates available, skipping ad %s", ad_id)
                    _update_static_ad_record(ad_id, status="failed")
                    results.append({"ad_id": ad_id, "status": "failed"})
                    continue

                # Resolve product image — prefer pre-processed composite
                image_url = sa.get("image_url", "")
                product_id = str(sa.get("product_id") or "")
                product_image_source = _resolve_product_image_source(
                    product_id, product_map, product_assets_map
                )
                anthropic_product_source = _resolve_product_image_source(
                    product_id, product_map, product_assets_map, prefer_no_bg=True
                )

                # image_url from user takes priority for the hero shot
                final_image = image_url if image_url else None

                output_path = None
                if use_anthropic:
                    ad_type = sa.get("ad_type", "product_specific")
                    product_images: List[str] = []
                    product_names: List[str] = []

                    if ad_type == "general_brand":
                        collab_products = _select_collab_products(products, variant_id)
                        for prod in collab_products:
                            pid = str(prod.get("id"))
                            src = _resolve_product_image_source(
                                pid, product_map, product_assets_map, prefer_no_bg=True
                            )
                            if src:
                                product_images.append(src)
                                product_names.append(prod.get("product_name", "Product"))
                    else:
                        src = final_image or anthropic_product_source
                        if src:
                            product_images = [src]
                            product_names = [product_map.get(product_id, {}).get("product_name", "Product")]

                    if product_images:
                        output_path = svg_generator.generate(
                            headline=sa.get("headline", ""),
                            subheading=sa.get("subheading", ""),
                            cta_text=sa.get("cta_text", ""),
                            body_text=sa.get("body_text", ""),
                            brand_colors=brand_colors,
                            brand_name=brand_name,
                            product_images=product_images,
                            product_names=product_names,
                            style_hint=_build_style_hint(sa),
                            width=ad_width,
                            height=ad_height,
                            variant_id=variant_id,
                            ad_id=ad_id,
                            ad_type=ad_type,
                        )

                # Fallback to template-based generator if Anthropic fails
                if not output_path:
                    if not template:
                        logger.warning("No template available for fallback ad %s", ad_id)
                        _update_static_ad_record(ad_id, status="failed")
                        results.append({"ad_id": ad_id, "status": "failed"})
                        continue
                    output_path = generator.generate(
                        template=template,
                        headline=sa.get("headline", ""),
                        subheading=sa.get("subheading", ""),
                        cta_text=sa.get("cta_text", ""),
                        body_text=sa.get("body_text", ""),
                        brand_colors=brand_colors,
                        brand_name=brand_name,
                        logo_url=logo_url,
                        product_image_url=product_image_source,
                        image_url=final_image,
                        width=ad_width,
                        height=ad_height,
                        variant_id=variant_id,
                        ad_id=ad_id,  # Pass ad_id to ensure unique filenames per product
                    )

                # Copy to campaign output directory
                out_dir = _static_ad_output_dir(cid, sa)
                ensure_dir(out_dir)
                final_path = os.path.join(out_dir, os.path.basename(output_path))
                if not os.path.exists(final_path):
                    shutil.copy2(output_path, final_path)

                # Create a thumbnail (smaller version)
                thumb_path = os.path.join(out_dir, f"thumb_{os.path.basename(output_path)}")
                if final_path.lower().endswith(".svg"):
                    # Keep SVG thumbnails as SVG; do not rasterize.
                    thumb_path = final_path
                else:
                    try:
                        from PIL import Image as PILImage
                        thumb = PILImage.open(final_path)
                        thumb.thumbnail((300, 300), PILImage.LANCZOS)
                        thumb.save(thumb_path, quality=85)
                    except Exception:
                        thumb_path = final_path

                fsize = file_size_mb(final_path)

                qa_score = 80.0
                if not final_path.lower().endswith(".svg"):
                    qa_result = qa.validate(
                        final_path,
                        expected_width=ad_width,
                        expected_height=ad_height,
                        headline=sa.get("headline", ""),
                        cta_text=sa.get("cta_text", ""),
                    )
                    qa_score = qa_result.overall_score

                _update_static_ad_record(
                    ad_id,
                    status="completed",
                    file_path=final_path,
                    thumbnail_path=thumb_path,
                    file_size_mb=fsize,
                    width=ad_width,
                    height=ad_height,
                    quality_score=qa_score,
                )
                results.append({
                    "ad_id": ad_id,
                    "status": "completed",
                    "file_path": final_path,
                    "quality_score": qa_score,
                })

            except Exception as exc:
                logger.error("Static ad generation failed for %s: %s", ad_id, exc)
                _update_static_ad_record(ad_id, status="failed")
                results.append({"ad_id": ad_id, "status": "failed"})

        return {"campaign_id": cid, "static_ads": results}

    except Exception as exc:
        logger.error("Static ads processing failed: %s", traceback.format_exc())
        for sa in static_ad_records:
            _update_static_ad_record(str(sa["id"]), status="failed")
        raise


def _static_ad_output_dir(campaign_id: str, static_ad: Dict) -> str:
    """Build output directory for a static ad."""
    ad_type = static_ad.get("ad_type", "product_specific")
    variant_id = static_ad.get("variant_id", 1)
    angle = static_ad.get("message_angle", "benefit")

    if ad_type == "general_brand":
        return os.path.join(
            BASE_OUTPUT,
            f"campaign_{campaign_id}",
            "static_ads",
            "general_brand",
            f"variant_{variant_id}_{angle}",
        )
    return os.path.join(
        BASE_OUTPUT,
        f"campaign_{campaign_id}",
        "static_ads",
        "product_specific",
        f"variant_{variant_id}_{angle}",
    )


# ────────────────────────────────────────────────────────────
#  Pipeline: full campaign orchestrator
# ────────────────────────────────────────────────────────────

def run_campaign(campaign_id: str) -> Dict:
    """
    Complete campaign pipeline – works identically whether called from
    a Celery task or from a background thread.
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

        work = tmp_dir(prefix="campaign_assets_")
        asset_proc = AssetProcessor(work)
        bg_primary = brand_identity.get("colors", {}).get("background", "#FFFFFF")
        bg_secondary = brand_identity.get("colors", {}).get("secondary", "#F0F0F0")

        # Group videos by product
        product_video_map: Dict[str, List[Dict]] = {}
        brand_video_list: List[Dict] = []
        for v in videos:
            v_dict = dict(v)
            product_plans = strategy.get("product_plans", [])
            if v.get("video_type") == "product_specific" and v.get("product_id"):
                pid = str(v["product_id"])
                if pid not in product_video_map:
                    product_video_map[pid] = []
                for pp in product_plans:
                    for var in pp.get("variants", []):
                        if var.get("variant_id") == v.get("variant_id"):
                            v_dict["creative"] = {
                                "video_style": pp.get("video_style", "product_hero"),
                                "pacing": var.get("pacing", "medium"),
                            }
                product_video_map[pid].append(v_dict)
            else:
                brand_plan = strategy.get("brand_plan", {})
                layouts = brand_plan.get("layout_types", ["sequential_carousel"])
                v_idx = v.get("variant_id", 1) - 1
                v_dict["layout_type"] = layouts[v_idx % len(layouts)] if layouts else "sequential_carousel"
                v_dict["pacing"] = "medium"
                for bv in brand_plan.get("variants", []):
                    if bv.get("variant_id") == v.get("variant_id"):
                        v_dict["pacing"] = bv.get("pacing", "medium")
                brand_video_list.append(v_dict)

        # Pre-download and composite all product images
        product_composites: List[str] = []
        product_assets_map: Dict[str, Dict] = {}
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
                product_assets_map[str(prod["id"])] = assets
            except Exception as exc:
                logger.warning("Asset prep failed for product %s: %s", prod["id"], exc)

        update_campaign_progress(cid, 15, "generating")
        _update_campaign_record(cid, overall_progress=15)

        # Process each product sequentially (in sync mode) or via Celery group
        for pid, vid_records in product_video_map.items():
            prod_data = product_data_map.get(
                pid,
                {"product_image_url": "", "product_name": "unknown", "product_index": 0},
            )
            try:
                process_product_videos(
                    cid, pid, prod_data, vid_records,
                    brand_identity, platforms, duration,
                )
            except Exception as exc:
                logger.error("Product %s failed: %s", pid, exc)

        if brand_video_list and product_composites:
            try:
                process_brand_videos(
                    cid, product_composites, brand_video_list,
                    brand_identity, platforms, duration,
                )
            except Exception as exc:
                logger.error("Brand videos failed: %s", exc)

        # ── Generate static ads ────────────────────────────
        static_ads = data.get("static_ads", [])
        if static_ads:
            try:
                queued_static = [
                    sa for sa in static_ads
                    if sa.get("status") in ("queued", None)
                ]
                if queued_static:
                    # Pass processed composites so static ads use clean
                    # bg-removed product images on brand backgrounds
                    process_static_ads(
                        cid, queued_static, brand_identity, products,
                        product_assets_map=product_assets_map,
                    )
            except Exception as exc:
                logger.error("Static ads failed: %s", exc)

        # ── Finalise ───────────────────────────────────────
        final_data = _get_campaign_data(cid)
        total = len(final_data["videos"])
        completed = sum(1 for v in final_data["videos"] if v.get("status") == "completed")
        failed = sum(1 for v in final_data["videos"] if v.get("status") == "failed")

        if failed == total:
            final_status = "failed"
        elif completed > 0:
            final_status = "completed"
        else:
            final_status = "failed"

        progress = round((completed / total) * 100, 1) if total else 0
        _update_campaign_record(cid, status=final_status, overall_progress=progress)
        update_campaign_progress(cid, progress, final_status)

        # Generate campaign_summary.json
        try:
            from app.services.download import generate_campaign_summary
            generate_campaign_summary(BASE_OUTPUT, cid, final_data)
        except Exception as exc:
            logger.warning("Failed to write campaign summary: %s", exc)

        # Upload to storage (local copy or S3)
        try:
            from app.services.storage import get_storage
            storage = get_storage()
            storage.ensure_bucket()
            camp_dir_path = os.path.join(BASE_OUTPUT, f"campaign_{cid}")
            if os.path.isdir(camp_dir_path):
                storage.upload_directory(camp_dir_path, f"campaigns/{cid}")
                # NOTE: This module uses stdlib logging; don't pass structured kwargs.
                logger.info("campaign_uploaded campaign_id=%s", cid)
        except Exception as exc:
            logger.warning("Storage upload failed (non-fatal): %s", exc)

        # Fire webhooks
        _fire_campaign_webhook(cid, final_status, {
            "campaign_id": cid, "status": final_status,
            "total_videos": total, "completed": completed, "failed": failed,
        })

        return {
            "campaign_id": cid, "status": final_status,
            "total_videos": total, "completed": completed, "failed": failed,
        }

    except Exception as exc:
        logger.error("Campaign pipeline failed: %s", traceback.format_exc())
        _update_campaign_record(cid, status="failed", error_message=str(exc))
        update_campaign_progress(cid, 0, "failed")
        _fire_campaign_webhook(cid, "failed", {
            "campaign_id": cid, "status": "failed", "error": str(exc),
        })
        raise


def _fire_campaign_webhook(campaign_id: str, status: str, payload: dict) -> None:
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
        send_webhook_sync(webhook_url, f"campaign.{status}", payload, secret=webhook_secret)
    except Exception as exc:
        logger.warning("Webhook fire failed: %s", exc)
