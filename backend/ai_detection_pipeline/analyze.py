"""
CLI Entrypoint — AI-Generated Video Detection System

Usage:
    python analyze.py <video_path> [--metadata "optional text"] [--config config.yaml]

Outputs structured JSON verdict with confidence score (0-100), contributing signals, and caveats.
"""

from typing import Dict, Any
import argparse
import os
import sys
import json

module_dir = os.path.dirname(os.path.abspath(__file__))
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

try:
    from .pipeline import AIDetectionPipeline
except ImportError:
    try:
        from pipeline import AIDetectionPipeline
    except ImportError:
        from backend.ai_detection_pipeline.pipeline import AIDetectionPipeline


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a video file for AI generation signatures and produce a confidence verdict."
    )
    parser.add_argument(
        "video_path",
        type=str,
        help="Path to the target video file (.mp4, .mov, .avi, etc.)",
    )
    parser.add_argument(
        "--metadata",
        type=str,
        default=None,
        help="Optional text metadata or captions associated with the video",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom config.yaml configuration file",
    )

    args = parser.parse_args()

    if not os.path.exists(args.video_path):
        error_payload = {
            "error": f"Video file not found: {args.video_path}",
            "verdict": "inconclusive",
            "confidence": 0,
        }
        print(json.dumps(error_payload, indent=2))
        sys.exit(1)

    pipeline = AIDetectionPipeline(config_path=args.config)
    result = pipeline.analyze_video(
        video_path=args.video_path,
        metadata_text=args.metadata,
    )

    # Print structured JSON output to stdout
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
