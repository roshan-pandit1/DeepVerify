"""
schemas/claims.py — Pydantic schemas for claim submission, extraction, verification, and audit logs.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ClaimSubmissionRequest(BaseModel):
    raw_input: str = Field(..., min_length=3, max_length=10000, description="Raw claim text, web URL, or media description")
    input_type: str = Field(default="text", description="Input type: 'text', 'url', or 'media'")


class AssertionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    assertion_text: str
    entities: List[str] = []
    confidence_weight: float = 1.0


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    raw_input: str
    input_type: str
    normalized_text: Optional[str] = None
    status: str
    created_at: datetime


class ClaimDetailResponse(ClaimResponse):
    assertions: List[AssertionResponse] = []


class EvidenceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_name: str
    source_url: Optional[str] = None
    content_snippet: str
    stance: str
    credibility_score: float


class VerificationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_id: str
    verdict: str
    confidence_score: float
    summary_explanation: str
    evidence_items: List[EvidenceItemResponse] = []
    completed_at: datetime


class AuditLogEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_id: str
    stage_name: str
    input_summary: str
    output_summary: str
    execution_time_ms: int
    timestamp: datetime
