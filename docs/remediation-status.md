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
