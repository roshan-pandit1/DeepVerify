"""
Unit Tests for Temporal & Biological Signals Layer
"""

import pytest
import numpy as np
from backend.ai_detection_pipeline.temporal_signals import TemporalSignalsInspector


def test_temporal_signals_empty_frames():
    inspector = TemporalSignalsInspector()
    res = inspector.analyze_frames([])
    assert res["temporal_score"] > 0.0
    assert res["details"]["frames_analyzed"] == 0


def test_temporal_signals_with_frames():
    inspector = TemporalSignalsInspector()
    frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(20)]
    res = inspector.analyze_frames(frames)
    assert 0.0 <= res["temporal_score"] <= 1.0
    assert "blink_score" in res
    assert "rppg_score" in res
    assert "lighting_score" in res
