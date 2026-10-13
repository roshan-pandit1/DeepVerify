"""Bounded legacy file receipt. Callers supply a fresh server-generated job path."""
from contextlib import asynccontextmanager
from pathlib import Path
import shutil

from fastapi import HTTPException

CHUNK_BYTES = 64 * 1024


@asynccontextmanager
async def receive_upload(upload, job_dir: Path, max_bytes: int):
    if max_bytes <= 0:
        raise ValueError('Upload byte limit must be positive')
    job_dir.mkdir(parents=True, exist_ok=False)
    path = job_dir / 'video.mp4'
    try:
        try:
            total = 0
            with path.open('xb') as output:
                while True:
                    # At most one byte beyond the bound is ever read, never the rest.
                    chunk = await upload.read(min(CHUNK_BYTES, max_bytes - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise HTTPException(413, 'Video exceeds the configured upload size limit.')
                    output.write(chunk)
        finally:
            await upload.close()
        # Keep the cleanup scope open through DB persistence and job registration.
        yield str(path), total
    except BaseException:
        # CancelledError is a BaseException: remove partial files on disconnect too.
        shutil.rmtree(job_dir)
        raise
