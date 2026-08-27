"""
pipeline/signal_forensics.py — Deterministic Math-Based Signal Forensics Layer

Zero-GPU overhead deterministic signal forensic analysis algorithms:
1. Error Level Analysis (ELA): JPEG re-compression error comparison.
2. 2D FFT Frequency Analysis: High-frequency to total power ratio for GAN/diffusion artifacts.
3. Color Space Variance: Channel standard deviation imbalance in YCrCb color space.
4. Texture Entropy (Laplacian Variance): Detects over-smooth AI backgrounds (no-face AI gen).
5. HSV Saturation Uniformity: AI-gen content has unnaturally uniform colour saturation bands.
"""
import logging
from typing import Union, List, Dict, Any
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def compute_ela_score(frame: Union[Image.Image, np.ndarray]) -> float:
    """
    Error Level Analysis (ELA):
    Compress the frame at 90% JPEG quality in memory, compare it to the original,
    and return a normalized score in [0.0, 1.0] based on the mean absolute difference.
    """
    try:
        if isinstance(frame, Image.Image):
            img_np = np.array(frame)
            if img_np.ndim == 3 and img_np.shape[2] == 3:
                bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            elif img_np.ndim == 2:
                bgr = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
            else:
                bgr = img_np
        elif isinstance(frame, np.ndarray):
            if frame.ndim == 3 and frame.shape[2] == 3:
                bgr = frame
            elif frame.ndim == 2:
                bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            else:
                bgr = frame
        else:
            return 0.0

        # Compress to 90% JPEG quality in memory
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        success, enc_img = cv2.imencode(".jpg", bgr, encode_param)
        if not success:
            return 0.0

        decoded = cv2.imdecode(enc_img, cv2.IMREAD_COLOR)
        if decoded is None or decoded.shape != bgr.shape:
            return 0.0

        # Calculate mean absolute pixel difference
        diff = cv2.absdiff(bgr, decoded)
        mean_diff = float(np.mean(diff))

        # Normalize score into [0.0, 1.0]. A mean difference of 25.5 corresponds to 1.0.
        ela_score = min(1.0, mean_diff / 25.5)
        return float(ela_score)

    except Exception as exc:
        logger.warning("ELA calculation error: %s", exc)
        return 0.0


def compute_fft_score(frame: Union[Image.Image, np.ndarray]) -> float:
    """
    2D FFT Frequency Analysis:
    Apply a 2D Fast Fourier Transform, mask low frequencies at the center,
    and calculate the ratio of high-frequency power to total power to detect
    unnatural GAN/diffusion grid artifacts.
    """
    try:
        if isinstance(frame, Image.Image):
            img_np = np.array(frame)
            if img_np.ndim == 3:
                gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_np
        elif isinstance(frame, np.ndarray):
            if frame.ndim == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
        else:
            return 0.0

        h, w = gray.shape
        if h == 0 or w == 0:
            return 0.0

        # 2D Fast Fourier Transform
        f = np.fft.fft2(gray.astype(np.float32))
        fshift = np.fft.fftshift(f)
        magnitude_power = np.abs(fshift) ** 2

        total_power = np.sum(magnitude_power)
        if total_power < 1e-10:
            return 0.0

        # Mask low frequencies at center (10% radius from center)
        cy, cx = h // 2, w // 2
        r_h, r_w = max(1, int(h * 0.1)), max(1, int(w * 0.1))

        low_freq_power = np.sum(
            magnitude_power[
                max(0, cy - r_h) : min(h, cy + r_h),
                max(0, cx - r_w) : min(w, cx + r_w),
            ]
        )
        high_freq_power = total_power - low_freq_power

        fft_ratio = float(high_freq_power / total_power)
        return max(0.0, min(1.0, fft_ratio))

    except Exception as exc:
        logger.warning("2D FFT calculation error: %s", exc)
        return 0.0


def compute_color_imbalance(frame: Union[Image.Image, np.ndarray]) -> float:
    """
    Color Space Variance:
    Convert the frame to YCrCb and calculate the relative imbalance between
    the standard deviation of the Cr and Cb channels.
    """
    try:
        if isinstance(frame, Image.Image):
            img_np = np.array(frame)
            if img_np.ndim == 3 and img_np.shape[2] == 3:
                ycrcb = cv2.cvtColor(img_np, cv2.COLOR_RGB2YCrCb)
            else:
                return 0.0
        elif isinstance(frame, np.ndarray):
            if frame.ndim == 3 and frame.shape[2] == 3:
                ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
            else:
                return 0.0
        else:
            return 0.0

        _, cr, cb = cv2.split(ycrcb)
        std_cr = float(np.std(cr))
        std_cb = float(np.std(cb))

        total_std = std_cr + std_cb
        if total_std < 1e-10:
            return 0.0

        imbalance = abs(std_cr - std_cb) / total_std
        return float(imbalance)

    except Exception as exc:
        logger.warning("Color space imbalance calculation error: %s", exc)
        return 0.0


def compute_texture_entropy(frame: Union[Image.Image, np.ndarray]) -> float:
    """
    Texture Entropy via Laplacian Variance.
    AI-generated images (especially scene/landscape reels with no faces) have
    unnaturally smooth, low-entropy backgrounds. Authentic camera footage from
    handheld devices has significant Laplacian variance from natural grain and
    motion blur.

    Returns a score in [0.0, 1.0] where LOW values indicate AI-smooth content.
    We invert it so high score = more suspicious (AI-like smoothness).
    """
    try:
        if isinstance(frame, Image.Image):
            img_np = np.array(frame)
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if img_np.ndim == 3 else img_np
        elif isinstance(frame, np.ndarray):
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        else:
            return 0.0

        laplacian_var = float(cv2.Laplacian(gray.astype(np.float32), cv2.CV_64F).var())
        # Real camera footage: laplacian_var > 200 (natural grain + motion)
        # AI-smooth generated: laplacian_var < 50
        # Score: 1.0 = very smooth (AI-like), 0.0 = noisy (camera-like)
        # Normalize: below 30 → 1.0 suspicious, above 400 → 0.0 authentic
        smooth_score = max(0.0, min(1.0, 1.0 - (laplacian_var / 400.0)))
        return float(smooth_score)
    except Exception as exc:
        logger.warning("Texture entropy calculation error: %s", exc)
        return 0.0


def compute_saturation_uniformity(frame: Union[Image.Image, np.ndarray]) -> float:
    """
    HSV Saturation Uniformity Score.
    AI-generated videos tend to have unnaturally uniform saturation across frames
    (no natural highlight blow-out, no shadow desaturation from real-world lighting).
    High score = suspicious uniformity.
    """
    try:
        if isinstance(frame, Image.Image):
            img_np = np.array(frame)
            bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR) if img_np.ndim == 3 else None
        elif isinstance(frame, np.ndarray):
            bgr = frame if frame.ndim == 3 else None
        else:
            return 0.0

        if bgr is None:
            return 0.0

        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        sat_channel = hsv[:, :, 1].astype(np.float32)
        sat_std = float(np.std(sat_channel))
        # Real footage: std dev of saturation > 40 (natural variation)
        # AI-gen: std dev typically < 25 (over-uniform palette)
        # Score: 1.0 = very uniform (AI-like), 0.0 = natural variation
        uniformity_score = max(0.0, min(1.0, 1.0 - (sat_std / 60.0)))
        return float(uniformity_score)
    except Exception as exc:
        logger.warning("Saturation uniformity calculation error: %s", exc)
        return 0.0


def analyze_signal_forensics(
    frames: List[Union[Image.Image, np.ndarray]],
    job_id: str = "",
) -> Dict[str, Any]:
    """
    Aggregates ELA, 2D FFT, and Color Space Variance across a batch of frames and salient crops.
    """
    tag = f"[{job_id}]" if job_id else ""

    if not frames:
        logger.warning("%s Signal Forensics: no frames provided.", tag)
        return {
            "signal_anomaly_detected": False,
            "metrics": {
                "ela_score": 0.0,
                "fft_ratio": 0.0,
                "color_imbalance": 0.0,
                "frames_analyzed": 0,
            },
            "error": "No frames provided",
        }

    try:
        # Prepare both original frames and center salient crops
        eval_items = []
        for f in frames:
            eval_items.append(f)
            if isinstance(f, Image.Image):
                w, h = f.size
                min_dim = min(w, h)
                crop = f.crop(((w - min_dim) // 2, (h - min_dim) // 2, (w + min_dim) // 2, (h + min_dim) // 2))
                eval_items.append(crop)

        ela_scores = [compute_ela_score(item) for item in eval_items]
        fft_scores = [compute_fft_score(item) for item in eval_items]
        color_scores = [compute_color_imbalance(item) for item in eval_items]
        texture_scores = [compute_texture_entropy(item) for item in eval_items]
        sat_scores = [compute_saturation_uniformity(item) for item in eval_items]

        mean_ela = float(np.mean(ela_scores)) if ela_scores else 0.0
        peak_ela = float(np.max(ela_scores)) if ela_scores else 0.0
        mean_fft = float(np.mean(fft_scores)) if fft_scores else 0.0
        mean_color = float(np.mean(color_scores)) if color_scores else 0.0
        mean_texture = float(np.mean(texture_scores)) if texture_scores else 0.0
        mean_sat_uniformity = float(np.mean(sat_scores)) if sat_scores else 0.0

        # Primary signal anomaly (existing logic - unchanged)
        signal_anomaly_detected = bool(
            mean_ela > 0.50 or peak_ela > 0.75 or (mean_fft > 0.90 and mean_color > 0.55)
        )

        # Non-face AI generation score: fires when background is unnaturally smooth
        # AND colour palette is unnaturally uniform — signature of generative AI video.
        # Threshold: texture smoothness > 0.55 AND sat uniformity > 0.55
        ai_gen_no_face_score = round((mean_texture * 0.6 + mean_sat_uniformity * 0.4), 4)
        ai_gen_suspected = bool(mean_texture > 0.55 and mean_sat_uniformity > 0.55)

        logger.info(
            "%s Signal Forensics complete: frames=%d  mean_ela=%.4f  peak_ela=%.4f  "
            "mean_fft=%.4f  color_imbalance=%.4f  texture=%.4f  sat_uniformity=%.4f  "
            "anomaly=%s  ai_gen_no_face=%s",
            tag,
            len(frames),
            mean_ela,
            peak_ela,
            mean_fft,
            mean_color,
            mean_texture,
            mean_sat_uniformity,
            signal_anomaly_detected,
            ai_gen_suspected,
        )

        return {
            "signal_anomaly_detected": signal_anomaly_detected,
            "ai_gen_suspected": ai_gen_suspected,
            "metrics": {
                "ela_score": round(mean_ela, 4),
                "fft_ratio": round(mean_fft, 4),
                "color_imbalance": round(mean_color, 4),
                "texture_smooth_score": round(mean_texture, 4),
                "sat_uniformity_score": round(mean_sat_uniformity, 4),
                "ai_gen_no_face_score": ai_gen_no_face_score,
                "frames_analyzed": len(frames),
            },
            "error": None,
        }

    except Exception as exc:
        logger.error("%s Signal Forensics execution failed: %s", tag, exc)
        return {
            "signal_anomaly_detected": False,
            "metrics": {
                "ela_score": 0.0,
                "fft_ratio": 0.0,
                "color_imbalance": 0.0,
                "frames_analyzed": len(frames),
            },
            "error": str(exc),
        }
