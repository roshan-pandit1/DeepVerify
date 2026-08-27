"""
Unit Tests for Pixel & Frequency Forensics Layer
"""

import pytest
import numpy as np
from backend.ai_detection_pipeline.pixel_forensics import (
    PixelForensicsInspector,
    MockPixelClassifier,
)


def test_pixel_forensics_mock_classifier():
    classifier = MockPixelClassifier(fixed_score=0.88)
    inspector = PixelForensicsInspector(classifier=classifier)

    dummy_frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    res = inspector.analyze_frames([dummy_frame, dummy_frame])

    assert res["avg_score"] > 0.60
    assert len(res["per_frame_scores"]) == 2
    assert res["details"]["frames_analyzed"] == 2


def test_fft_spectral_anomaly_calculation():
    inspector = PixelForensicsInspector()

    # Synthetic periodic pattern frame (simulating GAN upsampling artifact grid)
    x = np.linspace(0, 10 * np.pi, 256)
    y = np.linspace(0, 10 * np.pi, 256)
    xx, yy = np.meshgrid(x, y)
    grid_pattern = ((np.sin(xx * 5) + np.cos(yy * 5)) * 127 + 128).astype(np.uint8)
    frame = np.stack([grid_pattern] * 3, axis=-1)

    anomaly_score = inspector.compute_fft_spectral_anomaly(frame)
    assert 0.0 <= anomaly_score <= 1.0
