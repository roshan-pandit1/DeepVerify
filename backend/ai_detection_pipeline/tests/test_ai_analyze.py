"""
Integration Tests for CLI Entrypoint and Pipeline Execution
"""

import pytest
import subprocess
import json
import sys
from backend.ai_detection_pipeline.pipeline import AIDetectionPipeline


def test_pipeline_end_to_end(tmp_path):
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"\x00" * 1024)

    pipeline = AIDetectionPipeline()
    res = pipeline.analyze_video(str(video_file), metadata_text="Sample Sora generation")

    assert "verdict" in res
    assert "confidence" in res
    assert "layer_scores" in res
    assert "contributing_signals" in res
    assert "caveats" in res


def test_cli_execution(tmp_path):
    video_file = tmp_path / "sample_cli.mp4"
    video_file.write_bytes(b"\x00" * 1024)

    cmd = [
        sys.executable,
        "backend/ai_detection_pipeline/analyze.py",
        str(video_file),
        "--metadata",
        "OpenAI Sora test clip",
    ]

    env = {"PYTHONPATH": "."}
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert result.returncode == 0

    output_json = json.loads(result.stdout)
    assert "verdict" in output_json
    assert "confidence" in output_json
    assert output_json["video_path"] == str(video_file)
