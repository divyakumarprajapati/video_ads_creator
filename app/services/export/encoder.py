"""
Platform-Specific Export Service.

Takes a raw master video and encodes it into every requested platform's
format, generating thumbnails and metadata along the way.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, List

from app.core.enums import Platform
from app.core.logging import get_logger
from app.services.strategy.platform_specs import PlatformSpec, get_platform_spec
from app.utils.ffmpeg import encode_for_platform, extract_thumbnail, probe
from app.utils.file_utils import ensure_dir, file_size_mb

logger = get_logger(__name__)


@dataclass
class ExportResult:
    platform: str
    file_path: str
    file_size_mb: float
    resolution: str
    aspect_ratio: str
    thumbnail_path: str


class PlatformEncoder:
    """Encode one master video into N platform exports."""

    def encode_all(
        self,
        master_path: str,
        output_dir: str,
        platforms: List[Platform],
        max_duration: float | None = None,
    ) -> List[ExportResult]:
        """Return a list of *ExportResult* – one per platform."""
        ensure_dir(output_dir)
        results: List[ExportResult] = []

        for platform in platforms:
            spec = get_platform_spec(platform)
            out_file = os.path.join(output_dir, f"{platform.value}.mp4")
            thumb_file = os.path.join(output_dir, f"{platform.value}_thumb.jpg")

            try:
                encode_for_platform(
                    master_path, out_file,
                    width=spec.width, height=spec.height,
                    fps=spec.fps, crf=spec.crf,
                    codec=spec.codec,
                    audio_codec=spec.audio_codec,
                    audio_bitrate=spec.audio_bitrate,
                    max_duration=max_duration or spec.max_duration,
                )
                extract_thumbnail(out_file, thumb_file, timestamp=1.0)

                results.append(ExportResult(
                    platform=platform.value,
                    file_path=out_file,
                    file_size_mb=file_size_mb(out_file),
                    resolution=f"{spec.width}x{spec.height}",
                    aspect_ratio=spec.aspect_ratio,
                    thumbnail_path=thumb_file,
                ))
                logger.info("platform_encoded", platform=platform.value, size_mb=file_size_mb(out_file))

            except Exception as exc:
                logger.error("platform_encode_failed", platform=platform.value, error=str(exc))
                results.append(ExportResult(
                    platform=platform.value,
                    file_path="",
                    file_size_mb=0.0,
                    resolution=f"{spec.width}x{spec.height}",
                    aspect_ratio=spec.aspect_ratio,
                    thumbnail_path="",
                ))

        # Write metadata JSON
        meta_path = os.path.join(output_dir, "metadata.json")
        meta = {
            "exports": [asdict(r) for r in results],
            "master_video": master_path,
        }
        try:
            info = probe(master_path)
            meta["master_info"] = {
                "width": info.width,
                "height": info.height,
                "duration": info.duration,
                "fps": info.fps,
                "codec": info.codec,
                "file_size_mb": info.file_size_mb,
            }
        except Exception:
            pass
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        return results
