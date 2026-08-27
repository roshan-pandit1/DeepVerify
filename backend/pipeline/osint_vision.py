"""
pipeline/osint_vision.py — Keyframe extraction and GCP Vision reverse image search.

Provides:
  1. extract_keyframes(video_path, num_frames=3):
     Extracts evenly-spaced frames (e.g., 25%, 50%, 75%) from a video file using cv2.
  2. reverse_image_search(frame_path):
     Performs reverse image search using Google Cloud Vision API (WebDetection),
     returning best_guess_labels and pages_with_matching_images.
     Includes try/except blocks for graceful failure.
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import cv2

logger = logging.getLogger(__name__)


def extract_keyframes(video_path: str, num_frames: int = 3) -> List[str]:
    """
    Extract `num_frames` evenly spaced frames across the duration of a video file.

    For num_frames=3, frames are extracted at 25%, 50%, and 75% of total frames.

    Args:
        video_path: Absolute or relative path to the video file.
        num_frames: Number of keyframes to extract (default: 3).

    Returns:
        List of absolute file paths to the saved keyframe images.
    """
    if not video_path or not os.path.exists(video_path):
        logger.warning("osint_vision: Video path does not exist: %s", video_path)
        return []

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames <= 0:
        logger.warning("osint_vision: Video has invalid total frames (%d): %s", total_frames, video_path)
        cap.release()
        return []

    # Determine save directory
    video_dir = Path(video_path).parent
    keyframes_dir = video_dir / "osint_keyframes"
    keyframes_dir.mkdir(parents=True, exist_ok=True)

    extracted_paths: List[str] = []

    # Calculate ratios, e.g. for num_frames=3 -> [0.25, 0.50, 0.75]
    ratios = [(i + 1) / (num_frames + 1) for i in range(num_frames)]

    for idx, ratio in enumerate(ratios):
        target_frame = int(total_frames * ratio)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        if not ret or frame is None:
            logger.warning("osint_vision: Failed to read frame at ratio %.2f (frame %d)", ratio, target_frame)
            continue

        out_filename = f"osint_keyframe_{idx + 1}_{target_frame}.jpg"
        out_path = str(keyframes_dir / out_filename)
        cv2.imwrite(out_path, frame)
        extracted_paths.append(out_path)

    cap.release()
    logger.info("osint_vision: Extracted %d keyframes from %s", len(extracted_paths), video_path)
    return extracted_paths


def reverse_image_search(frame_path: str) -> Dict[str, Any]:
    """
    Query Google Cloud Vision API (WebDetection) for a keyframe image.

    Args:
        frame_path: Path to the image frame file.

    Returns:
        Dict containing:
            "best_guess_labels": list[str]
            "pages_with_matching_images": list[str]
            "error": str | None
    """
    best_guess_labels: List[str] = []
    pages_with_matching_images: List[str] = []

    if not frame_path or not os.path.exists(frame_path):
        logger.warning("osint_vision: Image frame_path does not exist: %s", frame_path)
        return {
            "best_guess_labels": [],
            "pages_with_matching_images": [],
            "error": f"File not found: {frame_path}"
        }

    try:
        from google.cloud import vision  # type: ignore

        logger.info("osint_vision: Performing GCP Vision reverse image search on %s", frame_path)
        client = vision.ImageAnnotatorClient()

        with open(frame_path, "rb") as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = client.web_detection(image=image)

        if response.error.message:
            logger.warning("osint_vision: GCP Vision API returned error: %s", response.error.message)
            return {
                "best_guess_labels": [],
                "pages_with_matching_images": [],
                "error": response.error.message,
            }

        web_detection = response.web_detection
        if web_detection:
            if web_detection.best_guess_labels:
                for label_obj in web_detection.best_guess_labels:
                    if hasattr(label_obj, "label") and label_obj.label:
                        best_guess_labels.append(str(label_obj.label))

            if web_detection.pages_with_matching_images:
                for page_obj in web_detection.pages_with_matching_images:
                    if hasattr(page_obj, "url") and page_obj.url:
                        pages_with_matching_images.append(str(page_obj.url))

        logger.info(
            "osint_vision: Reverse image search complete. Labels: %s, Pages count: %d",
            best_guess_labels, len(pages_with_matching_images)
        )

        return {
            "best_guess_labels": best_guess_labels,
            "pages_with_matching_images": pages_with_matching_images,
            "error": None,
        }

    except Exception as exc:
        logger.warning("osint_vision: GCP Vision API reverse image search failed (non-fatal): %s", exc)
        return {
            "best_guess_labels": [],
            "pages_with_matching_images": [],
            "error": str(exc),
        }
