"""
routes/claims.py — FastAPI route handlers for claim submission, entity extraction, verdict reports, and audit logs.
"""
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db, Claim, Assertion, EvidenceItem, VerificationResult, AuditLogEntry, ClaimInputType, ClaimStatus, AsyncSessionLocal
from schemas.claims import (
    ClaimSubmissionRequest,
    ClaimResponse,
    ClaimDetailResponse,
    VerificationResultResponse,
    AuditLogEntryResponse,
    AssertionResponse,
    EvidenceItemResponse,
)
from pipeline.ai_detection_pipeline.claim_extractor import process_claim_extraction
from pipeline.credibility_pipeline.credibility_engine import fetch_evidence_for_assertion
from pipeline.ai_detection_pipeline.stance_evaluator import evaluate_and_aggregate_verdict

logger = logging.getLogger("deepverify.routes.claims")
router = APIRouter(prefix="/claims", tags=["Narrative Verification Claims"])


async def run_full_verification_pipeline(claim_id: str):
    """Background task to run the complete end-to-end extraction and verification pipeline."""
    async with AsyncSessionLocal() as session:
        claim = await session.get(Claim, claim_id)
        if not claim:
            logger.error("[%s] Claim not found during background verification execution", claim_id)
            return

        try:
            # 1. Extract assertions & entities
            assertions = await process_claim_extraction(session, claim)

            # 2. Gather evidence for assertions
            all_evidence = []
            for assertion in assertions:
                items = await fetch_evidence_for_assertion(session, assertion)
                all_evidence.extend(items)

            # 3. Evaluate stance & aggregate final verdict
            await evaluate_and_aggregate_verdict(session, claim, assertions, all_evidence)
            logger.info("[%s] Full verification pipeline completed successfully", claim_id)
        except Exception as exc:
            logger.exception("[%s] Verification pipeline failed: %s", claim_id, exc)
            await session.rollback()
            failed_claim = await session.get(Claim, claim_id)
            if failed_claim:
                failed_claim.status = ClaimStatus.FAILED
                await session.commit()


@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED, summary="Submit a claim for verification")
async def submit_claim(
    payload: ClaimSubmissionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    input_type_val = payload.input_type.lower()
    if input_type_val not in ("text", "url", "media"):
        raise HTTPException(
            status_code=400,
            detail="Invalid input_type. Allowed values are 'text', 'url', or 'media'.",
        )

    claim = Claim(
        raw_input=payload.raw_input,
        input_type=ClaimInputType(input_type_val),
        status=ClaimStatus.SUBMITTED,
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)

    # Queue background verification pipeline
    background_tasks.add_task(run_full_verification_pipeline, claim.id)
    logger.info("[%s] Claim submitted and verification queued", claim.id)

    return claim


@router.get("", response_model=List[ClaimResponse], summary="List submitted claims")
async def list_claims(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Claim).order_by(Claim.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{claim_id}", response_model=ClaimDetailResponse, summary="Get claim details and assertions")
async def get_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Claim).options(selectinload(Claim.assertions)).where(Claim.id == claim_id)
    result = await db.execute(stmt)
    claim = result.scalar_one_or_none()

    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")

    assertion_responses = []
    for a in claim.assertions:
        try:
            parsed_entities = json.loads(a.entity_names_json or "[]")
        except (json.JSONDecodeError, TypeError):
            parsed_entities = []

        assertion_responses.append(
            AssertionResponse(
                id=a.id,
                assertion_text=a.assertion_text,
                entities=parsed_entities,
                confidence_weight=a.confidence_weight,
            )
        )

    return ClaimDetailResponse(
        id=claim.id,
        raw_input=claim.raw_input,
        input_type=claim.input_type.value,
        normalized_text=claim.normalized_text,
        status=claim.status.value,
        created_at=claim.created_at,
        assertions=assertion_responses,
    )



@router.get("/{claim_id}/verdict", response_model=VerificationResultResponse, summary="Get verification verdict and evidence report")
async def get_claim_verdict(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(VerificationResult).where(VerificationResult.claim_id == claim_id)
    res = await db.execute(stmt)
    verdict_record = res.scalar_one_or_none()

    if not verdict_record:
        # Check claim status
        claim = await db.get(Claim, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")
        if claim.status == ClaimStatus.FAILED:
            raise HTTPException(status_code=422, detail="Verification processing failed for this claim.")
        raise HTTPException(status_code=202, detail="Verification in progress. Please poll status.")

    # Fetch evidence items
    assertions_stmt = select(Assertion).where(Assertion.claim_id == claim_id)
    assertions_res = await db.execute(assertions_stmt)
    assertions = assertions_res.scalars().all()

    evidence_responses = []
    for assertion in assertions:
        ev_stmt = select(EvidenceItem).where(EvidenceItem.assertion_id == assertion.id)
        ev_res = await db.execute(ev_stmt)
        for ev in ev_res.scalars().all():
            evidence_responses.append(
                EvidenceItemResponse(
                    id=ev.id,
                    source_name=ev.source_name,
                    source_url=ev.source_url,
                    content_snippet=ev.content_snippet,
                    stance=ev.stance.value,
                    credibility_score=ev.credibility_score,
                )
            )

    return VerificationResultResponse(
        id=verdict_record.id,
        claim_id=verdict_record.claim_id,
        verdict=verdict_record.verdict.value,
        confidence_score=verdict_record.confidence_score,
        summary_explanation=verdict_record.summary_explanation,
        evidence_items=evidence_responses,
        completed_at=verdict_record.completed_at,
    )


@router.get("/{claim_id}/audit-trail", response_model=List[AuditLogEntryResponse], summary="Get chronological audit log for claim verification")
async def get_claim_audit_trail(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLogEntry).where(AuditLogEntry.claim_id == claim_id).order_by(AuditLogEntry.timestamp.asc())
    res = await db.execute(stmt)
    entries = res.scalars().all()

    return [
        AuditLogEntryResponse(
            id=entry.id,
            claim_id=entry.claim_id,
            stage_name=entry.stage_name,
            input_summary=entry.input_summary,
            output_summary=entry.output_summary,
            execution_time_ms=entry.execution_time_ms,
            timestamp=entry.timestamp,
        )
        for entry in entries
    ]
