"""
pipeline/video_processor.py — Video ingestion, frame extraction, audio stripping.

Handles:
  - URL downloads via yt-dlp (YouTube, TikTok, X/Twitter, Reddit, etc.)
  - Direct MP4/MOV file uploads
  - Frame extraction at configurable FPS via OpenCV
  - Audio extraction to MP3 via ffmpeg subprocess
  - Scene change detection via frame differencing for keyframe selection
"""
import asyncio
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class VideoProcessorResult:
    job_id: str
    video_path: str
    audio_path: Optional[str]
    frames_dir: str
    frame_paths: list[str] = field(default_factory=list)
    keyframe_paths: list[str] = field(default_factory=list)   # top scene-change keyframes
    duration_seconds: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None


def _job_dir(job_id: str) -> Path:
    d = Path(f"/tmp/uploads/{job_id}")
    d.mkdir(parents=True, exist_ok=True)
    return d


async def download_from_url(job_id: str, url: str) -> VideoProcessorResult:
    """Download a video from a social media URL using yt-dlp."""
    settings = get_settings()
    dest_dir = _job_dir(job_id)
    output_path = dest_dir / "video.mp4"

    max_mb = settings.max_video_size_mb
    logger.info("[%s] Downloading URL: %s", job_id, url)

    import yt_dlp
    import json
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'outtmpl': str(output_path),
        'noplaylist': True,
        'max_filesize': max_mb * 1024 * 1024,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 60,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }

    # Support cookies for authentication
    if settings.cookies_file_path:
        cookies_path = Path(settings.cookies_file_path)
    else:
        cookies_path = Path("cookies.txt")
        
    if cookies_path.exists():
        logger.info("[%s] Using cookies from %s for authentication", job_id, cookies_path)
        ydl_opts['cookiefile'] = str(cookies_path.resolve())

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    try:
        await asyncio.to_thread(_download)
    except yt_dlp.utils.DownloadError as exc:
        err_str = str(exc).lower()
        logger.warning("[%s] yt-dlp DownloadError: %s", job_id, err_str)
        
        # Check for private/restricted keywords
        restricted_keywords = ["login", "registered users", "private", "follow this account", "age-restricted", "sign in"]
        if any(kw in err_str for kw in restricted_keywords):
            return VideoProcessorResult(
                job_id=job_id, video_path="", audio_path=None, frames_dir="",
                error_code="PRIVATE_OR_RESTRICTED_MEDIA",
                error="This video is from a private account or requires authentication."
            )
            
        return VideoProcessorResult(
            job_id=job_id, video_path="", audio_path=None, frames_dir="",
            error_code="DOWNLOAD_FAILED",
            error=f"Video download failed: {str(exc)}"
        )
    except Exception as exc:
        logger.error("[%s] yt-dlp unexpected error: %s", job_id, exc)
        return VideoProcessorResult(
            job_id=job_id, video_path="", audio_path=None, frames_dir="",
            error_code="DOWNLOAD_FAILED",
            error=f"Unexpected download error: {str(exc)}"
        )

    if not output_path.exists():
        return VideoProcessorResult(
            job_id=job_id, video_path="", audio_path=None, frames_dir="",
            error_code="DOWNLOAD_FAILED",
            error="yt-dlp completed but output file not found."
        )

    logger.info("[%s] Download complete: %s (%.1f MB)", job_id, output_path,
                output_path.stat().st_size / 1024 / 1024)
    return await _process_video_file(job_id, str(output_path))


async def process_uploaded_file(job_id: str, upload_path: str) -> VideoProcessorResult:
    """Process a locally saved upload. Moves it to the job directory."""
    dest_dir = _job_dir(job_id)
    dest_path = dest_dir / "video.mp4"

    src = Path(upload_path)
    if not src.exists():
        return VideoProcessorResult(
            job_id=job_id, video_path="", audio_path=None, frames_dir="",
            error=f"Uploaded file not found: {upload_path}",
        )

    # Move/copy to job dir
    if src != dest_path:
        shutil.copy2(str(src), str(dest_path))

    return await _process_video_file(job_id, str(dest_path))


async def _process_video_file(job_id: str, video_path: str) -> VideoProcessorResult:
    """Extract frames and audio from a local video file."""
    settings = get_settings()
    dest_dir = _job_dir(job_id)
    frames_dir = dest_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    # --- Compress Video ---
    compressed_path = await _compress_video(job_id, video_path, dest_dir)
    if compressed_path:
        video_path = compressed_path
    
    # --- Probe video metadata ---
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return VideoProcessorResult(
            job_id=job_id, video_path=video_path, audio_path=None,
            frames_dir=str(frames_dir),
            error="OpenCV could not open video file. Unsupported format?",
        )

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / native_fps if native_fps > 0 else 0

    logger.info(
        "[%s] Video: %dx%d @ %.1f fps, %.1fs duration, %d total frames",
        job_id, width, height, native_fps, duration, total_frames,
    )

    # --- Extract 1 frame per FRAME_SAMPLE_RATE seconds ---
    sample_rate = settings.frame_sample_rate
    frame_interval = max(1, int(native_fps * sample_rate))
    frame_paths: list[str] = []
    frame_timestamps: list[float] = []

    frame_idx = 0
    saved = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            timestamp = frame_idx / native_fps
            out_path = frames_dir / f"frame_{saved:05d}_{timestamp:.2f}s.jpg"
            cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            frame_paths.append(str(out_path))
            frame_timestamps.append(timestamp)
            saved += 1
        frame_idx += 1

    cap.release()
    logger.info("[%s] Extracted %d frames at %ds intervals", job_id, saved, sample_rate)

    # --- Scene change detection for keyframe selection ---
    keyframe_paths = _detect_scene_keyframes(frame_paths, top_n=3)
    logger.info("[%s] Selected %d keyframes", job_id, len(keyframe_paths))

    # --- Extract audio via ffmpeg ---
    audio_path = await _extract_audio(job_id, video_path, dest_dir)

    return VideoProcessorResult(
        job_id=job_id,
        video_path=video_path,
        audio_path=audio_path,
        frames_dir=str(frames_dir),
        frame_paths=frame_paths,
        keyframe_paths=keyframe_paths,
        duration_seconds=duration,
        fps=native_fps,
        width=width,
        height=height,
    )


def _detect_scene_keyframes(frame_paths: list[str], top_n: int = 3) -> list[str]:
    """
    Detect scene changes via mean absolute difference between consecutive frames.
    Returns the top_n frames with the highest inter-frame difference
    (i.e., the most visually distinct moments), which serve as good OSINT keyframes.
    """
    if len(frame_paths) <= top_n:
        return frame_paths

    scores: list[tuple[float, str]] = []
    prev_gray = None

    for path in frame_paths:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        img = cv2.resize(img, (320, 180))  # Fast comparison at low res
        if prev_gray is not None:
            diff = float(np.mean(np.abs(img.astype(np.float32) - prev_gray.astype(np.float32))))
            scores.append((diff, path))
        prev_gray = img

    # Sort by largest scene change, take top_n
    scores.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scores[:top_n]]


async def _extract_audio(job_id: str, video_path: str, dest_dir: Path) -> Optional[str]:
    """Extract audio track to MP3 using ffmpeg. Returns None if video is silent/has no audio."""
    audio_path = dest_dir / "audio.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",                          # No video
        "-ar", "16000",                 # 16kHz sample rate (Whisper optimal)
        "-ac", "1",                     # Mono
        "-b:a", "64k",
        str(audio_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            err = stderr.decode(errors="replace")
            # Check for "no audio stream" — not a failure, just silent video
            if "no audio" in err.lower() or "does not contain" in err.lower():
                logger.info("[%s] Video has no audio track.", job_id)
                return None
            logger.warning("[%s] ffmpeg audio extraction warning: %s", job_id, err[:300])
            return None

        if audio_path.exists() and audio_path.stat().st_size > 1000:
            logger.info("[%s] Audio extracted: %s", job_id, audio_path)
            return str(audio_path)
        else:
            logger.info("[%s] Audio file empty — silent video.", job_id)
            return None

    except asyncio.TimeoutError:
        logger.warning("[%s] ffmpeg audio extraction timed out", job_id)
        return None
    except Exception as exc:
        logger.warning("[%s] ffmpeg error: %s", job_id, exc)
        return None

async def _compress_video(job_id: str, input_path: str, dest_dir: Path) -> Optional[str]:
    """
    Compress the video to reduce file size significantly (480p, 15 FPS, low bitrate).
    """
    output_path = dest_dir / "compressed.mp4"
    logger.info("[%s] Compressing video to save space: %s", job_id, input_path)
    
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "scale='min(480,iw)':-2",  # Scale width to max 480px, keep aspect ratio
        "-r", "15",                       # Drop to 15 FPS
        "-vcodec", "libx264",
        "-b:v", "200k",                   # 200 kbps video bitrate
        "-acodec", "aac",
        "-b:a", "64k",                    # 64 kbps audio bitrate
        str(output_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        
        if proc.returncode == 0 and output_path.exists():
            old_size = Path(input_path).stat().st_size
            new_size = output_path.stat().st_size
            logger.info(
                "[%s] Video compressed successfully: %.2f MB -> %.2f KB", 
                job_id, old_size / (1024 * 1024), new_size / 1024
            )
            return str(output_path)
        else:
            err = stderr.decode(errors="replace")
            logger.warning("[%s] ffmpeg compression failed or output missing: %s", job_id, err[:300])
            return None
            
    except asyncio.TimeoutError:
        logger.warning("[%s] ffmpeg compression timed out after 300s", job_id)
        return None
    except Exception as exc:
        logger.warning("[%s] ffmpeg compression error: %s", job_id, exc)
        return None

