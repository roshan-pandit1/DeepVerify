"""
Pipeline Orchestrator — Content Credibility & Manipulation Detection System

Ingests video data (transcript, uploader metadata, engagement metrics, frames) and runs
all three detection layers through the weighted ensemble to produce a final Credibility Score (0-100)
and a human moderation routing decision.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import os
import json

try:
    from .lexicon import LexiconAnalyzer
    from .content_model import BaseContentModel, MockContentModel
    from .source_credibility import SourceNetworkAnalyzer
    from .ensemble import EnsembleEngine
except ImportError:
    from lexicon import LexiconAnalyzer
    from content_model import BaseContentModel, MockContentModel
    from source_credibility import SourceNetworkAnalyzer
    from ensemble import EnsembleEngine


@dataclass
class PipelineResult:
    """Output payload from video credibility analysis."""

    video_id: str
    final_score: float
    routing_decision: str
    routing_label: str
    layer_scores: Dict[str, float]
    explanation: Dict[str, Any]
    raw_layer_outputs: Dict[str, Any]


@dataclass
class VideoInput:
    """Input payload for video credibility analysis."""

    video_id: str
    transcript: str = ""
    captions: str = ""
    uploader_metadata: Dict[str, Any] = field(
        default_factory=lambda: {
            "account_age_days": 365,
            "is_verified": False,
            "historical_violation_count": 0,
        }
    )
    engagement_data: Dict[str, Any] = field(
        default_factory=lambda: {
            "share_velocity": 10.0,
            "new_account_share_ratio": 0.0,
            "share_timestamps": [],
        }
    )
    video_frames: Optional[List[Any]] = None


class CredibilityPipeline:
    """Orchestrates multi-layer credibility analysis."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        content_model: Optional[BaseContentModel] = None,
    ):
        if config_path is None:
            # Look for default config.yaml in module folder
            module_dir = os.path.dirname(os.path.abspath(__file__))
            default_cfg = os.path.join(module_dir, "config.yaml")
            if os.path.exists(default_cfg):
                config_path = default_cfg

        self.lexicon_layer = LexiconAnalyzer(config_path=config_path)
        self.content_layer = content_model or MockContentModel()
        self.source_layer = SourceNetworkAnalyzer(config_path=config_path)
        self.ensemble_layer = EnsembleEngine(config_path=config_path)

    def run(self, input_data: VideoInput) -> Dict[str, Any]:
        """
        Executes end-to-end analysis across Lexicon, Content Model, and Source/Network layers.
        """
        # Combine transcript + captions for text analysis
        full_text = f"{input_data.transcript}\n{input_data.captions}".strip()

        # 1. Lexicon Layer (fast pre-filter)
        lexicon_res = self.lexicon_layer.analyze(full_text)

        # 2. Content Model Layer (Transformer / Multimodal)
        content_res = self.content_layer.predict(
            transcript=full_text, video_frames=input_data.video_frames
        )

        # 3. Source & Network Credibility Layer
        meta = input_data.uploader_metadata or {}
        eng = input_data.engagement_data or {}

        source_res = self.source_layer.analyze(
            account_age_days=meta.get("account_age_days", 365),
            is_verified=meta.get("is_verified", False),
            historical_violation_count=meta.get("historical_violation_count", 0),
            share_velocity=eng.get("share_velocity", 10.0),
            new_account_share_ratio=eng.get("new_account_share_ratio", 0.0),
            share_timestamps=eng.get("share_timestamps", []),
        )

        # 4. Ensemble & Routing Engine
        ensemble_res = self.ensemble_layer.evaluate(
            lexicon_res=lexicon_res,
            content_res=content_res,
            source_res=source_res,
        )

        # Return structured output object
        return {
            "video_id": input_data.video_id,
            "final_score": ensemble_res["final_score"],
            "routing_decision": ensemble_res["routing_decision"],
            "routing_label": ensemble_res["routing_label"],
            "layer_scores": ensemble_res["layer_scores"],
            "explanation": ensemble_res["explanation"],
            "raw_layer_outputs": {
                "lexicon": lexicon_res,
                "content_model": content_res,
                "source_network": source_res,
            },
        }


def main():
    """Demonstration execution of the Credibility Pipeline."""
    print("==================================================================")
    print("Content Credibility & Manipulation Detection System - Pipeline Run")
    print("==================================================================")

    pipeline = CredibilityPipeline()

    # Sample input: Suspicious viral clip
    suspect_input = VideoInput(
        video_id="video_sample_001",
        transcript="Doctors hate this shocking secret! They don't want you to know the truth. Share before deleted!",
        captions="Must watch emergency update repost now!",
        uploader_metadata={
            "account_age_days": 12,
            "is_verified": False,
            "historical_violation_count": 2,
        },
        engagement_data={
            "share_velocity": 48.5,  # extreme share burst
            "new_account_share_ratio": 0.65,  # bot coordination signal
            "share_timestamps": [1.0, 2.1, 2.5, 3.0, 4.2, 5.0, 8.1],
        },
    )

    result = pipeline.run(suspect_input)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
