"""
Weighted Ensemble & Routing Engine

Combines signals from:
1. Lexicon Layer (0.15 weight default)
2. Content Model Layer (0.45 weight default)
3. Source/Network Credibility Layer (0.40 weight default)

Outputs a Video Credibility Score (0-100) and a moderation routing decision.

POLICY DIRECTIVE:
No automated removal or takedown logic. Output is strictly a routing recommendation
for human review queues or distribution adjustments.
"""

from typing import Dict, Any, List, Optional
import os
import yaml


class EnsembleEngine:
    """Combines multi-layer signals, assigns routing decisions, and generates explanation logs."""

    def __init__(self, config_path: Optional[str] = None):
        self.w_lexicon = 0.15
        self.w_content = 0.45
        self.w_source = 0.40

        self.threshold_human_review = 80.0
        self.threshold_reduce_distribution = 50.0

        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                if cfg and "ensemble_weights" in cfg:
                    w = cfg["ensemble_weights"]
                    self.w_lexicon = w.get("lexicon", 0.15)
                    self.w_content = w.get("content_model", 0.45)
                    self.w_source = w.get("source_network", 0.40)

                if cfg and "routing_thresholds" in cfg:
                    rt = cfg["routing_thresholds"]
                    self.threshold_human_review = rt.get("human_review", 80.0)
                    self.threshold_reduce_distribution = rt.get("reduce_distribution", 50.0)

    def evaluate(
        self,
        lexicon_res: Dict[str, Any],
        content_res: Dict[str, Any],
        source_res: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculates ensemble score and routing decision.

        Scores:
        - lexicon_density: 0.0 to 1.0 (higher = more manipulative markers)
        - content_risk: 0.0 to 1.0 (higher = more content risk)
        - source_credibility: 0.0 to 1.0 (higher = more trusted) -> risk = (1.0 - credibility)
        """
        lexicon_density = lexicon_res.get("density_score", 0.0)
        content_risk = content_res.get("content_risk_score", 0.0)
        source_credibility = source_res.get("source_credibility_score", 1.0)

        source_risk = max(0.0, min(1.0, 1.0 - source_credibility))

        # Weighted risk calculation
        total_weight = self.w_lexicon + self.w_content + self.w_source or 1.0
        weighted_risk_0_1 = (
            (self.w_lexicon * lexicon_density)
            + (self.w_content * content_risk)
            + (self.w_source * source_risk)
        ) / total_weight

        # Scale to 0-100 final risk score
        final_score = round(weighted_risk_0_1 * 100.0, 1)

        # Routing decision
        if final_score > self.threshold_human_review:
            routing_decision = "flag_for_human_review"
            routing_label = "Auto-flagged for human review (Hold distribution)"
        elif final_score >= self.threshold_reduce_distribution:
            routing_decision = "reduce_distribution_pending_review"
            routing_label = "Reduce distribution (Queue for review)"
        else:
            routing_decision = "no_action"
            routing_label = "No action required"

        # Generate top contributing factors for transparency/appeals
        factors = []

        if lexicon_density >= 0.5:
            cats = lexicon_res.get("categories_triggered", [])
            bonus_str = " (with co-occurrence bonus)" if lexicon_res.get("cooccurrence_bonus_applied") else ""
            factors.append(
                f"High rhetorical manipulation score ({lexicon_density:.2f}): "
                f"triggered {len(cats)} categories ({', '.join(cats)}){bonus_str}"
            )

        if content_risk >= 0.4:
            labels = content_res.get("category_labels", [])
            factors.append(
                f"Content model flagged high risk ({content_risk:.2f}) "
                f"for categories: {', '.join(labels)}"
            )

        if source_credibility <= 0.5:
            reasons = source_res.get("anomaly_reasons", [])
            reasons_str = f" [{'; '.join(reasons)}]" if reasons else ""
            factors.append(
                f"Low source credibility ({source_credibility:.2f}) / "
                f"Account trust ({source_res.get('account_trust_score', 0.0):.2f}){reasons_str}"
            )

        if not factors:
            factors.append("All layers returned normal baseline signals.")

        return {
            "final_score": final_score,
            "routing_decision": routing_decision,
            "routing_label": routing_label,
            "layer_scores": {
                "lexicon": round(lexicon_density, 3),
                "content_model": round(content_risk, 3),
                "source_network_credibility": round(source_credibility, 3),
                "source_network_risk": round(source_risk, 3),
            },
            "explanation": {
                "categories_triggered": lexicon_res.get("categories_triggered", []),
                "content_labels": content_res.get("category_labels", []),
                "top_contributing_factors": factors,
            },
        }
