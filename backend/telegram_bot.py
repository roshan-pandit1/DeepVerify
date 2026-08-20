"""
telegram_bot.py — Telegram bot polling and message handling.
"""
import asyncio
import logging
import uuid
from pathlib import Path

import httpx

from config import get_settings
from database import AsyncSessionLocal, Job, JobStatus
from pipeline.orchestrator import run_pipeline

logger = logging.getLogger(__name__)


async def handle_update(update: dict):
    try:
        settings = get_settings()
        message = update.get("message")
        if not message:
            return

        chat_id = str(message.get("chat", {}).get("id"))
        if not chat_id:
            return

        async def reply(text: str):
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": text}
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(url, json=payload)
            except Exception as e:
                logger.error("Failed to send reply: %s", e)

        text = message.get("text") or message.get("caption") or ""
        video = message.get("video") or message.get("document")

        if text.startswith("/start"):
            await reply("👋 Welcome to DeepVerify! Send me a video file or a social media URL, and I will analyze it for deepfakes.")
            return

        job_id = str(uuid.uuid4())
        job_dir = Path(f"/tmp/uploads/{job_id}")
        job_dir.mkdir(parents=True, exist_ok=True)

        source_type = None
        source_url = None
        video_path = None
        original_filename = None

        if video:
            # Document objects have file_name, video objects have file_name sometimes.
            mime_type = video.get("mime_type", "")
            if "video" not in mime_type and not (video.get("file_name", "").endswith(('.mp4', '.mov', '.webm', '.mkv'))):
                await reply("❌ Please upload a valid video file format (MP4, MOV, WebM).")
                return

            file_size = video.get("file_size", 0)
            if file_size > 20 * 1024 * 1024:
                await reply("❌ Video is too large! The Telegram Bot API limits downloads to 20MB. Please use the web interface for larger files.")
                return

            file_id = video.get("file_id")
            original_filename = video.get("file_name", "telegram_upload.mp4")
            video_path = str(job_dir / "video.mp4")
            source_type = "file"

            await reply("⏳ Downloading video from Telegram...")
            async with httpx.AsyncClient() as client:
                file_resp = await client.get(f"https://api.telegram.org/bot{settings.telegram_bot_token}/getFile?file_id={file_id}")
                file_data = file_resp.json()
                if not file_data.get("ok"):
                    await reply("❌ Failed to get video from Telegram.")
                    return
                telegram_file_path = file_data["result"]["file_path"]

                download_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{telegram_file_path}"
                async with client.stream("GET", download_url) as response:
                    with open(video_path, "wb") as f_out:
                        async for chunk in response.aiter_bytes():
                            f_out.write(chunk)
        elif text and (text.startswith("http://") or text.startswith("https://")):
            source_type = "url"
            source_url = text
        else:
            await reply("Please send a valid video file or a URL.")
            return

        async with AsyncSessionLocal() as session:
            job = Job(
                id=job_id,
                status=JobStatus.PENDING,
                source_type=source_type,
                source_url=source_url,
                original_filename=original_filename,
                video_path=video_path,
                telegram_chat_id=chat_id,
            )
            session.add(job)
            await session.commit()

        await reply(f"✅ Analysis started! Job ID: `{job_id[:8]}`\nI will notify you here when the report is ready.")
        asyncio.create_task(run_pipeline(job_id))
    except Exception as e:
        logger.error("Exception in handle_update: %s", e)
        try:
            chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
            if chat_id:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        f"https://api.telegram.org/bot{get_settings().telegram_bot_token}/sendMessage",
                        json={"chat_id": chat_id, "text": "❌ An internal error occurred while processing your message."}
                    )
        except Exception:
            pass


async def poll_telegram():
    settings = get_settings()
    if not settings.telegram_enabled:
        logger.info("Telegram polling disabled (keys missing).")
        return

    logger.info("Starting Telegram Bot long-polling...")
    offset = 0
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"

    async with httpx.AsyncClient(timeout=40.0) as client:
        while True:
            try:
                resp = await client.get(url, params={"offset": offset, "timeout": 30})
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            # Handle update asynchronously so polling continues
                            asyncio.create_task(handle_update(update))
                    else:
                        logger.error("Telegram getUpdates error: %s", data)
                        await asyncio.sleep(5)
                else:
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                logger.info("Telegram polling task cancelled.")
                break
            except Exception as e:
                logger.error("Telegram polling exception: %s", e)
                await asyncio.sleep(5)
