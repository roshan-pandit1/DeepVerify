"""
Lexicon Layer — Rhetorical Marker Analysis Engine

Fast, first-pass filter scoring rhetorical manipulation patterns (urgency, false authority,
us-vs-them framing, certainty inflation, urgent CTA).

Key Design Principle:
Lexicon score is a TRIGGER, not a VERDICT. It measures cross-category co-occurrence,
never repetition of a single term.
"""

from typing import Dict, List, Any, Optional
import os
import yaml


# Fallback Seed Categories (Populate real terms from labeled datasets in production)
DEFAULT_LEXICON_CATEGORIES = {
    "urgency_fear": {
        "description": "Manufactures imminent threat/crisis",
        "seed_terms": ["before it's too late", "they don't want you to know", "shocking secret"],
        "weight": 1.0,
    },
    "ingroup_outgroup": {
        "description": "Us-vs-them / dehumanizing framing",
        "seed_terms": ["enemy of the people", "those people", "destroying our country"],
        "weight": 1.2,
    },
    "false_authority": {
        "description": "Unverified credential claims, fake expert appeals",
        "seed_terms": ["doctors hate this", "insider reveals", "secret source confirms"],
        "weight": 1.0,
    },
    "certainty_inflation": {
        "description": "Absolutist language on contested claims",
        "seed_terms": ["always", "never", "100% proven", "undeniable proof"],
        "weight": 0.7,
    },
    "urgent_cta": {
        "description": "Amplification pressure tactics",
        "seed_terms": ["share before deleted", "repost now", "spread this fast"],
        "weight": 1.1,
    },
}


def compute_density_score(
    text: str,
    categories: Optional[Dict[str, Any]] = None,
    cooccurrence_threshold: int = 3,
    cooccurrence_bonus: float = 0.15,
) -> Dict[str, Any]:
    """
    Returns per-category hits + a combined density score (0.0 to 1.0).

    Density rewards CO-OCCURRENCE across categories, not repetition
    within one category. Adds a bonus when `cooccurrence_threshold`+ distinct
    categories are triggered.
    """
    if categories is None:
        categories = DEFAULT_LEXICON_CATEGORIES

    text_lower = text.lower() if text else ""
    category_hits = {}

    for cat, data in categories.items():
        seed_terms = data.get("seed_terms", [])
        weight = data.get("weight", 1.0)
        hits = [t for t in seed_terms if t in text_lower]
        category_hits[cat] = {
            "hit": len(hits) > 0,
            "terms_found": hits,
            "weight": weight,
        }

    categories_triggered = [c for c, v in category_hits.items() if v["hit"]]
    n_triggered = len(categories_triggered)
    weighted_sum = sum(category_hits[c]["weight"] for c in categories_triggered)
    max_possible = sum(v.get("weight", 1.0) for v in categories.values()) or 1.0

    # Co-occurrence bonus: 3+ distinct categories in short text = strong signal
    bonus = cooccurrence_bonus if n_triggered >= cooccurrence_threshold else 0.0

    raw_ratio = weighted_sum / max_possible
    density_score = min(1.0, raw_ratio + bonus)

    return {
        "density_score": round(float(density_score), 3),
        "categories_triggered": categories_triggered,
        "cooccurrence_bonus_applied": bonus > 0.0,
        "detail": category_hits,
    }


class LexiconAnalyzer:
    """Configurable Lexicon Analysis class."""

    def __init__(self, config_path: Optional[str] = None):
        self.categories = DEFAULT_LEXICON_CATEGORIES
        self.cooccurrence_threshold = 3
        self.cooccurrence_bonus = 0.15

        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                if cfg and "lexicon_categories" in cfg:
                    self.categories = cfg["lexicon_categories"]
                if cfg and "lexicon_params" in cfg:
                    self.cooccurrence_threshold = cfg["lexicon_params"].get(
                        "cooccurrence_threshold", 3
                    )
                    self.cooccurrence_bonus = cfg["lexicon_params"].get(
                        "cooccurrence_bonus", 0.15
                    )

    def analyze(self, transcript: str) -> Dict[str, Any]:
        return compute_density_score(
            text=transcript,
            categories=self.categories,
            cooccurrence_threshold=self.cooccurrence_threshold,
            cooccurrence_bonus=self.cooccurrence_bonus,
        )
