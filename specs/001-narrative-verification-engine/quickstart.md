# Quickstart & End-to-End Validation Guide: DeepVerify

This guide documents the procedures for launching, validating, and testing the DeepVerify narrative verification feature end-to-end.

## Prerequisites

- **Python**: 3.10+ (virtual environment at `.venv` or `backend/venv`)
- **Node.js**: 18+ & npm
- **Database**: SQLite (default local DB at `backend/deepfake.db` or root `deepfake.db`)

## 1. Setup & Dependencies

```bash
# 1. Activate Python virtual environment and install backend dependencies
cd /home/pang/Desktop/DeepFake/backend
source ../.venv/bin/activate || source venv/bin/activate
pip install -r requirements.txt

# 2. Install frontend dependencies
cd /home/pang/Desktop/DeepFake/frontend
npm install
```

## 2. Launch Development Servers

```bash
# Terminal A: Start FastAPI Backend Server
cd /home/pang/Desktop/DeepFake/backend
python -m uvicorn main:app --reload --port 8000

# Terminal B: Start Next.js Frontend Server
cd /home/pang/Desktop/DeepFake/frontend
npm run dev -- -p 3000
```

## 3. End-to-End API Validation Scenario

### Step A: Submit a Claim for Verification
```bash
curl -X POST "http://localhost:8000/api/v1/claims" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "An official report confirms solar power efficiency exceeded 90% in 2025.",
    "input_type": "text"
  }'
```
*Expected Response (201 Created)*:
Returns JSON containing `id`, `status: "extracted"` or `"verifying"`, and timestamp.

### Step B: Fetch Verification Verdict & Evidence Breakdown
```bash
# Replace {CLAIM_ID} with the ID from Step A
curl -X GET "http://localhost:8000/api/v1/claims/{CLAIM_ID}/verdict"
```
*Expected Response (200 OK)*:
Returns JSON containing `verdict` (`Verified`, `Uncertain`, `Unsupported`, or `Contested`), `confidence_score`, `summary_explanation`, and an array of `evidence_items`.

### Step C: Inspect the Audit Trail
```bash
curl -X GET "http://localhost:8000/api/v1/claims/{CLAIM_ID}/audit-trail"
```
*Expected Response (200 OK)*:
Returns a chronological array of `AuditLogEntryResponse` objects displaying each execution stage (`NORMALIZATION`, `ENTITY_EXTRACTION`, `EVIDENCE_RETRIEVAL`, `STANCE_EVALUATION`, `VERDICT_AGGREGATION`) and execution timing.

## 4. Running Automated Tests

```bash
# Execute backend test suite
cd /home/pang/Desktop/DeepFake/backend
pytest test_*.py
```

## Contracts & References

- **Data Models**: [data-model.md](data-model.md)
- **API Contracts**: [contracts/claims-api.json](contracts/claims-api.json)
- **Feature Specification**: [spec.md](spec.md)
