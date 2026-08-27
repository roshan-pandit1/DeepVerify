"""
pipeline/threat_restriction.py — Misinformation Panic Index & Context Mismatch Evaluator.

Provides:
  1. calculate_panic_index(core_claim_text, virality_speed):
     Computes a 1-100 panic index score based on high-risk keyword triggers
     (e.g., military, riot, border, violence) and viral share velocity.
  2. evaluate_context_mismatch(user_claim, vision_labels):
     Uses an LLM call to determine whether the user's caption/claim contradicts
     the authentic context returned by Google Cloud Vision best_guess_labels.
"""
import json
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# High-risk keywords associated with societal panic and high-impact misinformation
_HIGH_RISK_KEYWORDS = {
    "military", "riot", "border", "violence", "invasion", "war", "attack",
    "casualty", "casualties", "breaking", "crisis", "explosion", "terror",
    "terrorist", "insurgency", "conflict", "bomb", "protest", "unrest",
    "shooting", "massacre", "emergency", "evacuation", "airstrike"
}


def calculate_panic_index(core_claim_text: str, virality_speed: float = 0.0) -> float:
    """
    Calculate a Panic Index score (1 - 100) based on high-risk keyword triggers
    and the virality velocity (e.g. shares/min or relative virality speed).

    Args:
        core_claim_text: Text caption, title, or claim accompanying the media.
        virality_speed: Numerical velocity metric (0.0 to 100.0+).

    Returns:
        Panic index score bounded between 1.0 and 100.0.
    """
    if not core_claim_text:
        claim_str = ""
    else:
        claim_str = str(core_claim_text).lower()

    # Extract words
    words = set(re.findall(r'\b\w+\b', claim_str))
    matching_keywords = words.intersection(_HIGH_RISK_KEYWORDS)

    # Keyword panic score: 25 points base per matched high-risk keyword (max 60 pts)
    keyword_score = min(60.0, len(matching_keywords) * 25.0)

    # Virality contribution: scale virality_speed up to 40 pts
    try:
        speed_val = float(virality_speed)
    except (ValueError, TypeError):
        speed_val = 0.0

    virality_score = min(40.0, max(0.0, speed_val * 0.4 if speed_val <= 100.0 else 40.0))

    # Base baseline score: if matching keywords present, minimum base score is 20.0
    base_score = 20.0 if matching_keywords else 1.0

    total_panic = base_score + keyword_score + virality_score
    final_score = round(min(100.0, max(1.0, total_panic)), 2)

    logger.info(
        "threat_restriction: Panic index calculation: text='%s' (keywords=%s), speed=%.1f => panic_index=%.2f",
        core_claim_text[:50] if core_claim_text else "", list(matching_keywords), speed_val, final_score
    )
    return final_score


def evaluate_context_mismatch(user_claim: str, vision_labels: List[str]) -> bool:
    """
    Use an LLM call to compare user's caption/claim against Google Vision best_guess_labels.

    Returns True if the LLM detects a contradiction/out-of-context mismatch,
    False otherwise.

    Args:
        user_claim: Caption or claim submitted with the video.
        vision_labels: List of reverse image best_guess_labels from GCP Vision.

    Returns:
        bool: True if context mismatch/contradiction detected, else False.
    """
    if not user_claim or not vision_labels:
        logger.info("threat_restriction: Empty user_claim or vision_labels — returning mismatch=False")
        return False

    # Retrieve API configuration
    try:
        from config import get_settings  # type: ignore
        settings = get_settings()
        groq_key = getattr(settings, "groq_api_key", "")
        openai_key = getattr(settings, "openai_api_key", "")
        llm_provider = getattr(settings, "llm_provider", "openai")
    except Exception as e:
        logger.warning("threat_restriction: Could not load settings: %s", e)
        groq_key = ""
        openai_key = ""
        llm_provider = "openai"

    prompt_text = (
        "You are an expert OSINT media verification and cheapfake analysis agent.\n"
        "Analyze whether the provided User Claim directly contradicts or misrepresents "
        "the actual historical/authentic context indicated by the Reverse Image Vision Labels.\n\n"
        f"User Claim: \"{user_claim}\"\n"
        f"Vision Search Best-Guess Labels: {vision_labels}\n\n"
        "Determine if there is a context mismatch or out-of-context deception (e.g. video from one event/location/year "
        "falsely claimed to be a different ongoing crisis/conflict).\n"
        "Respond ONLY with valid JSON in this exact structure:\n"
        "{\n"
        "  \"context_mismatch\": true or false,\n"
        "  \"reasoning\": \"<concise 1-2 sentence explanation>\"\n"
        "}"
    )

    try:
        if groq_key:
            from groq import Groq  # type: ignore
            client = Groq(api_key=groq_key)
            response = client.chat.completions.create(
                model="groq/compound-mini",
                messages=[
                    {"role": "system", "content": "You are a media verification engine. Respond only in JSON."},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout=20,
            )
            raw_text = response.choices[0].message.content or "{}"
        elif openai_key:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a media verification engine. Respond only in JSON."},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout=20,
            )
            raw_text = response.choices[0].message.content or "{}"
        else:
            logger.warning("threat_restriction: Neither Groq nor OpenAI API key available — returning mismatch=False")
            return False

        # Clean markdown wrappers if present
        raw_text = raw_text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        parsed = json.loads(raw_text)
        is_mismatch = bool(parsed.get("context_mismatch", False))
        reasoning = parsed.get("reasoning", "")
        logger.info(
            "threat_restriction: LLM context mismatch evaluation result: mismatch=%s, reasoning='%s'",
            is_mismatch, reasoning
        )
        return is_mismatch

    except Exception as exc:
        logger.warning("threat_restriction: LLM context mismatch evaluation failed (non-fatal): %s", exc)
        return False
