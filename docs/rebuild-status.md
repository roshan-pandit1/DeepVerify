# Rebuild status — milestone three

Verified locally on **2026-10-12**. Branch: **`rebuild/investigation-platform`**.

## Repository and recovery

- Inspected the repository, README, prior status, schema, tests and applicable `frontend/AGENTS.md`. Milestone-two commits `f58af2d` and `983db4e` were present at task start; the working tree was initially clean.
- During the pause, foundation commit **`55fc57d`** appeared with the pilot workflow. Git's remote-tracking reflog records an external push of that commit. The agent preserved it and did not perform that push.
- Local verification checkpoint **`7dedf4e`** adds isolated service smoke, durable worker-process failure reporting and the corresponding check. Backend suite: 67 passing tests; production build/type check and process smoke passed.
- The final documentation checkpoint is listed in `git log --oneline` and the completion report. **Subsequent checkpoints remain local until a push is authorized; no deployment was performed.**

## Implemented in milestone three

- Additive migration 3: durable live-run/request budgets, search/source latency records, worker observations, pilot review policies, independent opinions/adjudication history and confirmed failure observations. Existing investigations, feedback, source snapshots, dataset versions/hashes, split assignments, final-audit reservations, promotion and rollback records remain preserved.
- Repeatable readiness command checks database/migrations, credential booleans, counts, active/effective ranker, job/worker observations, optional API/frontend/admin HTTP status and evaluation eligibility without displaying secrets.
- Bounded SerpAPI live-validation command uses four unlabeled factual/temporal/qualified/insufficient-evidence probes plus a public non-article extraction probe. Search/source caps, per-query cost bound and durable reservations constrain retries/crashes. Missing credentials produce a blocked report with zero requests, never fixtures masquerading as live evidence.
- Versioned, unpopulated 60-group pilot specification across six topics, explicit language/geographic scope and sampling biases. Bounded collection preserves assertion/context, claim/source groups, snapshots/hashes, URLs, timestamps, extraction limitations and raw candidate status.
- Blind initial JSON/Markdown packets and blank CSV response sheets; separate citation phase; actual reviewer identifiers and timestamps; at least 20% double-reviewed groups; explicit adjudication, preserved disagreements and invalidated stale approvals. No machine or human opinion auto-approves itself. Kappa requires enough nondegenerate paired reviews.
- Stage evaluation retains identical-example ranking, stance, extraction, sufficiency and citation reports, adding coverage, review-provenance counts, paired per-claim differences, category regressions and seed-persisted component-bootstrap intervals. Existing point gates are strengthened with an uncertainty gate. Inconclusive/failed/insufficient evaluation leaves the active model unchanged.
- Frozen final audit remains separate from training/development. Existing final reports are returned historically for the same artifact, not recomputed silently with new metrics. Final-audit reservations and rollback remain intact.
- Development-only failure analysis reports traceable approved errors and independently confirmed human observations. Source age does not automatically mean stale; unknown web recall and misleading-context claims are not invented.
- Repeatable isolated HTTP/API/worker/admin/frontend smoke with temporary synthetic data and token, cleanup and log-secret checks.

## Observed environment and measurements

- Database was absent and is now initialized through migration 3.
- `SERPAPI_API_KEY`: **missing**. Valid `INVESTIGATION_ADMIN_TOKEN`: **missing**. Values were not printed.
- Real investigations: **0**; evidence items: **0**; benchmark cases: **0**; independent opinions: **0**; approved feedback/evaluation labels: **0**.
- Active and effective ranker: **`baseline-v1`**. No real fitting, promotion, final audit or rollback was necessary or attempted.
- Live-validation and collection commands produced **blocked reports** with **0 external provider/source requests**. The pilot specification remains unpopulated.
- Reviewed baseline ranking, stance, extraction, sufficiency, citation support, agreement and candidate improvement: **not measured**. Observed quality failure analysis: **pending**.
- **Does independently reviewed feedback demonstrably improve ranking? Not yet measured.** Synthetic tests are functionality checks only.

## Checks actually run

- `python -m pytest investigation_tests -q`: **67 passed**, including original regression workflows and new redaction, budget, provenance, blind-review, disagreement, agreement-threshold, pending-state, uncertainty, holdout-exclusion and process-failure checks.
- `npx tsc --noEmit`: **passed**.
- `npm run build`: **passed**. Existing multiple-lockfile workspace-root warning remains; frontend source was unchanged.
- `python -m investigation.smoke --with-frontend`: **passed** for real local HTTP API, separate worker, offline report, source API, protected admin allow/deny, secret-free logs and built frontend routes. Temporary fixture data was cleaned up; zero real benchmark cases added.
- Actual initialized-database service check: API/frontend HTTP 200; administrator correctly blocked without its token; separate empty worker iteration succeeded. Temporary servers were stopped. No browser interaction automation was run.
- Actual readiness/live/collection/status/failure commands generated JSON/Markdown under the ignored artifact directory. See [observed results](milestone-three-results.md) for the report inventory and exact distinctions.

## Remaining gaps and limitations

- No live provider validation or real-source benchmark collection has occurred without credentials. No real human reviewers or approved labels are available; no real quality/improvement claim is supported.
- English/public-web convenience sampling and a 60-group target are not population representativeness or statistical adequacy. Source availability, search ranking and curator/reviewer choices bias the sample.
- DOM extraction, publication dates, stance triage and sufficiency remain heuristic/limited as documented in milestone two. No speculative quality changes were made without observed errors.
- Exact text/URL hashes and human groups cannot automatically resolve all rewritten syndication or semantic paraphrases. Inspect groups before freezing; shared sources can collapse the number of independent components.
- Bootstrap intervals are descriptive development estimates, especially with small samples or repeated selection; they do not turn ranking scores into factual confidence. True web recall requires independently identified reference evidence.
- Shared-token administration records self-reported reviewer identities, not verified accounts. Practical blinding does not prevent a trusted filesystem administrator from inspecting predictions. SQLite remains the storage adapter; Supabase configuration was not substituted for retrieval credentials.

## Next step

Configure SerpAPI/admin secrets locally, populate curator-selected real plans, run bounded collection, obtain independent reviews/adjudication, then freeze and evaluate. Keep the baseline active until existing and strengthened gates pass on eligible development data, and use the final holdout only through the preserved one-shot audit workflow.

Exact commands: [README](../README.md). Review definitions/protocol: [pilot review guide](pilot-review-guide.md). Specification: [pilot-benchmark-spec.json](pilot-benchmark-spec.json).
