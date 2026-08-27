"""
Unit Tests for Content Model Layer
"""

import pytest
from backend.credibility_pipeline.content_model import MockContentModel


def test_mock_content_model_default_heuristics():
    model = MockContentModel()

    # Clean text
    res_clean = model.predict("Normal conversation about sports and weather.")
    assert res_clean["content_risk_score"] == 0.15
    assert "none" in res_clean["category_labels"]

    # Misinfo text
    res_misinfo = model.predict("This is fake news and a conspiracy hoax!")
    assert res_misinfo["content_risk_score"] > 0.4
    assert "misinfo" in res_misinfo["category_labels"]

    # Deepfake / manipulated media text
    res_df = model.predict("This is a deepfake with cloned voice.")
    assert res_df["content_risk_score"] > 0.4
    assert "manipulated_media" in res_df["category_labels"]


def test_mock_content_model_preset_override():
    model = MockContentModel(default_risk_score=0.85, default_labels=["manipulated_media"])
    res = model.predict("Anything here")
    assert res["content_risk_score"] == 0.85
    assert "manipulated_media" in res["category_labels"]
