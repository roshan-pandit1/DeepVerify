"""
Unit Tests for Weighted Ensemble Engine & Verdict Bands
"""

import pytest
from backend.ai_detection_pipeline.ensemble import EnsembleEngine


def test_ensemble_provenance_dominance():
    engine = EnsembleEngine()
    prov_res = {"provenance_found": True, "source": "C2PA Verified", "confidence_if_found": 0.95}
    pixel_res = {"avg_score": 0.10, "details": {}}
    temp_res = {"temporal_score": 0.10, "details": {}}
    fp_res = {"match_found": False, "confidence": 0.0, "details": {}}

    res = engine.evaluate(prov_res, pixel_res, temp_res, fp_res)
    assert res["confidence"] == 95
    assert res["verdict"] == "likely_ai"
    assert res["dominance_applied"] is True


def test_ensemble_weighted_combination_likely_ai():
    engine = EnsembleEngine()
    prov_res = {"provenance_found": False, "confidence_if_found": 0.0}
    pixel_res = {"avg_score": 0.85, "details": {"fft_avg_anomaly": 0.60}}
    temp_res = {"temporal_score": 0.70, "details": {}}
    fp_res = {"match_found": True, "matched_model": "Runway Gen-3 Alpha", "confidence": 0.88, "details": {}}

    res = engine.evaluate(prov_res, pixel_res, temp_res, fp_res)
    assert res["confidence"] >= 60
    assert res["verdict"] == "likely_ai"
    assert len(res["contributing_signals"]) >= 2
    assert "caveats" in res


def test_ensemble_likely_real():
    engine = EnsembleEngine()
    prov_res = {"provenance_found": False, "confidence_if_found": 0.0}
    pixel_res = {"avg_score": 0.15, "details": {}}
    temp_res = {"temporal_score": 0.15, "details": {}}
    fp_res = {"match_found": False, "confidence": 0.0, "details": {}}

    res = engine.evaluate(prov_res, pixel_res, temp_res, fp_res)
    assert res["confidence"] < 40
    assert res["verdict"] == "likely_real"
