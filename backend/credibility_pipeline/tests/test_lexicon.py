"""
Unit Tests for Lexicon Layer
"""

import pytest
from backend.credibility_pipeline.lexicon import compute_density_score, LexiconAnalyzer


def test_lexicon_clean_text():
    text = "This is a clean news report about public transit and budget meetings."
    res = compute_density_score(text)
    assert res["density_score"] == 0.0
    assert len(res["categories_triggered"]) == 0
    assert res["cooccurrence_bonus_applied"] is False


def test_lexicon_single_category_hit():
    text = "Top insider reveals secret details."
    res = compute_density_score(text)
    assert res["density_score"] > 0.0
    assert "false_authority" in res["categories_triggered"]
    assert res["cooccurrence_bonus_applied"] is False


def test_lexicon_cooccurrence_bonus():
    # Trigger 3 distinct categories: urgency_fear, false_authority, urgent_cta
    text = "Doctors hate this! Before it's too late share before deleted!"
    res = compute_density_score(text)
    assert len(res["categories_triggered"]) >= 3
    assert res["cooccurrence_bonus_applied"] is True
    assert res["density_score"] >= 0.5


def test_lexicon_analyzer_class():
    analyzer = LexiconAnalyzer()
    res = analyzer.analyze("repost now before it's too late")
    assert "urgent_cta" in res["categories_triggered"]
    assert "urgency_fear" in res["categories_triggered"]
