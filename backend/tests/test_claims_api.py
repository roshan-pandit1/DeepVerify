"""
test_claims_api.py — API contract and route tests for claim submission, extraction, verdict, and audit log endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from database import init_db, Claim, ClaimStatus, AsyncSessionLocal
from routes.claims import run_full_verification_pipeline

@pytest.mark.anyio
async def test_claim_submission_and_extraction_e2e():
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Submit claim
        payload = {
            "raw_input": "NASA confirmed a new lunar observation standard in 2025.",
            "input_type": "text"
        }
        res = await client.post("/api/v1/claims", json=payload)
        assert res.status_code == 201
        data = res.json()
        claim_id = data["id"]
        assert data["raw_input"] == payload["raw_input"]
        assert data["status"] == "submitted"

        # 2. Get claim detail (with extracted assertions)
        res_detail = await client.get(f"/api/v1/claims/{claim_id}")
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["id"] == claim_id
        assert detail_data["normalized_text"] is not None
        assert len(detail_data["assertions"]) > 0

        # 3. Get verification verdict
        res_verdict = await client.get(f"/api/v1/claims/{claim_id}/verdict")
        assert res_verdict.status_code == 200
        verdict_data = res_verdict.json()
        assert verdict_data["verdict"] in ["Verified", "Uncertain", "Unsupported", "Contested"]
        assert 0.0 <= verdict_data["confidence_score"] <= 100.0

        # 4. Get audit trail
        res_audit = await client.get(f"/api/v1/claims/{claim_id}/audit-trail")
        assert res_audit.status_code == 200
        audit_entries = res_audit.json()
        assert len(audit_entries) >= 4
        stages = [e["stage_name"] for e in audit_entries]
        assert "NORMALIZATION" in stages
        assert "ENTITY_EXTRACTION" in stages
        assert "EVIDENCE_RETRIEVAL" in stages
        assert "VERDICT_AGGREGATION" in stages


@pytest.mark.anyio
async def test_pending_claim_verdict_202():
    await init_db()
    async with AsyncSessionLocal() as session:
        claim = Claim(
            raw_input="Testing pending claim response status",
            status=ClaimStatus.SUBMITTED,
        )
        session.add(claim)
        await session.commit()
        claim_id = claim.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/claims/{claim_id}/verdict")
        assert res.status_code == 202
        data = res.json()
        assert "Verification in progress" in data["detail"]


@pytest.mark.anyio
async def test_pipeline_failure_rollback():
    await init_db()
    # Execute pipeline with non-existent claim ID -> triggers graceful exception handling & rollback
    await run_full_verification_pipeline("invalid-non-existent-uuid-12345")
