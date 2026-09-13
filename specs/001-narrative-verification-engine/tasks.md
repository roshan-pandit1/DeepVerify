# Tasks: DeepVerify Narrative Verification Engine

**Feature**: DeepVerify Narrative Verification Engine  
**Branch**: `001-narrative-verification-engine`  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and core configuration management

- [x] T001 Initialize backend environment settings in `backend/config.py` using Pydantic Settings to load `ENV`, `DATABASE_URL`, `LOG_LEVEL`, and API credentials
- [x] T002 [P] Setup structured diagnostic logging infrastructure in `backend/logging_config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database connection, error handling, and API routing infrastructure that MUST be complete before ANY user story implementation

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete

- [x] T003 Configure database connection manager and SQLAlchemy async session factory in `backend/database.py` targeting `sqlite+aiosqlite:///./deepfake.db`
- [x] T004 Create SQLAlchemy declarative base metadata and table initialization helper `init_db()` in `backend/database.py`
- [x] T005 [P] Implement global API error handling middleware and standard JSON error response schemas in `backend/middleware/error_handler.py`
- [x] T006 [P] Setup APIRouter registration in `backend/main.py` with `/api/v1` prefix and CORS middleware

**Checkpoint**: Foundation ready - user story implementation complete

---

## Phase 3: User Story 1 - Claim Submission and Entity Extraction (Priority: P1) 🎯 MVP

**Goal**: Allow users to submit claims (text, URL, media metadata), normalize text, extract entities and assertions, and track claim status.

**Independent Test**: Submit a claim via `POST /api/v1/claims` or frontend form, and verify that normalized text, extracted entities, and sub-assertions are returned with status `extracted` and persisted in DB.

### Tests for User Story 1

- [x] T007 [P] [US1] Write API contract and route tests for claim submission and extraction in `backend/tests/test_claims_api.py`

### Implementation for User Story 1

- [x] T008 [P] [US1] Create `Claim` ORM model in `backend/database.py` with attributes `id` (String UUIDv4 PK), `raw_input` (Text, NOT NULL), `input_type` (Enum `text`/`url`/`media`, NOT NULL), `normalized_text` (Text, NULLABLE), `status` (Enum `submitted`/`extracted`/`verifying`/`completed`/`failed`, Default `submitted`), `created_at` (Datetime UTC), `updated_at` (Datetime UTC)
- [x] T009 [P] [US1] Create `Assertion` ORM model in `backend/database.py` with attributes `id` (String UUIDv4 PK), `claim_id` (String UUIDv4 FK -> `Claim.id` ON DELETE CASCADE, NOT NULL), `assertion_text` (Text, NOT NULL), `entity_names_json` (Text JSON string, array of extracted entity strings), `confidence_weight` (Float 0.0 to 1.0, Default 1.0), `created_at` (Datetime UTC)
- [x] T010 [P] [US1] Define Pydantic validation schemas (`ClaimSubmissionRequest`, `ClaimResponse`, `ClaimDetailResponse`) in `backend/schemas/claims.py`
- [x] T011 [US1] Implement claim extraction and text normalization engine in `backend/pipeline/ai_detection_pipeline/claim_extractor.py` (depends on T008, T009)
- [x] T012 [US1] Implement `POST /api/v1/claims`, `GET /api/v1/claims`, and `GET /api/v1/claims/{id}` API route handlers in `backend/routes/claims.py` (depends on T010, T011)
- [x] T013 [P] [US1] Create claim submission form component `ClaimSubmissionForm.tsx` in `frontend/src/components/ClaimSubmissionForm.tsx`
- [x] T014 [P] [US1] Create claim detail view component `ClaimDetailView.tsx` in `frontend/src/components/ClaimDetailView.tsx`
- [x] T015 [US1] Connect claim submission and extraction frontend components to API endpoints in `frontend/src/app/page.tsx`

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently (MVP ready!)

---

## Phase 4: User Story 2 - Automated Verification & Evidence Analysis (Priority: P2)

**Goal**: Execute evidence retrieval against OSINT/AI pipeline, calculate source credibility scores, and determine evidence stance (`supports`, `refutes`, `neutral`).

**Independent Test**: Run the verification pipeline on extracted assertions and verify that `EvidenceItem` records and stance classifications are generated with credibility scores.

### Tests for User Story 2

- [x] T016 [P] [US2] Write unit and integration tests for evidence retrieval and credibility pipeline in `backend/tests/test_pipeline.py`

### Implementation for User Story 2

- [x] T017 [P] [US2] Create `EvidenceItem` ORM model in `backend/database.py` with attributes `id` (String UUIDv4 PK), `assertion_id` (String UUIDv4 FK -> `Assertion.id` ON DELETE CASCADE, NOT NULL), `source_name` (String 255, NOT NULL), `source_url` (String 2048, NULLABLE), `content_snippet` (Text, NOT NULL), `stance` (Enum `supports`/`refutes`/`neutral`, NOT NULL), `credibility_score` (Float 0.0 to 1.0, NOT NULL), `retrieved_at` (Datetime UTC)
- [x] T018 [P] [US2] Create `VerificationResult` ORM model in `backend/database.py` with attributes `id` (String UUIDv4 PK), `claim_id` (String UUIDv4 FK -> `Claim.id` ON DELETE CASCADE, Unique, NOT NULL), `verdict` (Enum `Verified`/`Uncertain`/`Unsupported`/`Contested`, NOT NULL), `confidence_score` (Float 0.0 to 100.0, NOT NULL), `summary_explanation` (Text, NOT NULL), `completed_at` (Datetime UTC)
- [x] T019 [US2] Implement OSINT search and source credibility scoring engine in `backend/pipeline/credibility_pipeline/credibility_engine.py` (depends on T017)
- [x] T020 [US2] Implement stance evaluation and overall verdict aggregation engine in `backend/pipeline/ai_detection_pipeline/stance_evaluator.py` (depends on T018, T019)
- [x] T021 [US2] Integrate background verification task runner in `backend/routes/claims.py` to trigger full pipeline on claim creation
- [x] T022 [US2] Implement `GET /api/v1/claims/{id}/verdict` route handler in `backend/routes/claims.py` returning `VerificationResultResponse`
- [x] T023 [P] [US2] Create `VerdictCard.tsx` component in `frontend/src/components/VerdictCard.tsx` to render verdict badge, confidence meter, and evidence cards

**Checkpoint**: User Stories 1 AND 2 are both independently functional

---

## Phase 5: User Story 3 - Explainable Report & Audit Trail (Priority: P3)

**Goal**: Present an interactive verification report dashboard with verdict badges, confidence breakdown, evidence sources, and chronological audit trail.

**Independent Test**: View a completed claim verification report at `/report/{id}` or call `GET /api/v1/claims/{id}/audit-trail` and confirm that step-by-step audit entries (`NORMALIZATION`, `ENTITY_EXTRACTION`, `EVIDENCE_RETRIEVAL`, `VERDICT_AGGREGATION`), timing metrics, and verdicts are displayed.

### Tests for User Story 3

- [x] T024 [P] [US3] Add audit trail contract and timeline integration tests in `backend/tests/test_claims_api.py` validating chronological audit entries for all pipeline stages

### Implementation for User Story 3

- [x] T025 [P] [US3] Create `AuditLogEntry` ORM model in `backend/database.py` with attributes `id` (String UUIDv4 PK), `claim_id` (String UUIDv4 FK -> `Claim.id` ON DELETE CASCADE, NOT NULL), `stage_name` (String 100, NOT NULL), `input_summary` (Text, NOT NULL), `output_summary` (Text, NOT NULL), `execution_time_ms` (Integer, NOT NULL), and `timestamp` (Datetime UTC)
- [x] T026 [US3] Implement pipeline audit logging utility in `backend/pipeline/audit_logger.py` with `record_audit_stage()` recording execution duration and stage summaries
- [x] T027 [US3] Implement `GET /api/v1/claims/{id}/audit-trail` API route handler in `backend/routes/claims.py` returning chronological `AuditLogEntryResponse` objects
- [x] T028 [P] [US3] Create `AuditTrailViewer.tsx` component in `frontend/src/components/AuditTrailViewer.tsx` rendering stage names, execution timings, and input/output summaries
- [x] T029 [US3] Implement interactive report page in `frontend/src/app/report/[id]/page.tsx` integrating `ClaimDetailView`, `VerdictCard`, and `AuditTrailViewer`
- [x] T030 [US3] Connect report navigation link between `ClaimSubmissionForm` / `page.tsx` and the report view at `/report/{id}`

**Checkpoint**: User Stories 1, 2, and 3 are fully functional, integrated, and verified (FR-006, FR-007, SC-003 complete)

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, security hardening, and end-to-end validation

- [x] T031 [P] Update root and backend README documentation in `README.md` and `backend/README.md`
- [x] T032 Perform security review: verify CORS configuration, input sanitization, and credential handling in `backend/config.py`
- [x] T033 Execute complete validation workflow in `specs/001-narrative-verification-engine/quickstart.md`, including measuring latency for extraction (<3s, SC-001) and full pipeline (<15s, SC-002), and confirming all automated test suites pass
