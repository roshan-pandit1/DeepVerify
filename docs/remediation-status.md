# Sequential remediation — 2026-10-13

Work starts from clean `main` commit `44df135`, on the new local branch
`rebuild/investigation-platform`. No push or deployment is authorized.
Historical milestone reports describe earlier environments, not this checkout.

## 1. Verification environment and baseline

- Created root `.venv` with Python 3.9.6; installed
  `backend/requirements-investigation.txt`. Python 3.14 was also available but
  was not selected for these older pinned scientific dependencies.
- Installed Node 22.23.3 in `/tmp`, verified against the official Node release
  SHA-256 manifest. `.node-version` selects supported Node 22; the frontend
  requires Node >=20.9. npm 10.9.9 installed the existing frontend lockfile.
- Commands (activate `.venv` and put Node on PATH for your environment):
  `python3 -m venv .venv`, `.venv/bin/python -m pip install -r backend/requirements-investigation.txt`,
  `cd frontend && npm ci`.
- Backend baseline: `cd backend && ../.venv/bin/python -m pytest investigation_tests -q`
  **67 passed**. No database containing user records was used by this suite.
- Frontend baseline: `npx tsc --noEmit` passed. Documented investigation-only
  ESLint command passed. Full `npm run lint` failed with **15 pre-existing errors
  and 9 warnings** in legacy components/routes and `frontend/lib/api.ts`.
  These are separate from investigation changes; the lint rules were not weakened.
- Initial sandbox installs could not reach package registries; approved network
  installation succeeded. Syntax checks are not treated as runtime tests.
- `npm run build` failed because Turbopack could not bind its compilation port
  (`Operation not permitted`), including the approved retry. The supported
  alternative `npm run build -- --webpack` **passed**. Both builds reported the
  pre-existing multiple-lockfile root warning.

Subsequent sections record each checkpoint's checks and limitations. Commit IDs
are available in the sequential Git log and the completion report.

## 2. Startup and deployment

Verified the mismatch. API and worker now have explicit launcher roles; default
startup installs/imports no legacy media, Telegram or blockchain code. Storage
paths are independent of working directory; private deployments require explicit
absolute paths. Compose provisions both processes on one host with the same bind
mount; Procfile/Nixpacks alone do not provision workers or shared storage.

Checks: from backend, `../.venv/bin/python -m pytest investigation_tests/test_runtime.py investigation_tests/test_foundation.py investigation_tests/test_evaluation.py -q`
(**37 passed**); `../.venv/bin/python -m investigation.smoke` (**passed**, including
API restart with queued work and separate worker). Smoke required approved local
socket access. `bash -n backend/start.sh`, `git diff --check` and
`DEEPVERIFY_DATA_DIR=/tmp docker compose --env-file backend/.env.investigation.example config --no-env-resolution --quiet`
passed. Containers were not built or deployed; shared-mount/UID setup remains an
operator requirement. An initial pytest invocation from root failed import
collection; the documented backend working-directory invocation passed.

## 3. Legacy URL ingestion

Verified route/background/Telegram paths. The yt-dlp graph includes extractor,
redirect, manifest/fragment and potentially external downloader requests; no
complete egress boundary exists here. Removed execution of that downloader and
fail closed for **all** URLs, with a clear 503 at the API and a disabled result at
the shared processor. No initial-URL-only security claim or unsafe opt-in flag.
File uploads remain optional. Investigation fetching is unchanged.

`cd backend && ../.venv/bin/python -m pytest investigation_tests/test_legacy_safety.py investigation_tests/test_ingestion.py investigation_tests/test_foundation.py -q`:
**38 passed**. Includes legacy private/metadata/public/redirect/manifest rejection,
file-only acceptance, and existing permitted public fetch/DNS pinning/private
redirect checks. No live downloader or media-model execution was performed.

## 4. Legacy upload memory and cleanup

Verified unbounded read-before-limit. Replaced it with a 64 KiB bounded receiver,
reading at most one byte beyond the configured limit and returning HTTP 413.
The cleanup scope includes database persistence/job registration and catches
cancellation; server filenames ignore supplied filenames. Documented upstream
multipart/body/spool limits. No media-model behavior was changed.

`cd backend && ../.venv/bin/python -m pytest investigation_tests/test_legacy_upload.py investigation_tests/test_legacy_safety.py -q`:
**15 passed** (accepted/exact-limit, oversize early stop, read failure,
cancellation, persistence failure, preserved pre-existing directory, URL guards).
These exercise the actual upload helper; the heavyweight legacy application's
full pipeline was not started. Also corrected the prior section's test count to
38 (the actual result); no prior commit was rewritten.

## 5. Cookie hygiene

Confirmed tracking without printing contents. Removed only the index entry;
verified the surviving local file against its pre-change SHA-256 without printing
the hash or values. Exact path/common exports are ignored. Non-secret domains
identify YouTube and Instagram. Removed obsolete runtime advice to supply cookies;
URL ingestion no longer loads them. README documents historical exposure and
account-owner session review/invalidation. No session was invalidated and no
history was rewritten.

Checks: `git ls-files backend/cookies.txt` empty; `git check-ignore -q backend/cookies.txt`
passed; programmatic scan found no cookie values in staged additions or install
logs. Staged deletion was reviewed via metadata/stat only. Legacy safety suite:
**9 passed**. Historical cookie content remains in prior commits.

## 6. Per-result retrieval isolation

Verified whole-assertion loss from malformed provider items/URLs. Provider mapping
and worker validation now isolate each item. Separate result transactions retain
successes and roll back failed source/evidence graphs; canonical deduplication
survives retries. Mixed and all-invalid outcomes are distinct. Additive migration
4 stores safe result-failure references. Private structural diagnostics exclude
raw exception messages/locals/URLs to avoid leaking arbitrary sensitive content.

`cd backend && ../.venv/bin/python -m pytest investigation_tests/test_result_isolation.py investigation_tests/test_foundation.py investigation_tests/test_sources.py investigation_tests/test_evaluation.py -q`:
**51 passed**, covering mixed/all-invalid/duplicates/provider failure/retry,
persistence rollback, private log permissions/redaction, migrations and evaluation
protections. Global storage outages are not recoverable without repairing storage.

## 7. Frontend response ordering

Verified stale load/navigation race. Selections now increment a generation and
abort pending loads. Generation checks also protect against transports that
ignore cancellation; new investigation and unmount invalidate loads/actions.
Polling is serial, abortable and scoped to the selected investigation. Loading,
errors, feedback reloads and mutation continuations respect selection changes.

Added Vitest/Testing Library following the installed Next.js guide. The initial
install had a Node-types peer conflict; aligning types to Node 22 resolved it.
The selected jsdom version requires Node 22.22.2+ on the 22.x line; manifest and
README now declare compatible runtimes. The lockfile includes test dependencies.

From frontend: `npm test` **6 passed** (deliberately reordered responses, new
selection, errors, obsolete polling, serial polling/refresh, unmount).
`npx tsc --noEmit` passed; `npx eslint src/components/InvestigationWorkspace.tsx src/lib/investigation-api.ts tests vitest.config.mts`
passed without warnings; `npm run build -- --webpack` passed. Initial polling
tests installed fake timers after scheduling real timers; corrected the test
setup and reran. These are DOM behavioral tests, not live-browser/live-provider
tests. Full legacy lint failures remain the recorded baseline.

## 8. Generated dependencies

Confirmed 4,136 tracked root node_modules files. Removed index entries only;
verified local `node_modules/lucide-react/package.json` remains. Added recursive
node_modules ignore. Kept root manifests/lockfile: it is a historical standalone
icon dependency with no root app scripts; frontend has an independent package.
Explicit frontend bundler/tracing roots remove the multiple-lockfile warning.

Clean frontend `npm ci` passed (**514 packages**); clean root lockfile installation
in `/tmp/deepverify-root-install` passed (**2 packages**), preserving the existing
root installation. `git ls-files 'node_modules/**' '**/node_modules/**'` is empty;
ignore checks and `git diff --check` passed. Frontend behavioral tests and the
Webpack production build were rerun after the clean installation.
