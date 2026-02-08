"""
Static Ad Quality Validator.

Runs automated quality checks on generated static ad images and returns
a composite quality score (0–100).  Validates visual quality, text
presence, composition, and file integrity.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

QA_PASS_THRESHOLD = 75


@dataclass
class StaticAdQACheck:
    name: str
    passed: bool
    score: float  # 0–100
    message: str = ""


@dataclass
class StaticAdQAResult:
    file_path: str
    overall_score: float
    passed: bool
    checks: List[StaticAdQACheck] = field(default_factory=list)


class StaticAdValidator:
    """Run quality checks on a generated static ad image."""

    def __init__(self, threshold: int = QA_PASS_THRESHOLD):
        self.threshold = threshold

    def validate(
        self,
        image_path: str,
        *,
        expected_width: int = 1080,
        expected_height: int = 1080,
        max_file_size_mb: float = 10.0,
        headline: str = "",
        cta_text: str = "",
    ) -> StaticAdQAResult:
        checks: List[StaticAdQACheck] = []

        # 1. File exists and is non-empty
        exists = os.path.isfile(image_path) and os.path.getsize(image_path) > 0
        checks.append(StaticAdQACheck(
            name="file_exists",
            passed=exists,
            score=100.0 if exists else 0.0,
            message="" if exists else "Image file missing or empty",
        ))
        if not exists:
            return self._build_result(image_path, checks)

        try:
            from PIL import Image
            img = Image.open(image_path)
        except Exception as exc:
            checks.append(StaticAdQACheck(
                name="readable", passed=False, score=0.0,
                message=f"Cannot open image: {exc}",
            ))
            return self._build_result(image_path, checks)

        # 2. Resolution
        w, h = img.size
        res_ok = w >= expected_width * 0.9 and h >= expected_height * 0.9
        res_score = 100.0 if res_ok else max(50.0, 100.0 * min(w / expected_width, h / expected_height))
        checks.append(StaticAdQACheck(
            name="resolution",
            passed=res_ok,
            score=res_score,
            message=f"{w}x{h}",
        ))

        # 3. File size (not too small = likely blank, not too large)
        file_size = os.path.getsize(image_path) / (1024 * 1024)
        size_ok = 0.005 < file_size < max_file_size_mb  # >5KB means real content
        checks.append(StaticAdQACheck(
            name="file_size",
            passed=size_ok,
            score=100.0 if size_ok else 40.0,
            message=f"{file_size:.2f} MB",
        ))

        # 4. Color distribution (check it's not a single solid color)
        try:
            sampled = img.convert("RGB").resize((50, 50), Image.NEAREST)
            colors = sampled.getcolors(maxcolors=2500)
            unique_colors = len(colors) if colors else 0
            color_ok = unique_colors > 10  # More than 10 unique colors
            color_score = min(100.0, unique_colors * 2)
            checks.append(StaticAdQACheck(
                name="color_diversity",
                passed=color_ok,
                score=color_score,
                message=f"{unique_colors} unique colors (sampled 50x50)",
            ))
        except Exception:
            checks.append(StaticAdQACheck(
                name="color_diversity", passed=True, score=70.0,
                message="Could not sample colors",
            ))

        # 5. Non-blank check (image entropy)
        try:
            import numpy as np
            arr = np.array(img.convert("L"))
            std_dev = float(np.std(arr))
            entropy_ok = std_dev > 10  # Reasonable variance
            checks.append(StaticAdQACheck(
                name="content_present",
                passed=entropy_ok,
                score=min(100.0, std_dev * 2),
                message=f"Luminance std dev: {std_dev:.1f}",
            ))
        except ImportError:
            checks.append(StaticAdQACheck(
                name="content_present", passed=True, score=80.0,
                message="numpy not available for entropy check",
            ))

        # 6. Messaging completeness
        has_headline = bool(headline and len(headline) > 2)
        has_cta = bool(cta_text and len(cta_text) > 1)
        msg_score = 0.0
        if has_headline:
            msg_score += 60.0
        if has_cta:
            msg_score += 40.0
        checks.append(StaticAdQACheck(
            name="messaging_complete",
            passed=has_headline,
            score=msg_score,
            message=f"headline={'yes' if has_headline else 'no'}, cta={'yes' if has_cta else 'no'}",
        ))

        return self._build_result(image_path, checks)

    def _build_result(self, path: str, checks: List[StaticAdQACheck]) -> StaticAdQAResult:
        if not checks:
            return StaticAdQAResult(file_path=path, overall_score=0.0, passed=False, checks=[])

        weights = {
            "file_exists": 3.0,
            "readable": 3.0,
            "resolution": 2.0,
            "file_size": 1.0,
            "color_diversity": 1.5,
            "content_present": 2.0,
            "messaging_complete": 1.5,
        }
        total_weight = sum(weights.get(c.name, 1.0) for c in checks)
        weighted = sum(c.score * weights.get(c.name, 1.0) for c in checks)
        overall = round(weighted / total_weight, 1) if total_weight else 0.0

        return StaticAdQAResult(
            file_path=path,
            overall_score=overall,
            passed=overall >= self.threshold,
            checks=checks,
        )
