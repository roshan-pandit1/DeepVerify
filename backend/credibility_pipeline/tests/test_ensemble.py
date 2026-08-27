"""
Unit Tests for Ensemble & Routing Engine
"""

import pytest
from backend.credibility_pipeline.ensemble import EnsembleEngine


def test_ensemble_low_risk_no_action():
    engine = EnsembleEngine()
    lexicon_res = {"density_score": 0.0, "categories_triggered": []}
    content_res = {"content_risk_score": 0.10, "category_labels": ["none"]}
    source_res = {"source_credibility_score": 0.95, "account_trust_score": 0.95, "anomaly_reasons": []}

    res = engine.evaluate(lexicon_res, content_res, source_res)
    assert res["final_score"] < 50.0
    assert res["routing_decision"] == "no_action"


def test_ensemble_high_risk_flag_for_human_review():
    engine = EnsembleEngine()
    lexicon_res = {
        "density_score": 0.80,
        "categories_triggered": ["urgency_fear", "false_authority", "urgent_cta"],
        "cooccurrence_bonus_applied": True,
    }
    content_res = {
        "content_risk_score": 0.90,
        "category_labels": ["misinfo", "manipulated_media"],
    }
    source_res = {
        "source_credibility_score": 0.10,
        "account_trust_score": 0.15,
        "anomaly_reasons": ["High share velocity z-score"],
    }

    res = engine.evaluate(lexicon_res, content_res, source_res)
    assert res["final_score"] > 80.0
    assert res["routing_decision"] == "flag_for_human_review"
    assert len(res["explanation"]["top_contributing_factors"]) >= 2


def test_ensemble_medium_risk_reduce_distribution():
    engine = EnsembleEngine()
    lexicon_res = {"density_score": 0.40, "categories_triggered": ["urgency_fear"]}
    content_res = {"content_risk_score": 0.60, "category_labels": ["misinfo"]}
    source_res = {"source_credibility_score": 0.40, "account_trust_score": 0.50, "anomaly_reasons": []}

    res = engine.evaluate(lexicon_res, content_res, source_res)
    assert 50.0 <= res["final_score"] <= 80.0
    assert res["routing_decision"] == "reduce_distribution_pending_review"
