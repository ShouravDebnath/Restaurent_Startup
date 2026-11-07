# Restaurant AI Monitoring

Privacy-first restaurant table operations SaaS. Phases 0–2 provide the specification, repository foundation, a real multi-restaurant PostgreSQL database, local sign-in, backend/database authorization, and connected configuration screens. Live camera access, inference, floor-map simulation, tasks, analytics, and billing remain later milestones. Phase 3 has not started.

## Documentation and current status

- [Codex project handoff](docs/CODEX_HANDOFF.md): startup vision, actual implementation, independent verification, risks, roadmap, and Phase 2 requirements.
- [Master specification](docs/MASTER_SPEC.md): product authority and development milestones.
- [Implementation plan](docs/implementation_plan.md): milestone sequence and current blockers.
- [Phase explanations and index](docs/phase_explanations/README.md): beginner-friendly phase records.
- [Phase 2 explanation](docs/phase_explanations/PHASE_02.md): setup, architecture, roles, APIs, actual verification, and remaining limitations.
- [Approved Phase 2 design](docs/PHASE_02_ARCHITECTURE_PROPOSAL.md): authentication/isolation alternatives and the founder's approved choices.
- [Fresh Phase 2 review](docs/phase_explanations/PHASE_02.md#pre-phase-3-review-2026-11-07) and [local checkpoint manifest](docs/PHASE_02_CHECKPOINT.md): 152 tests passed again; commit awaits approval.
- [Detailed Phase 3 proposal](docs/PHASE_03_IMPLEMENTATION_PLAN.md): requirements, security choices, technology, implementation sequence and acceptance tests; no Phase 3 implementation yet.

The 2026-11-07 Phase 2 check passed 152 Python tests with real PostgreSQL, Python lint/dependency checks, frontend lint/types/build, running-stack checks, and an actual Edge browser flow. Cross-restaurant and explicit location boundaries are enforced by FastAPI and PostgreSQL RLS. The existing database container/volume was retained, backed up, and upgraded with additive migrations. Ports remain restricted to this PC. Read the [Phase 2 results](docs/phase_explanations/PHASE_02.md#actual-verification-results) for exact scope; earlier Phase 1 reports are historical.

## Repository layout

- `apps/web`: Next.js landing page, sign-in, configuration screens, fixed API proxy.
- `services/api`: FastAPI authentication/resources, PostgreSQL models, migrations, administration, security tests.
- `services/edge-agent`: Python edge-agent package placeholder.
- `packages/contracts`: versioned shared contract notes.
- `docs`: specification, architecture, API, threat model, and implementation plan.
- `references`: supplied blueprint and reference reel; do not treat the reel as accuracy evidence.
- `scripts`: isolated test database, private backup, running-stack and installed Edge verification helpers.

## Local setup

The current project is configured and running. Real local values belong in ignored `.env`; the template has no credentials. Administrative `POSTGRES_*` values stay separate from the API's restricted `APP_DB_*` runtime values. Compose supplies runtime `PGUSER`, `PGPASSWORD`, and `PGDATABASE` privately. Original configuration copies, demo credentials, and backups stay under ignored `.secrets/`. Generated files and dependencies remain excluded from Git and private values are excluded from Docker build contexts.

1. Preserve the existing `.env`. For a new checkout only, copy `.env.example` and privately supply administrator credentials. Keep current credentials for an existing database volume. Follow the [Phase 2 bootstrap sequence](docs/phase_explanations/PHASE_02.md#bootstrap-a-checkout-or-apply-reviewed-forward-migrations): prepare private runtime settings, start the database, back up, migrate, provision the restricted login, optionally seed synthetic data, then build/start applications. A fresh API must not start with administrator credentials or before migrations.
2. For this already-configured project, start Docker Desktop and use `docker compose up -d --no-build --pull never --wait --wait-timeout 60`.
3. Open `http://localhost:3000/sign-in`. Read the `a_owner` or `b_owner` account from `.secrets/phase2-demo-credentials.json` locally; never paste that file into chat or Git. `/settings` is the configuration workspace; `/` retains the original synthetic foundation page.
4. `http://localhost:8000/health` checks the API; `/ready` also checks restricted database readiness. The synthetic `/v1/demo/tenant` remains public in demo mode and never reads customer rows.
5. Open `http://localhost:8000/docs` for typed API documentation. Protected routes use the session cookie; changes also need the allowed origin and CSRF header.

Docker runs the application stack. Existing Python project dependencies support tests/admin commands; Node.js/npm support host web checks. Python integration tests now require the separately authorized disposable PostgreSQL test server.

This is local development, not a public/pilot security approval. The sanitized configuration and restricted credential wiring have now been built and verified in running containers. Custom web ports require matching exact `ALLOWED_ORIGINS`. Preserve volumes and private settings; never reset data or install software without the required approval. Use synthetic or explicitly authorized inputs only. No footage was processed in Phase 2.

## Verification commands

From PowerShell at the repository root, use the repaired project environment:

```powershell
.\.venv\Scripts\python.exe scripts/start_phase2_test_db.py
# The script waits for the isolated PostgreSQL instance to become ready.

Push-Location services/api
& ..\..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
& ..\..\.venv\Scripts\python.exe -m ruff check --no-cache .
Pop-Location

Push-Location services/edge-agent
& ..\..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
& ..\..\.venv\Scripts\python.exe -m ruff check --no-cache .
Pop-Location

Push-Location apps/web
npm run lint
& .\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
Pop-Location

.\.venv\Scripts\python.exe -m pip check
docker compose config --quiet
docker compose ps
.\.venv\Scripts\python.exe scripts/verify_phase2_runtime.py
.\.venv\Scripts\python.exe scripts/verify_phase2_browser.py
```

These are Phase 2 local checks and preserve Phase 1 behavior. Runtime/browser scripts require the explicit synthetic seed and add synthetic table records. The Edge check requires the existing Windows Edge installation. They do not prove camera compatibility, AI accuracy, or production readiness.

The project `.venv` works without `PYTHONPATH` overrides. CI now configures isolated PostgreSQL integration tests; hosted CI was not run because nothing was pushed. API/web images were rebuilt with the approved changes, using the existing npm lockfile and no npm dependency upgrades. The master specification, reference assets, and edge-agent source were preserved.

Remaining findings: npm audit reports 8 affected entries (1 high, 7 moderate), `next lint` is deprecated, and Starlette/HTTPX emits a test warning. The legacy database administrator password is weak and was preserved as instructed; rotate it through a reviewed procedure before public/pilot use. The API uses a separate generated password. Managed MFA, email verification/account recovery, production TLS/secret storage/hardening, dependency remediation, external security review, and later camera/device features remain open. See the full [limitations](docs/phase_explanations/PHASE_02.md#remaining-limitations-and-technical-debt).

The existing local checkpoint is `6808a81b7339f241701eb03552d952827872f168` on `main`. Phase 2 changes are uncommitted for founder review; no remote was added/changed and nothing was pushed. `.gitignore` protects private environments/credentials, dependencies, generated files, databases/backups, footage, and model assets. Ignore rules cannot detect secrets embedded in source or prevent forced additions; review each future commit.
