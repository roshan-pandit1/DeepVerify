"""
AI-Generated Video Detection Pipeline Package.
"""

from .provenance import ProvenanceInspector
from .pixel_forensics import PixelForensicsInspector, BasePixelClassifier, MockPixelClassifier
from .temporal_signals import TemporalSignalsInspector
from .model_fingerprint import ModelFingerprintInspector
from .ensemble import EnsembleEngine
from .pipeline import AIDetectionPipeline

__all__ = [
    "ProvenanceInspector",
    "PixelForensicsInspector",
    "BasePixelClassifier",
    "MockPixelClassifier",
    "TemporalSignalsInspector",
    "ModelFingerprintInspector",
    "EnsembleEngine",
    "AIDetectionPipeline",
]
