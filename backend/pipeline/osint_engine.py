"""
pipeline/osint_engine.py — Audio transcription, reverse image OSINT, LLM synthesis.

Stage breakdown:
  A. Groq Whisper (whisper-large-v3) → verbatim transcript with timestamps
  B. SerpApi Google Lens → reverse image search on top scene keyframes
  C. OpenAI (gpt-4o-mini) or Anthropic (claude-3-5-sonnet) → evidence synthesis
     → structured JSON verdict

All stages are independent and can gracefully skip on failure.
"""
import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class AudioResult:
    transcript_segments: list[TranscriptSegment] = field(default_factory=list)
    full_text: str = ""
    language: str = "unknown"
    duration: float = 0.0
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class OsintMatch:
    title: str
    url: str
    source: str
    thumbnail: Optional[str] = None
    date_published: Optional[str] = None


@dataclass
class OsintResult:
    matches: list[OsintMatch] = field(default_factory=list)
    keyframes_searched: int = 0
    patient_zero_match: Optional[OsintMatch] = None
    culprit_intel: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class VerdictResult:
    authenticity_score: int              # 0–100 (100 = fully real)
    verdict_category: str               # Authentic / AI-Generated Deepfake / Out-of-Context Cheapfake / Manipulated Audio
    summary_headline: str
    key_findings: list[str]
    c2pa_status: dict
    timeline_events: list[dict]
    confidence_breakdown: dict
    raw_llm_response: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Stage A: Groq Whisper Transcription
# ---------------------------------------------------------------------------

async def transcribe_audio(job_id: str, audio_path: Optional[str]) -> AudioResult:
    """
    Transcribe audio using Groq Whisper. Returns timestamped segments.
    Skips gracefully if audio_path is None (silent video).
    """
    if not audio_path or not Path(audio_path).exists():
        logger.info("[%s] No audio file — skipping transcription.", job_id)
        return AudioResult(skipped=True, skip_reason="No audio track in video.")

    settings = get_settings()

    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=settings.groq_api_key)
        logger.info("[%s] Sending audio to Groq Whisper...", job_id)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Run in thread executor since Groq SDK is sync
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                file=(Path(audio_path).name, audio_bytes),
                model="whisper-large-v3",
                response_format="verbose_json",
            ),
        )

        segments: list[TranscriptSegment] = []
        raw_segments = getattr(response, "segments", []) or []
        for seg in raw_segments:
            if isinstance(seg, dict):
                segments.append(TranscriptSegment(
                    start=float(seg.get("start", 0)),
                    end=float(seg.get("end", 0)),
                    text=str(seg.get("text", "")).strip(),
                ))
            else:
                segments.append(TranscriptSegment(
                    start=float(getattr(seg, "start", 0)),
                    end=float(getattr(seg, "end", 0)),
                    text=str(getattr(seg, "text", "")).strip(),
                ))

        full_text = getattr(response, "text", "") or " ".join(s.text for s in segments)
        language = getattr(response, "language", "unknown") or "unknown"
        duration = getattr(response, "duration", 0.0) or 0.0

        logger.info("[%s] Transcription complete: %d segments, lang=%s", job_id, len(segments), language)

        return AudioResult(
            transcript_segments=segments,
            full_text=full_text.strip(),
            language=language,
            duration=float(duration),
        )

    except Exception as exc:
        logger.error("[%s] Groq transcription error: %s", job_id, exc)
        return AudioResult(skipped=True, skip_reason=f"Transcription failed: {exc}")


# ---------------------------------------------------------------------------
# Stage B: SerpApi Google Lens Reverse Image Search
# ---------------------------------------------------------------------------

def _image_to_data_uri(image_path: str) -> Optional[str]:
    """Convert a local image to a base64 data URI (not usable by SerpApi — helper only)."""
    try:
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:image/jpeg;base64,{data}"
    except Exception:
        return None


def _get_public_keyframe_url(job_id: str, kf_path: str, api_base_url: str, settings) -> str:
    """
    Returns a publicly accessible HTTPS URL for Google Lens.
    If Supabase is configured, uploads keyframe to Supabase Storage.
    Otherwise falls back to api_base_url/static/...
    """
    if settings.supabase_enabled:
        try:
            from supabase import create_client
            # Normalize Supabase base URL (remove /rest/v1 if present)
            base_url = settings.supabase_url.rstrip("/")
            if base_url.endswith("/rest/v1"):
                base_url = base_url[:-8].rstrip("/")
            supabase = create_client(base_url, settings.supabase_service_key)
            file_name = f"{job_id}/{Path(kf_path).name}"
            with open(kf_path, "rb") as f:
                img_data = f.read()
            supabase.storage.from_("keyframes").upload(file_name, img_data, file_options={"upsert": "true"})
            public_url = supabase.storage.from_("keyframes").get_public_url(file_name)
            logger.info("[%s] Uploaded keyframe to Supabase for public OSINT: %s", job_id, public_url)
            return public_url
        except Exception as exc:
            logger.warning("[%s] Failed to upload keyframe to Supabase: %s", job_id, exc)

    relative = Path(kf_path).relative_to(Path("/tmp"))
    return f"{api_base_url}/static/{relative}"


async def run_reverse_image_search(
    job_id: str,
    keyframe_paths: list[str],
    api_base_url: str,
) -> OsintResult:
    """
    Run Google Lens reverse image search on the top scene keyframes.
    keyframes are served as static files via FastAPI or uploaded to Supabase Storage.
    """
    settings = get_settings()

    if not keyframe_paths:
        return OsintResult(skipped=True, skip_reason="No keyframes available for reverse search.")

    # Use at most 2 keyframes to conserve API credits
    keyframes_to_search = keyframe_paths[:2]
    all_matches: list[OsintMatch] = []

    try:
        from serpapi import GoogleSearch  # type: ignore
    except ImportError:
        return OsintResult(skipped=True, skip_reason="google-search-results package not installed.")

    loop = asyncio.get_event_loop()

    for kf_path in keyframes_to_search:
        # Build a publicly accessible URL for this keyframe
        public_url = _get_public_keyframe_url(job_id, kf_path, api_base_url, settings)

        logger.info("[%s] Reverse image search: %s", job_id, public_url)

        params = {
            "engine": "google_lens",
            "url": public_url,
            "api_key": settings.serpapi_api_key,
            "hl": "en",
            "gl": "us",
        }

        try:
            results = await loop.run_in_executor(
                None,
                lambda p=params: GoogleSearch(p).get_dict(),
            )

            visual_matches = results.get("visual_matches", [])[:5]
            for match in visual_matches:
                title = match.get("title", "Unknown")
                url = match.get("link", match.get("url", ""))
                source = match.get("source", "")
                thumbnail = match.get("thumbnail", None)
                # SerpApi Google Lens doesn't always return dates — check if present
                date_published = match.get("date", None)

                if url:
                    all_matches.append(OsintMatch(
                        title=title,
                        url=url,
                        source=source,
                        thumbnail=thumbnail,
                        date_published=date_published,
                    ))

            # Small delay to be polite to API
            await asyncio.sleep(1)

        except Exception as exc:
            logger.warning("[%s] SerpApi error for keyframe %s: %s", job_id, kf_path, exc)
            continue

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_matches: list[OsintMatch] = []
    for m in all_matches:
        if m.url not in seen_urls:
            seen_urls.add(m.url)
            unique_matches.append(m)

    logger.info("[%s] Reverse search: %d unique matches from %d keyframes",
                job_id, len(unique_matches), len(keyframes_to_search))

    # Temporal Backtracing to find Patient Zero
    import dateparser
    patient_zero_match = None
    earliest_date = None
    
    for m in unique_matches:
        if m.date_published:
            parsed_date = dateparser.parse(m.date_published)
            if parsed_date:
                if earliest_date is None or parsed_date < earliest_date:
                    earliest_date = parsed_date
                    patient_zero_match = m
                    
    # Extract culprit intel from Patient Zero
    culprit_intel = []
    if patient_zero_match:
        logger.info("[%s] Found Patient Zero: %s (Published: %s)", job_id, patient_zero_match.url, patient_zero_match.date_published)
        culprit_intel = await extract_culprit_intel(job_id, patient_zero_match)

    return OsintResult(
        matches=unique_matches,
        keyframes_searched=len(keyframes_to_search),
        patient_zero_match=patient_zero_match,
        culprit_intel=culprit_intel,
    )


async def extract_culprit_intel(job_id: str, match: OsintMatch) -> list[str]:
    """
    Passes the Patient Zero match to the LLM to extract usernames, handles, and channels.
    Uses Groq as primary LLM (fast, free-tier) with a strict timeout.
    """
    settings = get_settings()
    prompt = f"""Analyze the following earliest known upload ("Patient Zero") of a deepfake video.
Extract potential usernames, channel names, or social media handles associated with this source.
Do not invent anything. If none can be clearly extracted from the URL, title, or source string, return an empty JSON array.

Title: {match.title}
Source: {match.source}
URL: {match.url}

Respond ONLY with a JSON array of strings. No other text. Example: ["@FakeNewsChannel"]"""

    loop = asyncio.get_event_loop()
    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="groq/compound",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=20,
            ),
        )
        raw = response.choices[0].message.content or "[]"

        # Clean up possible markdown fences
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]

        parsed = json.loads(raw.strip())
        if isinstance(parsed, list):
            return [str(p) for p in parsed]
        return []

    except Exception as exc:
        logger.warning("[%s] Failed to extract culprit intel: %s", job_id, exc)
        return []


# ---------------------------------------------------------------------------
# Stage C: LLM Evidence Synthesis
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM_PROMPT = """You are a professional digital media forensics analyst.
Your task is to analyze evidence from a multi-modal deepfake detection system and produce
a structured, accurate forensic verdict.

Respond with ONLY a valid JSON object. No markdown, no code blocks, no explanation outside the JSON.

The JSON must have exactly these fields:
{
  "authenticity_score": <integer 0-100, where 100 = certainly real, 0 = certainly AI/fake>,
  "verdict_category": <one of: "Authentic", "AI-Generated Deepfake", "Out-of-Context Cheapfake", "Manipulated Audio", "Inconclusive">,
  "summary_headline": <single punchy sentence max 20 words>,
  "key_findings": [<3-4 forensic proof strings>],
  "confidence_breakdown": {
    "c2pa_weight": <0-100>,
    "facial_artifacts_weight": <0-100>,
    "audio_consistency_weight": <0-100>,
    "osint_context_weight": <0-100>
  }
}

Be precise, evidence-based, and avoid speculation beyond what the data supports.
"""

def _build_synthesis_prompt(
    c2pa_status: dict,
    facial_score: float,
    suspicious_frame_count: int,
    audio_result: dict,
    osint_matches: list[dict],
    video_duration: float,
) -> str:
    osint_summary = "\n".join(
        f"  - [{m.get('source', 'Unknown')}] \"{m.get('title', '')}\" → {m.get('url', '')}"
        + (f" (published: {m['date_published']})" if m.get("date_published") else "")
        for m in osint_matches[:5]
    ) or "  - No reverse image matches found."

    transcript_preview = audio_result.get("full_text", "")[:800] or "(No audio / silent video)"

    return f"""FORENSIC EVIDENCE REPORT
========================

VIDEO DURATION: {video_duration:.1f} seconds

C2PA CRYPTOGRAPHIC SIGNATURE:
  Status: {c2pa_status.get("status", "no_manifest")}
  AI Generated: {c2pa_status.get("is_ai_generated", False)}
  Generator: {c2pa_status.get("generator", "N/A")}
  Digital Source Type: {c2pa_status.get("digital_source_type", "N/A")}
  Message: {c2pa_status.get("message", "No manifest found")}

FACIAL ARTIFACT ANALYSIS:
  Global Manipulation Confidence: {facial_score:.1f}%
  Frames With Suspicious Artifacts (>60% threshold): {suspicious_frame_count}
  Note: Score based on {"fine-tuned deepfake classifier" if facial_score > 0 else "frequency-domain heuristic"}

AUDIO TRANSCRIPTION:
  Language: {audio_result.get("language", "N/A")}
  Duration: {audio_result.get("duration", 0):.1f}s
  Skipped: {audio_result.get("skipped", False)}
  Transcript (first 800 chars): {transcript_preview}

OSINT REVERSE IMAGE SEARCH:
  Keyframes Searched: {osint_matches[0].get("keyframes_searched", 0) if osint_matches else 0}
  Web Matches Found:
{osint_summary}

Based on all evidence above, produce your forensic verdict JSON.
"""


async def synthesize_verdict(
    job_id: str,
    c2pa_result: dict,
    vision_result: dict,
    audio_result: dict,
    osint_result: dict,
    video_duration: float,
) -> VerdictResult:
    """
    Send all pipeline evidence to Groq for a structured verdict.
    Primary: groq/compound  |  Fallback: openai/gpt-oss-20b via Groq
    Strict 30s timeout prevents silent hangs on quota errors.
    """
    settings = get_settings()

    osint_matches = [
        {
            "title": m.get("title", ""),
            "url": m.get("url", ""),
            "source": m.get("source", ""),
            "date_published": m.get("date_published"),
            "keyframes_searched": osint_result.get("keyframes_searched", 0),
        }
        for m in osint_result.get("matches", [])
    ]

    prompt = _build_synthesis_prompt(
        c2pa_status=c2pa_result,
        facial_score=vision_result.get("facial_artifact_score", 0.0),
        suspicious_frame_count=len(vision_result.get("suspicious_frames", [])),
        audio_result=audio_result,
        osint_matches=osint_matches,
        video_duration=video_duration,
    )

    loop = asyncio.get_event_loop()
    raw_response = ""

    # Try models in order until one succeeds
    _GROQ_MODELS = ["groq/compound", "openai/gpt-oss-20b"]

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        last_exc = None

        for model in _GROQ_MODELS:
            try:
                logger.info("[%s] LLM synthesis using model: %s", job_id, model)
                response = await loop.run_in_executor(
                    None,
                    lambda m=model: client.chat.completions.create(
                        model=m,
                        messages=[
                            {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.1,
                        timeout=30,
                    ),
                )
                raw_response = response.choices[0].message.content or ""

                # Strip markdown fences if present
                raw_response = raw_response.strip()
                if raw_response.startswith("```json"):
                    raw_response = raw_response[7:]
                if raw_response.startswith("```"):
                    raw_response = raw_response[3:]
                if raw_response.endswith("```"):
                    raw_response = raw_response[:-3]
                raw_response = raw_response.strip()

                logger.info("[%s] LLM synthesis complete via %s (%d chars)", job_id, model, len(raw_response))
                break  # success
            except Exception as exc:
                logger.warning("[%s] Model %s failed: %s — trying next", job_id, model, exc)
                last_exc = exc
                continue
        else:
            raise last_exc or RuntimeError("All LLM models failed")

        parsed = json.loads(raw_response)
        return VerdictResult(
            authenticity_score=int(parsed.get("authenticity_score", 50)),
            verdict_category=parsed.get("verdict_category", "Inconclusive"),
            summary_headline=parsed.get("summary_headline", "Analysis inconclusive."),
            key_findings=parsed.get("key_findings", []),
            confidence_breakdown=parsed.get("confidence_breakdown", {}),
            c2pa_status=c2pa_result,
            timeline_events=[],   # Populated by orchestrator
            raw_llm_response=raw_response,
        )

    except json.JSONDecodeError as exc:
        logger.error("[%s] LLM JSON parse error: %s\nRaw: %s", job_id, exc, raw_response[:500])
        return VerdictResult(
            authenticity_score=50,
            verdict_category="Inconclusive",
            summary_headline="LLM synthesis produced invalid JSON — manual review required.",
            key_findings=["LLM response could not be parsed."],
            confidence_breakdown={},
            c2pa_status=c2pa_result,
            timeline_events=[],
            raw_llm_response=raw_response,
            error=f"JSON parse error: {exc}",
        )
    except Exception as exc:
        logger.error("[%s] LLM synthesis error: %s", job_id, exc)
        return VerdictResult(
            authenticity_score=50,
            verdict_category="Inconclusive",
            summary_headline="LLM synthesis failed — see system logs.",
            key_findings=[f"Error during synthesis: {exc}"],
            confidence_breakdown={},
            c2pa_status=c2pa_result,
            timeline_events=[],
            error=str(exc),
        )
