# Feature Specification: DeepVerify Narrative Verification Engine

**Feature Branch**: `001-narrative-verification-engine`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Create the initial product specification for DeepVerify. DeepVerify is a narrative verification engine that helps users assess the credibility of online claims and narratives. The system should accept user-submitted claims and relevant evidence such as text, URLs, and media, then analyze the available evidence using AI-assisted verification and OSINT-style analysis."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Claim Submission and Entity Extraction (Priority: P1)

As an analyst or user evaluating online information, I want to submit text claims, URLs, or media files so that the system can parse, normalize, and extract core factual assertions and entities.

**Why this priority**: This is the fundamental entry point for the narrative verification engine. Without claim input and normalization, downstream verification processing cannot occur.

**Independent Test**: Can be tested independently by submitting a claim string or URL via the submission API/form and verifying that normalized text, extracted entities, and sub-assertions are returned and saved with status `Extracted`.

**Acceptance Scenarios**:

1. **Given** a user on the claim submission interface, **When** they paste a claim text or valid web URL and submit, **Then** the system creates a claim record, normalizes the content, extracts key entities/assertions, and returns an `Extracted` status.
2. **Given** an empty submission or invalid URL format, **When** the user attempts submission, **Then** the system rejects the input client-side and server-side with an explanatory `400 Bad Request` validation error.

---

### User Story 2 - Automated Verification & Evidence Analysis (Priority: P2)

As a user assessing claim credibility, I want the system to gather supporting and contradicting evidence via AI and OSINT pipelines so that source credibility and narrative consistency are evaluated automatically.

**Why this priority**: Delivers the core value proposition by transforming raw claims into evidence-backed assessments with source credibility scoring.

**Independent Test**: Can be tested by executing the verification pipeline against a pre-extracted claim record and confirming that supporting/contradicting evidence items, source credibility scores, and stance metrics are populated.

**Acceptance Scenarios**:

1. **Given** a normalized claim with extracted assertions, **When** the verification pipeline executes, **Then** it queries evidence sources, evaluates source credibility, and tags each evidence item with a stance (`supports`, `refutes`, or `neutral`).
2. **Given** conflicting evidence from multiple sources, **When** analysis completes, **Then** the system detects narrative inconsistencies and flags the claim as `Contested` or `Uncertain` with supporting evidence details.

---

### User Story 3 - Explainable Report & Audit Trail (Priority: P3)

As an auditor or end user, I want an interactive verification report that presents clear verdicts, confidence metrics, evidence breakdowns, and a step-by-step audit trail so that I can inspect how conclusions were derived.

**Why this priority**: Ensures transparency, explainability, and user trust by exposing the decision path rather than acting as a black-box AI tool.

**Independent Test**: Can be tested independently by rendering a completed verification report page and verifying that verified facts, uncertain claims, and unsupported claims are categorized visually alongside a chronological audit log.

**Acceptance Scenarios**:

1. **Given** a completed verification run, **When** the user views the claim report dashboard, **Then** the report displays a clear verdict (`Verified`, `Uncertain`, `Unsupported`, or `Contested`), a 0-100% confidence score, and categorized evidence cards.
2. **Given** a user inspecting the verification methodology, **When** they expand the "Audit Trail" section, **Then** every execution stage, data retrieval timestamp, and AI scoring step is listed in chronological order.

---

### Edge Cases

- **Unreachable Evidence Sources**: If external OSINT tools or web scrapers fail or return zero results, the system MUST flag the claim as `Uncertain - Insufficient Evidence` and log the retrieval failure in the audit trail without crashing.
- **Contradictory Evidence of Equal Weight**: When high-credibility sources directly contradict each other, the system MUST assign a `Contested` verdict and display both stance groups with balanced weightings.
- **Oversized Media or Input Length**: Extremely long text submissions or large media files MUST be validated and capped at the API boundary, returning a clear size-limit warning to the user.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept claim submissions containing plain text, web URLs, or uploaded media metadata (for `media` inputs, `raw_input` accepts media URLs, local file paths e.g. from `/tmp/uploads`, or media metadata JSON strings).
- **FR-002**: System MUST normalize submitted text and extract named entities, key assertions, and temporal/spatial context.
- **FR-003**: System MUST execute an isolated evidence retrieval module to gather supporting and refuting evidence from configured OSINT and knowledge sources.
- **FR-004**: System MUST compute source credibility scores for retrieved evidence on a 0.0–1.0 scale using a domain reputation heuristic index (e.g., authoritative news and fact-checking outlets rated 0.80–0.95, unverified or social domains rated 0.30–0.50, default 0.50).
- **FR-005**: System MUST evaluate evidence stance (`supports`, `refutes`, `neutral`) for each assertion and aggregate them into an overall verdict (`Verified`, `Uncertain`, `Unsupported`, `Contested`) with a numerical confidence score (0-100%).
- **FR-006**: System MUST record an immutable audit trail entry for every stage of the extraction, evidence gathering, stance evaluation, and verdict generation process.
- **FR-007**: System MUST present an interactive verification dashboard in the React frontend showing verdict badges, confidence breakdown, evidence sources, and audit logs.
- **FR-008**: System MUST decouple the AI and verification pipeline logic from FastAPI HTTP route handlers and frontend UI components into separate, modular Python packages.
- **FR-009**: System MUST persist claims, extracted assertions, evidence records, verdicts, and audit logs in a relational SQL database with foreign key integrity.

### Key Entities

- **Claim**: Represents the top-level user submission. Attributes: `id`, `raw_input` (text statement, URL, or media reference path/metadata), `input_type` (`text`/`url`/`media`), `normalized_text`, `status` (`submitted`/`extracted`/`verifying`/`completed`/`failed`), `created_at`.
- **Assertion**: Represents an extracted atomic factual claim. Attributes: `id`, `claim_id`, `assertion_text`, `entity_names` (array), `confidence_weight`.
- **EvidenceItem**: Represents a retrieved piece of evidence. Attributes: `id`, `assertion_id`, `source_name`, `source_url`, `content_snippet`, `stance` (`supports`/`refutes`/`neutral`), `credibility_score`.
- **VerificationResult**: Represents the final aggregated evaluation. Attributes: `id`, `claim_id`, `verdict` (`Verified`/`Uncertain`/`Unsupported`/`Contested`), `confidence_score`, `summary_explanation`, `completed_at`.
- **AuditLogEntry**: Represents an individual execution record in the verification lifecycle. Attributes: `id`, `claim_id`, `stage_name`, `input_summary`, `output_summary`, `execution_time_ms`, `timestamp`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Initial claim extraction and entity parsing completes within 3 seconds for text and URL inputs.
- **SC-002**: End-to-end verification pipeline completes execution in under 15 seconds for standard claims.
- **SC-003**: 100% of completed verification reports display a complete, step-by-step audit trail without missing processing stages.
- **SC-004**: 100% of claims are categorized clearly into one of the four explicit verdict states (`Verified`, `Uncertain`, `Unsupported`, `Contested`) with supporting evidence links.

## Assumptions

- **Target Deployment**: The system is designed for local development and academic evaluation using FastAPI (Python) backend and Next.js (React) frontend.
- **Data Persistence**: Uses a standard SQL database (SQLite for local evaluation / PostgreSQL option) managed via SQLAlchemy async ORM and declarative schema initializers (`init_db()`) with relational foreign key integrity.
- **Modular Pipeline Isolation**: AI and OSINT processing run as modular internal Python services (`backend/pipeline/`) rather than external distributed microservices, keeping architecture simple and maintainable.
- **Authentication Scope**: The narrative verification engine currently operates in an open/public academic evaluation mode without user login barriers to facilitate frictionless demonstration. Session/JWT-based multi-user authentication is intentionally deferred to a future multi-tenant iteration.
