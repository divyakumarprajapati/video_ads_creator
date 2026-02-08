"""
Asset Preparation Service.

Downloads product images, removes backgrounds, upscales, generates
backgrounds, and caches results.  Each method is idempotent – if the
output file already exists it is returned immediately.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.image import (
    composite_product_on_background,
    create_gradient_background,
    create_solid_background,
    download_image,
    enhance_image,
    extract_subject_rgba,
    trim_transparent,
    resize_image,
)

logger = get_logger(__name__)
settings = get_settings()


class AssetProcessor:
    """Stateless helper – all state lives on disk (cached by path)."""

    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

    MAX_IMAGE_SIZE_BYTES = settings.max_image_size_mb * 1024 * 1024
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

    # ── Download ───────────────────────────────────────────

    def download_product_image(self, url: str, product_idx: int) -> str:
        dest = os.path.join(self.work_dir, f"product_{product_idx}_original.png")
        if os.path.exists(dest):
            return dest
        path = download_image(url, dest)
        self._validate_image(path, product_idx)
        return path

    def _validate_image(self, path: str, product_idx: int) -> None:
        """Check file size and image format after download."""
        file_size = os.path.getsize(path)
        if file_size > self.MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Product {product_idx} image exceeds {settings.max_image_size_mb} MB limit "
                f"(actual: {file_size / (1024*1024):.1f} MB)"
            )
        # Validate that Pillow can open it (format check)
        try:
            from PIL import Image
            img = Image.open(path)
            img.verify()
            fmt = (img.format or "").lower()
            if fmt not in ("jpeg", "jpg", "png", "webp"):
                logger.warning("unusual_image_format", format=fmt, product_idx=product_idx)
        except Exception as exc:
            raise ValueError(
                f"Product {product_idx} image is not a valid image file: {exc}"
            )

    # ── Background removal ─────────────────────────────────

    def remove_background(self, image_path: str, product_idx: int) -> str:
        dest = os.path.join(self.work_dir, f"product_{product_idx}_nobg.png")
        if os.path.exists(dest):
            return dest
        try:
            from rembg import remove
            from PIL import Image

            inp = Image.open(image_path)
            out = remove(inp)
            out = trim_transparent(out)
            out.save(dest)
            logger.info("background_removed", product_idx=product_idx)
            return dest
        except Exception as exc:
            logger.warning("rembg_failed_falling_back", error=str(exc))
            try:
                from PIL import Image
                raw = Image.open(image_path)
                cleaned = extract_subject_rgba(raw)
                cleaned = enhance_image(cleaned)
                cleaned.save(dest)
                return dest
            except Exception:
                # Last-resort fallback: copy original
                import shutil
                shutil.copy2(image_path, dest)
                return dest

    # ── Upscale ────────────────────────────────────────────

    def upscale_image(self, image_path: str, product_idx: int, target: int = 2048) -> str:
        dest = os.path.join(self.work_dir, f"product_{product_idx}_upscaled.png")
        if os.path.exists(dest):
            return dest
        try:
            # Try Real-ESRGAN if available
            from PIL import Image
            img = Image.open(image_path)
            if max(img.size) >= target:
                img.save(dest)
                return dest
            # Attempt Real-ESRGAN via subprocess
            import subprocess
            result = subprocess.run(
                [
                    "realesrgan-ncnn-vulkan",
                    "-i", image_path,
                    "-o", dest,
                    "-s", "4",
                ],
                capture_output=True,
            )
            if result.returncode == 0 and os.path.exists(dest):
                logger.info("upscaled_with_realesrgan", product_idx=product_idx)
                return dest
        except Exception:
            pass

        # Fallback: Pillow LANCZOS upscale
        return resize_image(image_path, dest, size=(target, target), keep_aspect=True)

    # ── Background generation ──────────────────────────────

    def generate_background(
        self,
        product_idx: int,
        *,
        bg_color: str = "#FFFFFF",
        secondary_color: str = "#F0F0F0",
        size: tuple = (1080, 1080),
        use_gradient: bool = True,
    ) -> str:
        dest = os.path.join(self.work_dir, f"bg_{product_idx}.png")
        if os.path.exists(dest):
            return dest
        if use_gradient:
            return create_gradient_background(dest, size=size,
                                              color_top=bg_color,
                                              color_bottom=secondary_color)
        return create_solid_background(dest, size=size, color=bg_color)

    # ── Composite (product on background) ──────────────────

    def composite(self, product_path: str, bg_path: str, product_idx: int) -> str:
        dest = os.path.join(self.work_dir, f"composite_{product_idx}.png")
        if os.path.exists(dest):
            return dest
        return composite_product_on_background(product_path, bg_path, dest)

    # ── SDXL image generation (optional AI) ────────────────

    def generate_image_sdxl(
        self,
        prompt: str,
        dest_name: str,
        *,
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
    ) -> Optional[str]:
        """
        Generate an image with SDXL.  Returns None if the model is not
        available (graceful degradation).
        """
        dest = os.path.join(self.work_dir, dest_name)
        if os.path.exists(dest):
            return dest
        try:
            import torch
            from diffusers import StableDiffusionXLPipeline

            pipe = StableDiffusionXLPipeline.from_pretrained(
                settings.sdxl_model_path,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            ).to("cuda")

            image = pipe(
                prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
            ).images[0]
            image.save(dest)
            logger.info("sdxl_image_generated", prompt=prompt[:60])
            return dest
        except Exception as exc:
            logger.warning("sdxl_unavailable", error=str(exc))
            return None

    # ── Full asset-prep pipeline for one product ───────────

    def prepare_product_assets(
        self,
        image_url: str,
        product_idx: int,
        bg_primary: str = "#FFFFFF",
        bg_secondary: str = "#F0F0F0",
    ) -> dict:
        """
        Run the full asset prep pipeline and return a dict of paths:
        original, no_bg, upscaled, background, composite
        """
        original = self.download_product_image(image_url, product_idx)
        no_bg = self.remove_background(original, product_idx)
        upscaled = self.upscale_image(no_bg, product_idx)
        background = self.generate_background(
            product_idx, bg_color=bg_primary, secondary_color=bg_secondary
        )
        composite = self.composite(upscaled, background, product_idx)

        return {
            "original": original,
            "no_bg": no_bg,
            "upscaled": upscaled,
            "background": background,
            "composite": composite,
        }
