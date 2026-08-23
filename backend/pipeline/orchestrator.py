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

from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal, Job, JobStatus
from pipeline import c2pa_inspector, video_processor, vision_model, osint_engine, resemble_service
from pipeline.telegram_notifier import send_verdict_notification
from pipeline.blockchain_service import BlockchainService

logger = logging.getLogger(__name__)


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
        source_type = job.source_type
        source_url = job.source_url
        video_path = job.video_path  # Pre-set if file was already saved
        telegram_chat_id = job.telegram_chat_id

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
            if telegram_chat_id:
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
        if telegram_chat_id:
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
            osint_res = await osint_engine.run_reverse_image_search(
                job_id=job_id,
                keyframe_paths=proc_result.keyframe_paths,
                api_base_url=settings.api_base_url,
            )
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

    # ── Fire all 4 stages concurrently ────────────────────────────────
    c2pa_data, (audio_data, resemble_data), vision_data, osint_data = await asyncio.gather(
        _run_c2pa(),
        _run_audio(),
        _run_vision(),
        _run_osint(),
    )

    logger.info("[%s] Parallel stages complete — moving to LLM synthesis", job_id)

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

    except asyncio.TimeoutError:
        logger.error("[%s] LLM synthesis timed out after 45s — producing fallback verdict", job_id)
        verdict_data = {
            "authenticity_score": 50,
            "verdict_category": "Inconclusive",
            "summary_headline": "Analysis complete — LLM synthesis timed out.",
            "key_findings": ["LLM synthesis exceeded 45s deadline. All other forensic data is available."],
            "confidence_breakdown": {},
            "c2pa_status": c2pa_data,
            "timeline_events": _build_timeline_events(vision_data, audio_data, settings.api_base_url, job_id),
        }
    except Exception as exc:
        logger.error("[%s] LLM synthesis error: %s", job_id, exc)
        verdict_data = {
            "authenticity_score": 50,
            "verdict_category": "Inconclusive",
            "summary_headline": "Analysis partially complete — LLM synthesis failed.",
            "key_findings": [str(exc)],
            "confidence_breakdown": {},
            "c2pa_status": c2pa_data,
            "timeline_events": [],
        }

    # ------------------------------------------------------------------ #
    # Assemble final result
    # ------------------------------------------------------------------ #
    final_result = {
        "job_id": job_id,
        "verdict": verdict_data,
        "audio": audio_data,
        "vision": vision_data,
        "osint": osint_data,
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
