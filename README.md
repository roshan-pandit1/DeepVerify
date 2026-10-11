# DeepVerify

An evidence-based claim investigation platform: **claim/article → editable assertions → durable retrieval worker → assertion-level report → reviewed feedback → persistent research memory**.

This is the rebuilt first milestone. The published legacy implementation was inspected rather than treated as evidence of earlier milestone completion. Next.js and FastAPI are retained. Blockchain, psychological/threat scoring, Telegram, and media forensics remain legacy code outside the new investigation entry point.

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

This reuses `claims`, `assertions`, `evidence_items`, and `audit_log_entries` with their existing SQLAlchemy names and enum values. It creates investigation, metadata, jobs, searches, feedback, review-history, and model-provenance tables; it does not replace legacy rows or reinterpret their historical confidence scores. Only new investigations appear in the new history. Existing legacy records remain in their original tables.

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
4. Inspect source title, link, search snippet, provider-supplied publication date if available, retrieval time, method, ranking method, stance prediction, limitations, and query failures.
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
- Connected-component splits keep each investigation, lexically related assertions (Jaccard ≥0.35), duplicate canonical URLs, and duplicate normalized passages together, including transitive connections. The holdout is a deterministic 30% of components. Lexical grouping can miss semantic paraphrases; review topic grouping before making real-world performance claims. A heavily shared source may collapse data into too few independent groups.
- Fitting requires ≥40 eligible examples, ≥8 independent groups, ≥20 training examples, both labels in both splits, and ≥3 evaluation assertions with ≥5 judged sources and at least one relevant source each. Otherwise the command exits without fitting or promotion: **“collecting reviewed feedback.”**
- Baseline and candidate use exactly the same held-out examples. Precision@5 uses denominator 5; NDCG@5 uses binary relevance with log2 discount, macro-averaged per assertion. Reports include query/example/group counts and limitations.
- Promotion recomputes evaluation and requires NDCG@5 improvement ≥0.01 without reducing precision@5. Any feedback change invalidates the snapshot until re-export/retraining. Failed evaluation cannot activate a candidate. No auto-training or auto-promotion occurs. Historical evaluation reports and decisions remain in the database.
- Rollback to baseline always works. Candidate rollback requires a previously promoted model. Missing/corrupt active artifacts fall back to the baseline and expose that state.

Every investigation updates **retrieval memory**, not model weights. Related research uses versioned `lexical-jaccard-v1` behind an embedding interface. The UI links matching previous investigations and dates; prior evidence is never silently copied into fresh live results. Offline and live memory are separated.

## Source and assessment boundaries

Live evidence is currently **search snippets**, not full-source article passages. Article URL ingestion extracts page text only for generating editable assertion candidates; it does not make retrieved evidence into full-source passages. Dates are optional provider metadata, not independently verified publication dates.

Stance triage marks zero lexical overlap as `unrelated`; other evidence is `needing review`. Keyword overlap never becomes automatic support. Approved stance reviews produce supported, contradicted, mixed, or insufficient-evidence assessments, with explanations and source-level limitations. One approved supporting source means source-level support, not independently established truth. Source reputation is not used as proof; missing evidence is not falsehood. No probability-like confidence displays appear in the new experience.

Article fetching permits only public HTTP/HTTPS on ports 80/443. All resolved addresses must be public; connections are pinned to a validated IP with hostname-verified TLS. Redirects are revalidated (maximum four requests). DNS lookup, socket operations, total read deadline, and 1 MB response limits are bounded. HTML/plain text only; compressed responses are rejected. Scripts/styles/navigation are stripped. Source content remains untrusted data; no source instructions are executed. Extraction does not support JavaScript-rendered pages or paywall bypassing.

## Verification

```sh
cd backend
../.venv/bin/python -m pytest investigation_tests -q
cd ../frontend
npx tsc --noEmit
npx eslint src/components/InvestigationWorkspace.tsx src/app/review/page.tsx src/lib/investigation-api.ts src/app/page.tsx src/app/history/page.tsx
npm run build
```

The dedicated investigation tests avoid legacy test fixtures that mock unrelated heavyweight media dependencies. Synthetic fixtures check software functionality only, not real-world factual accuracy or ranking improvement. See `docs/rebuild-status.md` for results, limitations, and credential-dependent checks.

## Recovery

Work is checkpointed on `rebuild/investigation-platform`. `git log --oneline rebuild/investigation-platform` lists local commits. **Nothing is pushed or deployed; remote backup remains pending until a push is authorized.** Existing legacy code and local files were preserved. Generated datasets, credentials, cookies, databases, and model artifacts are not included in rebuild commits.

Next milestone: full-source evidence passages with extraction provenance, a reviewed real-world evaluation dataset with human-validated topic grouping, and real-provider validation.
