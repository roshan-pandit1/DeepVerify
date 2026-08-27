"""
pipeline/psychological_analysis.py — Pillar 3: Psychological Manipulation & Cognitive Threat Analysis.

Disinformation operates on two layers:
  1. Visual — fabricated imagery (Pillars 1 & 2).
  2. Cognitive — manipulative speech engineered to polarize, panic, or incite.

This module analyses the Whisper transcript produced by Stage A (osint_engine)
using a Groq LLM to detect five categories of psychological manipulation:

  1. Us-vs-Them Polarization
  2. Manufactured Panic / Fear-Mongering
  3. Dehumanizing / Scapegoating Language
  4. Conspiracy Framing
  5. Incitement to Unrest / Vigilantism

Design notes:
  • Runs *after* the parallel gather so the Whisper transcript is available.
  • Reuses the project's Groq client pattern (settings.groq_api_key).
  • Non-fatal: any error or missing transcript returns a clean fallback dict.
  • Uses response_format=json_object to guarantee parseable output.
  • The function is synchronous (Groq SDK is sync); callers should run it in
    an executor if they need async non-blocking behaviour.

Output dict (stored in final_result["psychological_threat"]):
    {
        "is_psychological_threat": bool,
        "metrics": {
            "manipulation_score": float,       # 0–1
            "detected_tactics": list[str],
            "reasoning": str,
        },
        "error": str | None,
    }
"""
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_PSYCHOLOGICAL_ANALYSIS_PROMPT = """You are a senior forensic analyst specializing in propaganda, \
cognitive warfare, and societal manipulation.
Analyze the following transcript from a video for psychological manipulation tactics \
designed to brainwash, polarize, or panic the public.

Transcript to evaluate:
\"\"\"{transcript}\"\"\"

Evaluate the text against these 5 manipulation vectors:
1. Us-vs-Them Polarization: Extreme division, demonizing groups.
2. Manufactured Panic / Fear-Mongering: Inducing acute dread or paranoia without evidence.
3. Dehumanizing / Scapegoating Language: Degrading specific communities or individuals.
4. Conspiracy Framing: Promoting unverifiable harmful claims to erode institutional trust.
5. Incitement to Unrest / Vigilantism: Urging illegal, violent, or disruptive mass action.

Respond ONLY with valid JSON in this exact structure:
{{
  "is_psychological_threat": <true/false>,
  "manipulation_score": <float between 0.0 and 1.0>,
  "detected_tactics": [<list of strings of identified tactics>],
  "reasoning": "<concise 2-sentence explanation of the cognitive manipulation risk>"
}}"""

_MIN_TRANSCRIPT_LENGTH = 15   # Characters — anything shorter has no signal


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_psychological_threat(
    transcript: str,
    job_id: str = "",
) -> dict:
    """
    Analyse the transcribed audio for cognitive manipulation, propaganda,
    and brainwashing rhetoric using a Groq LLM.

    Args:
        transcript: Full transcript text from Whisper transcription.
        job_id:     Optional job identifier for log tracing.

    Returns:
        Dict with keys: is_psychological_threat, metrics, error.
    """
    tag = f"[{job_id}]" if job_id else ""

    # ── Guard: no substantive speech ────────────────────────────────────
    if not transcript or len(transcript.strip()) < _MIN_TRANSCRIPT_LENGTH:
        logger.info("%s PsychThreat: transcript too short or empty — skipping.", tag)
        return {
            "is_psychological_threat": False,
            "metrics": {
                "manipulation_score": 0.0,
                "detected_tactics": [],
                "reasoning": "No substantive speech or audio dialogue detected to evaluate.",
            },
            "error": None,
        }

    # ── Guard: Groq API key ──────────────────────────────────────────────
    try:
        from config import get_settings  # type: ignore
        settings = get_settings()
        groq_api_key = settings.groq_api_key
    except Exception:
        groq_api_key = None

    if not groq_api_key:
        logger.warning("%s PsychThreat: GROQ_API_KEY not configured — skipping.", tag)
        return {
            "is_psychological_threat": False,
            "metrics": {
                "manipulation_score": 0.0,
                "detected_tactics": [],
                "reasoning": "GROQ_API_KEY not configured.",
            },
            "error": "GROQ_API_KEY missing",
        }

    # ── LLM call ─────────────────────────────────────────────────────────
    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=groq_api_key)

        logger.info(
            "%s PsychThreat: sending %d-char transcript for manipulation analysis.",
            tag, len(transcript),
        )

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a specialized forensic intelligence engine. "
                        "Respond only with JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": _PSYCHOLOGICAL_ANALYSIS_PROMPT.format(
                        transcript=transcript[:4000]  # Clip to avoid token overflow
                    ),
                },
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            timeout=30,
        )

        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)

        is_threat = bool(result.get("is_psychological_threat", False))
        score = round(float(result.get("manipulation_score", 0.0)), 4)
        tactics = result.get("detected_tactics", [])
        reasoning = result.get("reasoning", "")

        logger.info(
            "%s PsychThreat: threat=%s  score=%.3f  tactics=%s",
            tag, is_threat, score, tactics,
        )

        return {
            "is_psychological_threat": is_threat,
            "metrics": {
                "manipulation_score": score,
                "detected_tactics": tactics if isinstance(tactics, list) else [],
                "reasoning": reasoning,
            },
            "error": None,
        }

    except Exception as exc:
        logger.error("%s PsychThreat: LLM call failed — %s", tag, exc)
        return {
            "is_psychological_threat": False,
            "metrics": {
                "manipulation_score": 0.0,
                "detected_tactics": [],
                "reasoning": f"Analysis failed: {exc}",
            },
            "error": str(exc),
        }
