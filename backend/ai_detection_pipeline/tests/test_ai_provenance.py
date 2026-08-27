"""
Unit Tests for Provenance Layer
"""

import pytest
from backend.ai_detection_pipeline.provenance import ProvenanceInspector


def test_provenance_nonexistent_file():
    inspector = ProvenanceInspector()
    res = inspector.analyze("nonexistent_video.mp4")
    assert res["provenance_found"] is False
    assert res["source"] is None
    assert res["confidence_if_found"] == 0.0


def test_provenance_c2pa_check(tmp_path):
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41adobe:c2pa_manifest")

    inspector = ProvenanceInspector()
    res = inspector.analyze(str(video_file))
    assert res["provenance_found"] is True
    assert "C2PA" in res["source"]
    assert res["confidence_if_found"] > 0.80
