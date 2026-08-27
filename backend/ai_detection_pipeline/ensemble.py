"""
Layer 5: Weighted Ensemble Engine

Combines signals from:
1. Provenance Layer (0.35 weight)
2. Pixel Forensics Layer (0.25 weight)
3. Temporal Signals Layer (0.25 weight)
4. Model Fingerprint Layer (0.15 weight)

Enforces Provenance Dominance Rule when verified C2PA / Watermarks exist.
Maps aggregate score to confidence bands (90-100, 60-89, 40-59, 0-39) and formats
contributing signals and caveats.
"""

from typing import Dict, Any, List, Optional
import os
import yaml


class EnsembleEngine:
    """Ensemble engine combining multi-modal detection signals."""

    def __init__(self, config_path: Optional[str] = None):
        self.w_prov = 0.35
        self.w_pixel = 0.25
        self.w_temp = 0.25
        self.w_fp = 0.15
        self.dominance_threshold = 0.85

        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                if cfg and "ensemble_weights" in cfg:
                    w = cfg["ensemble_weights"]
                    self.w_prov = w.get("provenance", 0.35)
                    self.w_pixel = w.get("pixel_forensics", 0.25)
                    self.w_temp = w.get("temporal_signals", 0.25)
                    self.w_fp = w.get("model_fingerprint", 0.15)
                if cfg and "provenance_params" in cfg:
                    self.dominance_threshold = cfg["provenance_params"].get(
                        "dominance_threshold", 0.85
                    )

    def evaluate(
        self,
        prov_res: Dict[str, Any],
        pixel_res: Dict[str, Any],
        temp_res: Dict[str, Any],
        fp_res: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculates ensemble score, verdict band, contributing signals, and plain-language caveats.
        """
        prov_found = prov_res.get("provenance_found", False)
        prov_conf = prov_res.get("confidence_if_found", 0.0)

        pixel_score = pixel_res.get("avg_score", 0.20)
        temp_score = temp_res.get("temporal_score", 0.20)
        fp_matched = fp_res.get("match_found", False)
        fp_conf = fp_res.get("confidence", 0.0) if fp_matched else 0.0

        # Check Provenance Dominance Rule
        # If C2PA/watermark is present with high confidence, let it dominate
        if prov_found and prov_conf >= self.dominance_threshold:
            final_confidence = round(prov_conf * 100.0)
            dominance_applied = True
        else:
            dominance_applied = False
            # When provenance is absent, it is neutral (weight 0.0) and does not drag down other signals
            prov_weight = self.w_prov if prov_found else 0.0
            prov_score = prov_conf if prov_found else 0.0

            total_weight = prov_weight + self.w_pixel + self.w_temp + self.w_fp
            if total_weight <= 0.0:
                total_weight = 1.0

            weighted_sum = (
                (prov_weight * prov_score)
                + (self.w_pixel * pixel_score)
                + (self.w_temp * temp_score)
                + (self.w_fp * fp_conf)
            )
            final_confidence = round((weighted_sum / total_weight) * 100.0)

        final_confidence = max(0, min(100, final_confidence))

        # Map to Confidence Bands
        if final_confidence >= 90:
            verdict = "likely_ai"
            band_label = "High Confidence AI-Generated"
        elif final_confidence >= 60:
            verdict = "likely_ai"
            band_label = "Likely AI-Generated"
        elif final_confidence >= 40:
            verdict = "inconclusive"
            band_label = "Inconclusive Evidence"
        else:
            verdict = "likely_real"
            band_label = "Likely Real / Insufficient AI Signal"

        # Construct Contributing Signals
        signals = []
        if prov_found:
            signals.append(f"Provenance match confirmed: {prov_res.get('source')} ({round(prov_conf*100)}% confidence)")

        if pixel_score >= 0.50:
            details = pixel_res.get("details", {})
            fft_anom = details.get("fft_avg_anomaly", 0.0)
            signals.append(f"Pixel forensics detected synthetic spatial/spectral artifacts (score: {pixel_score:.2f}, FFT anomaly: {fft_anom:.2f})")

        if temp_score >= 0.50:
            signals.append(f"Temporal analysis detected physiological/illumination inconsistencies (score: {temp_score:.2f})")

        if fp_matched:
            signals.append(f"Model fingerprint matched known generator signature: {fp_res.get('matched_model')} ({round(fp_conf*100)}% confidence)")

        if not signals:
            signals.append("No significant synthetic AI signals detected across layers.")

        # Construct Plain-Language Caveats
        caveat_parts = []
        if not prov_found:
            caveat_parts.append("No C2PA provenance metadata or AI watermark found")
        if not fp_matched:
            caveat_parts.append("No matching signature in model fingerprint database")

        if caveat_parts:
            caveats = "; ".join(caveat_parts) + ". Score based on available pixel, temporal, and metadata signals."
        else:
            caveats = "Verified provenance credentials detected intact."

        return {
            "verdict": verdict,
            "confidence": final_confidence,
            "band_label": band_label,
            "dominance_applied": dominance_applied,
            "layer_scores": {
                "provenance": round(prov_conf if prov_found else 0.0, 3),
                "pixel_forensics": round(pixel_score, 3),
                "temporal_signals": round(temp_score, 3),
                "model_fingerprint": round(fp_conf, 3),
            },
            "contributing_signals": signals,
            "caveats": caveats,
        }
