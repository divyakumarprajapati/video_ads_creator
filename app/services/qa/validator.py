"""
Quality Assurance Validator.

Runs a battery of automated checks on generated videos and returns a
composite quality score (0–100).  Videos scoring below the threshold are
flagged for retry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.utils.ffmpeg import probe, VideoInfo

logger = get_logger(__name__)

# Threshold below which a video is rejected
QA_PASS_THRESHOLD = 80


@dataclass
class QACheck:
    name: str
    passed: bool
    score: float  # 0–100
    message: str = ""


@dataclass
class QAResult:
    video_path: str
    overall_score: float
    passed: bool
    checks: List[QACheck] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "video_path": self.video_path,
            "overall_score": self.overall_score,
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "score": c.score, "message": c.message}
                for c in self.checks
            ],
        }


class QAValidator:
    """Run all quality checks on a video file."""

    def __init__(self, threshold: int = QA_PASS_THRESHOLD):
        self.threshold = threshold

    def validate(
        self,
        video_path: str,
        *,
        expected_min_duration: float = 3.0,
        expected_max_duration: float = 65.0,
        expected_min_width: int = 480,
        expected_min_height: int = 480,
        expected_min_fps: float = 24.0,
        max_file_size_mb: float = 300.0,
    ) -> QAResult:
        checks: List[QACheck] = []

        # Check 1: File exists and is non-empty
        exists = os.path.isfile(video_path) and os.path.getsize(video_path) > 0
        checks.append(QACheck(
            name="file_exists",
            passed=exists,
            score=100.0 if exists else 0.0,
            message="" if exists else "Video file missing or empty",
        ))
        if not exists:
            return self._build_result(video_path, checks)

        # Get video info
        try:
            info = probe(video_path)
        except Exception as exc:
            checks.append(QACheck(
                name="probe", passed=False, score=0.0,
                message=f"Cannot probe video: {exc}",
            ))
            return self._build_result(video_path, checks)

        # Check 2: Resolution
        res_ok = info.width >= expected_min_width and info.height >= expected_min_height
        res_score = 100.0 if res_ok else max(
            0.0, 100.0 * min(info.width / expected_min_width, info.height / expected_min_height)
        )
        checks.append(QACheck(
            name="resolution",
            passed=res_ok,
            score=res_score,
            message=f"{info.width}x{info.height}",
        ))

        # Check 3: Duration
        dur_ok = expected_min_duration <= info.duration <= expected_max_duration
        dur_score = 100.0 if dur_ok else 50.0
        checks.append(QACheck(
            name="duration",
            passed=dur_ok,
            score=dur_score,
            message=f"{info.duration:.1f}s",
        ))

        # Check 4: Frame rate
        fps_ok = info.fps >= expected_min_fps
        fps_score = 100.0 if fps_ok else max(0.0, 100.0 * info.fps / expected_min_fps)
        checks.append(QACheck(
            name="frame_rate",
            passed=fps_ok,
            score=fps_score,
            message=f"{info.fps} fps",
        ))

        # Check 5: Codec (should be h264)
        codec_ok = info.codec in ("h264", "libx264", "avc1")
        checks.append(QACheck(
            name="codec",
            passed=codec_ok,
            score=100.0 if codec_ok else 60.0,
            message=info.codec,
        ))

        # Check 6: File size
        size_ok = info.file_size_mb <= max_file_size_mb
        checks.append(QACheck(
            name="file_size",
            passed=size_ok,
            score=100.0 if size_ok else 50.0,
            message=f"{info.file_size_mb:.1f} MB",
        ))

        # Check 7: Clarity heuristic (file_size / duration – very low = likely broken)
        if info.duration > 0:
            bitrate_mbps = (info.file_size_mb * 8) / info.duration
            clarity_ok = bitrate_mbps > 0.5  # at least 0.5 Mbps
            checks.append(QACheck(
                name="clarity",
                passed=clarity_ok,
                score=100.0 if clarity_ok else 40.0,
                message=f"{bitrate_mbps:.2f} Mbps",
            ))

        return self._build_result(video_path, checks)

    def _build_result(self, video_path: str, checks: List[QACheck]) -> QAResult:
        if not checks:
            return QAResult(video_path=video_path, overall_score=0.0, passed=False, checks=[])

        weights = {
            "file_exists": 3.0,
            "resolution": 2.0,
            "duration": 1.5,
            "frame_rate": 1.0,
            "codec": 1.0,
            "file_size": 1.0,
            "clarity": 1.5,
            "probe": 3.0,
        }
        total_weight = sum(weights.get(c.name, 1.0) for c in checks)
        weighted = sum(c.score * weights.get(c.name, 1.0) for c in checks)
        overall = round(weighted / total_weight, 1) if total_weight else 0.0

        return QAResult(
            video_path=video_path,
            overall_score=overall,
            passed=overall >= self.threshold,
            checks=checks,
        )
