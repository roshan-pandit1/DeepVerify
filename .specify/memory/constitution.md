<!--
### Sync Impact Report
- **Version Change**: Uninitialized (`[CONSTITUTION_VERSION]`) → `1.0.0`
- **Modified Principles**: Initialized project core principles replacing template placeholders.
- **Added Sections**:
  - Core Principles:
    - I. Clean and Maintainable Code
    - II. Security First & Data Protection
    - III. Modular & Decoupled Architecture
    - IV. Authentication & Authorization Standard
    - V. Database Integrity & Migration Control
    - VI. Strict API & Input Validation
    - VII. Explicit Error Handling & Logging
    - VIII. Pragmatic Testing & Verification
    - IX. Clear & Living Documentation
    - X. Pragmatic Scalability & Resource Management
    - XI. Performance & Responsiveness
    - XII. Git & Version Control Best Practices
  - Development Workflow & Quality Gates
  - Governance
- **Removed Sections**: Unpopulated placeholder sections.
- **Follow-up TODOs**: None.
-->

# DeepVerify Project Constitution

## Core Principles

### I. Clean and Maintainable Code
All backend (Python/FastAPI) and frontend (TypeScript/Next.js) code MUST adhere to strict readability, consistency, and clean code standards.
- Functions MUST be small, single-purpose, and named clearly after their intent.
- Avoid dead code, commented-out logic, and magic numbers; use explicit configuration constants.
- Python code MUST follow PEP 8 standards; TypeScript MUST enforce strict type checking.
- Rationale: University project codebases move fast across team members; readability prevents refactoring bottlenecks and lowers cognitive overhead.

### II. Security First & Data Protection
Security MUST NOT be an afterthought. All data entry points and sensitive operations MUST be hardened.
- Secrets, API keys, and credentials MUST NEVER be hardcoded; they MUST be loaded via `.env` files and environment variables.
- Sensitive files (`.env`, private keys, local DBs, credentials) MUST be listed in `.gitignore`.
- User data, uploaded media files, and analysis tokens MUST be sanitized to prevent path traversal, injection, and unauthorized file access.
- Rationale: Protecting system integrity and credentials is required for public demonstration and evaluation.

### III. Modular & Decoupled Architecture
The system MUST maintain strict separation of concerns between backend services, frontend presentation, and AI/OSINT analytical pipelines.
- Backend API routes MUST delegate business logic and heavy processing to domain services or processing modules rather than embedding logic in route handlers.
- Frontend components MUST separate UI rendering from API communication and state management.
- AI detection and credibility pipelines MUST be self-contained modules with clear input/output contracts.
- Rationale: Modular components enable independent testing, easier debugging, and straightforward assignment of project responsibilities among teammates.

### IV. Authentication & Authorization Standard
Every request touching protected resources or user-specific data MUST be authenticated and authorized.
- Use lightweight, industry-standard authentication mechanisms (e.g., JWT or secure session tokens).
- Route handlers MUST enforce role-based or ownership-based access controls explicitly at the endpoint boundary.
- Passwords MUST be hashed using secure algorithms (e.g., bcrypt/Argon2) before storage.
- Rationale: Ensures multi-user security without overcomplicating identity management for a major project submission.

### V. Database Integrity & Migration Control
Database access and schema definitions MUST enforce structural integrity and predictable evolution.
- Foreign keys, unique constraints, non-null checks, and data types MUST be declared at the schema level.
- Schema changes MUST be managed through explicit migration scripts or versioned database initializers.
- Transactions MUST be used for multi-step write operations to ensure atomic consistency.
- Rationale: Prevents database corruption, orphan records, and breaking changes during team development.

### VI. Strict API & Input Validation
All external inputs (HTTP payloads, query parameters, path variables, webhooks) MUST be validated before execution.
- Backend endpoints MUST use strict schema validators (e.g., Pydantic models) to reject invalid payloads with `400 Bad Request`.
- Frontend forms MUST validate input constraints client-side before dispatching API requests.
- Rationale: Prevents invalid state propagation, runtime crashes, and unexpected injection vectors.

### VII. Explicit Error Handling & Logging
Failures MUST be handled gracefully and diagnosed easily without leaking internal stack traces to clients.
- Exceptions MUST be caught explicitly; silent failures or broad empty `except:` blocks are forbidden.
- API error responses MUST follow a unified JSON error format with human-readable error messages and standard HTTP status codes.
- Diagnostic logging MUST record operational events and errors with appropriate log levels (`INFO`, `WARNING`, `ERROR`).
- Rationale: Structured error responses improve frontend UX and simplify backend debugging.

### VIII. Pragmatic Testing & Verification
Code quality MUST be verified through automated tests covering core utility functions, API contracts, and pipeline workflows.
- Backend services MUST include unit tests for core logic and integration tests for key API endpoints.
- Essential user flows MUST be verified before merging feature branches.
- Tests MUST run fast and execute against isolated test databases or mock services.
- Rationale: Keeps testing overhead low for an academic project while guaranteeing core feature reliability.

### IX. Clear & Living Documentation
Project documentation MUST remain accurate, concise, and updated alongside code changes.
- Root and module `README.md` files MUST describe setup, environment configuration, run commands, and architecture overview.
- APIs MUST be documented via standard interactive specs (OpenAPI / FastAPI Swagger docs).
- Non-obvious algorithms or complex pipeline stages MUST include explanatory docstrings.
- Rationale: Ensures external evaluators and team members can set up, run, and grade the project without friction.

### X. Pragmatic Scalability & Resource Management
System design SHOULD accommodate typical academic evaluation loads efficiently without over-engineering enterprise cloud infrastructure.
- Long-running tasks (e.g., video/audio deepfake processing, OSINT enrichment) SHOULD run asynchronously or asynchronously batched to avoid blocking main web server threads.
- Uploaded media and temporary processing artifacts MUST be cleaned up or cached with retention limits.
- Avoid introducing complex distributed message queues or multi-cluster orchestration unless explicitly needed.
- Rationale: Balances responsive user experience with simple deployment and manageable hosting requirements.

### XI. Performance & Responsiveness
The application MUST deliver a responsive UI and fast API responses.
- Frontend pages MUST load efficiently with optimized assets, loading states, and responsive layouts.
- Backend queries MUST index heavily queried columns and avoid N+1 query patterns.
- AI pipeline inference SHOULD use lightweight models or cached results where appropriate to maintain low response latency.
- Rationale: A snappy UI and fast response times create a great user impression during project evaluation and live demos.

### XII. Git & Version Control Best Practices
Version control MUST be used disciplinedly to maintain codebase history and enable seamless teamwork.
- The `main` branch MUST always remain buildable and working.
- Feature work MUST take place on descriptive feature branches (e.g., `feature/ai-detection`, `fix/auth-jwt`).
- Commit messages MUST be descriptive and state the intent of the change.
- Sensitive files, build artifacts, virtual environments, and binary media dumps MUST NEVER be committed to Git.
- Rationale: Prevents branch conflicts, broken deployments, and accidental credential leaks.

## Development Workflow & Quality Gates

### Quality Gates
Before any pull request or feature branch is merged into `main`, the code MUST pass the following checks:
1. **Linting & Formatting**: Code passes standard style and linting checks without critical errors.
2. **Automated Tests**: All existing and new unit/integration tests pass.
3. **No Unhandled Secrets**: Code scan confirms no `.env` values, API keys, or credentials are added.
4. **Build Verification**: Frontend Next.js build (`npm run build`) and backend execution verify cleanly.

## Governance

### Amendment Procedure
1. Any team member can propose an amendment to this constitution.
2. Amendments require review and unanimous agreement among the core project contributors.
3. Once agreed upon, the amendment MUST be documented in `.specify/memory/constitution.md` with an updated version number and date.

### Versioning Policy
- **MAJOR version bump**: Backward-incompatible principle removals, major architectural pivots, or governance restructuring.
- **MINOR version bump**: Addition of new principles, sections, or materially expanded guidelines.
- **PATCH version bump**: Clarifications, formatting fixes, or minor wording adjustments.

### Compliance
All feature specifications (`spec.md`), implementation plans (`plan.md`), and task breakdowns (`tasks.md`) MUST align with the principles defined in this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-09-13 | **Last Amended**: 2026-09-13
