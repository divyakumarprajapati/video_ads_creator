"""
Platform-specific export specifications.

Single source of truth for every platform's aspect ratio, resolution, duration
limits, codec requirements, and file-size caps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from app.core.enums import Platform


@dataclass(frozen=True)
class PlatformSpec:
    platform: Platform
    aspect_ratio: str          # e.g. "1:1", "9:16"
    width: int
    height: int
    max_duration: int          # seconds
    min_duration: int          # seconds
    codec: str
    fps: int
    audio_codec: str
    audio_bitrate: str
    max_file_size_mb: float
    crf: int


PLATFORM_SPECS: Dict[Platform, PlatformSpec] = {
    Platform.INSTAGRAM_FEED: PlatformSpec(
        platform=Platform.INSTAGRAM_FEED,
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        max_duration=60,
        min_duration=3,
        codec="libx264",
        fps=30,
        audio_codec="aac",
        audio_bitrate="192k",
        max_file_size_mb=100.0,
        crf=23,
    ),
    Platform.INSTAGRAM_STORY: PlatformSpec(
        platform=Platform.INSTAGRAM_STORY,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        max_duration=60,
        min_duration=3,
        codec="libx264",
        fps=30,
        audio_codec="aac",
        audio_bitrate="192k",
        max_file_size_mb=100.0,
        crf=23,
    ),
    Platform.TIKTOK: PlatformSpec(
        platform=Platform.TIKTOK,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        max_duration=60,
        min_duration=5,
        codec="libx264",
        fps=30,
        audio_codec="aac",
        audio_bitrate="192k",
        max_file_size_mb=287.0,
        crf=23,
    ),
    Platform.YOUTUBE_SHORTS: PlatformSpec(
        platform=Platform.YOUTUBE_SHORTS,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        max_duration=60,
        min_duration=5,
        codec="libx264",
        fps=30,
        audio_codec="aac",
        audio_bitrate="192k",
        max_file_size_mb=256.0,
        crf=23,
    ),
    Platform.META_ADS: PlatformSpec(
        platform=Platform.META_ADS,
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        max_duration=60,
        min_duration=3,
        codec="libx264",
        fps=30,
        audio_codec="aac",
        audio_bitrate="192k",
        max_file_size_mb=100.0,
        crf=23,
    ),
}


def get_platform_spec(platform: Platform) -> PlatformSpec:
    return PLATFORM_SPECS[platform]
