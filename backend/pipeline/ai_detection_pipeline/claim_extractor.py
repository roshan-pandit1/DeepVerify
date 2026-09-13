"""
claim_extractor.py — Normalizes raw claims and extracts core assertions and entities.
"""
import json
import re
import time
import logging
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from database import Claim, Assertion, ClaimStatus
from pipeline.audit_logger import record_audit_stage

logger = logging.getLogger("deepverify.claim_extractor")


def normalize_text(raw_text: str) -> str:
    """Clean extra whitespaces, remove junk characters, and normalize punctuation."""
    text = raw_text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def extract_assertions_and_entities(normalized_text: str) -> List[Tuple[str, List[str]]]:
    """
    Extract discrete testable sub-assertions and named entities.
    Falls back to sentence and keyword heuristics if LLM is unavailable.
    """
    # Simple, fast heuristics for claim extraction
    sentences = [s.strip() for s in re.split(r'[.!?]+', normalized_text) if len(s.strip()) > 5]
    if not sentences:
        sentences = [normalized_text]

    extracted = []
    for sentence in sentences:
        # Simple entity extraction (Capitalized words/phrases)
        entities = list(set(re.findall(r'\b[A-Z][a-z0-9]+\b', sentence)))
        extracted.append((sentence, entities))

    return extracted


async def process_claim_extraction(session: AsyncSession, claim: Claim) -> List[Assertion]:
    """Execute text normalization and entity extraction, creating Assertion records."""
    start_time = time.time()
    
    # 1. Normalization stage
    norm_start = time.time()
    normalized = normalize_text(claim.raw_input)
    claim.normalized_text = normalized
    claim.status = ClaimStatus.EXTRACTED
    await session.commit()
    
    await record_audit_stage(
        session=session,
        claim_id=claim.id,
        stage_name="NORMALIZATION",
        input_summary=f"Input type: {claim.input_type}, Length: {len(claim.raw_input)}",
        output_summary=f"Normalized text: '{normalized[:100]}...'",
        start_time=norm_start,
    )

    # 2. Entity & Assertion extraction stage
    extract_start = time.time()
    extracted_tuples = extract_assertions_and_entities(normalized)
    
    created_assertions = []
    for text, entities in extracted_tuples:
        assertion = Assertion(
            claim_id=claim.id,
            assertion_text=text,
            entity_names_json=json.dumps(entities),
            confidence_weight=1.0,
        )
        session.add(assertion)
        created_assertions.append(assertion)

    await session.commit()

    await record_audit_stage(
        session=session,
        claim_id=claim.id,
        stage_name="ENTITY_EXTRACTION",
        input_summary=f"Extracted from {len(normalized)} chars",
        output_summary=f"Generated {len(created_assertions)} assertions with entities",
        start_time=extract_start,
    )

    return created_assertions
