# Restaurant AI Monitoring

**Phase 7 checkpoint verification — 2026-11-12:** Fresh complete regression passes **650 tests**, zero skips, plus **eleven browser groups** and frontend/Python checks. The founder verified A02 totals and opened its CSV in Excel. All 615 current baseline records, credentials/calibrations and the database volume are preserved. [The exact 55-file checkpoint review](docs/PHASE_07_CHECKPOINT.md) records security findings and separate commit/push approval gates. Earlier 636/210-test results below remain historical.

**A02 Analytics correction — 2026-11-12:** The saved DEMO scenario workflow now contributes to DEMO visit/reset summaries without changing history. Exact A02 filters show one completed visit/reset and 110.85 seconds cleaning. Current verification: 210 relevant tests, eleven isolated browser groups and the actual deployed A02 report/CSV/browser. [Root cause, results and the older arrival explanation](docs/phase_explanations/PHASE_07.md#a02-demo-analytics-correction--2026-11-12). The earlier 636-test full run below remains historical; it was not rerun for this correction.

**Current Phase 7 work — 2026-11-12:** Approved implementation adds human-reviewed suggestions, protected staff workflow and manager reports/CSV. [The Phase 7 explanation](docs/phase_explanations/PHASE_07.md) records current tests and limitations. Verification passes **636 tests** and **ten browser groups**, including the prepared Linux web image and interrupted-export protection. Separately approved additive `0009` and matching local API/web/TLS code are active; all 580 original records and protected credentials/calibrations are preserved, and existing locations remain OFF. No commit/push or Phase 8 is included.

**Phase 4 local demo:** grant explicit preview access in `http://localhost:3000/settings`, then run `.\.venv\Scripts\python.exe -m restaurant_edge.cli serve --config .secrets/phase4/sources.json` and open `http://127.0.0.1:8765`. See the [complete beginner walkthrough](docs/phase_explanations/PHASE_04.md#windows-11-run-and-demonstrate). Use synthetic or explicitly authorized sources only.

**Phase 5 real-model lab:** add `--ai-debug --models .secrets/phase5/models/catalog.json` and open `/analysis`. The separately approved RF-DETR Nano model now runs locally in the existing CPU ONNX Runtime; conversion tools are isolated in `.cache/phase5-rfdetr-export/.venv`. [The walkthrough and actual results](docs/phase_explanations/PHASE_05.md) distinguish 445 passing tests, real-model synthetic integration and simulated authority. Managers approve saved model/seating profiles. Real-person footage/restaurant accuracy remain unverified; `SR.mp4` stays unauthorized and YOLOX acquisition stays held. AI observations remain shadow-only. See the Phase 6 explanation for subsequent secure device synchronization.

**Current checkpoint and next step:** Phase 6 is published as `fd983c7a656ab36f031db2900ef15a3da1362cbe` after separate approvals, with matching local/GitHub/tracking hashes verified on 2026-11-11. [Its explanation](docs/phase_explanations/PHASE_06.md) records 529 passing tests, six browser groups, applied 0007/0008 migrations, preservation and remaining limits. [Phase 7 was subsequently approved](docs/PHASE_07_IMPLEMENTATION_PLAN.md); its implementation and actual verification are recorded in [PHASE_07.md](docs/phase_explanations/PHASE_07.md). The earlier planning task made no application changes. That separate approval was subsequently granted; exact `0009`, restricted grants and matching local services are now active. No Phase 7 commit or push has been made.

Privacy-first restaurant table operations SaaS. Phases 0–3 provide the specification, foundation, multi-restaurant database, sign-in/authorization/configuration, and an interactive DEMO floor dashboard with persistent timers, tasks, staff actions, activity and SSE updates. Phase 4 adds Windows-local synthetic MP4 processing, private authorized preview and persistent visual table calibration. Phase 5 adds actual RF-DETR CPU inference and local shadow estimates on synthetic video. Webcam/RTSP adapters have simulated tests; physical camera compatibility and restaurant accuracy remain unverified. Phase 6 adds local device synchronization; approved Phase 7 adds reviewed workflow and analytics under verification. Billing remains a later milestone.

## Documentation and current status

- [Codex project handoff](docs/CODEX_HANDOFF.md): startup vision, actual implementation, independent verification, risks, roadmap, and Phase 2 requirements.
- [Master specification](docs/MASTER_SPEC.md): product authority and development milestones.
- [Implementation plan](docs/implementation_plan.md): milestone sequence and current blockers.
- [Phase explanations and index](docs/phase_explanations/README.md): beginner-friendly phase records.
- [Phase 2 explanation](docs/phase_explanations/PHASE_02.md): setup, architecture, roles, APIs, actual verification, and remaining limitations.
- [Approved Phase 2 design](docs/PHASE_02_ARCHITECTURE_PROPOSAL.md): authentication/isolation alternatives and the founder's approved choices.
- [Fresh Phase 2 review](docs/phase_explanations/PHASE_02.md#pre-phase-3-review-2026-11-07) and [historical checkpoint manifest](docs/PHASE_02_CHECKPOINT.md): foundation saved as `62ad229` on local `main`.
- [Phase 3 explanation](docs/phase_explanations/PHASE_03.md): dashboard behavior, current verification, Windows commands and limits.
- [Phase 3 GitHub checkpoint review](docs/PHASE_03_CHECKPOINT.md): fresh tests, secret review, existing GitHub commit and proposed documentation checkpoint.
- [Approved Phase 3 plan](docs/PHASE_03_IMPLEMENTATION_PLAN.md) and [required credential rotation procedure](docs/DATABASE_CREDENTIAL_ROTATION.md).
- [Phase 4 explanation](docs/phase_explanations/PHASE_04.md): working local preview/calibration, Windows commands, 333 passing tests, nine browser groups and limitations; [approved plan](docs/PHASE_04_IMPLEMENTATION_PLAN.md).
- [Phase 4 checkpoint review](docs/PHASE_04_CHECKPOINT.md): fresh verification, founder-confirmed Revision 7 reload, reviewed file manifest and completed local/GitHub checkpoint.
- [Approved Phase 5 proposal](docs/PHASE_05_IMPLEMENTATION_PLAN.md), [dependency/model review](docs/PHASE_05_DEPENDENCY_REVIEW.md) and [current implementation record](docs/phase_explanations/PHASE_05.md): approved RF-DETR Nano runs on synthetic video; YOLOX acquisition remains held and real-person/restaurant evaluation is incomplete.
- [Phase 5 checkpoint review](docs/PHASE_05_CHECKPOINT.md): manual evidence, fresh 445-test pass, retained intermittent MP4 timing failure, preservation and reviewed files; later separate approvals completed its local/GitHub publication.
- [Phase 6 explanation](docs/phase_explanations/PHASE_06.md): implemented local device synchronization, 529-test verification, Windows commands and remaining limitations.
- [Approved Phase 6 design](docs/PHASE_06_IMPLEMENTATION_PLAN.md): exact roadmap, device security, outbox/recovery, database/APIs and acceptance plan, with implementation outcomes.
- [Phase 6 checkpoint review](docs/PHASE_06_CHECKPOINT.md): complete 68-file manifest, exclusions, verification evidence and separate commit/push approval gates.
- [Approved Phase 7 plan](docs/PHASE_07_IMPLEMENTATION_PLAN.md), [implementation explanation](docs/phase_explanations/PHASE_07.md) and [migration review](docs/PHASE_07_MIGRATION_REVIEW.md): assisted human review, protected staff tasks, scoped analytics/CSV, actual checks and approval gates.

The 2026-11-07 Phase 2 check passed 152 Python tests with real PostgreSQL, Python lint/dependency checks, frontend lint/types/build, running-stack checks, and an actual Edge browser flow. Cross-restaurant and explicit location boundaries are enforced by FastAPI and PostgreSQL RLS. The existing database container/volume was retained, backed up, and upgraded with additive migrations. Ports remain restricted to this PC. Read the [Phase 2 results](docs/phase_explanations/PHASE_02.md#actual-verification-results) for exact scope; earlier Phase 1 reports are historical.

## Repository layout

To open the configured Phase 3 workspace, visit `http://localhost:3000/dashboard` and sign in with a privately stored demo account. Select **DEMO A Dining Room** or **DEMO B Dining Room**. For a checkout that has only the Phase 2 seed, follow [Phase 3 setup](docs/phase_explanations/PHASE_03.md#windows-11-run-instructions), including the explicit `management seed-dashboard` command; it adds records without resetting existing data.

- `apps/web`: Next.js landing/sign-in/settings, DEMO floor/staff dashboard, fixed HTTP/SSE proxy.
- `services/api`: FastAPI authentication/resources, PostgreSQL models, migrations, administration, security tests.
- `services/edge-agent`: native Windows local video readers, supervised capture, protected companion and visual calibration editor.
- `packages/contracts`: versioned shared contract notes.
- `docs`: specification, architecture, API, threat model, and implementation plan.
- `references`: supplied blueprint and reference reel; do not treat the reel as accuracy evidence.
- `scripts`: isolated test database, private backup, running-stack and installed Edge verification helpers.

## Local setup

The current project is configured and running. Real local values belong in ignored `.env`; the template has no credentials. Administrative `POSTGRES_*` values stay separate from the API's restricted `APP_DB_*` runtime values. Compose supplies runtime `PGUSER`, `PGPASSWORD`, and `PGDATABASE` privately. Original configuration copies, demo credentials, and backups stay under ignored `.secrets/`. Generated files and dependencies remain excluded from Git and private values are excluded from Docker build contexts.

1. Preserve the existing `.env`. For a new checkout only, copy `.env.example` and privately supply administrator credentials. Keep current credentials for an existing database volume. Follow the [Phase 2 bootstrap sequence](docs/phase_explanations/PHASE_02.md#bootstrap-a-checkout-or-apply-reviewed-forward-migrations): prepare private runtime settings, start the database, back up, migrate, provision the restricted login, optionally seed synthetic data, then build/start applications. A fresh API must not start with administrator credentials or before migrations.
2. For this already-configured project, start Docker Desktop and use `docker compose start db api web` to reuse the existing containers and their settings. If an application container needs recreation, explicitly set `$env:EDGE_SYNC_ENABLED = 'true'` and follow the [Phase 6 startup instructions](docs/phase_explanations/PHASE_06.md#windows-11-run-and-test-instructions); otherwise the opt-in device feature defaults to disabled.
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

The project `.venv` works without `PYTHONPATH` overrides. CI configures isolated PostgreSQL integration tests; hosted CI results were not checked by this review. Fresh Phase 3 checks passed all 262 Python tests, ten dashboard-browser groups, four API restart-recovery groups, lint, types and the production build. API/web images use the existing npm lockfile with no npm dependency upgrades. The master specification and reference assets were preserved; Phase 4 extends the edge package with the approved local input/calibration implementation.

Remaining findings: npm audit reports 8 affected entries (1 high, 7 moderate), `next lint` is deprecated, and Starlette/HTTPX emits a test warning. The legacy database administrator password is weak and was preserved as instructed; rotate it through a reviewed procedure before public/pilot use. The API uses a separate generated password. Managed MFA, email verification/account recovery, production TLS/secret storage/hardening, dependency remediation, external security review, physical camera validation and later workflow/analytics remain open. See the full [limitations](docs/phase_explanations/PHASE_02.md#remaining-limitations-and-technical-debt).

Phase 3 implementation is saved in `3342c42` (`V1`). After separate founder approvals, its verification checkpoint `899f74368b9487ae1c33e0d0c0e511e37b396f36` was pushed and confirmed on GitHub `main` on 2026-11-08, Asia/Dhaka. Phase 1/2 checkpoints remain its ancestors. Phase 4 was separately approved and is implemented locally, with 333 tests (all 262 earlier cases retained), nine real browser integration groups and additive migrations 0005/0006. All original 347 public records and ten users/password hashes, database volume, credentials and earlier migration files are preserved. Its separately approved checkpoint `143831395429785a2a5647b7317aafc0fe4fdea7` is committed and published on GitHub `main`. Phase 5 planning was followed by separate implementation/package/model approvals. Its local shadow workflow now includes actual RF-DETR Nano CPU inference and synthetic-video verification; real-person detection and restaurant occupancy accuracy remain unverified, so Phase 5 is not fully validated. YOLOX acquisition remains held; no training was performed. `.gitignore` protects private environments/credentials, dependencies, generated files, databases/backups, footage, and model assets. Ignore rules cannot detect secrets embedded in source or prevent forced additions; review each future commit.
