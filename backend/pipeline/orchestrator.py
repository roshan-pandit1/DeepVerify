"""
pipeline/orchestrator.py — Runs all 6 pipeline stages in sequence.

Updates the Job DB record after each stage so the frontend can poll progress.
Handles per-stage exceptions gracefully — a failed stage produces a partial
result but does not abort the whole job (exception logged, stage marked skipped).

Called from FastAPI BackgroundTasks: asyncio-compatible throughout.
"""
import asyncio
import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=env_path)

import cv2
from PIL import Image

from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal, Job, JobStatus
from pipeline import c2pa_inspector, video_processor, vision_model, osint_engine, resemble_service, temporal_analysis, visual_threat_analysis, psychological_analysis, signal_forensics, osint_vision, threat_restriction
from pipeline.telegram_notifier import send_verdict_notification
from pipeline.blockchain_service import BlockchainService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single-Pass Frame Extractor
# ---------------------------------------------------------------------------

def extract_shared_frames(
    video_path: str,
    count: int = 15,
) -> list[Image.Image]:
    """
    Open the video file ONCE and extract `count` evenly-spaced frames in a
    single forward sequential read (fastest possible I/O path).

    Frames are returned at their NATIVE resolution as PIL RGB images.
    Do NOT resize here — the HF ImageProcessor handles aspect-ratio-aware
    centre-cropping internally, preserving subtle GAN artifacts that a
    hard cv2.resize to 224×224 would destroy.

    Returns an empty list if the file cannot be read.
    """
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames <= 0:
        cap.release()
        return []

    step = max(1, total_frames // count)
    frames: list[Image.Image] = []
    current_idx = 0

    while cap.isOpened() and len(frames) < count:
        ret, frame = cap.read()
        if not ret:
            break
        if current_idx % step == 0:
            # DO NOT resize — pass native resolution to preserve artifacts.
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(rgb))
        current_idx += 1

    cap.release()
    return frames


async def _update_job(job_id: str, **kwargs):
    """Update specific columns on the Job row."""
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            logger.error("Job %s not found in DB during update", job_id)
            return
        for k, v in kwargs.items():
            setattr(job, k, v)
        await session.commit()


async def run_pipeline(job_id: str):
    """
    Master orchestrator. Runs all 6 stages, updates DB status between each.
    Final result_json stored as serialized dict on the Job row.
    """
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("[%s] Pipeline starting", job_id)
    logger.info("=" * 60)

    # ------------------------------------------------------------------ #
    # Stage 0: Load job from DB
    # ------------------------------------------------------------------ #
    async with AsyncSessionLocal() as session:
        job: Optional[Job] = await session.get(Job, job_id)
        if not job:
            logger.error("[%s] Job not found — aborting pipeline.", job_id)
            return
        source_type = str(job.source_type)
        source_url = str(job.source_url or "")
        video_path = str(job.video_path or "")  # Pre-set if file was already saved
        telegram_chat_id = str(job.telegram_chat_id) if job.telegram_chat_id is not None else None
        user_claim = str(getattr(job, "user_claim", "") or "")
        virality_speed_raw = getattr(job, "virality_speed", None)
        try:
            virality_speed = float(virality_speed_raw) if virality_speed_raw is not None else 0.0
        except (ValueError, TypeError):
            virality_speed = 0.0

    # ------------------------------------------------------------------ #
    # Stage 1: Ingestion
    # ------------------------------------------------------------------ #
    await _update_job(job_id, status=JobStatus.INGESTING)
    logger.info("[%s] Stage 1: Ingestion", job_id)

    try:
        if source_type == "url":
            proc_result = await video_processor.download_from_url(job_id, source_url)
        else:
            proc_result = await video_processor.process_uploaded_file(job_id, video_path)

        if proc_result.error:
            if proc_result.error_code == "PRIVATE_OR_RESTRICTED_MEDIA":
                error_msg = json.dumps({
                    "error_code": "PRIVATE_OR_RESTRICTED_MEDIA",
                    "message": "This video is from a private account or requires authentication.",
                    "actionable_hint": "Our servers cannot bypass private account walls. Please screen-record or download the video directly to your device and use the file uploader."
                })
            else:
                error_msg = f"Ingestion failed: {proc_result.error}"

            await _update_job(
                job_id,
                status=JobStatus.FAILED,
                error_message=error_msg,
            )
            logger.error("[%s] Ingestion failed: %s", job_id, proc_result.error)
            # Send failure notification to telegram if applicable
            if telegram_chat_id is not None:
                from pipeline.telegram_notifier import httpx
                settings = get_settings()
                url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
                
                # Format a clean message instead of dumping JSON
                display_msg = proc_result.error
                cookie_hint = ""
                if proc_result.error_code == "PRIVATE_OR_RESTRICTED_MEDIA":
                    display_msg = "This video is from a private account or requires authentication."
                    cookie_hint = "\n\n(Optional) If you want your backend to access login-gated videos, export your session cookies using a browser extension (like Get cookies.txt LOCALLY) and save the file as backend/cookies.txt"
                
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(url, json={
                            "chat_id": telegram_chat_id,
                            "text": f"❌ Analysis Failed\n\n{display_msg}{cookie_hint}"
                        })
                except Exception:
                    pass
            return

        await _update_job(
            job_id,
            video_path=proc_result.video_path,
            audio_path=proc_result.audio_path,
        )

    except Exception as exc:
        error_msg = f"Ingestion exception: {exc}"
        await _update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message=error_msg,
        )
        logger.exception("[%s] Ingestion exception", job_id)
        if telegram_chat_id is not None:
            from pipeline.telegram_notifier import httpx
            settings = get_settings()
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(url, json={
                        "chat_id": telegram_chat_id,
                        "text": f"❌ Analysis Failed\n\n{error_msg}"
                    })
            except Exception:
                pass
        return

    # ------------------------------------------------------------------ #
    # Stages 2–5: Run C2PA, Audio, Vision, OSINT in PARALLEL
    # ------------------------------------------------------------------ #
    await _update_job(job_id, status=JobStatus.C2PA)
    logger.info("[%s] Stages 2-5: Running C2PA / Audio / Vision / OSINT in parallel", job_id)

    gradcam_dir = f"/tmp/uploads/{job_id}/gradcam"
    has_weights = bool(os.getenv("MODEL_WEIGHTS_PATH", "").strip())
    loop = asyncio.get_event_loop()

    # ── Single-pass frame extraction (runs once; shared across pillars) ──
    logger.info("[%s] Extracting shared frames (single-pass) …", job_id)
    shared_frames: list[Image.Image] = await loop.run_in_executor(
        None,
        lambda: extract_shared_frames(proc_result.video_path, count=15),
    )
    # Pillar 2 (CLIP threat) only needs ~5 frames — thin the set to save compute
    threat_frames = shared_frames[::3] if len(shared_frames) >= 5 else shared_frames
    logger.info(
        "[%s] Shared frames ready: %d total, %d for threat detection",
        job_id, len(shared_frames), len(threat_frames),
    )

    # ── helpers that each return their data dict ───────────────────────

    async def _run_c2pa() -> dict:
        try:
            c2pa_res = c2pa_inspector.inspect(proc_result.video_path)
            data = dataclasses.asdict(c2pa_res)
            data.pop("raw_manifest", None)
            return data
        except Exception as exc:
            logger.warning("[%s] C2PA error (non-fatal): %s", job_id, exc)
            return {"status": "error", "message": str(exc), "is_ai_generated": False}

    async def _run_audio() -> tuple[dict, dict]:
        audio: dict = {}
        resemble: dict = {}
        try:
            audio_res = await osint_engine.transcribe_audio(job_id, proc_result.audio_path)
            audio = {
                "full_text": audio_res.full_text,
                "language": audio_res.language,
                "duration": audio_res.duration,
                "skipped": audio_res.skipped,
                "skip_reason": audio_res.skip_reason,
                "segments": [
                    {"start": s.start, "end": s.end, "text": s.text}
                    for s in audio_res.transcript_segments
                ],
            }
        except Exception as exc:
            logger.warning("[%s] Audio error (non-fatal): %s", job_id, exc)
            audio = {"skipped": True, "skip_reason": str(exc), "segments": []}

        try:
            resemble = await resemble_service.run_audio_attribution(job_id, proc_result.audio_path)
        except Exception as exc:
            logger.warning("[%s] Resemble AI error: %s", job_id, exc)
            resemble = {"source": "Unknown", "confidence": 0.0, "error": str(exc)}

        return audio, resemble

    async def _run_vision() -> dict:
        try:
            vision_res = await loop.run_in_executor(
                None,
                lambda: vision_model.run_vision_pipeline(
                    job_id=job_id,
                    frame_paths=proc_result.frame_paths,
                    gradcam_dir=gradcam_dir,
                    has_fine_tuned_weights=has_weights,
                ),
            )
            return {
                "facial_artifact_score": vision_res.facial_artifact_score,
                "faces_detected": vision_res.faces_detected,
                "frames_analyzed": vision_res.frames_analyzed,
                "skipped_reason": vision_res.skipped_reason,
                "error": vision_res.error,
                "frame_scores": [
                    {
                        "frame_path": fs.frame_path,
                        "timestamp": fs.timestamp,
                        "face_detected": fs.face_detected,
                        "manipulation_score": fs.manipulation_score,
                        "gradcam_path": fs.gradcam_path,
                    }
                    for fs in vision_res.frame_scores
                ],
                "suspicious_frames": [
                    {
                        "frame_path": fs.frame_path,
                        "timestamp": fs.timestamp,
                        "manipulation_score": fs.manipulation_score,
                        "gradcam_path": fs.gradcam_path,
                    }
                    for fs in vision_res.suspicious_frames
                ],
            }
        except Exception as exc:
            logger.warning("[%s] Vision error (non-fatal): %s", job_id, exc)
            return {
                "facial_artifact_score": 0.0,
                "faces_detected": 0,
                "frames_analyzed": 0,
                "error": str(exc),
                "frame_scores": [],
                "suspicious_frames": [],
            }

    async def _run_osint() -> dict:
        try:
            # ── 1. Check in-memory process cache (fastest) ─────────────────
            cached = osint_engine.get_cached_osint(source_url)
            if cached:
                logger.info("[%s] OSINT: in-memory cache HIT (%d matches)", job_id, len(cached.matches))
                osint_res = cached
            else:
                # ── 2. Check persistent DB cache ────────────────────────────
                from database import OsintCache
                from pipeline.osint_engine import OsintResult, OsintMatch, _cache_key
                url_hash = _cache_key(source_url)
                osint_res = None
                async with AsyncSessionLocal() as sess:
                    db_entry = await sess.get(OsintCache, url_hash)
                    if db_entry:
                        try:
                            raw_matches = json.loads(db_entry.result_json)
                            matches = [
                                OsintMatch(
                                    title=m.get("title", ""),
                                    url=m.get("url", ""),
                                    source=m.get("source", ""),
                                    thumbnail=m.get("thumbnail"),
                                    date_published=m.get("date_published"),
                                )
                                for m in raw_matches
                            ]
                            osint_res = OsintResult(matches=matches, keyframes_searched=2)
                            logger.info("[%s] OSINT: DB cache HIT (%d matches)", job_id, len(matches))
                            osint_engine.set_cached_osint(source_url, osint_res)  # warm in-memory
                        except Exception as parse_exc:
                            logger.warning("[%s] OSINT DB cache parse error: %s", job_id, parse_exc)
                            osint_res = None

                # ── 3. Live SerpAPI fetch ───────────────────────────────────
                if osint_res is None:
                    osint_res = await osint_engine.run_reverse_image_search(
                        job_id=job_id,
                        keyframe_paths=proc_result.keyframe_paths,
                        api_base_url=settings.api_base_url,
                    )
                    # Persist to DB if we got results
                    if osint_res.matches:
                        osint_engine.set_cached_osint(source_url, osint_res)
                        try:
                            matches_json = json.dumps([
                                {"title": m.title, "url": m.url, "source": m.source,
                                 "thumbnail": m.thumbnail, "date_published": m.date_published}
                                for m in osint_res.matches
                            ])
                            from database import OsintCache
                            from pipeline.osint_engine import _cache_key
                            async with AsyncSessionLocal() as sess:
                                entry = OsintCache(
                                    url_hash=_cache_key(source_url),
                                    source_url=source_url[:1000],
                                    result_json=matches_json,
                                )
                                await sess.merge(entry)
                                await sess.commit()
                            logger.info("[%s] OSINT: persisted %d matches to DB cache", job_id, len(osint_res.matches))
                        except Exception as db_exc:
                            logger.warning("[%s] OSINT DB cache write error: %s", job_id, db_exc)

            return {
                "matches": [
                    {
                        "title": m.title,
                        "url": m.url,
                        "source": m.source,
                        "thumbnail": m.thumbnail,
                        "date_published": m.date_published,
                    }
                    for m in osint_res.matches
                ],
                "keyframes_searched": osint_res.keyframes_searched,
                "patient_zero_match": {
                    "title": osint_res.patient_zero_match.title,
                    "url": osint_res.patient_zero_match.url,
                    "source": osint_res.patient_zero_match.source,
                    "date_published": osint_res.patient_zero_match.date_published,
                } if osint_res.patient_zero_match else None,
                "culprit_intel": osint_res.culprit_intel,
                "skipped": osint_res.skipped,
                "skip_reason": osint_res.skip_reason,
            }
        except Exception as exc:
            logger.warning("[%s] OSINT error (non-fatal): %s", job_id, exc)
            return {"matches": [], "keyframes_searched": 0, "patient_zero_match": None, "culprit_intel": [], "skipped": True, "skip_reason": str(exc)}


    async def _run_temporal() -> dict:
        """Pillar 1: Temporal Inconsistency Detection — batched inference on shared_frames."""
        try:
            result = await loop.run_in_executor(
                None,
                lambda: temporal_analysis.analyze_temporal_manipulation(
                    frames=shared_frames,
                    job_id=job_id,
                ),
            )
            return result
        except Exception as exc:
            logger.warning("[%s] Temporal analysis error (non-fatal): %s", job_id, exc)
            return {
                "is_manipulated": False,
                "metrics": {},
                "error": str(exc),
            }

    async def _run_visual_threat() -> dict:
        """Pillar 2: Visual Threat Detection — batched CLIP inference on threat_frames."""
        try:
            result = await loop.run_in_executor(
                None,
                lambda: visual_threat_analysis.analyze_visual_threats(
                    frames=threat_frames,
                    job_id=job_id,
                ),
            )
            return result
        except Exception as exc:
            logger.warning("[%s] Visual threat analysis error (non-fatal): %s", job_id, exc)
            return {
                "is_visual_threat": False,
                "metrics": {},
                "error": str(exc),
            }

    async def _run_signal_forensics() -> dict:
        """Pillar 4: Deterministic Signal Forensics — ELA, 2D FFT, Color Space Variance on shared_frames."""
        try:
            result = await loop.run_in_executor(
                None,
                lambda: signal_forensics.analyze_signal_forensics(
                    frames=shared_frames,
                    job_id=job_id,
                ),
            )
            return result
        except Exception as exc:
            logger.warning("[%s] Signal forensics error (non-fatal): %s", job_id, exc)
            return {
                "signal_anomaly_detected": False,
                "metrics": {},
                "error": str(exc),
            }

    # ── Fire all 7 stages concurrently ────────────────────────────────
    (
        c2pa_data,
        (audio_data, resemble_data),
        vision_data,
        osint_data,
        temporal_data,
        visual_threat_data,
        signal_forensics_data,
    ) = await asyncio.gather(
        _run_c2pa(),
        _run_audio(),
        _run_vision(),
        _run_osint(),
        _run_temporal(),
        _run_visual_threat(),
        _run_signal_forensics(),
    )

    logger.info("[%s] Parallel stages complete — moving to LLM synthesis", job_id)

    # ------------------------------------------------------------------ #
    # Pillar 3: Psychological Threat Analysis (sequential — needs transcript)
    # ------------------------------------------------------------------ #
    logger.info("[%s] Pillar 3: Psychological threat analysis", job_id)
    transcript_text = audio_data.get("full_text", "") or ""
    psych_data: dict = await loop.run_in_executor(
        None,
        lambda: psychological_analysis.analyze_psychological_threat(
            transcript=transcript_text,
            job_id=job_id,
        ),
    )

    # ------------------------------------------------------------------ #
    # Stage 6: LLM Evidence Synthesis
    # ------------------------------------------------------------------ #
    await _update_job(job_id, status=JobStatus.SYNTHESIS)
    logger.info("[%s] Stage 6: LLM synthesis", job_id)

    verdict_data: dict = {}
    try:
        # Hard 45s deadline — if Groq hangs we still complete the job
        verdict_res = await asyncio.wait_for(
            osint_engine.synthesize_verdict(
                job_id=job_id,
                c2pa_result=c2pa_data,
                vision_result=vision_data,
                audio_result=audio_data,
                osint_result=osint_data,
                video_duration=proc_result.duration_seconds,
                temporal_result=temporal_data,
                visual_threat_result=visual_threat_data,
                psychological_result=psych_data,
                signal_forensics_result=signal_forensics_data,
            ),
            timeout=45.0,
        )

        # Build timeline events from frame scores + audio segments
        timeline_events = _build_timeline_events(vision_data, audio_data, settings.api_base_url, job_id)

        verdict_data = {
            "authenticity_score": verdict_res.authenticity_score,
            "verdict_category": verdict_res.verdict_category,
            "summary_headline": verdict_res.summary_headline,
            "key_findings": verdict_res.key_findings,
            "confidence_breakdown": verdict_res.confidence_breakdown,
            "c2pa_status": c2pa_data,
            "timeline_events": timeline_events,
        }

    except (asyncio.TimeoutError, Exception) as exc:
        logger.error("[%s] LLM synthesis error/timeout: %s — producing calibrated fallback verdict", job_id, exc)
        auth_score, verdict_cat, key_findings = osint_engine.calculate_weighted_verdict(
            c2pa_data, vision_data, temporal_data, visual_threat_data, signal_forensics_data, None, osint_data
        )

        headline = "Verified Authentic — No AI manipulation or temporal artifacts detected." if verdict_cat == "Authentic" else "AI-Generated Deepfake Detected."

        verdict_data = {
            "authenticity_score": auth_score,
            "verdict_category": verdict_cat,
            "summary_headline": headline,
            "key_findings": key_findings,
            "confidence_breakdown": {"c2pa_weight": 90, "facial_artifacts_weight": 90},
            "c2pa_status": c2pa_data,
            "timeline_events": _build_timeline_events(vision_data, audio_data, settings.api_base_url, job_id),
        }

    # ------------------------------------------------------------------ #
    # OSINT Vision & Threat Restriction Analysis
    # ------------------------------------------------------------------ #
    logger.info("[%s] OSINT Vision & Threat Restriction pipeline", job_id)
    osint_restriction_data: dict = {}
    try:
        # Extract 3 evenly spaced keyframes
        osint_keyframes = await loop.run_in_executor(
            None,
            lambda: osint_vision.extract_keyframes(proc_result.video_path, num_frames=3)
        )

        best_guess_labels: list[str] = []
        matching_urls: list[str] = []

        for k_path in osint_keyframes:
            vis_res = await loop.run_in_executor(
                None,
                lambda p=k_path: osint_vision.reverse_image_search(p)
            )
            best_guess_labels.extend(vis_res.get("best_guess_labels", []))
            matching_urls.extend(vis_res.get("pages_with_matching_images", []))

        # Deduplicate
        unique_labels = list(dict.fromkeys(best_guess_labels))
        unique_urls = list(dict.fromkeys(matching_urls))

        effective_claim = user_claim or transcript_text or source_url

        panic_index = threat_restriction.calculate_panic_index(effective_claim, virality_speed)

        context_mismatch = False
        if unique_labels and effective_claim:
            context_mismatch = await loop.run_in_executor(
                None,
                lambda: threat_restriction.evaluate_context_mismatch(effective_claim, unique_labels)
            )

        if context_mismatch and panic_index > 80:
            restriction_status = "RESTRICTED - High Impact Misinformation"
        else:
            restriction_status = "CLEARED"

        osint_restriction_data = {
            "restriction_status": restriction_status,
            "panic_index": panic_index,
            "context_mismatch": context_mismatch,
            "best_guess_labels": unique_labels,
            "pages_with_matching_images": unique_urls,
            "keyframes": osint_keyframes,
        }
    except Exception as exc:
        logger.warning("[%s] OSINT Vision & Threat Restriction error (non-fatal): %s", job_id, exc)
        osint_restriction_data = {
            "restriction_status": "CLEARED",
            "panic_index": 1.0,
            "context_mismatch": False,
            "best_guess_labels": [],
            "pages_with_matching_images": [],
            "keyframes": [],
            "error": str(exc),
        }

    # ------------------------------------------------------------------ #
    # Assemble final result
    # ------------------------------------------------------------------ #
    restriction_status_val = osint_restriction_data.get("restriction_status", "CLEARED")

    final_result = {
        "job_id": job_id,
        "restriction_status": restriction_status_val,
        "verdict": verdict_data,
        "audio": audio_data,
        "vision": vision_data,
        "osint": osint_data,
        "osint_vision": {
            "best_guess_labels": osint_restriction_data.get("best_guess_labels", []),
            "pages_with_matching_images": osint_restriction_data.get("pages_with_matching_images", []),
            "keyframes": osint_restriction_data.get("keyframes", []),
        },
        "threat_restriction": {
            "panic_index": osint_restriction_data.get("panic_index", 1.0),
            "context_mismatch": osint_restriction_data.get("context_mismatch", False),
            "restriction_status": restriction_status_val,
        },
        "temporal": temporal_data,
        "visual_threat": visual_threat_data,
        "psychological_threat": psych_data,
        "signal_forensics": signal_forensics_data,
        "attribution": {
            "resemble_source": resemble_data.get("source", "Unknown"),
            "patient_zero_date": osint_data.get("patient_zero_match", {}).get("date_published") if osint_data.get("patient_zero_match") else None,
            "patient_zero_url": osint_data.get("patient_zero_match", {}).get("url") if osint_data.get("patient_zero_match") else None,
            "culprit_handles": osint_data.get("culprit_intel", []),
        },
        "video_meta": {
            "duration_seconds": proc_result.duration_seconds,
            "fps": proc_result.fps,
            "width": proc_result.width,
            "height": proc_result.height,
            "video_path": proc_result.video_path,
            "keyframe_paths": proc_result.keyframe_paths,
        },
    }

    await _update_job(
        job_id,
        status=JobStatus.COMPLETE,
        result_json=json.dumps(final_result),
    )

    logger.info(
        "[%s] Pipeline COMPLETE — verdict: %s (%d%% real)",
        job_id,
        verdict_data.get("verdict_category"),
        verdict_data.get("authenticity_score"),
    )

    # ------------------------------------------------------------------ #
    # Stage 7: Blockchain Attestation (non-blocking, non-fatal)          #
    # ------------------------------------------------------------------ #
    logger.info("[%s] Stage 7: Blockchain attestation", job_id)
    try:
        bc_service = BlockchainService()
        loop = asyncio.get_event_loop()
        bc_result = await loop.run_in_executor(
            None,
            lambda: bc_service.run(
                job_id=job_id,
                video_path=proc_result.video_path,
                report_payload=final_result,
                authenticity_score=int(verdict_data.get("authenticity_score", 50)),
                verdict_category=str(verdict_data.get("verdict_category", "Inconclusive")),
                attributed_source=str(resemble_data.get("source", "Unknown")),
            ),
        )

        # Persist blockchain metadata to DB
        await _update_job(
            job_id,
            sha256_hash=bc_result.get("sha256"),
            perceptual_hash=bc_result.get("phash"),
            ipfs_cid=bc_result.get("ipfs_cid"),
            tx_hash=bc_result.get("tx_hash"),
            on_chain_status=bc_result.get("status", "off_chain"),
        )

        # Inject blockchain data into the stored result JSON so the frontend gets it
        final_result["blockchain"] = bc_result
        await _update_job(job_id, result_json=json.dumps(final_result))

        logger.info(
            "[%s] Blockchain attestation: status=%s  tx=%s",
            job_id,
            bc_result.get("status"),
            bc_result.get("tx_hash") or "n/a",
        )

    except Exception as bc_exc:
        logger.warning("[%s] Blockchain attestation error (non-fatal): %s", job_id, bc_exc)

    # ------------------------------------------------------------------ #
    # Post-completion: Telegram notification (non-blocking, non-fatal)
    # ------------------------------------------------------------------ #
    await send_verdict_notification(
        job_id=job_id,
        verdict_category=verdict_data.get("verdict_category", "Inconclusive"),
        authenticity_score=int(verdict_data.get("authenticity_score", 50)),
        summary_headline=verdict_data.get("summary_headline", ""),
        facial_score=float(vision_data.get("facial_artifact_score", 0.0)),
        c2pa_is_ai=bool(c2pa_data.get("is_ai_generated", False)),
        chat_id=telegram_chat_id,
    )


def _build_timeline_events(
    vision_data: dict,
    audio_data: dict,
    api_base_url: str,
    job_id: str,
) -> list[dict]:
    """
    Merge vision frame scores and audio transcript segments into a unified timeline.
    """
    events: list[dict] = []

    # Vision events (all frames with face detection)
    for fs in vision_data.get("frame_scores", []):
        if not fs.get("face_detected"):
            continue
        score = fs.get("manipulation_score", 0)
        is_suspicious = score > 0.60
        gradcam_path = fs.get("gradcam_path")

        # Build public URL for gradcam image
        gradcam_url = None
        if gradcam_path:
            try:
                rel = Path(gradcam_path).relative_to(Path("/tmp"))
                gradcam_url = f"{api_base_url}/static/{rel}"
            except ValueError:
                gradcam_url = None

        # Build public URL for raw frame
        frame_path = fs.get("frame_path", "")
        frame_url = None
        if frame_path:
            try:
                rel = Path(frame_path).relative_to(Path("/tmp"))
                frame_url = f"{api_base_url}/static/{rel}"
            except ValueError:
                frame_url = None

        events.append({
            "type": "vision",
            "timestamp": fs.get("timestamp", 0),
            "label": f"{'⚠️ Suspicious' if is_suspicious else '✓ Normal'} face detected",
            "score": round(score * 100, 1),
            "is_anomaly": is_suspicious,
            "frame_url": frame_url,
            "gradcam_url": gradcam_url,
        })

    # Audio events (transcript segments)
    for seg in audio_data.get("segments", []):
        events.append({
            "type": "audio",
            "timestamp": seg.get("start", 0),
            "label": seg.get("text", "")[:80],
            "score": None,
            "is_anomaly": False,
            "frame_url": None,
            "gradcam_url": None,
        })

    # Sort by timestamp
    events.sort(key=lambda e: e["timestamp"])
    return events
