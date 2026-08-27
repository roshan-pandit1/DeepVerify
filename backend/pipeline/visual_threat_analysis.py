"""
pipeline/visual_threat_analysis.py — Pillar 2: Visual Threat Detection.

Disinformation campaigns frequently weaponise videos containing violence,
riots, or armed conflict.  This module uses CLIP (Contrastive Language–Image
Pre-training) via a zero-shot image-classification pipeline to score
keyframes against a set of abstract threat labels — no fine-tuned dataset
required.

v2 — Single-Pass / Batched Inference:
  • Accepts a pre-extracted list[PIL.Image] instead of a video_path string.
  • Runs all frames through CLIP in a SINGLE batched call — eliminating
    repeated model invocations and per-frame Python overhead.
  • Owns its own singleton with explicit device + dtype selection.

Algorithm:
  1. Receive threat_frames (a thinned slice of shared_frames) from the
     orchestrator's single-pass extractor.
  2. Send the entire batch to CLIP in one call with all threat labels.
  3. Collect the highest threat score and flagged label set across all frames.
  4. Return structured result dict compatible with the orchestrator.

Model: openai/clip-vit-base-patch32
Output dict (stored in final_result["visual_threat"]):
    {
        "is_visual_threat": bool,
        "metrics": {
            "max_threat_score":  float,   # 0–1
            "flagged_content":   list[str],
            "frames_analyzed":   int,
        },
        "error": str | None,
    }
"""
import logging

import torch
from PIL import Image
from transformers import pipeline as hf_pipeline  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Threat label set
# ---------------------------------------------------------------------------
_THREAT_LABELS = [
    "a peaceful scene",
    "a crowded indoor market with people walking normally",
    "a violent protest or riot",
    "weapons, firearms, or armed conflict",
    "blood, injury, or physical violence",
]
_THREAT_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# Singleton loader
# ---------------------------------------------------------------------------
_THREAT_SINGLETON = None


def _get_threat_detector():
    """Lazy-load the CLIP zero-shot pipeline (once per process)."""
    global _THREAT_SINGLETON
    if _THREAT_SINGLETON is None:
        device = 0 if torch.cuda.is_available() else -1
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        logger.info(
            "Loading Zero-Shot Visual Threat Model (openai/clip-vit-base-patch32) "
            "on device=%s dtype=%s …", device, dtype
        )
        _THREAT_SINGLETON = hf_pipeline(
            "zero-shot-image-classification",
            model="openai/clip-vit-base-patch32",
            device=device,
            torch_dtype=dtype,
        )
        logger.info("Visual Threat Model loaded.")
    return _THREAT_SINGLETON


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_visual_threats(
    frames: list[Image.Image],
    job_id: str = "",
) -> dict:
    """
    Score a pre-extracted list of PIL frames for violent or threatening imagery
    using a single batched CLIP zero-shot inference call.

    Args:
        frames:  List of PIL RGB images (threat_frames slice from orchestrator).
        job_id:  Optional job identifier for log tracing.

    Returns:
        Dict with keys: is_visual_threat, metrics, error.
    """
    tag = f"[{job_id}]" if job_id else ""

    if not frames:
        logger.warning("%s VisualThreat: no frames provided.", tag)
        return {
            "is_visual_threat": False,
            "metrics": {
                "max_threat_score": 0.0,
                "flagged_content": [],
                "frames_analyzed": 0,
            },
            "error": "No frames provided",
        }

    try:
        detector = _get_threat_detector()

        # ── Single batched forward pass ───────────────────────────────────
        batch_results = detector(
            frames,
            candidate_labels=_THREAT_LABELS,
            batch_size=len(frames),
        )

        highest_threat_score = 0.0
        flagged_labels: set[str] = set()

        for res in batch_results:
            for item in res:
                if item["label"] == "a peaceful scene" or "market" in item["label"]:
                    continue
                score = float(item["score"])
                if score > _THREAT_THRESHOLD:
                    highest_threat_score = max(highest_threat_score, score)
                    flagged_labels.add(item["label"])

        is_threat = highest_threat_score > _THREAT_THRESHOLD

        logger.info(
            "%s VisualThreat: frames=%d  max_score=%.3f  flagged=%s  threat=%s",
            tag, len(frames), highest_threat_score, list(flagged_labels), is_threat,
        )

        return {
            "is_visual_threat": is_threat,
            "metrics": {
                "max_threat_score": round(highest_threat_score, 4),
                "flagged_content": list(flagged_labels),
                "frames_analyzed": len(frames),
            },
            "error": None,
        }

    except Exception as exc:
        logger.error("%s VisualThreat: inference failed — %s", tag, exc)
        return {
            "is_visual_threat": False,
            "metrics": {
                "max_threat_score": 0.0,
                "flagged_content": [],
                "frames_analyzed": len(frames),
            },
            "error": str(exc),
        }
