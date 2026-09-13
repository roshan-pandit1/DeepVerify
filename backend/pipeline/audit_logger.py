"""
audit_logger.py — Audit logging helper for recording verification pipeline stages.
"""
import time
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from database import AuditLogEntry

logger = logging.getLogger("deepverify.audit")


async def record_audit_stage(
    session: AsyncSession,
    claim_id: str,
    stage_name: str,
    input_summary: str,
    output_summary: str,
    start_time: float,
) -> AuditLogEntry:
    execution_time_ms = int((time.time() - start_time) * 1000)
    entry = AuditLogEntry(
        claim_id=claim_id,
        stage_name=stage_name,
        input_summary=input_summary[:1000],
        output_summary=output_summary[:1000],
        execution_time_ms=execution_time_ms,
    )
    session.add(entry)
    await session.commit()
    logger.info("[%s] Audit stage recorded: %s (%d ms)", claim_id, stage_name, execution_time_ms)
    return entry
