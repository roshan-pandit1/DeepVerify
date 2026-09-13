"""
stance_evaluator.py — Evaluates evidence stances and aggregates overall claim verdict.
"""
import time
import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from database import Claim, Assertion, EvidenceItem, VerificationResult, VerdictType, ClaimStatus, EvidenceStance
from pipeline.audit_logger import record_audit_stage

logger = logging.getLogger("deepverify.stance_evaluator")


async def evaluate_and_aggregate_verdict(
    session: AsyncSession,
    claim: Claim,
    assertions: List[Assertion],
    evidence_items: List[EvidenceItem]
) -> VerificationResult:
    """Calculate aggregate confidence score and assign verdict classification."""
    start_time = time.time()
    claim.status = ClaimStatus.VERIFYING
    await session.commit()

    # 1. Stance evaluation stage
    stance_start = time.time()
    supports_weight = sum(item.credibility_score for item in evidence_items if item.stance == EvidenceStance.SUPPORTS)
    refutes_weight = sum(item.credibility_score for item in evidence_items if item.stance == EvidenceStance.REFUTES)
    total_weight = supports_weight + refutes_weight

    await record_audit_stage(
        session=session,
        claim_id=claim.id,
        stage_name="STANCE_EVALUATION",
        input_summary=f"Evaluated {len(evidence_items)} evidence items",
        output_summary=f"Supports weight: {supports_weight:.2f}, Refutes weight: {refutes_weight:.2f}",
        start_time=stance_start,
    )

    # 2. Verdict aggregation stage
    verdict_start = time.time()
    if not evidence_items or total_weight == 0:
        verdict = VerdictType.UNCERTAIN
        confidence_score = 50.0
        summary = "Insufficient or inconclusive evidence was found across available OSINT sources."
    elif refutes_weight > 0 and supports_weight > 0 and abs(supports_weight - refutes_weight) < 0.3:
        verdict = VerdictType.CONTESTED
        confidence_score = 65.0
        summary = "Contradictory evidence of comparable credibility exists across multiple sources."
    elif refutes_weight > supports_weight:
        verdict = VerdictType.UNSUPPORTED
        confidence_score = min(95.0, (refutes_weight / total_weight) * 100.0)
        summary = "Extensive refuting evidence indicates the claim is false or unsupported."
    else:
        verdict = VerdictType.VERIFIED
        confidence_score = min(98.0, (supports_weight / (total_weight or 1.0)) * 100.0)
        summary = "High-credibility supporting evidence corroborates the core factual assertions of this claim."

    result = VerificationResult(
        claim_id=claim.id,
        verdict=verdict,
        confidence_score=round(confidence_score, 1),
        summary_explanation=summary,
    )
    session.add(result)
    
    claim.status = ClaimStatus.COMPLETED
    await session.commit()

    await record_audit_stage(
        session=session,
        claim_id=claim.id,
        stage_name="VERDICT_AGGREGATION",
        input_summary=f"Aggregated verdict classification for claim {claim.id}",
        output_summary=f"Verdict: {verdict.value}, Confidence: {confidence_score:.1f}%",
        start_time=verdict_start,
    )

    return result
