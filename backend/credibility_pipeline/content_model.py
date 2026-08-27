"""
Content Model Layer — Transformer & Multimodal Analysis Interface

Provides abstract base class and mock implementation for content risk evaluation
(claim detection, toxicity/hate speech, deepfake/manipulated media classification).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class BaseContentModel(ABC):
    """
    Abstract interface for Content Classification Models.
    Real implementations will wrap HuggingFace Transformers, CLIP, or fine-tuned deepfake models.
    """

    @abstractmethod
    def predict(
        self, transcript: str, video_frames: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate content risk across text and video modal signals.

        Returns:
            dict containing:
                - content_risk_score: float (0.0 to 1.0)
                - category_labels: List[str] (e.g. ["misinfo", "manipulated_media"])
                - details: dict (per-category model outputs)
        """
        pass


class MockContentModel(BaseContentModel):
    """
    Mock implementation of Content Model for testing and modular execution.

    Allows deterministic score overrides or heuristic mock predictions.
    TODO: Replace or pair with fine-tuned HuggingFace text classifier + visual CLIP model.
    """

    def __init__(
        self,
        default_risk_score: Optional[float] = None,
        default_labels: Optional[List[str]] = None,
    ):
        self.default_risk_score = default_risk_score
        self.default_labels = default_labels

    def predict(
        self, transcript: str, video_frames: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates risk score using mock heuristics or preset test defaults.
        """
        # If deterministic test values were provided, use them
        if self.default_risk_score is not None:
            labels = self.default_labels or (["none"] if self.default_risk_score < 0.3 else ["misinfo"])
            return {
                "content_risk_score": round(float(self.default_risk_score), 3),
                "category_labels": labels,
                "details": {
                    "text_model_confidence": self.default_risk_score,
                    "frame_analysis_triggered": video_frames is not None and len(video_frames) > 0,
                    "model_name": "MockContentModel (Test Fixed Score)",
                },
            }

        # Rule-based fallback heuristic for mock behavior
        text_lower = (transcript or "").lower()
        labels = []
        risk = 0.15

        if any(term in text_lower for term in ["fake news", "conspiracy", "hoax", "proven false"]):
            labels.append("misinfo")
            risk += 0.35

        if any(term in text_lower for term in ["deepfake", "ai generated", "cloned voice", "manipulated"]):
            labels.append("manipulated_media")
            risk += 0.40

        if any(term in text_lower for term in ["hate", "destroy them", "subhuman"]):
            labels.append("hate_speech")
            risk += 0.30

        if not labels:
            labels.append("none")

        final_risk = min(1.0, risk)

        return {
            "content_risk_score": round(float(final_risk), 3),
            "category_labels": labels,
            "details": {
                "text_heuristic_risk": final_risk,
                "frames_processed": len(video_frames) if video_frames else 0,
                "model_name": "MockContentModel (Rule-Based Stub)",
                # TODO: Integrate trained Transformer model pipeline:
                # - Text model: pipeline("text-classification", model="your-org/misinfo-detector")
                # - Vision model: CLIP / ResNet deepfake frame classifier
            },
        }
