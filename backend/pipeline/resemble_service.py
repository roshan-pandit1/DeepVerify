"""
pipeline/resemble_service.py — Integration with Resemble AI Detect API
Provides audio attribution to determine which generative AI model created the deepfake.
"""
import logging
import asyncio
from typing import Optional
from pathlib import Path

import httpx
from config import get_settings

logger = logging.getLogger(__name__)

async def run_audio_attribution(job_id: str, audio_path: Optional[str]) -> dict:
    """
    Sends the extracted audio to Resemble AI for Source Tracing.
    Requires RESEMBLE_API_KEY in the environment.
    """
    if not audio_path or not Path(audio_path).exists():
        logger.info("[%s] No audio file for attribution.", job_id)
        return {"source": "Unknown", "confidence": 0.0, "error": "No audio track"}

    settings = get_settings()
    api_key = settings.resemble_api_key

    if not api_key:
        logger.warning("[%s] RESEMBLE_API_KEY not configured, skipping attribution.", job_id)
        return {"source": "Unknown / Organic", "confidence": 0.0, "skipped": True}

    url = "https://detect.api.resemble.ai/v1/detect"
    
    # Required flags as per implementation plan
    data = {
        "audio_source_tracing": "true",
        "intelligence": "true",
    }
    
    logger.info("[%s] Sending audio to Resemble AI for Source Tracing...", job_id)
    
    try:
        with open(audio_path, "rb") as f:
            file_bytes = f.read()
            
        files = {
            "file": (Path(audio_path).name, file_bytes, "audio/wav")
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Token {api_key}"},
                data=data,
                files=files
            )
            
            if response.status_code == 200:
                result = response.json()
                # Parse the response to extract source tracing info
                # The exact structure depends on Resemble's payload. Usually it's in result["source_tracing"] or result["details"]
                source = result.get("source_tracing", {}).get("model", "Unknown")
                confidence = result.get("source_tracing", {}).get("confidence", 0.0)
                
                # If they just return it at the top level
                if source == "Unknown" and "model" in result:
                    source = result.get("model")
                if "fake_probability" in result:
                    confidence = result.get("fake_probability", 0.0)
                    
                if not source or source == "Unknown":
                    # If probability is very low, it's organic
                    if confidence < 0.2:
                        source = "Unknown / Organic"
                        
                logger.info("[%s] Resemble AI returned source: %s", job_id, source)
                return {
                    "source": source,
                    "confidence": confidence,
                    "raw_response": result
                }
            else:
                logger.error("[%s] Resemble AI API error: %s - %s", job_id, response.status_code, response.text)
                return {"source": "Unknown", "confidence": 0.0, "error": f"API Error {response.status_code}"}
                
    except Exception as exc:
        logger.exception("[%s] Error during Resemble AI attribution: %s", job_id, exc)
        return {"source": "Unknown", "confidence": 0.0, "error": str(exc)}
