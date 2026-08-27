"""
Unit Tests for Model Fingerprint Layer
"""

import pytest
from backend.ai_detection_pipeline.model_fingerprint import ModelFingerprintInspector


def test_model_fingerprint_keyword_match():
    inspector = ModelFingerprintInspector()
    res = inspector.analyze("dummy.mp4", metadata_text="Generated with OpenAI Sora hyperrealistic rendering")

    assert res["match_found"] is True
    assert res["matched_model"] == "OpenAI Sora"
    assert res["confidence"] >= 0.90


def test_model_fingerprint_no_match():
    inspector = ModelFingerprintInspector()
    res = inspector.analyze("dummy.mp4", metadata_text="Camera recording from iPhone 15 Pro")

    assert res["match_found"] is False
    assert res["matched_model"] is None
    assert res["confidence"] == 0.0
