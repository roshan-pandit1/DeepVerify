"""
Layer 2: Pixel & Frequency Forensics Inspector

Extracts sample frames and analyzes:
1. Spatial CNN deepfake/diffusion classifier interface (`BasePixelClassifier`)
2. Frequency-domain (FFT) high-frequency spectral periodic artifact analysis
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import os
import cv2
import numpy as np


class BasePixelClassifier(ABC):
    """
    Abstract interface for spatial CNN / vision classifiers (e.g. ResNet/EfficientNet/ViT).
    """

    @abstractmethod
    def predict_frame(self, frame: np.ndarray) -> float:
        """
        Takes a single BGR frame (np.ndarray) and returns AI likelihood score (0.0 to 1.0).
        """
        pass


class MockPixelClassifier(BasePixelClassifier):
    """
    Mock implementation of spatial pixel classifier for pipeline execution and testing.
    """

    def __init__(self, fixed_score: Optional[float] = None):
        self.fixed_score = fixed_score

    def predict_frame(self, frame: np.ndarray) -> float:
        if self.fixed_score is not None:
            return float(self.fixed_score)

        # Baseline heuristic fallback: check edge intensity variance
        if frame is None or frame.size == 0:
            return 0.20

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Unnaturally ultra-smooth or unnaturally sharp edges in mock heuristics
        if laplacian_var < 50.0 or laplacian_var > 1000.0:
            return 0.65
        return 0.25


class PixelForensicsInspector:
    """Extracts video frames and runs spatial CNN & FFT frequency artifact analysis."""

    def __init__(
        self,
        classifier: Optional[BasePixelClassifier] = None,
        sample_interval: int = 30,
        fft_threshold: float = 0.40,
    ):
        self.classifier = classifier or MockPixelClassifier()
        self.sample_interval = max(1, sample_interval)
        self.fft_threshold = fft_threshold

    def compute_fft_spectral_anomaly(self, frame: np.ndarray) -> float:
        """
        Calculates 2D Fast Fourier Transform (FFT) high-frequency spectral energy ratio.
        GAN/Diffusion upsampling leaves artificial periodic grid patterns in frequency space.
        """
        if frame is None or frame.size == 0:
            return 0.0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        h, w = gray.shape

        # 2D FFT and shift zero-frequency to center
        f_transform = np.fft.fft2(gray.astype(float))
        f_shift = np.fft.fftshift(f_transform)
        magnitude_spectrum = 20 * np.log(np.abs(f_shift) + 1e-8)

        # Calculate high-frequency outer ring vs center low-frequency energy ratio
        cy, cx = h // 2, w // 2
        r_inner = min(h, w) // 8

        y, x = np.ogrid[:h, :w]
        mask_center = (x - cx) ** 2 + (y - cy) ** 2 <= r_inner**2

        center_energy = np.mean(magnitude_spectrum[mask_center])
        outer_energy = np.mean(magnitude_spectrum[~mask_center])

        ratio = outer_energy / (center_energy + 1e-6)
        # Normalize spectral anomaly to 0.0 - 1.0 range
        anomaly_score = float(np.clip((ratio - 0.5) / 0.5, 0.0, 1.0))
        return round(anomaly_score, 3)

    def extract_frames_from_video(self, video_path: str) -> List[np.ndarray]:
        """Extracts sample frames from video at sample_interval."""
        if not os.path.exists(video_path):
            return []

        frames = []
        cap = cv2.VideoCapture(video_path)
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % self.sample_interval == 0:
                frames.append(frame)
            frame_idx += 1

        cap.release()
        return frames

    def analyze_frames(self, frames: List[np.ndarray]) -> Dict[str, Any]:
        """Runs spatial CNN classification and FFT frequency analysis across frames."""
        if not frames:
            return {
                "avg_score": 0.20,
                "per_frame_scores": [],
                "details": {
                    "frames_analyzed": 0,
                    "cnn_avg_score": 0.20,
                    "fft_avg_anomaly": 0.0,
                    "note": "No frames available for analysis",
                },
            }

        per_frame_scores = []
        cnn_scores = []
        fft_anomalies = []

        for f in frames:
            cnn_score = self.classifier.predict_frame(f)
            fft_score = self.compute_fft_spectral_anomaly(f)

            combined_frame_score = min(1.0, 0.7 * cnn_score + 0.3 * fft_score)

            cnn_scores.append(cnn_score)
            fft_anomalies.append(fft_score)
            per_frame_scores.append(round(combined_frame_score, 3))

        avg_score = float(np.mean(per_frame_scores))

        return {
            "avg_score": round(avg_score, 3),
            "per_frame_scores": per_frame_scores,
            "details": {
                "frames_analyzed": len(frames),
                "cnn_avg_score": round(float(np.mean(cnn_scores)), 3),
                "fft_avg_anomaly": round(float(np.mean(fft_anomalies)), 3),
            },
        }

    def analyze(self, video_path: str) -> Dict[str, Any]:
        """Extracts frames from video_path and evaluates pixel forensics."""
        frames = self.extract_frames_from_video(video_path)
        return self.analyze_frames(frames)
