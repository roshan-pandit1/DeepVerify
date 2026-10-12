# Rebuild status — milestone two

Verified locally on 2026-10-12. Branch: **`rebuild/investigation-platform`**.

## Repository and recovery

- Started milestone two from clean `ce79374`, tracking the milestone-one branch that the user pushed. Inspected the implementation, Git status, schema, tests, `frontend/AGENTS.md`, and installed Next.js guides before changing code.
- Milestone-one checkpoints: `a5df4da`, `fe93a5e`, `ce79374` (already pushed by the user).
- Milestone-two backend checkpoint: **`f58af2d`** — traceable passages, guarded stance interface, reviewable datasets, independent stage evaluation, and protected frozen holdout; 55 backend checks and synthetic CLI smoke passed.
- Frontend/documentation checkpoint hashes appear in `git log --oneline` and the completion report.
- **No milestone-two push or deployment. Local milestone-two commits are not remote backups; their remote backup remains pending authorization.**

## Implemented capabilities

- Additive migration 2 adds source documents/passages, evaluation datasets/cases/independent label history, evaluation reports and one-shot holdout reservations. Existing investigations, assertions, evidence, feedback, memory and model history remain intact; historical evidence is not silently reprocessed.
- Public-article extraction behind `SourceProvider`: title, paragraph-based main text, optional publisher date/provenance, original/final URLs, retrieval time, extraction version, body/text hashes, passage/context offsets, stored surrounding paragraphs, and retained original snippet.
- Public-only DNS-pinned fetches with verified TLS, bounded DNS/socket/read operations, redirect revalidation, size limits and no script execution. Explicit blocked/paywall/challenge/non-article/unsupported/timeout/network/extraction statuses; labeled snippet fallback; no access bypass.
- Replaceable stance interface. `guarded-passage-rules-v2` flags negation, entity/date/location mismatches, attribution and time sensitivity. It does not infer entailment from overlap or contradiction from missing support. Source sufficiency remains separately based on reviewed stances.
- Versioned `reviewed-investigation-v1` dataset capture/export/review/freeze CLI with topic groups, temporal context, coverage tags, source snapshots, machine predictions, independent relevance/stance/sufficiency/citation reviews, reviewer identifiers, approval state and history.
- Connected-component train/validation/holdout assignments and seeds persist with a frozen hash. Topic/investigation/URL/document-hash/passage links isolate related and duplicate sources, including transitive links. Cross-version split conflicts and copied holdout material are rejected.
- Stage reports: identical-example precision@5/NDCG@5; stance per-class precision/recall/F1, macro-F1 and confusion matrices; extraction outcomes; insufficient-evidence performance; independently reviewed citation support. Counts, distributions, versions, baseline comparisons, missing coverage and limitations are included.
- Reviewed-dataset ranking uses train only, validation for selection/promotion, and a one-shot final holdout. Repeated identical final requests return the saved report. Different model/method audits, further fitting and further validation/promotion on that dataset are blocked after final auditing begins. Interrupted audits retain their reservation.
- Original approved-feedback ranking export/train workflow remains available, excluding reserved evaluation components. Promotion rejection retains the active model; rollback remains available. Synthetic datasets cannot train promotable candidates or pass gates.
- Evidence cards show passage/fallback type, publication/fetch dates, stored context, extraction limitations, hashes and offsets, method and review state. The review desk now includes stored context. `/evaluation` exposes protected saved stage reports and promotion decisions; Markdown/JSON reports also persist locally.

## Checks actually run

- `python -m pytest investigation_tests -q`: **55 passed**. Includes all prior investigation/feedback/memory/worker/rollback checks plus:
  - private/reserved/multicast destinations, mixed DNS and unsafe redirects;
  - source extraction metadata/hashes/offsets/context, script removal, paywall/challenge/non-article failures, stored fallback and assertion/source association;
  - negation/date/entity/location/quotation/time-sensitive review flags;
  - independent evaluation approvals, prior relevance feedback not approving stance/sufficiency, frozen review immutability, synthetic training refusal;
  - transitive topic/URL/document-hash/syndicated-passage split isolation, reserved-feedback exclusion;
  - identical baseline/candidate examples, train/validation/holdout isolation, one-shot final audits, no post-holdout tuning;
  - insufficient-data and failed-evaluation rejection, retention of an already active candidate, and rollback;
  - idempotent migration and preservation of legacy records, memory and active model.
- Synthetic CLI smoke in an isolated temporary database: **passed** create/add/export, rejection before independent approvals, label review, freeze, insufficient-data evaluation, JSON/Markdown generation, source-document API, and protected administrator report API. Temporary data was cleaned up.
- `npx tsc --noEmit`: **passed**.
- Targeted ESLint for the investigation workspace, review/evaluation pages and API types: **passed**.
- `npm run build`: **passed**, including `/evaluation`. Existing multiple-lockfile workspace-root warning remains.
- No browser interaction automation was run; build/type/lint checks do not establish browser end-to-end behavior.

## Measured results and real-data availability

- The configured local environment has **no `SERPAPI_API_KEY` and no investigation database file**. No real reviewed corpus was available to capture/evaluate.
- **No real reviewed data demonstrates an improvement over the baseline.** No real candidate was trained or promoted, and no real stance/extraction/sufficiency accuracy was measured.
- Synthetic tests exercise gate acceptance/rejection using intentionally constructed features and fixture reviewer identifiers. Their scores are not real-world benchmarks or evidence of learning quality.
- Real-provider checks were **not run** because credentials were unavailable. Article-network tests used deterministic local/mock responses; broad live-site extraction compatibility is unvalidated.
- Current operational learning state for a new database remains **collecting reviewed feedback**, with the deterministic baseline active.

## Remaining limitations

- Article DOM/metadata extraction is heuristic: no JavaScript rendering, PDF extraction, paywall bypass, or guarantee that every relevant section is captured. Dates are unverified publisher/provider metadata. Extraction success measures parser/fetch completion, not human-verified extraction fidelity.
- Stance is conservative rule-based triage with explicit review flags, not a validated semantic model. Sufficiency remains the limited reviewed-source policy and needs an independently reviewed real dataset.
- Ranking evaluation measures reranking of a collected source pool, not web retrieval recall or query generation. Human topic review is required for semantic paraphrases/rewritten syndication; exact hashes cannot detect all duplicates.
- A frozen dataset cannot be edited. New final audits require disjoint holdout material; shared sources can collapse groups and prevent eligibility. Small samples report insufficiency; no automatic fitting or promotion occurs.
- Review identity is administrator-supplied under the shared token; it is not independently authenticated human identity. The local SQLite/filesystem administrator remains trusted. Account-level privacy, PostgreSQL, distributed deployment hardening and browser automation remain future work.

## Next milestone

1. Supply live-provider credentials and validate a documented sample of public sources, redirects, failure classes, dates, context and passage fidelity.
2. Collect genuinely reviewed relevance/stance/sufficiency/citation labels across all coverage categories, with independent reviewer provenance and manually checked topic/syndication groups.
3. Freeze a disjoint final audit set before model selection, measure each stage and compare the reviewed ranker to baseline on validation, then perform the one-shot final audit.
4. Add browser workflow automation and individual reviewer accounts before multi-user deployment.
