"""
FFmpeg wrapper – thin, typed interface around the ``ffmpeg`` CLI.

Every function builds the command-line arguments, executes the process,
and returns structured results.  No global state.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

FFMPEG = settings.ffmpeg_path
FFPROBE = settings.ffprobe_path


@dataclass
class VideoInfo:
    width: int
    height: int
    duration: float
    fps: float
    codec: str
    file_size_mb: float


def probe(path: str) -> VideoInfo:
    """Return metadata for a video file."""
    cmd = [
        FFPROBE, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)

    video_stream = next(
        (s for s in data.get("streams", []) if s["codec_type"] == "video"), {}
    )
    fmt = data.get("format", {})

    fps_str = video_stream.get("r_frame_rate", "30/1")
    num, den = fps_str.split("/")
    fps = float(num) / float(den) if float(den) else 30.0

    return VideoInfo(
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        duration=float(fmt.get("duration", 0)),
        fps=round(fps, 2),
        codec=video_stream.get("codec_name", "unknown"),
        file_size_mb=round(int(fmt.get("size", 0)) / (1024 * 1024), 2),
    )


def create_video_from_image(
    image_path: str,
    output_path: str,
    duration: float = 5.0,
    width: int = 1080,
    height: int = 1080,
    fps: int = 30,
    crf: int = 23,
) -> str:
    """Create a static video from a single image (with padding/scaling)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", image_path,
        "-t", str(duration),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-crf", str(crf),
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def add_text_overlay(
    input_path: str,
    output_path: str,
    text: str,
    *,
    fontsize: int = 48,
    fontcolor: str = "white",
    x: str = "(w-text_w)/2",
    y: str = "h-th-60",
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    font: str = "Arial",
    box: bool = True,
    boxcolor: str = "black@0.5",
) -> str:
    """Burn a text overlay onto a video."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    enable = f"between(t,{start_time},{end_time})" if end_time else "1"
    drawtext = (
        f"drawtext=text='{_escape(text)}':"
        f"fontsize={fontsize}:fontcolor={fontcolor}:"
        f"x={x}:y={y}:enable='{enable}'"
    )
    if box:
        drawtext += f":box=1:boxcolor={boxcolor}:boxborderw=10"

    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", drawtext, "-c:v", "libx264",
           "-crf", "23", "-c:a", "copy", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def add_multi_text_overlay(
    input_path: str,
    output_path: str,
    texts: List[Dict],
) -> str:
    """
    Add multiple text overlays in one pass.

    Each item in *texts*: {"text", "fontsize", "fontcolor", "x", "y",
                           "start_time", "end_time", "box", "boxcolor"}
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    parts = []
    for t in texts:
        enable = (
            f"between(t,{t.get('start_time', 0)},{t['end_time']})"
            if "end_time" in t else "1"
        )
        part = (
            f"drawtext=text='{_escape(t['text'])}':"
            f"fontsize={t.get('fontsize', 48)}:"
            f"fontcolor={t.get('fontcolor', 'white')}:"
            f"x={t.get('x', '(w-text_w)/2')}:"
            f"y={t.get('y', 'h-th-60')}:"
            f"enable='{enable}'"
        )
        if t.get("box", True):
            part += f":box=1:boxcolor={t.get('boxcolor', 'black@0.5')}:boxborderw=10"
        parts.append(part)

    vf = ",".join(parts)
    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", vf, "-c:v", "libx264",
           "-crf", "23", "-c:a", "copy", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def apply_zoom_effect(
    input_path: str,
    output_path: str,
    zoom_start: float = 1.0,
    zoom_end: float = 1.15,
    fps: int = 30,
) -> str:
    """Ken Burns slow-zoom on a video."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    vf = (
        f"zoompan=z='min({zoom_start}+({zoom_end}-{zoom_start})*on/({fps}*5),{zoom_end})':"
        f"d=1:s=1080x1080:fps={fps}"
    )
    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", vf,
           "-c:v", "libx264", "-crf", "23", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def concat_videos(input_paths: List[str], output_path: str) -> str:
    """Concatenate multiple videos using the concat demuxer."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    try:
        for p in input_paths:
            list_file.write(f"file '{p}'\n")
        list_file.close()
        cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0",
               "-i", list_file.name, "-c", "copy", output_path]
        subprocess.run(cmd, capture_output=True, check=True)
    finally:
        os.unlink(list_file.name)
    return output_path


def add_fade_transitions(
    input_path: str,
    output_path: str,
    fade_in: float = 0.5,
    fade_out: float = 0.5,
) -> str:
    """Add fade-in and fade-out to a video."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    info = probe(input_path)
    fade_out_start = max(0, info.duration - fade_out)
    vf = (
        f"fade=t=in:st=0:d={fade_in},"
        f"fade=t=out:st={fade_out_start}:d={fade_out}"
    )
    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", vf,
           "-c:v", "libx264", "-crf", "23", "-c:a", "copy", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def apply_color_grade(
    input_path: str,
    output_path: str,
    brightness: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
) -> str:
    """Basic colour grading via eq filter."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    vf = f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}"
    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", vf,
           "-c:v", "libx264", "-crf", "23", "-c:a", "copy", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def encode_for_platform(
    input_path: str,
    output_path: str,
    width: int,
    height: int,
    fps: int = 30,
    crf: int = 23,
    codec: str = "libx264",
    audio_codec: str = "aac",
    audio_bitrate: str = "192k",
    max_duration: Optional[float] = None,
) -> str:
    """Re-encode a video to exact platform specs."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={fps}"
    )
    cmd = [
        FFMPEG, "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", codec, "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-r", str(fps),
    ]
    # Handle audio: if source has audio encode it, else skip
    cmd += ["-c:a", audio_codec, "-b:a", audio_bitrate, "-strict", "experimental"]
    if max_duration:
        cmd += ["-t", str(max_duration)]
    cmd.append(output_path)
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError:
        # Retry without audio in case source has none
        cmd_no_audio = [
            FFMPEG, "-y", "-i", input_path,
            "-vf", vf,
            "-c:v", codec, "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-r", str(fps), "-an",
        ]
        if max_duration:
            cmd_no_audio += ["-t", str(max_duration)]
        cmd_no_audio.append(output_path)
        subprocess.run(cmd_no_audio, capture_output=True, check=True)
    return output_path


def extract_thumbnail(
    input_path: str,
    output_path: str,
    timestamp: float = 1.0,
) -> str:
    """Extract a single frame as a JPEG thumbnail."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [FFMPEG, "-y", "-i", input_path, "-ss", str(timestamp),
           "-vframes", "1", "-q:v", "2", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def create_grid_video(
    image_paths: List[str],
    output_path: str,
    grid_size: Tuple[int, int] = (2, 2),
    cell_width: int = 540,
    cell_height: int = 540,
    duration: float = 10.0,
    fps: int = 30,
) -> str:
    """Create a grid video from multiple product images."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cols, rows = grid_size
    total_w = cols * cell_width
    total_h = rows * cell_height

    inputs = []
    filter_parts = []
    for i, img in enumerate(image_paths[: cols * rows]):
        inputs += ["-loop", "1", "-t", str(duration), "-i", img]
        filter_parts.append(
            f"[{i}:v]scale={cell_width}:{cell_height}:force_original_aspect_ratio=decrease,"
            f"pad={cell_width}:{cell_height}:(ow-iw)/2:(oh-ih)/2[v{i}]"
        )

    # Build xstack layout
    positions = []
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx < len(image_paths):
                positions.append(f"{c * cell_width}_{r * cell_height}")

    inputs_labels = "|".join(f"[v{i}]" for i in range(min(len(image_paths), cols * rows)))
    layout = "|".join(positions[: min(len(image_paths), cols * rows)])
    filter_complex = ";".join(filter_parts) + f";{inputs_labels}xstack=inputs={min(len(image_paths), cols * rows)}:layout={layout}[out]"

    cmd = [FFMPEG, "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-t", str(duration),
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


# ── Helpers ─────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Escape special chars for FFmpeg drawtext filter."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "'\\''")
        .replace(":", "\\:")
        .replace("%", "%%")
    )
