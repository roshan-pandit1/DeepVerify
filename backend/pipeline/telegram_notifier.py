"""
pipeline/telegram_notifier.py — Send forensic verdict summary to a Telegram chat.

Uses the Telegram Bot HTTP API directly (no extra library needed).
Silently skips if TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not configured.

Message format:
  🔍 DeepVerify Analysis Complete
  ━━━━━━━━━━━━━━━━━━━━━━
  Verdict   : AI-Generated Deepfake 🚨
  Score     : 12% Real
  Headline  : ...
  Report    : http://localhost:3000/report/<id>
"""
import asyncio
import logging
from typing import Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

_VERDICT_EMOJI = {
    "Authentic": "✅",
    "AI-Generated Deepfake": "🚨",
    "Out-of-Context Cheapfake": "⚠️",
    "Manipulated Audio": "🎭",
    "Inconclusive": "❓",
}


async def send_verdict_notification(
    job_id: str,
    verdict_category: str,
    authenticity_score: int,
    summary_headline: str,
    facial_score: float,
    c2pa_is_ai: bool,
    chat_id: Optional[str] = None,
) -> None:
    """
    Fire-and-forget Telegram message. Never raises — logs and returns on any error.
    """
    settings = get_settings()

    if not settings.telegram_enabled:
        logger.debug("Telegram notifications disabled — skipping.")
        return

    emoji = _VERDICT_EMOJI.get(verdict_category, "🔍")
    report_url = f"{settings.frontend_url}/report/{job_id}"

    # Build message text (Markdown V2 escaping for special chars)
    def esc(text: str) -> str:
        """Escape MarkdownV2 special characters."""
        special = r"\_*[]()~`>#+-=|{}.!"
        return "".join(f"\\{c}" if c in special else c for c in str(text))

    score_bar = "█" * (authenticity_score // 10) + "░" * (10 - authenticity_score // 10)

    lines = [
        f"*🔍 DeepVerify Analysis Complete*",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"*Verdict:* {emoji} `{esc(verdict_category)}`",
        f"*Authenticity:* `{score_bar}` {esc(authenticity_score)}% Real",
        f"*Facial artifacts:* `{esc(f'{facial_score:.1f}')}%` suspicious",
        f"*C2PA AI flag:* {'`YES 🚨`' if c2pa_is_ai else '`No ✓`'}",
        f"",
        f"_{esc(summary_headline)}_",
        f"",
        f"*📋 Full Report:*",
        f"[View on DeepVerify]({report_url})",
        f"",
        f"*Job ID:* `{esc(job_id[:8])}\\.\\.\\. `",
    ]

    message = "\n".join(lines)

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id or settings.telegram_chat_id,
        "text": message,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": False,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("[%s] Telegram notification sent successfully.", job_id)
            else:
                # Log the error but never crash the pipeline
                logger.warning(
                    "[%s] Telegram API returned %d: %s",
                    job_id, resp.status_code, resp.text[:200],
                )
    except httpx.TimeoutException:
        logger.warning("[%s] Telegram notification timed out — skipping.", job_id)
    except Exception as exc:
        logger.warning("[%s] Telegram notification failed (non-fatal): %s", job_id, exc)
