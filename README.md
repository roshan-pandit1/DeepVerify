# DeepVerify

An evidence-based claim investigation platform: **claim/article → editable assertions → durable retrieval worker → assertion-level report → reviewed feedback → persistent research memory**.

This repository includes the first investigation milestone and the second evidence-quality/evaluation milestone. Next.js and FastAPI are retained. Blockchain, psychological/threat scoring, Telegram, and media forensics remain legacy code outside the investigation entry point. **Real-world evaluation is pending: no real reviewed corpus or live-provider credentials were available during milestone-two verification.**

## Setup

Python 3.9+ and Node.js 20.9+ are required. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-investigation.txt
cd frontend
npm ci
cp -n .env.example .env.local
cd ..
```

Review `backend/.env.investigation.example`. If `backend/.env` already exists, merge the new variables without overwriting existing settings. Otherwise:

```sh
cp -n backend/.env.investigation.example backend/.env
```

Set `INVESTIGATION_DB` to your existing SQLite **file path**, if applicable. The legacy default and new default are both `backend/deepfake.db` when launched from `backend/`. Do not silently switch databases. `DATABASE_URL` is a legacy setting; the new SQLite adapter uses `INVESTIGATION_DB`. PostgreSQL is not supported by this first milestone.

Generate an administrator token and place it in `backend/.env` (never the frontend):

```sh
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

`SERPAPI_API_KEY` enables live Google text search through the existing SerpAPI integration. No LLM, Brave, blockchain, Telegram, or media-model credentials are needed. Missing search credentials produce `unavailable` searches and an actionable partial report. Choosing **OFFLINE FIXTURES** explicitly uses fictional development evidence. It never falls back from live retrieval to fixtures, and fixtures are excluded from training.

`frontend/.env.local` must set `NEXT_PUBLIC_API_BASE_URL` to your API origin before building. If omitted, requests use the frontend origin (for an externally configured same-origin reverse proxy). There is no hard-coded API origin in the new interface. Set `FRONTEND_URL` to the frontend origin for CORS.

## Migration and application commands

Run the additive, idempotent migration against your configured database:

```sh
cd backend
../.venv/bin/python -m investigation.store
```

This reuses `claims`, `assertions`, `evidence_items`, and `audit_log_entries` with their existing SQLAlchemy names and enum values. Additive migrations 1 and 2 create investigation, metadata, jobs, searches, feedback, source-document/passage, reviewed-dataset, evaluation, and model-provenance tables. Existing rows, feedback, memory, active ranker, and rollback history are preserved. Historical evidence is not silently refetched or reclassified. Only investigations created by the new pipeline appear in its history.

In three terminals, from the repository root:

**API**
```sh
cd backend
../.venv/bin/uvicorn investigation.api:app --host 127.0.0.1 --port 8000
```

**Separate worker**
```sh
cd backend
../.venv/bin/python -m investigation.worker
```

**Frontend**
```sh
cd frontend
npm run dev
```

Open `http://localhost:3000`. API documentation: `http://localhost:8000/docs`. For a production frontend build:

```sh
cd frontend
npm run build
npm run start
```

The new API entry point is **`investigation.api:app`**, not the legacy `main:app`. A worker can process one queued job using `python -m investigation.worker --once`. API restarts do not lose queued work. A crashed worker's lease becomes reclaimable after **120 seconds**; committed assertion searches are skipped on recovery. The owner token fences late writes from an old worker. Partial investigations retry unsuccessful assertions only; create a new investigation to refresh all evidence.

## Workflow and API

1. Submit text (5–12,000 characters) or a public article URL. At most 20 assertions, each 5–1,500 characters.
2. Review, split, add, or remove assertion candidates before retrieval. Extraction is rule-based, with heuristic entities, ISO/year dates, and locations. It is not a general-purpose factuality or entity-resolution model.
3. Save assertions and queue retrieval. Evidence remains attached to its own assertion. Canonical source URLs deduplicate results within an assertion.
4. Inspect source title, original/final links, extracted passage and surrounding context (or explicitly labeled snippet fallback), publication/retrieval dates, extraction method/hashes, stance method/review status, limitations, and failures.
5. Submit relevance or stance feedback. Raw feedback remains pending. An approved stance correction changes the source-based assessment; only approved **live relevance** labels enter training exports.

Example submission:

```sh
curl -sS http://localhost:8000/api/investigations \
  -H 'Content-Type: application/json' \
  -d '{"text":"The Aurora Observatory opened in Oslo in 2024.","input_type":"text","provider":"offline"}'
```

Use the returned `claim_id`:

```sh
export INVESTIGATION_ID='replace-with-returned-id'
curl -sS -X PUT "http://localhost:8000/api/investigations/$INVESTIGATION_ID/assertions" \
  -H 'Content-Type: application/json' \
  -d '{"assertions":["The Aurora Observatory opened in Oslo in 2024."]}'
curl -sS -X POST "http://localhost:8000/api/investigations/$INVESTIGATION_ID/run"
curl -sS "http://localhost:8000/api/investigations/$INVESTIGATION_ID"
curl -sS http://localhost:8000/api/investigations
curl -sS http://localhost:8000/api/learning
```

`POST /api/evidence/{evidence_id}/feedback` accepts `reviewer` (session identifier), `dimension` (`relevance` or `stance`), and `label`. Relevance labels are `relevant`/`irrelevant`; stance labels are `supporting`/`contradicting`/`unrelated`/`needing review`. Repeated identical session/evidence/dimension/label submissions deduplicate.

## Feedback review

Open `/review`, enter the administrator token, inspect source/claim/prediction, and approve or reject with a reason. The token stays in page memory. API equivalents:

```sh
# Set this to the secret configured in backend/.env, without committing it.
read -s INVESTIGATION_ADMIN_TOKEN
export INVESTIGATION_ADMIN_TOKEN
curl -sS http://localhost:8000/api/admin/feedback \
  -H "Authorization: Bearer $INVESTIGATION_ADMIN_TOKEN"
export FEEDBACK_ID='replace-with-feedback-id'
curl -sS -X POST "http://localhost:8000/api/admin/feedback/$FEEDBACK_ID/review" \
  -H "Authorization: Bearer $INVESTIGATION_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approved","reason":"Compared the assertion with the cited passage."}'
```

Predictions are never overwritten by feedback. Approving a correction supersedes the previous approved label for that evidence/dimension and records both decisions. Revocations exclude labels from subsequent exports. Reviews and supersessions remain in `feedback_reviews`.

Administration is an initial shared bearer token, minimum 24 characters, with a single `token-administrator` audit identity. It has no individual admin accounts, role separation, rate limiting, or key rotation service. Submission/history are shared local-workspace endpoints, not private multi-user accounts. Use the documented loopback binding; authenticated multi-user deployment is a later milestone. CLI tokens passed as arguments may be visible in local process listings. The CLI also requires local filesystem access; the token does not protect against someone who already controls the database files.

## Reviewed ranking: export, train, evaluate, promote, roll back

From `backend/`, with the same database/artifact configuration and administrator token:

```sh
../.venv/bin/python -m investigation.training export --token "$INVESTIGATION_ADMIN_TOKEN"
export DATASET_ID='replace-with-exported-dataset-id'
../.venv/bin/python -m investigation.training train "$DATASET_ID" --token "$INVESTIGATION_ADMIN_TOKEN"
export MODEL_ID='replace-with-returned-candidate-id'
../.venv/bin/python -m investigation.training evaluate "$MODEL_ID" --token "$INVESTIGATION_ADMIN_TOKEN"
../.venv/bin/python -m investigation.training promote "$MODEL_ID" --token "$INVESTIGATION_ADMIN_TOKEN"
../.venv/bin/python -m investigation.training rollback baseline-v1 --token "$INVESTIGATION_ADMIN_TOKEN"
# Or restore a previously promoted candidate:
../.venv/bin/python -m investigation.training rollback "$MODEL_ID" --token "$INVESTIGATION_ADMIN_TOKEN"
```

- Baseline `baseline-v1`: deterministic lexical overlap (0.7), entity overlap (0.2), and temporal match (0.1). These are ranking weights, **not truth probabilities**. Missing publication date and missing semantic similarity have explicit feature flags. There are no semantic embeddings in this milestone.
- Candidate: scikit-learn logistic regression, deterministic seed, versioned feature definition `lexical-entities-temporal-v1`. JSON coefficients are used instead of executable pickle artifacts. Rankings are recorded at retrieval time; promotion applies to future retrievals, not old reports.
- Only approved live relevance labels are exported. The system's predictions/assessments are never ground truth. Offline fixtures and stance labels are excluded.
- Dataset snapshots use SHA-256 content IDs. Candidate IDs, feature names, scikit-learn version, coefficients, train/test membership, evaluation reports, and promotion/rollback decisions are persisted. Artifacts and datasets live in ignored `backend/investigation-data/` by default. Keep any custom artifact path outside version control.
- The original feedback-only command uses a deterministic 30% **validation** split, not a frozen final holdout. Connected components keep investigations, lexically related assertions (Jaccard ≥0.35), duplicate canonical/final URLs, document hashes, and normalized passages together. Frozen evaluation validation/holdout groups and their transitive duplicates are excluded from feedback-only exports. For human-reviewed topic groups and an independent final audit, use the three-way dataset workflow below.
- Fitting requires ≥40 eligible examples, ≥8 independent groups, ≥20 training examples, both labels in both splits, and ≥3 evaluation assertions with ≥5 judged sources and at least one relevant source each. Otherwise the command exits without fitting or promotion: **“collecting reviewed feedback.”**
- Baseline and candidate use exactly the same validation examples. Precision@5 uses denominator 5; NDCG@5 uses binary relevance with log2 discount, macro-averaged per assertion. Reports include query/example/group counts and limitations. This measures reranking of a fixed retrieval pool, not web-search recall or factual confidence.
- Promotion recomputes evaluation and requires NDCG@5 improvement ≥0.01 without reducing precision@5. Any feedback change invalidates the snapshot until re-export/retraining. Failed evaluation cannot activate a candidate. No auto-training or auto-promotion occurs. Historical evaluation reports and decisions remain in the database.
- Rollback to baseline always works. Candidate rollback requires a previously promoted model. Missing/corrupt active artifacts fall back to the baseline and expose that state.

Every investigation updates **retrieval memory**, not model weights. Related research uses versioned `lexical-jaccard-v1` behind an embedding interface. The UI links matching previous investigations and dates; prior evidence is never silently copied into fresh live results. Offline and live memory are separated.

## Source and assessment boundaries

`SOURCE_EXTRACTION_PROVIDER=public-article` (default) fetches search-result URLs through a replaceable `SourceProvider`. No additional credentials or model downloads are required. `snippets-only` disables fetching and records an explicit fallback. Offline fixture investigations never fetch live sources.

`article-dom-v1` extracts titles, paragraph-based main text from `<article>` (or an article-metadata-marked main/body container), and optional publisher metadata/JSON-LD/time-element dates. The paragraph most lexically related to the assertion is selected with its preceding/following paragraphs. These are relevance heuristics, not proof. Every source stores original/final URLs, retrieval timestamp, method/version, normalized-text SHA-256 and response-body SHA-256. The stored main text and passage/context character offsets make quotes traceable. `GET /api/sources/{source_id}` returns the stored text and metadata; page HTML/scripts are not served or executed.

Blocked/challenge pages, publisher-marked paywalls, non-articles, unsupported formats, redirect limits, unsafe destinations, timeouts, network failures, and insufficient article text have explicit extraction statuses. Search snippets survive these failures as **search snippet fallback**, with the error shown on the card. Successful passage extraction also preserves the original snippet. Dates are unverified publisher/provider metadata; a `<time>` fallback is explicitly marked as possibly not a publication date. Extraction can miss layout-specific content; it is not a browser, paywall bypass, or guarantee of complete article capture. Source hashes support traceability, not authenticity certification.

`STANCE_CLASSIFIER=guarded-rules` selects the replaceable `StanceClassifier` implementation `guarded-passage-rules-v2`. It flags negation differences, missing/mismatched dates, locations and named entities, quoted/attributed claims, and time-sensitive wording as `needing review`. It does not infer contradiction from a mismatch or support from keyword overlap. With no ambiguity flags, zero overlap is lexical `unrelated` triage; other passages remain `needing review`. `STANCE_CLASSIFIER=legacy` provides the original baseline. Unknown classifier settings fail explicitly; no remote model or hidden credential fallback exists. No improved stance accuracy is claimed.

Sufficiency uses approved source-stance reviews rather than unreviewed classifier output. It remains the first milestone's limited source-based policy, not an independently validated truth judgment. Approved stances can yield supported, contradicted, mixed, or insufficient-evidence assessments; one approved supporting source is source-level support only. Ranking scores, source reputation, and lack of support are never factual confidence or proof of falsehood.

Article fetching permits only public HTTP/HTTPS on ports 80/443. All resolved addresses must be public; connections are pinned to a validated IP with hostname-verified TLS. Redirects are revalidated (maximum four requests). DNS lookup (3 seconds), socket operations (up to 5 seconds), total response deadline (20 seconds), and 1 MB response limits are bounded. Compressed and non-text formats are rejected; plain text without article structure yields an explicit non-article fallback. Main text is capped at 200,000 characters and paragraphs at 12,000 characters. Scripts/styles/navigation are stripped. Page instructions, including JSON-LD content, are treated as data only. The worker renews its lease between bounded source fetches.

## Reviewable datasets and independent stage evaluation

The versioned format is `reviewed-investigation-v1`; see [dataset format and review protocol](docs/evaluation-dataset.md). Datasets snapshot completed/partial assertion reports, temporal context, human-assigned related-topic groups, coverage categories, source/passages, machine predictions, and separately reviewed labels. Relevance, stance, sufficiency, and citation-support approvals are independent. Existing approved feedback is captured as provenance/proposal, **not automatically approved evaluation labels**.

From `backend/`, using your administrator token (the evaluation CLI places its global `--token` **before** the command):

```sh
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  create --name reviewed-evidence --version 1 --seed 17
export EVAL_DATASET_ID='returned-dataset-id'
export ASSERTION_ID='assertion-id-from-a-completed-or-partial-report'
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  add "$EVAL_DATASET_ID" --assertion "$ASSERTION_ID" \
  --group 'human-assigned-topic-group' --temporal-context 'Specify the assertion as-of date or explain why timeless' \
  --categories time-sensitive relevant-not-entailing
export CASE_ID='returned-case-id'
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" export "$EVAL_DATASET_ID"
```

Use actual topic/context/categories for the case, not the placeholders above. Available coverage categories: `supported`, `contradicted`, `mixed`, `time-sensitive`, `insufficient`, `relevant-not-entailing`, `duplicate-syndicated`. They are sampling tags, not approved ground truth. Reports list missing coverage. For fixture-only datasets, add `--synthetic` to `create`; synthetic datasets cannot train promotable candidates or pass promotion gates.

Review the exported JSON plus cited sources. Record each independently determined label; replace the variables below with your actual review decisions. Do not invent reviewers or approve labels merely to satisfy a data threshold.

```sh
export EVIDENCE_ID='captured-evidence-id'
export REVIEWER='your-actual-reviewer-identifier'
export RELEVANCE_LABEL='relevant-or-irrelevant'
export STANCE_LABEL='supporting-or-contradicting-or-unrelated-or-needing review'
export SUFFICIENCY_LABEL='sufficient-or-insufficient'
export CITATION_LABEL='justified-or-not justified-or-needs review'
export REASON='Explain your source comparison and limitations'
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  label "$CASE_ID" --target "$EVIDENCE_ID" --dimension relevance --label "$RELEVANCE_LABEL" --reviewer "$REVIEWER" --status approved --reason "$REASON"
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  label "$CASE_ID" --target "$EVIDENCE_ID" --dimension stance --label "$STANCE_LABEL" --reviewer "$REVIEWER" --status approved --reason "$REASON"
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  label "$CASE_ID" --target "$EVIDENCE_ID" --dimension citation --label "$CITATION_LABEL" --reviewer "$REVIEWER" --status approved --reason "$REASON"
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  label "$CASE_ID" --dimension sufficiency --label "$SUFFICIENCY_LABEL" --reviewer "$REVIEWER" --status approved --reason "$REASON"
```

Repeat passage-level labels for every evidence item and sufficiency for every assertion. `--status proposed`/`rejected` records unapproved judgments. Review history and superseded approvals remain stored. Cases with no evidence need a separately reviewed sufficiency label; they still contribute to insufficient-evidence evaluation.

```sh
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" freeze "$EVAL_DATASET_ID"
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  evaluate "$EVAL_DATASET_ID" --partition validation
../.venv/bin/python -m investigation.training train-reviewed "$EVAL_DATASET_ID" --token "$INVESTIGATION_ADMIN_TOKEN"
export MODEL_ID='returned-candidate-id'
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  evaluate "$EVAL_DATASET_ID" --model "$MODEL_ID" --partition validation
../.venv/bin/python -m investigation.training promote "$MODEL_ID" --token "$INVESTIGATION_ADMIN_TOKEN"
# Only after model selection/promotion is complete: consume the final audit once.
../.venv/bin/python -m investigation.evaluation --token "$INVESTIGATION_ADMIN_TOKEN" \
  evaluate "$EVAL_DATASET_ID" --model "$MODEL_ID" --partition holdout
../.venv/bin/python -m investigation.training rollback baseline-v1 --token "$INVESTIGATION_ADMIN_TOKEN"
```

Freezing requires independent approved labels and locks the snapshots, reviews, group membership, random seed, and SHA-256 fingerprint. Connected components use investigation IDs, human topic groups, lexical relatedness, canonical/final URLs, exact normalized passages, and extracted document hashes (including syndicated copies). Components are deterministically partitioned approximately **60% train / 20% validation / 20% holdout**. All linked cases stay together. Small datasets can be frozen for review but report insufficient data and cannot meet training gates. Cross-version split conflicts and copied holdout topics/sources are rejected; a new final audit needs disjoint holdout material. Human topic review remains necessary for paraphrases and rewritten syndication.

`train-reviewed` fits **only approved relevance labels in the train partition**; model selection/promotion sees validation only. Neither generated assessments nor stance/sufficiency labels are ranking targets. Existing approved relevance feedback remains connected through the original export/train commands, with frozen validation/holdout components excluded. Thresholds remain ≥40 train+validation examples, ≥8 train+validation components, ≥20 training examples, both classes in each split, and ≥3 validation assertions with ≥5 sources and a relevant source each. In practice, the three-way split needs enough independent groups to supply those three validation assertions.

Stage reports persist JSON and readable Markdown under `INVESTIGATION_ARTIFACTS`, plus database audit records. View them at **`/evaluation`** with the administrator token, or `GET /api/admin/evaluations` with the bearer header:

- **Ranking:** baseline/candidate precision@5 and NDCG@5 on identical IDs, recorded example fingerprint, counts, label distribution, excluded short queries, and validation gate. No changes to search-query generation or retrieval recall are claimed.
- **Stance:** guarded-rules versus legacy baseline; fixed-class per-class precision/recall/F1, macro-F1, label distribution and confusion matrix. Zero denominators score zero, and absent declared classes remain in macro-F1.
- **Extraction:** recorded attempts, successes, categories and success rate; disabled/offline/legacy-not-attempted cases are not actual extraction attempts. The snippet-only baseline has no full-source passages. This measures operational extraction coverage, not human-verified fidelity.
- **Sufficiency:** captured report assessment versus independent sufficiency review, including insufficient-case precision/recall and confusion matrix; compared with an always-insufficient baseline. No new sufficiency accuracy is asserted.
- **Citation support:** human-reviewed justified/not-justified/needs-review counts for citations attached to non-insufficient assessments, plus justified rate among resolved judgments. There is no automatic citation-support probability.

Ranking promotion requires validation NDCG@5 improvement ≥0.01 with no precision@5 regression. Stance metrics do not authorize ranking promotion. Insufficient data, malformed/unavailable evaluation, or no improvement retain the currently active model and record rejection; rollback remains available. A frozen holdout is reserved atomically for **one model/method audit**; repeating the same request returns the saved report, and other model/method requests are rejected. A candidate must already have been selected/promoted on validation. Once the final audit starts, further fitting/validation/promotion on that dataset is closed. Holdout results cannot authorize promotion. An interrupted audit keeps its reservation rather than silently exposing the holdout again. Local database/filesystem administrators remain trusted; this is procedural isolation, not a cryptographic data enclave.

## Verification

```sh
cd backend
../.venv/bin/python -m pytest investigation_tests -q
cd ../frontend
npx tsc --noEmit
npx eslint src/components/InvestigationWorkspace.tsx src/app/review/page.tsx src/app/evaluation/page.tsx src/lib/investigation-api.ts src/app/page.tsx src/app/history/page.tsx
npm run build
```

The dedicated investigation tests avoid legacy test fixtures that mock unrelated heavyweight media dependencies. Synthetic fixtures check software functionality only, not real-world factual accuracy or ranking improvement. See `docs/rebuild-status.md` for results, limitations, and credential-dependent checks.

## Recovery

Work is checkpointed on `rebuild/investigation-platform`. `git log --oneline rebuild/investigation-platform` lists local commits. The user pushed milestone one through `ce79374`. **Milestone-two changes are local only: no push or deployment; their remote backup remains pending authorization.** Existing records and legacy code were preserved. Generated datasets, credentials, cookies, databases, and model artifacts are not included in commits.

Next milestone: collect genuinely reviewed real-world datasets, validate source extraction and provider behavior on real sites, review topic/syndication grouping, and measure stage quality plus ranking improvement before making accuracy claims.
