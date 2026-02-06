"""
Video Generation Service.

Turns prepared assets + creative plan into raw video clips using a
combination of FFmpeg effects and (optionally) AI animation models.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.ffmpeg import (
    add_fade_transitions,
    add_multi_text_overlay,
    apply_color_grade,
    apply_zoom_effect,
    concat_videos,
    create_grid_video,
    create_video_from_image,
)

logger = get_logger(__name__)
settings = get_settings()


class VideoGenerator:
    """
    Generates raw video clips.

    Strategies
    ----------
    - **product_hero**: zoom on product composite, text overlays
    - **lifestyle_scene**: slower pace, gradient background, soft text
    - **kinetic_text**: fast cuts, bold text animations
    - **abstract_motion**: animated background + centred product
    - **multi_product**: grid / carousel / hero-supporting layouts
    """

    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

    # ── Product-Specific Video ─────────────────────────────

    def generate_product_video(
        self,
        *,
        composite_path: str,
        video_style: str,
        variant_id: int,
        primary_message: str,
        secondary_message: str,
        cta_text: str,
        pacing: str = "medium",
        duration: int = 15,
        width: int = 1080,
        height: int = 1080,
        brand_colors: Optional[Dict] = None,
    ) -> str:
        """Generate a single product video variant.  Returns path to .mp4."""
        out_name = f"product_v{variant_id}_{video_style}.mp4"
        output = os.path.join(self.work_dir, out_name)
        if os.path.exists(output):
            return output

        # Step 1: Create base video from composite image
        base = os.path.join(self.work_dir, f"base_v{variant_id}.mp4")
        create_video_from_image(
            composite_path, base,
            duration=float(duration), width=width, height=height,
        )

        # Step 2: Apply motion effect based on style
        motion = os.path.join(self.work_dir, f"motion_v{variant_id}.mp4")
        if video_style in ("product_hero", "lifestyle_scene"):
            try:
                apply_zoom_effect(base, motion, zoom_start=1.0, zoom_end=1.12)
            except Exception:
                motion = base
        else:
            motion = base

        # Step 3: Colour grading (subtle brand tint)
        graded = os.path.join(self.work_dir, f"graded_v{variant_id}.mp4")
        try:
            sat = 1.1 if pacing == "fast" else 1.0
            apply_color_grade(motion, graded, brightness=0.02, contrast=1.05, saturation=sat)
        except Exception:
            graded = motion

        # Step 4: Text overlays
        pacing_secs = {"fast": 2.0, "medium": 3.0, "slow": 4.0}.get(pacing, 3.0)
        texts = [
            {
                "text": primary_message,
                "fontsize": 56,
                "fontcolor": "white",
                "x": "(w-text_w)/2",
                "y": "60",
                "start_time": 0.5,
                "end_time": 0.5 + pacing_secs,
                "box": True,
                "boxcolor": "black@0.6",
            },
            {
                "text": secondary_message,
                "fontsize": 36,
                "fontcolor": "white",
                "x": "(w-text_w)/2",
                "y": "140",
                "start_time": pacing_secs,
                "end_time": pacing_secs * 2,
                "box": True,
                "boxcolor": "black@0.4",
            },
            {
                "text": cta_text,
                "fontsize": 48,
                "fontcolor": "yellow",
                "x": "(w-text_w)/2",
                "y": "h-th-80",
                "start_time": duration - pacing_secs - 0.5,
                "end_time": float(duration),
                "box": True,
                "boxcolor": "black@0.7",
            },
        ]
        with_text = os.path.join(self.work_dir, f"text_v{variant_id}.mp4")
        try:
            add_multi_text_overlay(graded, with_text, texts)
        except Exception:
            with_text = graded

        # Step 5: Fade transitions
        try:
            add_fade_transitions(with_text, output, fade_in=0.5, fade_out=0.5)
        except Exception:
            # Copy as-is if fade fails
            import shutil
            shutil.copy2(with_text, output)

        logger.info("product_video_generated", variant=variant_id, style=video_style)
        return output

    # ── AnimateDiff AI animation (optional) ────────────────

    def animate_with_animatediff(
        self,
        image_path: str,
        output_path: str,
        prompt: str = "smooth product rotation, studio lighting",
        num_frames: int = 16,
    ) -> Optional[str]:
        """
        Use AnimateDiff to create a short animated clip from a still image.
        Returns None if models are not available.
        """
        try:
            import torch
            from diffusers import AnimateDiffPipeline, MotionAdapter, DDIMScheduler

            adapter = MotionAdapter.from_pretrained(settings.animatediff_model_path)
            pipe = AnimateDiffPipeline.from_pretrained(
                settings.sdxl_model_path,
                motion_adapter=adapter,
                torch_dtype=torch.float16,
            ).to("cuda")
            pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config)

            frames = pipe(prompt, num_frames=num_frames, num_inference_steps=20).frames[0]
            # Save frames as video
            from diffusers.utils import export_to_video
            export_to_video(frames, output_path, fps=settings.default_fps)
            return output_path
        except Exception as exc:
            logger.warning("animatediff_unavailable", error=str(exc))
            return None

    # ── General-Brand Multi-Product Video ──────────────────

    def generate_brand_video(
        self,
        *,
        product_composites: List[str],
        layout_type: str,
        variant_id: int,
        primary_message: str,
        secondary_message: str,
        cta_text: str,
        pacing: str = "medium",
        duration: int = 15,
        width: int = 1080,
        height: int = 1080,
    ) -> str:
        """Generate a general-brand video showcasing multiple products."""
        out_name = f"brand_v{variant_id}_{layout_type}.mp4"
        output = os.path.join(self.work_dir, out_name)
        if os.path.exists(output):
            return output

        if layout_type == "grid_layout" and len(product_composites) >= 4:
            return self._grid_brand_video(
                product_composites, output, variant_id,
                primary_message, secondary_message, cta_text,
                duration, width, height, pacing,
            )

        if layout_type == "sequential_carousel":
            return self._carousel_brand_video(
                product_composites, output, variant_id,
                primary_message, secondary_message, cta_text,
                duration, width, height, pacing,
            )

        # Default: hero_supporting / lifestyle_montage → carousel fallback
        return self._carousel_brand_video(
            product_composites, output, variant_id,
            primary_message, secondary_message, cta_text,
            duration, width, height, pacing,
        )

    def _grid_brand_video(
        self, composites, output, variant_id,
        primary_msg, secondary_msg, cta, duration, w, h, pacing,
    ) -> str:
        cols = 2 if len(composites) <= 4 else 3
        rows = 2 if len(composites) <= 4 else 3
        grid = os.path.join(self.work_dir, f"grid_v{variant_id}.mp4")
        try:
            create_grid_video(
                composites[:cols * rows], grid,
                grid_size=(cols, rows),
                cell_width=w // cols, cell_height=h // rows,
                duration=float(duration),
            )
        except Exception:
            # Fallback to carousel
            return self._carousel_brand_video(
                composites, output, variant_id,
                primary_msg, secondary_msg, cta, duration, w, h, pacing,
            )

        # Add text overlays
        pacing_secs = {"fast": 2.0, "medium": 3.0, "slow": 4.0}.get(pacing, 3.0)
        texts = [
            {"text": primary_msg, "fontsize": 52, "fontcolor": "white",
             "x": "(w-text_w)/2", "y": "40", "start_time": 0.5,
             "end_time": pacing_secs + 0.5, "box": True, "boxcolor": "black@0.6"},
            {"text": cta, "fontsize": 44, "fontcolor": "yellow",
             "x": "(w-text_w)/2", "y": "h-th-60",
             "start_time": duration - pacing_secs, "end_time": float(duration),
             "box": True, "boxcolor": "black@0.7"},
        ]
        try:
            add_multi_text_overlay(grid, output, texts)
        except Exception:
            import shutil
            shutil.copy2(grid, output)
        return output

    def _carousel_brand_video(
        self, composites, output, variant_id,
        primary_msg, secondary_msg, cta, duration, w, h, pacing,
    ) -> str:
        """Show products one-by-one, concatenated."""
        per_product = max(2.0, duration / max(len(composites), 1))
        clips = []
        for i, comp in enumerate(composites[:8]):  # cap at 8
            clip = os.path.join(self.work_dir, f"carousel_v{variant_id}_p{i}.mp4")
            create_video_from_image(comp, clip, duration=per_product, width=w, height=h)
            clips.append(clip)

        joined = os.path.join(self.work_dir, f"carousel_joined_v{variant_id}.mp4")
        try:
            concat_videos(clips, joined)
        except Exception:
            joined = clips[0] if clips else output

        # Overlays
        total_dur = per_product * min(len(composites), 8)
        pacing_secs = {"fast": 2.0, "medium": 3.0, "slow": 4.0}.get(pacing, 3.0)
        texts = [
            {"text": primary_msg, "fontsize": 52, "fontcolor": "white",
             "x": "(w-text_w)/2", "y": "40", "start_time": 0.3,
             "end_time": pacing_secs, "box": True, "boxcolor": "black@0.6"},
            {"text": cta, "fontsize": 44, "fontcolor": "yellow",
             "x": "(w-text_w)/2", "y": "h-th-60",
             "start_time": total_dur - pacing_secs, "end_time": total_dur,
             "box": True, "boxcolor": "black@0.7"},
        ]
        try:
            add_multi_text_overlay(joined, output, texts)
        except Exception:
            import shutil
            shutil.copy2(joined, output)

        logger.info("brand_video_generated", variant=variant_id, layout=composites)
        return output
