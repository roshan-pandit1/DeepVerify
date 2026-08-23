"""
pipeline/vision_model.py — Face detection, EfficientNet deepfake scoring, Grad-CAM heatmaps.

Pipeline:
  1. MTCNN (facenet-pytorch) → detect + crop faces per frame (224×224)
  2. EfficientNet-B4 (timm) → 2-class classification (real / manipulated)
     - If MODEL_WEIGHTS_PATH is set: loads fine-tuned weights
     - Otherwise: uses pretrained ImageNet weights + frequency-domain heuristic
  3. pytorch-grad-cam → overlay heatmap on suspicious frames (score > 0.60)
  4. Returns per-frame scores + aggregated confidence + Grad-CAM image paths

Edge cases handled:
  - Videos with no detectable faces → skip classifier, return score=0 / skip
  - Frames where MTCNN returns None → skip that frame
  - GPU if available, CPU fallback
"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms as T
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transforms (ImageNet normalization — same as EfficientNet pretraining)
# ---------------------------------------------------------------------------
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

_transform = T.Compose([
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class FrameScore:
    frame_path: str
    timestamp: float
    face_detected: bool
    manipulation_score: float           # 0.0–1.0 (1.0 = highly manipulated)
    gradcam_path: Optional[str] = None  # path to saved heatmap PNG


@dataclass
class VisionResult:
    frame_scores: list[FrameScore] = field(default_factory=list)
    facial_artifact_score: float = 0.0  # Global 0–100 score
    faces_detected: int = 0
    frames_analyzed: int = 0
    suspicious_frames: list[FrameScore] = field(default_factory=list)
    error: Optional[str] = None
    skipped_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Model loader (singleton per process)
# ---------------------------------------------------------------------------
_model_cache: dict = {}


def _load_model(device: torch.device):
    """Load EfficientNet-B4 classification model. Cached after first call."""
    if "model" in _model_cache:
        return _model_cache["model"]

    import timm  # type: ignore

    logger.info("Loading EfficientNet-B4 backbone from timm...")
    model = timm.create_model("efficientnet_b4", pretrained=True, num_classes=2)

    weights_path = os.getenv("MODEL_WEIGHTS_PATH", "").strip()
    if weights_path and Path(weights_path).exists():
        logger.info("Loading fine-tuned weights from %s", weights_path)
        state = torch.load(weights_path, map_location=device)
        # Accept both raw state_dict and {'model': state_dict} checkpoints
        if "model" in state:
            state = state["model"]
        elif "state_dict" in state:
            state = state["state_dict"]
        model.load_state_dict(state, strict=False)
        logger.info("Fine-tuned weights loaded successfully.")
    else:
        logger.info(
            "MODEL_WEIGHTS_PATH not set — using pretrained ImageNet backbone. "
            "Scores reflect frequency-domain heuristic, not a trained deepfake classifier."
        )

    model.to(device)
    model.eval()
    _model_cache["model"] = model
    return model


def _load_mtcnn(device: torch.device):
    """Load MTCNN face detector. Cached after first call."""
    if "mtcnn" in _model_cache:
        return _model_cache["mtcnn"]

    from facenet_pytorch import MTCNN  # type: ignore

    logger.info("Loading MTCNN face detector...")
    mtcnn = MTCNN(
        image_size=224,
        margin=20,
        keep_all=True,
        device=device,
        post_process=False,   # Return raw pixel values 0–255
    )
    _model_cache["mtcnn"] = mtcnn
    return mtcnn


# ---------------------------------------------------------------------------
# Grad-CAM
# ---------------------------------------------------------------------------

def _run_gradcam(model, input_tensor: torch.Tensor, face_crop_np: np.ndarray,
                  save_path: str) -> Optional[str]:
    """
    Generate Grad-CAM heatmap for the given face crop and save to disk.
    Returns path to saved PNG, or None on failure.
    """
    try:
        from pytorch_grad_cam import GradCAM                          # type: ignore
        from pytorch_grad_cam.utils.image import show_cam_on_image    # type: ignore
        from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget  # type: ignore

        # Target the last EfficientNet block's features
        # timm EfficientNet-B4: model.blocks[-1] is the last MBConv block
        target_layers = [model.blocks[-1]]

        cam = GradCAM(model=model, target_layers=target_layers)
        targets = [ClassifierOutputTarget(1)]  # class 1 = manipulated

        grayscale_cam = cam(input_tensor=input_tensor, targets=targets)

        # Overlay on original face crop (normalized to [0,1] float RGB)
        rgb_float = cv2.cvtColor(face_crop_np, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        rgb_float = cv2.resize(rgb_float, (224, 224))
        visualization = show_cam_on_image(rgb_float, grayscale_cam[0, :], use_rgb=True)

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(save_path, cv2.cvtColor(visualization, cv2.COLOR_RGB2BGR))
        return save_path

    except Exception as exc:
        logger.warning("Grad-CAM generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Hugging Face Vision Transformer Deepfake Classifier
# ---------------------------------------------------------------------------

_deepfake_detector = None


def _get_deepfake_detector():
    """Lazy-load the Hugging Face pipeline so it loads into memory exactly once."""
    global _deepfake_detector
    if _deepfake_detector is None:
        from transformers import pipeline as hf_pipeline
        logger.info("Loading pretrained Deepfake model from Hugging Face (dima806/deepfake_vs_real_image_detection)...")
        _deepfake_detector = hf_pipeline("image-classification", model="dima806/deepfake_vs_real_image_detection")
    return _deepfake_detector


def analyze_facial_artifacts(frame_path: str) -> float:
    """
    Analyzes a frame using a fine-tuned pretrained Deepfake AI model.
    Returns a float between 0.0 (Authentic) and 1.0 (Deepfake).
    """
    try:
        detector = _get_deepfake_detector()
        # Load image using Pillow
        img = Image.open(frame_path).convert('RGB')
        
        # Run inference
        results = detector(img)
        
        # The model returns a list of dictionaries, e.g.,
        # [{'label': 'fake', 'score': 0.98}, {'label': 'real', 'score': 0.02}]
        
        fake_score = 0.0
        
        # Extract the confidence score for the 'fake' label
        for result in results:
            if result['label'].lower() == 'fake':
                fake_score = result['score']
                break
                
        return float(fake_score)
        
    except Exception as e:
        logger.error(f"Error processing frame {frame_path}: {e}")
        return 0.0  # Default to safe on error


def analyze_video_multi_frame_average(frame_paths: list[str]) -> float:
    """
    Extracts 3 clear frames at 25%, 50%, and 75% of video duration,
    passes all three to analyze_facial_artifacts, and returns the average score.
    """
    if not frame_paths:
        return 0.0
    
    n = len(frame_paths)
    if n >= 3:
        target_indices = [int(n * 0.25), int(n * 0.50), int(n * 0.75)]
        sampled_frames = [frame_paths[idx] for idx in target_indices]
    else:
        sampled_frames = frame_paths

    scores = [analyze_facial_artifacts(fp) for fp in sampled_frames]
    return float(sum(scores) / len(scores)) if scores else 0.0


# ---------------------------------------------------------------------------
# Main inference function
# ---------------------------------------------------------------------------

def run_vision_pipeline(
    job_id: str,
    frame_paths: list[str],
    gradcam_dir: str,
    has_fine_tuned_weights: bool = False,
) -> VisionResult:
    """
    Run the full vision pipeline on a list of frame paths.
    CPU/GPU agnostic.
    """
    if not frame_paths:
        return VisionResult(skipped_reason="No frames available for analysis.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("[%s] Vision pipeline on device: %s, frames: %d", job_id, device, len(frame_paths))

    try:
        model = _load_model(device)
        mtcnn = _load_mtcnn(device)
    except Exception as exc:
        logger.error("[%s] Model loading failed: %s", job_id, exc)
        return VisionResult(error=f"Model loading failed: {exc}")

    Path(gradcam_dir).mkdir(parents=True, exist_ok=True)

    frame_scores: list[FrameScore] = []
    total_faces = 0
    use_heuristic = not has_fine_tuned_weights

    for idx, frame_path in enumerate(frame_paths):
        # Parse timestamp from filename (e.g. frame_00001_3.00s.jpg)
        timestamp = _parse_timestamp(frame_path, idx)

        img_bgr = cv2.imread(frame_path)
        if img_bgr is None:
            continue

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)

        # --- Face detection ---
        try:
            boxes, probs = mtcnn.detect(pil_img)
        except Exception as exc:
            logger.debug("MTCNN error on frame %s: %s", frame_path, exc)
            boxes, probs = None, None

        mtcnn_face_found = (boxes is not None and len(boxes) > 0)

        # --- Scoring ---
        if use_heuristic:
            score = analyze_facial_artifacts(frame_path)
            face_found = mtcnn_face_found or (score > 0.0)
            if not face_found and not mtcnn_face_found:
                frame_scores.append(FrameScore(
                    frame_path=frame_path,
                    timestamp=timestamp,
                    face_detected=False,
                    manipulation_score=0.0,
                ))
                continue
        else:
            if not mtcnn_face_found:
                frame_scores.append(FrameScore(
                    frame_path=frame_path,
                    timestamp=timestamp,
                    face_detected=False,
                    manipulation_score=0.0,
                ))
                continue

            # Process only the highest-confidence face per frame
            best_idx = int(np.argmax(probs)) if probs is not None else 0
            box = boxes[best_idx]
            x1, y1, x2, y2 = [max(0, int(c)) for c in box]
            face_crop_bgr = img_bgr[y1:y2, x1:x2]
            if face_crop_bgr.size == 0:
                continue
            face_crop_bgr = cv2.resize(face_crop_bgr, (224, 224))

            face_crop_rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)
            pil_face = Image.fromarray(face_crop_rgb)
            tensor = _transform(pil_face).unsqueeze(0).to(device)
            with torch.no_grad():
                logits = model(tensor)
                probs_out = torch.softmax(logits, dim=1)
                score = float(probs_out[0][1].item())  # class 1 = manipulated

        if mtcnn_face_found:
            total_faces += len(boxes)
        elif score > 0.0:
            total_faces += 1

        # --- Grad-CAM for suspicious frames ---
        gradcam_path = None
        if score > 0.60:
            cam_save = os.path.join(gradcam_dir, f"gradcam_{idx:05d}_{timestamp:.2f}s.png")
            # If MTCNN found box, use it for gradcam crop, else use full frame center crop
            if mtcnn_face_found:
                best_idx = int(np.argmax(probs)) if probs is not None else 0
                box = boxes[best_idx]
                x1, y1, x2, y2 = [max(0, int(c)) for c in box]
                face_crop_bgr = img_bgr[y1:y2, x1:x2]
                if face_crop_bgr.size > 0:
                    face_crop_bgr = cv2.resize(face_crop_bgr, (224, 224))
                else:
                    face_crop_bgr = cv2.resize(img_bgr, (224, 224))
            else:
                face_crop_bgr = cv2.resize(img_bgr, (224, 224))

            face_crop_rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)
            pil_face = Image.fromarray(face_crop_rgb)
            tensor = _transform(pil_face).unsqueeze(0).to(device)
            gradcam_path = _run_gradcam(model, tensor, face_crop_bgr, cam_save)

        frame_scores.append(FrameScore(
            frame_path=frame_path,
            timestamp=timestamp,
            face_detected=True,
            manipulation_score=score,
            gradcam_path=gradcam_path,
        ))

    # --- Aggregate score ---
    face_scores = [fs.manipulation_score for fs in frame_scores if fs.face_detected]
    if face_scores:
        # Weighted towards worst-case (max) but tempered by mean
        global_score = 0.6 * max(face_scores) + 0.4 * (sum(face_scores) / len(face_scores))
    else:
        global_score = 0.0

    suspicious = [fs for fs in frame_scores if fs.manipulation_score > 0.60]

    logger.info(
        "[%s] Vision complete: %d frames, %d faces, score=%.1f%%, suspicious=%d",
        job_id, len(frame_scores), total_faces, global_score * 100, len(suspicious),
    )

    return VisionResult(
        frame_scores=frame_scores,
        facial_artifact_score=round(global_score * 100, 1),
        faces_detected=total_faces,
        frames_analyzed=len(frame_scores),
        suspicious_frames=suspicious,
    )


def _parse_timestamp(frame_path: str, fallback_idx: int) -> float:
    """Extract timestamp float from filenames like frame_00001_3.00s.jpg"""
    stem = Path(frame_path).stem
    for part in stem.split("_"):
        part = part.rstrip("s")
        try:
            return float(part)
        except ValueError:
            continue
    return float(fallback_idx)
