# Technical Research: DeepVerify Narrative Verification Engine

## Research Decisions

### 1. Verification Pipeline Isolation & Architecture
- **Decision**: Implement the verification engine as modular, independent Python packages within `backend/ai_detection_pipeline/` and `backend/credibility_pipeline/` with explicit input/output dataclasses/schemas.
- **Rationale**: Isolates heavy AI/OSINT analytical logic from HTTP routing and database handlers. Ensures compliance with Constitution Principle III (Modular Architecture) and keeps the university project clean and testable.
- **Alternatives Considered**:
  - *Microservices / External Task Queues (Celery/RabbitMQ)*: Rejected as over-engineering for a university project setup.
  - *Monolithic route handler logic*: Rejected due to maintainability issues and violation of project constitution.

### 2. Async Execution & Pipeline Scheduling
- **Decision**: Use FastAPI background tasks (`BackgroundTasks` or async task runner) for non-blocking execution of evidence extraction and scoring while storing immediate status in SQLite via SQLAlchemy.
- **Rationale**: Keeps API endpoint response times under 500ms while processing heavy AI/OSINT pipelines asynchronously.
- **Alternatives Considered**:
  - *Synchronous blocking processing*: Rejected because complex claim verification can take several seconds, causing HTTP timeouts.
  - *Distributed Celery workers*: Rejected due to infrastructure complexity and external memory broker overhead.

### 3. Data Persistence & Migration
- **Decision**: Use SQLite with SQLAlchemy ORM (via `aiosqlite`) for local development, with explicit foreign key constraints and schema definitions in `backend/database.py`.
- **Rationale**: Provides zero-config, highly portable persistence for local evaluation and automated testing while supporting async IO.
- **Alternatives Considered**:
  - *Raw SQL strings*: Rejected due to maintenance risk and lack of schema type safety.
  - *NoSQL / MongoDB*: Rejected as relational foreign keys (`Claim` -> `Assertion` -> `EvidenceItem`) are core to audit trail integrity.

### 4. API Contract & Validation Schema
- **Decision**: Use Pydantic v2 schemas for strict payload validation, response serialization, and auto-generated OpenAPI documentation.
- **Rationale**: Guarantees Principle VI (Strict API Validation) and ensures frontend-backend contract consistency.
- **Alternatives Considered**:
  - *Manual JSON dictionary parsing*: Rejected due to high risk of runtime missing-key crashes.

### 5. Frontend State Management & API Integration
- **Decision**: Use Next.js 15 App Router with React Client Components, custom hooks for API fetching (`useSWR` / custom fetchers), and Tailwind CSS for responsive UI presentation.
- **Rationale**: Provides fast initial rendering, clear separation of UI from data fetching, and an intuitive user interface for claim investigation.
- **Alternatives Considered**:
  - *Redux Toolkit*: Rejected as global state complexity is unnecessary for standard REST endpoint data flows.
