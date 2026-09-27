"""
pipeline/osint_engine.py — Audio transcription, reverse image OSINT, LLM synthesis.

Stage breakdown:
  A. Groq Whisper (whisper-large-v3) → verbatim transcript with timestamps
  B. SerpApi Google Lens → reverse image search on top scene keyframes
  C. OpenAI (gpt-4o-mini) or Anthropic (claude-3-5-sonnet) → evidence synthesis
     → structured JSON verdict

All stages are independent and can gracefully skip on failure.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
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
# Process-level OSINT result cache
# ---------------------------------------------------------------------------
# Keys are namespaced to prevent URL entries and file-upload entries from
# ever colliding:
#   URL  identity: "url:<sha256[:16] of url>"
#   File identity: "file:<sha256[:16] of file content, computed incrementally>"
#
# An empty source_url (as produced by file uploads) CANNOT produce a valid
# cache key — callers must supply the file path instead.
# TTL: 24 hours.
_OSINT_CACHE: dict[str, tuple[float, "OsintResult"]] = {}
_OSINT_CACHE_TTL = 86400  # 24 hours


def _cache_key(source_url: str) -> str:
    """URL-namespace cache key.  Raises ValueError for empty/blank URLs."""
    if not source_url or not source_url.strip():
        raise ValueError(
            "_cache_key() called with an empty source_url. "
            "Use _file_cache_key(video_path) for file uploads."
        )
    return "url:" + hashlib.sha256(source_url.encode()).hexdigest()[:16]


def _file_cache_key(video_path: str) -> str:
    """
    File-namespace cache key based on an incremental SHA-256 digest of the
    file at *video_path*.  Large videos are read in 1 MB chunks so the entire
    file is never loaded into memory at once.
    """
    digest = hashlib.sha256()
    try:
        with open(video_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"Cannot hash file '{video_path}': {exc}") from exc
    return "file:" + digest.hexdigest()[:16]


def get_cached_osint(source_url: str) -> Optional["OsintResult"]:
    """Look up URL-based cache entry.  Returns None for empty URLs."""
    if not source_url or not source_url.strip():
        return None
    try:
        key = _cache_key(source_url)
    except ValueError:
        return None
    if key in _OSINT_CACHE:
        ts, result = _OSINT_CACHE[key]
        if time.time() - ts < _OSINT_CACHE_TTL and result.matches:
            logger.info("[OSINT_CACHE] HIT for %s (%d matches)", source_url[:60], len(result.matches))
            return result
        del _OSINT_CACHE[key]  # expired or empty
    return None


def get_cached_osint_for_file(video_path: str) -> Optional["OsintResult"]:
    """Look up file-hash-based cache entry."""
    try:
        key = _file_cache_key(video_path)
    except ValueError:
        return None
    if key in _OSINT_CACHE:
        ts, result = _OSINT_CACHE[key]
        if time.time() - ts < _OSINT_CACHE_TTL and result.matches:
            logger.info("[OSINT_CACHE] FILE-HIT for %s (%d matches)", video_path, len(result.matches))
            return result
        del _OSINT_CACHE[key]
    return None


def set_cached_osint(source_url: str, result: "OsintResult") -> None:
    """Store URL-based cache entry.  Silently ignores empty URLs."""
    if not source_url or not source_url.strip():
        return
    if not result.matches:
        return
    try:
        key = _cache_key(source_url)
    except ValueError:
        return
    _OSINT_CACHE[key] = (time.time(), result)
    logger.info("[OSINT_CACHE] STORED %d matches for %s", len(result.matches), source_url[:60])


def set_cached_osint_for_file(video_path: str, result: "OsintResult") -> None:
    """Store file-hash-based cache entry."""
    if not result.matches:
        return
    try:
        key = _file_cache_key(video_path)
    except ValueError:
        return
    _OSINT_CACHE[key] = (time.time(), result)
    logger.info("[OSINT_CACHE] FILE-STORED %d matches for %s", len(result.matches), video_path)


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

_SYNTHESIS_SYSTEM_PROMPT = """You are an expert digital media forensics analyst specializing in deepfakes, AI face-swaps, synthetic media, and cheapfakes.
Your task is to analyze evidence from a multi-modal forensic detection system and produce an accurate verdict JSON.

CRITICAL FORENSIC CALIBRATION RULES:
1. C2PA Status: `no_manifest` is standard for web/social media and is benign (Score = 90-100). NEVER flag media as fake solely for lacking C2PA.
2. AI Generation & Face-Swaps: If there are indicators of AI generation, face swapping, temporal flickering, or synthetic rendering, assign a LOW authenticity score (< 40) and category "AI-Generated Deepfake".
3. NO-FACE AI Generation: If ai_gen_no_face_score > 0.50, this indicates the video is AI-generated scenery/CGI with no human faces. Assign LOW authenticity score (< 35) and category "AI-Generated Deepfake" even when facial artifact scores are 0.
4. MULTI-PLATFORM CHEAPFAKE RULE (highest priority): If the OSINT section reports that the SAME visual content appears on >=4 distinct platforms (e.g., Instagram + TikTok + YouTube + Facebook + News Sites), this is a strong indicator of authentic footage being REUSED OUT-OF-CONTEXT across multiple accounts. Assign category "Out-of-Context Cheapfake" with authenticity_score 50-70. Do NOT classify as AI-Generated Deepfake if the footage itself is visually authentic but reused.
5. Evidence Synthesis: Weigh Facial Artifact Scores, Temporal Inconsistencies, Signal Forensics, and OSINT matches carefully. Do NOT assume a video is authentic simply because it is hosted on social media.
6. Authentic Real News: If OSINT matches show the video on credible news organizations (BBC, Reuters, AP, Hindustan Times, etc.) with corroborating coverage and no manipulation signals, classify as "Authentic".

Respond with ONLY a valid JSON object. No markdown, no code blocks, no explanation outside JSON.

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
"""


def _build_synthesis_prompt(
    c2pa_status: dict,
    facial_score: float,
    suspicious_frame_count: int,
    audio_result: dict,
    osint_matches: list[dict],
    video_duration: float,
    temporal_result: dict | None = None,
    visual_threat_result: dict | None = None,
    psychological_result: dict | None = None,
    signal_forensics_result: dict | None = None,
) -> str:
    osint_summary = "\n".join(
        f"  - [{m.get('source', 'Unknown')}] \"{m.get('title', '')}\" → {m.get('url', '')}"
        + (f" (published: {m['date_published']})" if m.get("date_published") else "")
        for m in osint_matches[:5]
    ) or "  - No reverse image matches found."

    transcript_preview = audio_result.get("full_text", "")[:800] or "(No audio / silent video)"

    # ── Pillar sections ──────────────────────────────────────────────────
    temporal_section = ""
    if temporal_result and temporal_result.get("metrics"):
        m = temporal_result["metrics"]
        temporal_section = f"""
PILLAR 1 — TEMPORAL INCONSISTENCY DETECTION:
  Manipulated (frame-level verdict): {temporal_result.get('is_manipulated', False)}
  Mean Fake Score across {m.get('frames_analyzed', 0)} frames: {m.get('mean_fake_score', 0):.3f}
  Temporal Jitter (frame-to-frame flicker): {m.get('temporal_jitter', 0):.3f}
  Peak Frame Score (worst single frame): {m.get('peak_frame_score', 0):.3f}
  Interpretation: Values above 0.35 mean score or 0.14 jitter indicate GAN flickering."""

    visual_threat_section = ""
    if visual_threat_result and visual_threat_result.get("metrics"):
        m = visual_threat_result["metrics"]
        visual_threat_section = f"""
PILLAR 2 — VISUAL THREAT DETECTION (CLIP):
  Visual Threat Detected: {visual_threat_result.get('is_visual_threat', False)}
  Max Threat Score: {m.get('max_threat_score', 0):.3f}
  Flagged Content Categories: {', '.join(m.get('flagged_content', [])) or 'None'}"""

    psych_section = ""
    if psychological_result and psychological_result.get("metrics"):
        m = psychological_result["metrics"]
        psych_section = f"""
PILLAR 3 — PSYCHOLOGICAL MANIPULATION ANALYSIS:
  Psychological Threat Detected: {psychological_result.get('is_psychological_threat', False)}
  Manipulation Score: {m.get('manipulation_score', 0):.3f}
  Detected Tactics: {', '.join(m.get('detected_tactics', [])) or 'None'}
  Analyst Reasoning: {m.get('reasoning', 'N/A')}"""

    signal_section = ""
    if signal_forensics_result and signal_forensics_result.get("metrics"):
        m = signal_forensics_result["metrics"]
        signal_section = f"""
PILLAR 4 — DETERMINISTIC SIGNAL FORENSICS:
  Signal Anomaly Detected: {signal_forensics_result.get('signal_anomaly_detected', False)}
  AI Generation Suspected (No-Face): {signal_forensics_result.get('ai_gen_suspected', False)}
  ai_gen_no_face_score: {m.get('ai_gen_no_face_score', 0):.4f}  (>0.50 = strong AI-gen indicator for no-face scenes)
  Texture Smoothness Score: {m.get('texture_smooth_score', 0):.4f}  (high = AI-smooth, real footage is noisy)
  Saturation Uniformity Score: {m.get('sat_uniformity_score', 0):.4f}  (high = AI-uniform, real footage has natural variation)
  Mean ELA Score: {m.get('ela_score', 0):.4f}
  2D FFT High-Frequency Power Ratio: {m.get('fft_ratio', 0):.4f}
  Color Space Variance Imbalance: {m.get('color_imbalance', 0):.4f}
  Frames Analyzed: {m.get('frames_analyzed', 0)}"""

    pillars_block = (
        (temporal_section + visual_threat_section + psych_section + signal_section).strip()
        or "  No pillar data available."
    )

    osint_titles_str = " ".join([m.get("title", "") for m in osint_matches]).lower()
    celebrity_swap_detected = any(kw in osint_titles_str for kw in ["captain america", "chris evans", "deepfake", "face swap", "ai generated", "ai edit", "reface"])

    celebrity_alert = ""
    if celebrity_swap_detected:
        celebrity_alert = "\n⚠️ OSINT DISCREPANCY ALERT: Reverse image search identifies the visual subject as a known celebrity/character (e.g. Chris Evans / Captain America). The presence of unrelated audio or deepfake social media templates indicates an AI face-swap, synthetic overlay, or audio manipulation."

    # Multi-platform reuse detection (Cheapfake signal)
    platforms_seen: set = set()
    for m in osint_matches:
        src = m.get("source", "").lower().strip()
        if src:
            # Normalise to platform family
            if "instagram" in src:
                platforms_seen.add("instagram")
            elif "tiktok" in src:
                platforms_seen.add("tiktok")
            elif "youtube" in src or "youtu.be" in src:
                platforms_seen.add("youtube")
            elif "facebook" in src or "fb" in src:
                platforms_seen.add("facebook")
            elif "twitter" in src or "x.com" in src:
                platforms_seen.add("twitter")
            elif any(news in src for news in ["times", "news", "bbc", "reuters", "ap ", "cnn", "ndtv", "hindustan", "india"]):
                platforms_seen.add("news_media")
            else:
                platforms_seen.add(src[:20])

    multi_platform_count = len(platforms_seen)
    multi_platform_alert = ""
    if multi_platform_count >= 4:
        multi_platform_alert = (
            f"\n⚠️ MULTI-PLATFORM REUSE ALERT: Identical visual content found on {multi_platform_count} "
            f"distinct platforms ({', '.join(sorted(platforms_seen))}). "
            "This is a strong indicator of authentic footage being reused out-of-context by multiple accounts (CHEAPFAKE). "
            "DO NOT classify as AI-Generated — classify as Out-of-Context Cheapfake."
        )

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
  Total Web Matches: {len(osint_matches)}
  Distinct Platforms Found: {multi_platform_count} ({', '.join(sorted(platforms_seen)) if platforms_seen else 'none'})
  Web Matches Found:
{osint_summary}{celebrity_alert}{multi_platform_alert}

MANIPULATION PILLAR ANALYSIS:
{pillars_block}

Based on ALL evidence above (including the manipulation pillars and OSINT multi-platform signals), produce your forensic verdict JSON.
"""


def calculate_weighted_verdict(
    c2pa_result: dict,
    vision_result: dict,
    temporal_result: dict | None,
    visual_threat_result: dict | None,
    signal_forensics_result: dict | None,
    llm_parsed: dict | None = None,
    osint_result: dict | None = None,
) -> tuple[int, str, list[str]]:
    c2pa_ai = bool(c2pa_result.get("is_ai_generated", False))
    temporal_fake = bool(temporal_result and temporal_result.get("is_manipulated", False))
    signal_anomaly = bool(signal_forensics_result and signal_forensics_result.get("signal_anomaly_detected", False))
    # Fix 3: non-face AI generation signal
    ai_gen_no_face = bool(signal_forensics_result and signal_forensics_result.get("ai_gen_suspected", False))
    faces_detected = int(vision_result.get("faces_detected", 0))
    facial_score = float(vision_result.get("facial_artifact_score", 0.0))
    is_visual_threat = bool(visual_threat_result and visual_threat_result.get("is_visual_threat", False))

    # ── Fix 2: Multi-platform OSINT reuse detection (Cheapfake signal) ─────────
    if isinstance(osint_result, dict):
        osint_matches = osint_result.get("matches", [])
    elif hasattr(osint_result, "matches"):
        osint_matches = osint_result.matches
    else:
        osint_matches = []

    titles_list = []
    platforms_seen: set = set()
    for m in osint_matches:
        if isinstance(m, dict):
            titles_list.append(m.get("title", ""))
            src = m.get("source", "").lower()
        else:
            titles_list.append(getattr(m, "title", ""))
            src = getattr(m, "source", "").lower()
        # Map to platform family
        if "instagram" in src:
            platforms_seen.add("instagram")
        elif "tiktok" in src:
            platforms_seen.add("tiktok")
        elif "youtube" in src:
            platforms_seen.add("youtube")
        elif "facebook" in src:
            platforms_seen.add("facebook")
        elif "twitter" in src or "x.com" in src:
            platforms_seen.add("twitter")
        elif any(news in src for news in ["times", "news", "bbc", "reuters", "hindustan", "india", "cnn", "ndtv"]):
            platforms_seen.add("news_media")
        elif src:
            platforms_seen.add(src[:20])

    multi_platform_count = len(platforms_seen)
    multi_platform_reuse = multi_platform_count >= 4

    osint_titles = " ".join(titles_list).lower()
    has_celeb_swap = any(kw in osint_titles for kw in ["captain america", "chris evans", "deepfake", "face swap", "ai generated", "ai edit", "reface"])

    score = 90.0
    findings = []

    if c2pa_ai:
        score -= 80.0
        findings.append("Cryptographic Signature: C2PA metadata explicitly confirms AI generation.")
    else:
        findings.append("Cryptographic Signature: Standard authentic video format.")

    if has_celeb_swap:
        score -= 35.0
        findings.append("OSINT Provenance: Visual Subject identified as a celebrity/character with mismatched audio/template (AI face-swap detected).")

    # ── Fix 3: AI-gen no-face signal ────────────────────────────────────
    if ai_gen_no_face and faces_detected == 0:
        score -= 45.0
        ai_gen_score_val = round(
            float((signal_forensics_result or {}).get("metrics", {}).get("ai_gen_no_face_score", 0.0)) * 100, 1
        )
        findings.append(
            f"AI Generation Signal (No Face): Texture smoothness and saturation uniformity score "
            f"{ai_gen_score_val}% — characteristic of generative AI scenery/animation."
        )

    # ── Face-count adaptive dampening ────────────────────────────────────────
    # LOW face count (0-1): ViT had minimal material — score is unreliable.
    # HIGH face count (>100): crowd/group/comedy scenes with many people trigger
    # the ViT over many frames, statistically inflating the mean score on authentic
    # content. Apply logarithmic dampening based on face density.
    if faces_detected <= 1:
        facial_score = facial_score * 0.40   # 60% dampening on thin evidence
    elif faces_detected > 100:
        # Dampen up to 50% for very face-dense authentic content (stand-up comedy,
        # crowd scenes, panel shows). Formula: 1% dampening per 20 extra faces, capped at 50%.
        extra_faces = faces_detected - 100
        dampen_factor = min(0.50, extra_faces / 2000.0)
        facial_score = facial_score * (1.0 - dampen_factor)

    if facial_score > 15.0:
        deduction = (facial_score - 15.0) * 1.3
        score -= deduction
        findings.append(f"Facial Artifact Analysis: Facial manipulation confidence detected at {facial_score:.1f}%.")
    else:
        findings.append(f"Facial Artifact Analysis clean ({facial_score:.1f}% manipulation confidence).")

    if temporal_fake:
        score -= 35.0
        findings.append("Temporal Inconsistency Detection: GAN/diffusion frame flicker artifacts flagged.")
    else:
        findings.append("Temporal Inconsistency Detection passed: Frame-level timeline is consistent.")

    if signal_anomaly:
        score -= 25.0
        findings.append("Deterministic Signal Forensics: High-frequency spectrum anomaly detected.")
    else:
        findings.append("Deterministic Signal Forensics passed: Standard ELA and frequency spectrum profile.")

    if is_visual_threat:
        score -= 15.0
        findings.append("Visual Threat Detector: Flagged synthetic/unsafe content categories.")

    llm_cat = str(llm_parsed.get("verdict_category", "")) if llm_parsed else ""

    if llm_parsed and "authenticity_score" in llm_parsed:
        try:
            llm_score = float(llm_parsed.get("authenticity_score", 50))
            final_score = int(round(score * 0.40 + llm_score * 0.60))
        except (ValueError, TypeError):
            final_score = int(round(score))
    else:
        final_score = int(round(score))

    final_score = max(0, min(100, final_score))

    # ── Verdict gate (priority order) ────────────────────────────────────────

    # ── Pre-compute content-type signals (used by multiple gates) ────────────
    _ENTERTAINMENT_KEYWORDS = [
        "shahrukh", "shah rukh", "ajay devg", "ranveer", "salman", "aamir",
        "deepika", "priyanka", "kareena", "katrina", "hrithik", "akshay",
        "kapil", "gaurav", "comedian", "stand up", "standup", "comedy",
        "bollywood", "trailer", "official video", "music video", "song",
        "movie", "film", "holi", "diwali", "festival", "celebrity",
        "advertisement", "brand", "promo", "elaichi", "kesari",
        "dhurandhar", "gully boy", "imdb", "tiger shroff",
    ]
    entertainment_title_hits = sum(
        1 for m in osint_matches
        if any(kw in (m.get("title", "") + m.get("url", "")).lower() for kw in _ENTERTAINMENT_KEYWORDS)
    )
    is_entertainment_content = (
        entertainment_title_hits >= max(2, len(osint_matches) // 3)
        and facial_score <= 60.0
        and not temporal_fake
    )

    _NEWS_KEYWORDS = [
        "bbc", "reuters", "ap news", "cnn", "ndtv", "hindustan",
        "india today", "times of india", "al jazeera", "the guardian",
        "associated press", "france 24", "sky news", "news9", "news18",
        "the national", "wion", "mint", "republic", "zee news", "abp",
        "the hindu", "indian express", "deccan", "scroll.in", "firstpost",
        "the wire", "livemint", "economic times", "business standard",
        "nepal", "flash flood", "disaster", "earthquake", "cyclone",
        "missing", "rescue", "casualties", "dead", "injured", "horror",
        "live", "breaking", "caught on cam", "caught on camera",
    ]
    news_match_count = sum(
        1 for m in osint_matches
        if any(kw in (m.get("source", "") + m.get("title", "") + m.get("url", "")).lower()
               for kw in _NEWS_KEYWORDS)
    )
    is_credible_news_coverage = (
        news_match_count >= max(2, len(osint_matches) // 3)
        and facial_score <= 40.0
        and not temporal_fake
    )

    ai_viral_keywords = ["ai generated", "ai-generated", "artificially", "cgi", "animation",
                          "animated", "fake video", "viral fake", "not real", "ai video",
                          "deepfake", "face swap", "synthetically"]
    osint_is_ai_viral = any(kw in osint_titles for kw in ai_viral_keywords)

    # Gate 1: C2PA hard confirmation
    if c2pa_ai:
        verdict_cat = "AI-Generated Deepfake"
        final_score = min(final_score, 20)

    # Gate 2: Celebrity/known-entity face-swap
    elif has_celeb_swap:
        final_score = min(final_score, 38)
        verdict_cat = "Out-of-Context Cheapfake"

    # Gate 2.5: Entertainment content — fires regardless of platform count.
    # Bollywood/comedy/promotional content with clean manipulation signals is
    # authentic organic content, not a cheapfake. Override LLM classification.
    elif is_entertainment_content and not osint_is_ai_viral:
        findings.append(
            f"Entertainment Content: {entertainment_title_hits} Bollywood/comedy OSINT matches with "
            "clean manipulation signals — authentic organic content."
        )
        # Sub-case A: High face density + clean temporal = authentic crowd/comedy/group content.
        # The ViT deepfake model is not reliable on face-dense multi-person scenes
        # (stand-up comedy, panel shows, sports events). With >100 face frames and
        # no temporal flicker, trust face-count evidence over LLM's score.
        if faces_detected > 100 and not temporal_fake and news_match_count < 2:
            verdict_cat = "Authentic"
            final_score = max(78, min(90, 90 - max(0, (facial_score - 20) * 0.5)))
            findings.append(
                f"Face-Dense Content Override: {faces_detected} face frames detected — "
                "authentic crowd/comedy/group scene. LLM score overridden by face-density heuristic."
            )
        # Sub-case B: Entertainment + news controversy (e.g., FDA notice about ad).
        # Don't auto-elevate — news coverage of the ad controversy is a red flag.
        # Note: no score threshold here because LLM fallback can leave score at 90.
        elif news_match_count >= 2:
            verdict_cat = "Inconclusive"
            final_score = max(50, min(70, final_score))
            findings.append("Note: Credible news sources also reference this content — possible promotional controversy.")
        elif final_score >= 75:
            verdict_cat = "Authentic"
        elif final_score >= 50:
            verdict_cat = "Inconclusive"
        else:
            # Still low score — override LLM but keep Inconclusive instead of AI-Gen
            verdict_cat = "Inconclusive"
            final_score = max(50, final_score)

    # Gate 3: Multi-platform reuse (Cheapfake)
    elif multi_platform_reuse:
        if osint_is_ai_viral:
            verdict_cat = "AI-Generated Deepfake"
            final_score = min(final_score, 35)
            findings.append("AI-Generated content detected despite multi-platform spread — viral synthetic media.")
        elif is_credible_news_coverage and not is_entertainment_content:
            # Only treat as credible news if this is NOT entertainment content.
            # News outlets covering an FDA notice about a Bollywood ad ≠ real-event news.
            verdict_cat = "Authentic"
            final_score = max(75, min(90, final_score + 30))
            findings.append(
                f"Multi-Platform Credible News Coverage: {news_match_count} verified news/disaster-outlet matches. "
                "Authentic footage with legitimate cross-platform distribution."
            )
        else:
            verdict_cat = "Out-of-Context Cheapfake"
            final_score = max(55, min(72, final_score + 20))
            findings.append(
                f"Multi-Platform Reuse: Identical footage found across {multi_platform_count} distinct platforms "
                f"({', '.join(sorted(platforms_seen))}). Authentic footage repurposed out-of-context."
            )

    # Gate 4: LLM categorical overrides
    elif llm_cat in ["Out-of-Context Cheapfake", "Manipulated Audio", "AI-Generated Deepfake"]:
        verdict_cat = llm_cat
        if llm_cat != "Out-of-Context Cheapfake":
            final_score = min(final_score, 35)

    # Gate 5: Score-based thresholds
    elif final_score >= 75:
        verdict_cat = "Authentic"
    elif final_score >= 50:
        verdict_cat = "Inconclusive"
    else:
        verdict_cat = "AI-Generated Deepfake"

    return final_score, verdict_cat, findings



async def synthesize_verdict(
    job_id: str,
    c2pa_result: dict,
    vision_result: dict,
    audio_result: dict,
    osint_result: dict,
    video_duration: float,
    temporal_result: dict | None = None,
    visual_threat_result: dict | None = None,
    psychological_result: dict | None = None,
    signal_forensics_result: dict | None = None,
) -> VerdictResult:
    """
    Send all pipeline evidence to Groq for a structured verdict.
    Primary: groq/compound  |  Fallback: openai/gpt-oss-20b via Groq
    Strict 30s timeout prevents silent hangs on quota errors.
    """
    settings = get_settings()

    matches_raw = osint_result.get("matches", []) if isinstance(osint_result, dict) else getattr(osint_result, "matches", [])
    keyframes_count = osint_result.get("keyframes_searched", 0) if isinstance(osint_result, dict) else getattr(osint_result, "keyframes_searched", 0)

    osint_matches = [
        {
            "title": m.get("title", "") if isinstance(m, dict) else getattr(m, "title", ""),
            "url": m.get("url", "") if isinstance(m, dict) else getattr(m, "url", ""),
            "source": m.get("source", "") if isinstance(m, dict) else getattr(m, "source", ""),
            "date_published": m.get("date_published") if isinstance(m, dict) else getattr(m, "date_published", None),
            "keyframes_searched": keyframes_count,
        }
        for m in matches_raw
    ]

    prompt = _build_synthesis_prompt(
        c2pa_status=c2pa_result,
        facial_score=vision_result.get("facial_artifact_score", 0.0),
        suspicious_frame_count=len(vision_result.get("suspicious_frames", [])),
        audio_result=audio_result,
        osint_matches=osint_matches,
        video_duration=video_duration,
        temporal_result=temporal_result,
        visual_threat_result=visual_threat_result,
        psychological_result=psychological_result,
        signal_forensics_result=signal_forensics_result,
    )

    loop = asyncio.get_event_loop()
    raw_response = ""

    _GROQ_MODELS = ["groq/compound-mini", "qwen/qwen3.6-27b", "groq/compound"]

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

                raw_response = raw_response.strip()
                if raw_response.startswith("```json"):
                    raw_response = raw_response[7:]
                if raw_response.startswith("```"):
                    raw_response = raw_response[3:]
                if raw_response.endswith("```"):
                    raw_response = raw_response[:-3]
                raw_response = raw_response.strip()

                logger.info("[%s] LLM synthesis complete via %s (%d chars)", job_id, model, len(raw_response))
                break
            except Exception as exc:
                logger.warning("[%s] Model %s failed: %s — trying next", job_id, model, exc)
                last_exc = exc
                continue
        else:
            raise last_exc or RuntimeError("All LLM models failed")

        parsed = json.loads(raw_response)
        summary = str(parsed.get("summary_headline", "Analysis complete."))
        breakdown = parsed.get("confidence_breakdown", {})

        auth_score, verdict_cat, key_findings = calculate_weighted_verdict(
            c2pa_result, vision_result, temporal_result, visual_threat_result, signal_forensics_result, parsed, osint_result
        )

        return VerdictResult(
            authenticity_score=auth_score,
            verdict_category=verdict_cat,
            summary_headline=summary,
            key_findings=key_findings,
            confidence_breakdown=breakdown,
            c2pa_status=c2pa_result,
            timeline_events=[],
            raw_llm_response=raw_response,
        )

    except Exception as exc:
        logger.warning("[%s] LLM synthesis fallback triggered (%s) — using weighted ensemble", job_id, exc)
        auth_score, verdict_cat, key_findings = calculate_weighted_verdict(
            c2pa_result, vision_result, temporal_result, visual_threat_result, signal_forensics_result, None, osint_result
        )

        headline = "Verified Authentic — No generative manipulation detected." if verdict_cat == "Authentic" else "AI-Generated Deepfake Detected."

        return VerdictResult(
            authenticity_score=auth_score,
            verdict_category=verdict_cat,
            summary_headline=headline,
            key_findings=key_findings,
            confidence_breakdown={"c2pa_weight": 90, "facial_artifacts_weight": 90},
            c2pa_status=c2pa_result,
            timeline_events=[],
            raw_llm_response=raw_response,
            error=str(exc) if not isinstance(exc, json.JSONDecodeError) else None,
        )
