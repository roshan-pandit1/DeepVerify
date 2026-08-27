"""
main.py — FastAPI application entry point.

Endpoints:
  POST /api/analyze          — Accept file upload or URL, start pipeline
  GET  /api/status/{job_id}  — Poll job status + current pipeline stage
  GET  /api/report/{job_id}  — Retrieve full forensic report JSON
  GET  /static/{path}        — Serve Grad-CAM heatmaps, frames, video files
"""
import json
import logging
import os
import shutil
import uuid
import asyncio

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=env_path)
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import select
from config import get_settings
from database import Job, JobStatus, AsyncSessionLocal, init_db
from pipeline.orchestrator import run_pipeline
from telegram_bot import poll_telegram

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
telegram_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_task
    logger.info("Starting up Video Authenticity Engine...")

    # Validate config (will SystemExit if keys missing)
    settings = get_settings()

    # Ensure temp upload directory exists
    Path("/tmp/uploads").mkdir(parents=True, exist_ok=True)

    # Initialize database
    await init_db()
    logger.info("Database initialized.")
    logger.info("API ready. LLM provider: %s", settings.llm_provider)
    logger.info("Frontend CORS origin: %s", settings.frontend_url)

    telegram_task = asyncio.create_task(poll_telegram())

    yield

    logger.info("Shutting down.")
    if telegram_task:
        telegram_task.cancel()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Video Authenticity & Cheapfake Verification Engine",
    description="Multi-modal deepfake detection API",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve /tmp/uploads as static files at /static/uploads/<job_id>/...
app.mount("/static", StaticFiles(directory="/tmp"), name="static")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/analyze", summary="Submit video file or URL for analysis")
async def analyze(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(default=None),
    source_url: Optional[str] = Form(default=None),
    user_claim: Optional[str] = Form(default=None),
    virality_speed: Optional[str] = Form(default=None),
):
    """
    Accept either:
      - A video file upload (multipart/form-data, field: file)
      - A social media URL (multipart/form-data, field: source_url)
    Optional fields:
      - user_claim: Caption or claim text accompanying the video
      - virality_speed: Share velocity metric (0-100+)

    Returns: { "job_id": "<uuid>" }
    """
    if not file and not source_url:
        raise HTTPException(
            status_code=422,
            detail="Provide either a video file (field: 'file') or a URL (field: 'source_url').",
        )

    job_id = str(uuid.uuid4())
    job_dir = Path(f"/tmp/uploads/{job_id}")
    job_dir.mkdir(parents=True, exist_ok=True)

    source_type = "url" if source_url else "file"
    video_path = None
    original_filename = None

    # If file upload: save to disk immediately
    if file:
        # Validate size
        max_bytes = settings.max_video_size_mb * 1024 * 1024
        content = await file.read()
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.max_video_size_mb}MB",
            )
        original_filename = file.filename or "upload.mp4"
        video_path = str(job_dir / "video.mp4")
        with open(video_path, "wb") as f_out:
            f_out.write(content)
        logger.info("[%s] File uploaded: %s (%.1f MB)", job_id, original_filename,
                    len(content) / 1024 / 1024)

    # Persist job to DB
    async with AsyncSessionLocal() as session:
        job = Job(
            id=job_id,
            status=JobStatus.PENDING,
            source_type=source_type,
            source_url=source_url,
            original_filename=original_filename,
            video_path=video_path,
            user_claim=user_claim,
            virality_speed=virality_speed,
        )
        session.add(job)
        await session.commit()

    # Enqueue background pipeline
    background_tasks.add_task(run_pipeline, job_id)
    logger.info("[%s] Job created, pipeline enqueued. source_type=%s", job_id, source_type)

    return {"job_id": job_id}


@app.get("/api/status/{job_id}", summary="Poll pipeline progress")
async def get_status(job_id: str):
    """
    Returns current job status and stage.
    Status values: pending | ingesting | c2pa | audio | vision | osint | synthesis | complete | failed
    """
    async with AsyncSessionLocal() as session:
        job: Optional[Job] = await session.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    STAGE_LABELS = {
        JobStatus.PENDING: {"label": "Queued", "step": 0},
        JobStatus.INGESTING: {"label": "Ingesting Video", "step": 1},
        JobStatus.C2PA: {"label": "C2PA Signature Check", "step": 2},
        JobStatus.AUDIO: {"label": "Audio Transcription", "step": 3},
        JobStatus.VISION: {"label": "Facial Artifact Analysis", "step": 4},
        JobStatus.OSINT: {"label": "OSINT Reverse Search", "step": 5},
        JobStatus.SYNTHESIS: {"label": "LLM Evidence Synthesis", "step": 6},
        JobStatus.COMPLETE: {"label": "Complete", "step": 7},
        JobStatus.FAILED: {"label": "Failed", "step": -1},
    }

    job_status = JobStatus(str(job.status.value if hasattr(job.status, "value") else job.status))
    stage_info = STAGE_LABELS.get(job_status, {"label": "Unknown", "step": 0})
    created_at = getattr(job, "created_at", None)
    updated_at = getattr(job, "updated_at", None)

    err_msg = getattr(job, "error_message", None)

    return {
        "job_id": job_id,
        "status": job_status.value,
        "stage_label": stage_info["label"],
        "stage_step": stage_info["step"],
        "total_steps": 6,
        "error_message": str(err_msg) if err_msg is not None else None,
        "created_at": created_at.isoformat() if created_at is not None else None,
        "updated_at": updated_at.isoformat() if updated_at is not None else None,
    }


@app.get("/api/report/{job_id}", summary="Retrieve full forensic report")
async def get_report(job_id: str):
    """
    Returns the complete forensic analysis report as JSON.
    Only available once status == 'complete'.
    """
    async with AsyncSessionLocal() as session:
        job: Optional[Job] = await session.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    job_status = JobStatus(str(job.status.value if hasattr(job.status, "value") else job.status))

    if job_status == JobStatus.FAILED:
        err_msg = getattr(job, "error_message", None)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Analysis failed",
                "message": str(err_msg) if err_msg is not None else "Unknown error",
            },
        )

    if job_status != JobStatus.COMPLETE:
        raise HTTPException(
            status_code=202,
            detail={
                "status": job_status.value,
                "message": "Analysis in progress. Poll /api/status/{job_id} for updates.",
            },
        )

    result_json_str = str(job.result_json or "")
    try:
        result = json.loads(result_json_str)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Report data corrupted: {exc}",
        )

    return JSONResponse(content=result)


@app.get("/api/jobs", summary="Retrieve a list of recent jobs")
async def get_jobs(limit: int = 20):
    """
    Returns the most recent jobs processed by the engine.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Job).order_by(Job.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        jobs = result.scalars().all()

    job_list = []
    for j in jobs:
        j_status = JobStatus(str(j.status.value if hasattr(j.status, "value") else j.status))
        j_created = getattr(j, "created_at", None)
        j_orig_name = getattr(j, "original_filename", None)
        job_list.append({
            "job_id": str(j.id),
            "status": j_status.value,
            "source_type": str(j.source_type),
            "original_filename": str(j_orig_name) if j_orig_name is not None else None,
            "created_at": j_created.isoformat() if j_created is not None else None,
        })
    return job_list


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Video Authenticity Engine"}
