"""
AI Detection Pipeline Orchestrator

Links Provenance, Pixel Forensics, Temporal Signals, and Model Fingerprint layers
to calculate AI generation confidence score (0-100), verdict band, evidence, and caveats.
"""

from typing import Dict, Any, List, Optional
import os
import sys
import json

module_dir = os.path.dirname(os.path.abspath(__file__))
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

try:
    from .provenance import ProvenanceInspector
    from .pixel_forensics import PixelForensicsInspector, BasePixelClassifier
    from .temporal_signals import TemporalSignalsInspector
    from .model_fingerprint import ModelFingerprintInspector
    from .ensemble import EnsembleEngine
except ImportError:
    from provenance import ProvenanceInspector
    from pixel_forensics import PixelForensicsInspector, BasePixelClassifier
    from temporal_signals import TemporalSignalsInspector
    from model_fingerprint import ModelFingerprintInspector
    from ensemble import EnsembleEngine


class AIDetectionPipeline:
    """Orchestrates four-signal AI detection analysis on video files."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        pixel_classifier: Optional[BasePixelClassifier] = None,
    ):
        if config_path is None:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            default_cfg = os.path.join(module_dir, "config.yaml")
            if os.path.exists(default_cfg):
                config_path = default_cfg

        self.config_path = config_path
        self.provenance_layer = ProvenanceInspector(config_path=config_path)
        self.pixel_layer = PixelForensicsInspector(
            classifier=pixel_classifier,
        )
        self.temporal_layer = TemporalSignalsInspector(config_path=config_path)
        self.fingerprint_layer = ModelFingerprintInspector(config_path=config_path)
        self.ensemble_layer = EnsembleEngine(config_path=config_path)

    def analyze_video(
        self,
        video_path: str,
        metadata_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs full 4-signal analysis on a video file.
        """
        # 1. Provenance & Watermark Layer
        prov_res = self.provenance_layer.analyze(video_path)

        # 2. Pixel & Frequency Forensics Layer
        pixel_res = self.pixel_layer.analyze(video_path)

        # 3. Temporal & Biological Signals Layer
        # Reuse extracted frames from pixel layer if available
        frames = self.pixel_layer.extract_frames_from_video(video_path)
        temp_res = self.temporal_layer.analyze(video_path, frames=frames)

        # 4. Model Fingerprint Layer
        fp_res = self.fingerprint_layer.analyze(
            video_path=video_path,
            frames=frames,
            metadata_text=metadata_text,
        )

        # 5. Weighted Ensemble Engine
        ensemble_res = self.ensemble_layer.evaluate(
            prov_res=prov_res,
            pixel_res=pixel_res,
            temp_res=temp_res,
            fp_res=fp_res,
        )

        return {
            "video_path": video_path,
            "verdict": ensemble_res["verdict"],
            "confidence": ensemble_res["confidence"],
            "band_label": ensemble_res["band_label"],
            "layer_scores": ensemble_res["layer_scores"],
            "contributing_signals": ensemble_res["contributing_signals"],
            "caveats": ensemble_res["caveats"],
            "raw_layer_outputs": {
                "provenance": prov_res,
                "pixel_forensics": pixel_res,
                "temporal_signals": temp_res,
                "model_fingerprint": fp_res,
            },
        }
