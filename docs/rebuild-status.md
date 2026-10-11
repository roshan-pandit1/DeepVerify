# Rebuild status — first working milestone

## Repository and recovery

- Started from the checked-out published repository, on a clean `main` tree. Inspected Git status, remotes, existing schemas/integrations, and applicable `frontend/AGENTS.md` plus installed Next.js guides.
- Branch: `rebuild/investigation-platform`.
- First checkpoint: `a5df4da` — persistent investigation API, leased worker, feedback/memory/ranking foundation; 20 passing checks at that checkpoint.
- Second checkpoint: `fe93a5e` — focused frontend/review desk, safe example configuration, expanded recovery/security/ranking verification; 31 backend checks, targeted lint, type checking, production build, and HTTP smoke passed.
- The documentation checkpoint hash is in `git log --oneline rebuild/investigation-platform` and the completion report.
- No push or deployment. **Local commits are not remote backups. Remote backup remains pending until a push is authorized.**

## Implemented

- Separate lightweight FastAPI investigation entry point; existing Next.js app is the focused primary interface. Legacy frontend preserved under `/legacy`; legacy backend/media code remains separate.
- Additive SQLite migration reuses existing claim/assertion/evidence/audit tables without changing historical records.
- Input limits, public URL ingestion with DNS-pinned connections and redirect/network/size protections, editable rule-based assertion candidates, heuristic entity/date/location metadata.
- Durable SQLite job queue, separate leased worker, interrupted-worker recovery, owner fencing, per-assertion progress, search provenance, explicit provider unavailability, partial results, retries, source deduplication.
- SerpAPI text search via a provider interface; explicit synthetic offline mode, separated from live evidence and memory.
- Assertion-linked source titles/URLs/snippets/dates/timestamps/methods, conservative stance predictions with explanations, approved stance assessments; no unsupported truth probabilities.
- Persistent investigation history and versioned lexical related-research retrieval. New investigations retrieve fresh evidence rather than treating cached findings as current.
- Session feedback, deduplication, independent predictions, protected review API and UI, approval/supersession/rejection history.
- Deterministic baseline and reviewed-only scikit-learn candidate CLI: versioned exports, leakage-aware connected-component splits, fit/evaluate/promote/rollback, equal-example precision@5 and NDCG@5, insufficient-data and failed-evaluation gates, stored evaluation/decision provenance.
- Responsive submission/report/history/audit/review interface; configurable API base URL and accurate learning status.

## Verified checks

- `python -m pytest investigation_tests -q`: **31 passed**. Includes invalid input; unavailable/failed/empty retrieval; assertion association and canonical-URL deduplication; edits locked after retrieval; durable leases and fencing; actual worker process termination/restart; committed partial-result preservation across interruption; feedback persistence, deduplication, approval/revocation boundaries; fixture exclusion; related memory separation; baseline fallback; connected-component leakage isolation; batch fitting/evaluation/promotion/rollback with synthetic data; insufficient-data, failed-evaluation and stale-label promotion rejection; legacy record preservation; public URL validation, mixed DNS rejection, redirect blocking, response-size limits, DNS-pinned requests and script removal.
- `npx tsc --noEmit`: passed.
- Production `npm run build`: passed with Next.js 16.3.1. Build reports an existing multiple-lockfile workspace-root warning.
- Targeted ESLint passed after fixing an effect-state rule violation in initial data fetching.
- Real HTTP smoke check passed: Uvicorn API submission → durable queue → separate worker process → offline assertion report. Built Next.js production server returned the expected HTML for `/`, `/review`, and `/history`. Temporary servers and data were cleaned up. This was not a browser interaction test or live-provider check.
- Documented CLI smoke checks passed in an isolated temporary database: migration, approved-data export, insufficient-data training refusal, baseline rollback, and invalid administrator-token refusal.
- `npm ci` completed; it reported 10 dependency audit findings (9 high, 1 critical) in the existing dependency tree. Dependency remediation was not part of these implementation checks.
- Synthetic data stays in temporary test directories; it does not demonstrate real-world accuracy or ranking improvement.

## Credential-dependent checks

- Live SerpAPI search, quota/authentication behavior against a real account, and real source/date quality have not been validated. `SERPAPI_API_KEY` required.
- Real public-article fetching is implemented but URL-network tests use mocked responses; no claim of broad real-site compatibility.
- No real reviewed relevance corpus is present; no eligible real candidate was trained, evaluated, or promoted.

## Current learning status

**Collecting reviewed feedback.** Baseline active by default. Every investigation updates research memory. Only approved live relevance labels are eligible for batch training. No real reviewed data demonstrates ranking improvement. Test-only synthetic improvements are functional checks, not product-performance evidence.

## Missing capabilities and limitations

- Full-source evidence passage retrieval and robust publication-date extraction are not implemented. Live evidence is explicitly search snippets.
- Rule-based assertion/entity/date/location extraction needs user editing and does not guarantee atomic decomposition or complete entity resolution.
- Stance classification is conservative lexical triage plus protected human correction, not validated semantic entailment. Assessments reflect reviewed source stance, with limited sufficiency criteria.
- Memory is lexical, not semantic. Related-claim split grouping is lexical and may miss paraphrases; independent real evaluation requires reviewed topic groups and a held-out dataset not repeatedly tuned against.
- SQLite/local workspace only; no PostgreSQL adapter, distributed queue, individual user/admin accounts, private investigation ownership, deployment hardening, or browser end-to-end automation.
- Shared administrator token and local filesystem trust are documented in README. Reviewer session identifiers are not verified human identities.
- Legacy records are preserved but not automatically reinterpreted/imported into the new investigation reports.

## Next milestone

1. Fetch full-source evidence passages safely, preserving exact passage provenance and extraction failures.
2. Assemble an approved real-world relevance/stance dataset with human-reviewed topic and source groups; establish a frozen evaluation set.
3. Validate SerpAPI and public-article behavior with real credentials and sources; measure retrieval coverage and reviewed ranking quality against the baseline.
4. Add browser workflow automation and account-level authorization before any multi-user deployment.
