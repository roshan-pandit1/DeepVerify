# Milestone three — observed results

Observed locally on **2026-10-12**, on `rebuild/investigation-platform`. This document records nonsensitive counts/statuses, not source snapshots or a benchmark dataset.

## Readiness

| Item | Observed result |
|---|---|
| Milestone-two implementations | `f58af2d` and `983db4e` present |
| Investigation database | Absent initially; initialized using additive migrations 1–3 |
| SerpAPI credential | Missing |
| Valid administrator token | Missing |
| Real investigations / evidence items | 0 / 0 |
| Candidate benchmark cases / independent opinions | 0 / 0 |
| Approved feedback / approved evaluation labels | 0 / 0 |
| Active/effective model | `baseline-v1` / `baseline-v1` |
| Model training/promotion | Not attempted: no eligible data; active model unchanged |
| Actual API / production frontend | HTTP 200 during temporary local service verification |
| Actual protected administrator endpoint | Correctly denied access (HTTP 403); readiness blocked until a real token is configured |
| Separate worker | Empty real-database iteration succeeded; isolated synthetic job also completed in a separate process |

The Supabase value supplied in chat was not used as a SerpAPI credential, printed, written into configuration, or committed. The existing investigation adapter remains SQLite.

## Live operational validation — blocked

The executable live command was run with a cap of four searches, three sources per query, a caller-supplied illustrative $0.01/query estimate and $0.04 declared cap. It stopped at credential checks:

- **0 live search requests; 0 live source fetches; 0 provider spend caused by these commands.**
- No fallback to synthetic evidence and no invented live success/failure outcomes.
- SerpAPI and valid administrator configuration are required before real retrieval can be exercised.
- The collection command also reported the empty candidate plan explicitly. The 60-group target remains a specification, not 60 completed cases.

The price example was used only to verify the blocked command; it is not a statement of SerpAPI account pricing. Real runs require a price bound appropriate to the operator's plan.

## Reviewed baseline and learning results

| Measurement | Result |
|---|---|
| Precision@5 / NDCG@5 | **Not measured** |
| Stance precision/recall/macro-F1/confusion matrix | **Not measured** |
| Real extraction success/failure distribution | **Not measured** |
| Insufficient-evidence performance | **Not measured** |
| Reviewed citation support rate | **Not measured** |
| Human inter-reviewer agreement / kappa | **Not measured** |
| Candidate paired deltas / uncertainty | **Not measured** |
| Frozen final holdout | Not created or accessed |
| Observed factual/retrieval failure examples | Pending independently reviewed cases; no findings invented |

**Does independently reviewed feedback demonstrably improve ranking? Not yet measured.** No inference of success is drawn from the training pipeline, synthetic gate tests, or software implementation.

## Functional verification — separate from quality measurement

- **67 backend tests passed.** Existing investigation, migration preservation, feedback, source extraction, memory, leased-worker recovery, split isolation, holdout protection, promotion and rollback checks remain passing.
- Added checks cover credential redaction in reports/provider logs; durable request/cost bounds; blocked commands making no requests; candidate provenance with no automatic labels; blind packets/blank CSV sheets; independent disagreement/adjudication history; revision invalidation; legacy frozen-hash stability; paired uncertainty with a positive point estimate but inconclusive interval; paired-review agreement thresholds; confirmed-only failure observations; exclusion of holdout cases from development; and durable pending state after worker-process failure.
- `npx tsc --noEmit` and `npm run build` passed. Existing Next.js multiple-lockfile workspace-root warning remains. No frontend source changes were needed.
- `python -m investigation.smoke --with-frontend` passed: real local HTTP API → durable queue → separate worker process → explicitly offline report; source trace endpoint; protected admin allow/deny with a **temporary test token**; secret-free server logs; built frontend routes `/`, `/review`, `/evaluation`, `/history`.
- Synthetic smoke data and token were removed. It added **zero real benchmark cases** and did not configure the actual administrator environment.
- Separate service verification against the initialized real database confirmed API/frontend HTTP readiness, missing-token denial, and an empty worker iteration. Temporary servers were stopped afterward. No deployment or browser interaction automation occurred.

## Local generated report locations

Ignored directory: `backend/investigation-data/pilot-reports/` (or configured artifact directory).

- `readiness.json` / `.md`: database, credential booleans, counts, active model, service observations.
- `live-validate.json` / `.md`: explicit blocked status and zero requests.
- `collect.json` / `.md`: blocked credentials and unpopulated candidate specification.
- `status.json` / `.md`: baseline/candidate measurements pending; promotion not attempted.
- `failures.json` / `.md`: pending failure analysis with no invented observations or recommendations.
- `synthetic-service-smoke.json` / `.md`: isolated functionality result, explicitly not a quality benchmark.

These generated artifacts, databases, filled review sheets, snapshots and model files remain outside version control. The checked-in benchmark specification and CSV headers contain no collected cases or labels.

## Next actions grounded in the observed blockers

1. Configure the missing SerpAPI key and local administrator token, then rerun readiness and the bounded live command.
2. Have a curator populate actual assertion plans in the ignored pilot specification copy; retain failures and record sampling scope/biases.
3. Recruit real reviewers, complete blind initial/citation review and independent adjudication, then freeze eligible groups and measure validation performance.

There is no observed quality evidence yet to justify changing source ranking or stance heuristics. Keep the baseline active until eligible, conclusive reviewed comparisons pass the predeclared gates.
