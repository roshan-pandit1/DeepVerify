"""
Layer 1: Provenance & Watermark Inspector

Checks for:
1. C2PA / Coalition for Content Provenance and Authenticity manifest metadata
2. Imperceptible AI digital watermarks (e.g. SynthID, Digimarc, C2PA soft bindings)

Output schema:
{
    "provenance_found": bool,
    "source": str | None,
    "confidence_if_found": float,
    "details": dict
}
"""

from typing import Dict, Any, Optional
import os
import json


class ProvenanceInspector:
    """Inspects video file metadata for C2PA manifests and digital AI watermarks."""

    def __init__(self, config_path: Optional[str] = None):
        self.c2pa_high_confidence = 0.95
        self.watermark_high_confidence = 0.90

    def check_c2pa(self, video_path: str) -> Dict[str, Any]:
        """
        Attempts to read C2PA manifest from file using c2pa-python library if installed.
        """
        if not os.path.exists(video_path):
            return {"found": False, "source": None, "confidence": 0.0, "error": "File not found"}

        try:
            import c2pa

            reader = c2pa.Reader.from_file(video_path)
            manifest = json.loads(reader.json())

            active_manifest = manifest.get("active_manifest")
            if active_manifest:
                claim = manifest.get("manifests", {}).get(active_manifest, {})
                generator = claim.get("claim_generator", "Unknown C2PA Generator")
                assertions = claim.get("assertions", [])

                is_ai_claimed = any(
                    "ai" in str(a).lower() or "generative" in str(a).lower()
                    for a in assertions
                )

                return {
                    "found": True,
                    "source": f"C2PA: {generator}",
                    "confidence": self.c2pa_high_confidence,
                    "is_ai_claimed": is_ai_claimed,
                    "manifest_id": active_manifest,
                }
        except ImportError:
            # Fallback metadata header scan if c2pa-python is missing
            pass
        except Exception as e:
            # No manifest found or parsing error
            pass

        # Stub fallback metadata check
        try:
            with open(video_path, "rb") as f:
                header = f.read(4096)
                if b"c2pa" in header.lower() or b"adobe:c2pa" in header.lower():
                    return {
                        "found": True,
                        "source": "C2PA (Header Tag Detected)",
                        "confidence": 0.85,
                        "is_ai_claimed": True,
                    }
        except Exception:
            pass

        return {"found": False, "source": None, "confidence": 0.0}

    def check_ai_watermark(self, video_path: str) -> Dict[str, Any]:
        """
        Stub inspector for imperceptible AI watermarks (e.g. SynthID, Digimarc).

        TODO: In production, integrate provider SDKs / APIs:
        - SynthID API verification (Google Cloud SynthID detector)
        - Digimarc / Truepic watermark readers
        """
        # Production stub return
        return {
            "watermark_found": False,
            "watermark_type": None,
            "confidence": 0.0,
            "note": "Production stub: SynthID/Digimarc SDK integration point",
        }

    def analyze(self, video_path: str) -> Dict[str, Any]:
        """
        Combines C2PA and digital watermark signals into a unified Provenance result.
        """
        c2pa_res = self.check_c2pa(video_path)
        wm_res = self.check_ai_watermark(video_path)

        provenance_found = c2pa_res.get("found", False) or wm_res.get("watermark_found", False)

        source = None
        confidence = 0.0

        if c2pa_res.get("found"):
            source = c2pa_res.get("source", "C2PA Credentials")
            confidence = c2pa_res.get("confidence", 0.95)
        elif wm_res.get("watermark_found"):
            source = f"Watermark ({wm_res.get('watermark_type')})"
            confidence = wm_res.get("confidence", 0.90)

        return {
            "provenance_found": provenance_found,
            "source": source,
            "confidence_if_found": confidence if provenance_found else 0.0,
            "details": {
                "c2pa": c2pa_res,
                "watermark": wm_res,
            },
        }
