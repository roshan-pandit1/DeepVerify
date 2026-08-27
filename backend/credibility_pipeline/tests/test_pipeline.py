"""
Integration Tests for End-to-End Pipeline
"""

import pytest
from backend.credibility_pipeline.pipeline import CredibilityPipeline, VideoInput


def test_pipeline_end_to_end_benign():
    pipeline = CredibilityPipeline()
    benign_input = VideoInput(
        video_id="video_benign_123",
        transcript="Good evening. The city council discussed transit budgets today.",
        uploader_metadata={
            "account_age_days": 1000,
            "is_verified": True,
            "historical_violation_count": 0,
        },
        engagement_data={"share_velocity": 8.0, "new_account_share_ratio": 0.02},
    )

    res = pipeline.run(benign_input)
    assert res["video_id"] == "video_benign_123"
    assert res["final_score"] < 50.0
    assert res["routing_decision"] == "no_action"
    assert "layer_scores" in res
    assert "explanation" in res


def test_pipeline_end_to_end_suspect():
    pipeline = CredibilityPipeline()
    suspect_input = VideoInput(
        video_id="video_suspect_999",
        transcript="Doctors hate this shocking secret! They don't want you to know. Fake news deepfake conspiracy hoax! Share before deleted!",
        uploader_metadata={
            "account_age_days": 5,
            "is_verified": False,
            "historical_violation_count": 2,
        },
        engagement_data={
            "share_velocity": 50.0,
            "new_account_share_ratio": 0.70,
            "share_timestamps": [1.0, 2.0, 3.0, 4.0, 5.0],
        },
    )

    res = pipeline.run(suspect_input)
    assert res["video_id"] == "video_suspect_999"
    assert res["final_score"] > 80.0
    assert res["routing_decision"] == "flag_for_human_review"
