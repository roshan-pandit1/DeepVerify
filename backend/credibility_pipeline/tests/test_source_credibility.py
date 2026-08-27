"""
Unit Tests for Source & Network Credibility Layer
"""

import pytest
from backend.credibility_pipeline.source_credibility import SourceNetworkAnalyzer


def test_trusted_account():
    analyzer = SourceNetworkAnalyzer()
    res = analyzer.analyze(
        account_age_days=730,
        is_verified=True,
        historical_violation_count=0,
        share_velocity=8.0,
        new_account_share_ratio=0.05,
    )
    assert res["account_trust_score"] >= 0.85
    assert res["propagation_anomaly_score"] == 0.0
    assert res["source_credibility_score"] >= 0.85
    assert len(res["anomaly_reasons"]) == 0


def test_suspicious_propagation_and_untrusted_account():
    analyzer = SourceNetworkAnalyzer()
    res = analyzer.analyze(
        account_age_days=10,
        is_verified=False,
        historical_violation_count=3,
        share_velocity=45.0,  # high z-score anomaly
        new_account_share_ratio=0.60,  # high bot ratio penalty
        share_timestamps=[1.0, 2.0, 3.0, 4.0, 5.0],  # micro burst
    )
    assert res["account_trust_score"] < 0.30
    assert res["propagation_anomaly_score"] > 0.70
    assert res["source_credibility_score"] < 0.20
    assert len(res["anomaly_reasons"]) >= 2
