# Implementation Plan: DeepVerify Narrative Verification Engine

**Branch**: `001-narrative-verification-engine` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-narrative-verification-engine/spec.md`

## Summary

Build the initial narrative verification engine for DeepVerify. The engine enables users to submit online claims (text, URLs, media metadata), extracts normalized factual assertions and entities, gathers supporting and refuting evidence using AI and OSINT pipelines, calculates source credibility metrics, and presents an explainable verdict report with a complete, step-by-step audit trail.

## Technical Context

**Language/Version**: Python 3.10+ (Backend), TypeScript / Node.js 18+ (Frontend)

**Primary Dependencies**: FastAPI 0.115, Pydantic v2, SQLAlchemy 2.0 (aiosqlite), HTTPX, Next.js 15, React 19, Tailwind CSS

**Storage**: SQLite (`deepfake.db`) managed via SQLAlchemy 2.0 async ORM and declarative table initializers (`init_db()`) with cascading foreign keys

**Input Handling**: Accepts text statements, web URLs, or media reference paths / metadata strings (integrating with `/tmp/uploads` media pipeline)

**Credibility Scoring Heuristic**: Source credibility evaluated on a 0.0–1.0 index using domain reputation tiers (0.80–0.95 for authoritative outlets, 0.30–0.50 for social/unverified sources, default 0.50) combined with stance corroboration

**Testing**: `pytest` (Backend API & Pipeline tests), React Testing Library / Jest (Frontend)

**Target Platform**: Linux Server / Web Browsers (Chrome, Firefox, Safari)

**Project Type**: Web Application (FastAPI backend + Next.js frontend)

**Performance Goals**: Claim extraction < 3s, full end-to-end verification pipeline < 15s

**Constraints**: Academic major project realistic scope; no unnecessary enterprise cloud or microservice infrastructure

**Scale/Scope**: Academic evaluation load, interactive demonstration, single/multi-user sessions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Clean & Maintainable Code (Principle I)**: Decoupled Python services, typed TypeScript frontend, PEP 8 compliance. -> **PASS**
- **Security First & Data Protection (Principle II)**: Input sanitization, environment variable secrets, no hardcoded API keys. -> **PASS**
- **Modular & Decoupled Architecture (Principle III)**: Verification logic isolated in `backend/pipeline/`, decoupled from HTTP routes & UI components. -> **PASS**
- **Authentication & Authorization (Principle IV)**: Public open access for academic evaluation and live demonstration without login barriers; public claim verification endpoints do not handle private user profile data. Multi-user session/JWT auth is intentionally deferred to a future multi-tenant feature branch. -> **PASS (Documented Scope Waiver)**
- **Database Integrity (Principle V)**: Relational integrity with explicit foreign keys and cascade rules (`Claim` -> `Assertion` -> `EvidenceItem` / `VerificationResult` / `AuditLogEntry`) initialized via async `init_db()`. -> **PASS**
- **Strict API Validation (Principle VI)**: OpenAPI contract enforced via Pydantic v2 schemas. -> **PASS**
- **Explicit Error Handling (Principle VII)**: Unified JSON error payload format, explicit exception handling. -> **PASS**
- **Pragmatic Testing (Principle VIII)**: Unit & contract testing via pytest. -> **PASS**
- **Clear Documentation (Principle IX)**: Quickstart guide, data model diagrams, OpenAPI specification. -> **PASS**
- **Pragmatic Scalability & Performance (Principles X & XI)**: Non-blocking async background tasks for pipeline processing. -> **PASS**
- **Git Best Practices (Principle XII)**: Feature branch workflows (`001-narrative-verification-engine`). -> **PASS**

## Project Structure

### Documentation (this feature)

```text
specs/001-narrative-verification-engine/
├── plan.md              # Implementation plan & architecture decisions
├── research.md          # Phase 0 output: Research decisions & rationale
├── data-model.md        # Phase 1 output: ER diagram & entity specifications
├── quickstart.md        # Phase 1 output: Run guide & E2E validation scenarios
└── contracts/
    └── claims-api.json  # Phase 1 output: OpenAPI 3.0 REST API contracts
```

### Source Code Layout

```text
backend/
├── main.py                    # FastAPI entrypoint & route registration
├── database.py                # SQLAlchemy ORM models & session setup
├── config.py                  # Pydantic environment configuration
├── pipeline/                  # Modular Verification & Analysis Pipeline
│   ├── credibility_pipeline/  # OSINT & source credibility scoring
│   └── ai_detection_pipeline/ # AI claim extraction & stance detection
└── tests/                     # Pytest suite
    ├── test_pipeline.py
    └── test_claims_api.py

frontend/
├── src/
│   ├── app/                   # Next.js 15 App Router pages
│   ├── components/            # UI components (ClaimForm, VerdictCard, AuditTrail)
│   └── lib/                   # API client & fetcher utilities
└── tests/
```

**Structure Decision**: Web application layout (`backend/` + `frontend/`) maintaining strict modularity between API endpoints, processing pipeline, and frontend views.

## Complexity Tracking

> Architecture adheres to project constitution principles with one documented scope waiver for academic demonstration.

| Principle / Area | Scope Decision & Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Principle IV (Authentication & Authorization)** | Open public verification endpoints for academic evaluation and friction-free demonstration; endpoints do not expose private user profile data. | Requiring mandatory user login/SSO introduces authentication friction and barrier to entry during evaluator demonstration. Multi-user auth is deferred to subsequent milestone. |
