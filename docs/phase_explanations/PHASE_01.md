# Phase 01: Repository Foundation

> **Latest status — 2026-11-07:** The [pre-Phase 2 environment/repository check](#pre-phase-2-environment-and-repository-check-2026-11-07) appended below supersedes earlier environment limitations. Existing containers and read-only PostgreSQL checks now pass, `.venv` is repaired, and Git/local-only networking protections are in place. Earlier reports remain historical records. Phase 2 has not started.

> **Current evidence note — 2026-11-06:** Earlier sections, including the “Final verification update,” are preserved historical reports from the previous assistant. The independent documentation-handoff results appended at the end are the current inspection record. They do not confirm that Docker, PostgreSQL, or localhost services are running now. See [CODEX_HANDOFF.md](../CODEX_HANDOFF.md) for the complete handoff. Phase 2 has not started.

## Phase overview and objectives

Phase 01 created the first runnable project foundation. Its objective was to make the repository ready for later product work: a backend service, a frontend shell, an edge-agent package, database migration scaffolding, Docker configuration, tests, and continuous integration.

This phase uses synthetic demo data only. It does not connect to real restaurant cameras and does not perform AI detection.

## Features implemented

- FastAPI backend with:
  - `GET /health` health check.
  - `GET /v1/demo/tenant` synthetic restaurant data.
- Next.js and TypeScript web shell with an explicit `DEMO MODE` label.
- Python edge-agent package with initial device-health objects.
- PostgreSQL service definition in Docker Compose.
- Alembic migration configuration and offline migration environment.
- Environment template using placeholder values only.
- API and edge-agent starter tests.
- Ruff lint configuration and CI workflow.
- Beginner setup instructions in `README.md`.
- Analysis of the supplied blueprint and video in `docs/reference_analysis.md`.

The reference reel was measured as an 84.64-second, 480x1068 vertical H.264/AAC video. It showed table overlays, availability labels, restaurant footage, dashboard concepts, and presenter segments. It was treated as product inspiration, not accuracy evidence.

## Files created or modified

### Root and documentation

- `README.md`: setup, URLs, test commands, and limitations.
- `AGENTS.md`: engineering rules, including the permanent Phase Documentation Rule.
- `.env.example`: safe local configuration template.
- `docker-compose.yml`: PostgreSQL, API, and web services.
- `.github/workflows/ci.yml`: API, edge-agent, and web CI jobs.
- `docs/reference_analysis.md`: written and video reference findings.
- `packages/contracts/README.md`: placeholder for future versioned shared contracts.

### API service

- `services/api/pyproject.toml`: dependencies and Python tooling.
- `services/api/src/restaurant_api/main.py`: FastAPI app, response models, health route, and demo route.
- `services/api/tests/test_health.py`: two API tests.
- `services/api/Dockerfile`: API container build instructions.
- `services/api/alembic.ini`: migration settings.
- `services/api/migrations/env.py`: online/offline Alembic environment.
- `services/api/migrations/script.py.mako`: future migration template.
- `services/api/migrations/README.md`: explains that real tenant migrations belong to Phase 2.

### Edge agent

- `services/edge-agent/pyproject.toml`: package and test configuration.
- `services/edge-agent/src/restaurant_edge/health.py`: initial health model and UTC heartbeat helper.
- `services/edge-agent/tests/test_health.py`: two edge-agent tests.

### Web app

- `apps/web/package.json`: Next.js, React, and TypeScript dependencies.
- `apps/web/app/page.tsx`: initial foundation screen.
- `apps/web/app/layout.tsx`: metadata and layout wrapper.
- `apps/web/app/globals.css`: visual styling.
- `apps/web/tsconfig.json`: TypeScript settings.
- `apps/web/next.config.ts`: standalone build configuration.
- `apps/web/Dockerfile`: web container build instructions.

## Technologies used and why

- **Python:** backend and edge-agent language. It is suitable for APIs and future computer-vision work.
- **FastAPI:** creates typed HTTP endpoints and automatic API documentation.
- **Pydantic:** validates API response data.
- **Next.js and TypeScript:** future dashboard foundation with type safety.
- **PostgreSQL:** planned durable cloud database for tenant and event data.
- **SQLAlchemy and Alembic:** planned database access and versioned schema changes.
- **Docker Compose:** lets the API, web app, and database run together.
- **pytest:** runs automated Python tests.
- **Ruff:** checks Python code style and common issues.
- **GitHub Actions:** describes repeatable checks for future pushes and pull requests.

## Step-by-step execution flow

1. A developer copies `.env.example` to `.env`.
2. Docker Compose can start PostgreSQL, the API, and the web shell when Docker is installed.
3. The web shell displays a clearly labeled synthetic foundation screen.
4. The API answers `/health` with service status and UTC check time.
5. The demo endpoint returns four synthetic tables with example states.
6. The edge-agent package can report that no camera is configured yet.
7. Python tests verify the API responses and edge health behavior.
8. Alembic can generate offline migration SQL, while real schema tables remain a Phase 2 task.

## How to run and test on Windows 11

Install Python 3.11+, Node.js/npm, and Docker Desktop first.

### Full stack

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open:

```text
http://localhost:3000
http://localhost:8000/health
http://localhost:8000/v1/demo/tenant
```

### API tests

```powershell
Set-Location services/api
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

### Edge-agent tests

```powershell
Set-Location ../edge-agent
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

### Offline migration check

```powershell
Set-Location ../api
python -m alembic upgrade head --sql
```

## Actual testing results and remaining limitations

**Passed on this Windows environment:**

- API tests: `2 passed`.
- Edge-agent tests: `2 passed`.
- Ruff checks for API and edge-agent: passed after import/style fixes.
- Alembic offline SQL generation: passed.
- Editor diagnostics for Python and TypeScript files: no errors.
- Required Phase 1 files and source secret scan: passed.
- Reference video metadata and representative frames were inspected.

**Not verified:**

- Next.js install, lint, or production build, because Node/npm were unavailable.
- Docker Compose startup, because Docker was unavailable.
- PostgreSQL-connected migrations, because no database container was running.
- Real authentication, tenant authorization, database schema, RTSP, webcam, AI detection, calibration, SSE, analytics, or cleaning workflows.
- Production privacy, accuracy, deployment, and legal compliance.

## Problems encountered and solutions

**Problem:** Node/npm and Docker were not installed.

**Solution:** Scaffolded the files and documented the exact commands, while reporting frontend and full-stack execution as unverified.

**Problem:** Video tools were initially unavailable.

**Solution:** Installed a local Python video reader for inspection only, measured the MP4, reviewed representative frames, and removed generated temporary frames afterward.

**Problem:** Ruff found import and UTC-style issues.

**Solution:** Applied the formatter's mechanical fixes and reran lint and tests until the checks passed.

**Problem:** `alembic check` attempted to connect to the unavailable Compose hostname `db`.

**Solution:** Used `alembic upgrade head --sql` to validate migration configuration offline without pretending PostgreSQL was running.

## Phase summary

Phase 01 created a clean foundation for future development. The backend, frontend shell, edge package, database migration boundary, tests, CI configuration, and documentation now exist. Only synthetic demo behavior is available. Real restaurant functionality must wait for later phases and explicit verification.

## Verification update: 2026-11-06

### Toolchain results

- Node.js: **PASSED**, `v26.13.0` is installed and usable. This is newer than the originally requested Node 22 LTS, but it is a supported LTS release for this project.
- npm: **PASSED**, `11.20.0` is installed and usable.
- Docker CLI: **PASSED**, `29.9.2` is installed.
- Docker Compose: **PASSED**, plugin `v5.6.1` is installed.
- WSL 2: **FAILED/NOT VERIFIED**, `wsl --status` reports that WSL is not installed and requires an elevated install/update operation.
- Docker engine: **FAILED**, Docker Desktop is present but reports `starting` and `Docker Desktop is unable to start`. Its Windows service is stopped.

### Frontend results

- `npm install`: **PASSED** in `apps/web`.
- `npm run lint`: **PASSED**, zero ESLint warnings or errors after aligning `eslint-config-next` with Next.js 15.
- TypeScript `tsc --noEmit`: **PASSED**.
- `npm run build`: **PASSED**. Next.js 15.5.29 generated the production build successfully.
- npm audit reported vulnerabilities in installed dependencies: first 2, then 8 after the ESLint setup. No automatic security upgrade was applied because `npm audit fix --force` can introduce breaking changes.

### Backend and edge results

- API Ruff check: **PASSED**.
- API pytest: **PASSED**, 2 tests.
- Edge-agent Ruff check: **PASSED**.
- Edge-agent pytest: **PASSED**, 2 tests.
- Live API smoke test: **PASSED**. `/health` returned `ok`; `/v1/demo/tenant` returned the synthetic organization, location, and four tables.

### Blocked checks

- Docker Compose startup: **BLOCKED** because the Docker engine cannot start.
- PostgreSQL connectivity: **BLOCKED** because PostgreSQL cannot start without Docker.
- Database migrations against PostgreSQL: **BLOCKED** for the same reason. Offline Alembic SQL generation remains previously verified.
- Full frontend/backend/database integration: **BLOCKED** until Docker and WSL are repaired.

### Changes made during verification

- Added the generated frontend `apps/web/.eslintrc.json` configuration.
- Added the frontend dependency lockfile after `npm install`.
- Aligned `apps/web/package.json` to `eslint-config-next` 15.5.29 so it matches Next.js 15 and prevents the ESLint circular-config error.

No Phase 2 code was started.

## Final verification update: 2026-11-06

### Windows and Docker results

- WSL 2: **PASSED**, default version 2, WSL version `3.0.3.0`, kernel `6.18.54.1`.
- WSL update: **PASSED**, already at the latest available version.
- Node.js: **PASSED**, `v26.13.0`.
- npm: **PASSED**, `11.20.0`.
- Docker engine: **PASSED**, Docker server `29.9.2` responded after Docker Desktop restart.
- Docker Compose: **PASSED**, `v5.6.1`.

### Compose and database results

- Web image build: **PASSED**.
- API image rebuild: **PASSED**.
- Compose startup: **PASSED**. API, web, and PostgreSQL containers were all running.
- PostgreSQL readiness: **PASSED**, `pg_isready` reported accepting connections.
- PostgreSQL SQL connectivity: **PASSED**, database `restaurant_ai` and user `restaurant` were reachable.
- Alembic migration execution: **PASSED** inside the API container.
- Database table state: `alembic_version` exists. No tenant tables were expected because those belong to Phase 2.

### End-to-end results

- `GET http://localhost:8000/health`: **PASSED**, returned `ok`.
- `GET http://localhost:8000/v1/demo/tenant`: **PASSED**, returned demo data with four tables.
- `GET http://localhost:3000`: **PASSED**, returned HTTP 200 and contained `DEMO MODE`.
- Frontend, API, and PostgreSQL containers communicated successfully through the Compose network and published ports.
- API Ruff and pytest: **PASSED**, 2 tests.
- Edge-agent Ruff and pytest: **PASSED**, 2 tests.
- TypeScript compiler: **PASSED** with `tsc --noEmit`.
- Frontend ESLint: **PASSED**, zero warnings or errors.
- Next.js production build: **PASSED**.

### Fixes made during final verification

- Added `apps/web/.dockerignore` so `node_modules` and `.next` are not copied into the Docker build context. This reduced the unnecessary context transfer that had delayed the first web build.
- Updated `services/api/Dockerfile` to copy `alembic.ini` and `migrations/` into the API image. This fixed the first migration failure: `No 'script_location' key found in configuration.`
- Pinned `eslint-config-next` to the Next.js 15 line and generated the frontend ESLint configuration. This fixed the ESLint circular-config error caused by installing version 16 against Next.js 15.

### Remaining limitations

- The database has only migration bookkeeping; tenant, user, table, camera, and event tables are Phase 2 work.
- The web page is still a foundation screen with synthetic data, not the live floor dashboard.
- No real authentication, tenant authorization, camera input, AI inference, calibration, SSE, analytics, or edge synchronization exists yet.
- npm reports dependency vulnerabilities. No forced audit upgrade was applied because it could introduce breaking changes.
- The Next.js command reports a warning about multiple lockfiles. The build and lint still pass; this warning should be cleaned up in a later maintenance task.

Phase 1 is now fully verified within its intended scope. Phase 2 has not started and requires founder approval.

## Independent documentation handoff: 2026-11-06

### Overview and what changed

The founder approved a documentation-only transfer to Codex. The handoff inspected the existing specification, source, configuration, tests, and earlier phase records. No application source, dependencies, or database contents were changed. No existing files were deleted; only Markdown documentation was created or updated. Generated verification artifacts are separate from application code.

Created [CODEX_HANDOFF.md](../CODEX_HANDOFF.md) with the startup vision, current architecture, technology explanations, feature status, actual checks, dependency findings, known risks, all future milestones, and the complete Phase 2 requirements/acceptance checklist. Updated the root README, target architecture/API/threat-model labels, roadmap, reference-analysis evidence note, and phase index to match current source. The master specification, reference blueprint, and Phase 00 explanation were preserved.

This handoff is not a new development phase and creates no Phase 02 completion document.

### Current implementation explained simply

The project has the pieces needed to start product development: a web page, a small API, a Python edge package, and database/container setup files. The web page shows static DEMO text. It does not fetch table data. The API returns one hard-coded synthetic restaurant/location with four tables; it does not query PostgreSQL. Each response creates new example timestamps, so they are not real occupancy timers.

The edge package only creates an unconfigured health object and a UTC timestamp. It does not read video or send heartbeats over a network. There are no tenant tables, user sessions, permission checks, calibration tools, detection models, live updates, staff workflows, or analytics.

The earlier statement that the web, API, and PostgreSQL communicated should therefore be read as the previous assistant's environment/startup report. Current source does not demonstrate an end-to-end browser-to-API-to-database data flow. Similarly, a successful health response does not verify database readiness.

### Actual verification in this handoff

| Check | Current result |
| --- | --- |
| API tests | **PASSED:** 2 tests in 0.62 seconds, using TestClient |
| Edge tests | **PASSED:** 2 tests in 0.02 seconds, testing health helpers |
| Python Ruff | **PASSED:** API and edge checks returned exit 0 |
| Frontend lint | **PASSED:** exit 0; deprecated command and multiple-lockfile notices remain |
| TypeScript | **PASSED:** local `tsc --noEmit --incremental false` returned exit 0 |
| Fresh production build | **PASSED:** isolated same-drive copy compiled, checked types/lint, and generated static pages |
| Compose configuration | **PASSED:** `docker compose config --quiet` returned exit 0 |
| Docker/localhost runtime | **BLOCKED / UNREACHABLE:** engine pipe unavailable; web, health, and demo URLs did not respond |
| PostgreSQL contents/connected migration | **NOT VERIFIED:** no database content was read or changed |
| Alembic heads/offline SQL | Configuration checks passed, but there are zero revision files/heads; offline output was not executed |
| npm audit | **FINDINGS:** 8 affected package entries: 1 high, 7 moderate; no upgrade applied |
| Blueprint/reference asset | Master/reference Markdown identical; MP4 headers confirm approximately 84.6408 seconds and 480×1068 |

### Environment and Windows 11 reproduction

The successful Python checks used the existing Anaconda Python 3.13.9 at `C:\ProgramData\anaconda3\python.exe`, with the relevant service's `src` on `PYTHONPATH`. The project `.venv` is Python 3.14.0 and currently reports `No module named pytest`. No packages were installed to repair it. Host Node is v26.13.0; Docker/CI still target Node 22 and Python 3.12. Host availability is not an approval of a new support policy or LTS designation.

From PowerShell, use the existing Anaconda executable for `-m pytest -q -p no:cacheprovider` and `-m ruff check --no-cache .` within each service. Use the local frontend commands for lint/type checks. Exact copyable commands and the isolated build location are in [the handoff's Windows 11 instructions](../CODEX_HANDOFF.md#windows-11-reproduction-using-existing-dependencies).

The build reused installed frontend dependencies through a directory junction and wrote generated output in an isolated E: directory. A C:-drive attempt during planning had a cross-drive resolution error; a same-drive retry and the fresh handoff build passed. No Docker rebuild or runtime/browser test is implied. Artifacts were retained; no existing files were deleted.

### Remaining limitations, problems, and next steps

- Docker is not currently available. Earlier running-container, PostgreSQL, and HTTP 200 results remain historical; repair/verification was not performed through installations, resets, or volume changes.
- Alembic has no application revisions and no model metadata. Offline SQL included migration-bookkeeping removal; it was printed only. It must not be treated as proof of tenant schema or executed against an existing database on this handoff's authority.
- The synthetic public endpoint does not prove tenant isolation. Authentication, explicit location grants, roles, audits, persistent entities, and adversarial tests remain Phase 2 work.
- npm findings involve PostCSS and the minimatch/typescript-eslint chain, with Next.js also flagged transitively. The handoff records advisories and the major-upgrade suggestion; no exploit or automated fix was attempted.
- Development configuration, incomplete environment-variable wiring, absent readiness checks, missing Git metadata/ignore rules, and narrow CI coverage need review. The handoff lists each finding and its consequence without changing application files.
- Earlier reference-video scene/codec/frame-rate findings remain historical. This inspection used headers and the existing written reference analysis, with no upload, decoder installation, or audio monitoring.

### Handoff summary and approval gate

The documentation now distinguishes the working starter checks from unavailable runtime checks and future product features. The original verification reports above are preserved so the founder can see the history. The project remains a foundation, with no implemented CCTV monitoring product or tested tenant isolation. Review the handoff, environment and dependency issues, and identity/location/database decisions before approving a separate Phase 2 proposal. Stop here; Phase 2 has not started.

## Pre-Phase 2 environment and repository check: 2026-11-07

### Overview and objectives

The founder requested a maintenance check before approving Phase 2. The goal was to make the existing Phase 1 foundation usable and better protected for local development, without rebuilding the product, deleting database data, adding authentication, or implementing camera features.

The earlier reports above remain historical. This section records the current check using the Asia/Dhaka date. Local development verification is not a claim of production security, real AI performance, or a completed Phase 2.

### Founder approvals and safety boundaries

Two specific permissions were obtained before the dependent work:

1. Install the two local Python packages and their declared dependencies into the existing project `.venv`. No global installation or npm upgrade was permitted.
2. Apply a validated Compose change through a brief container recreation, reusing existing local images and preserving the existing PostgreSQL volume. This changes container IDs but does not replace the volume or create a new database.

No volume deletion, database reset, SQL data/schema modification, image pull, Docker image rebuild, npm installation, npm upgrade, or `audit fix` was performed. No application behavior or Phase 2 feature was added. No Git commit, remote, push, or credential value was created or exposed in the report.

### Changes and important files

| File or area | Change and purpose |
| --- | --- |
| `.gitignore` | New rules for `.env` variants, credential/key files, local environments, dependencies, Python metadata, caches, builds, local databases/backups, logs, footage, and model artifacts. `.env.example` and dependency lockfiles remain eligible for review/commit. |
| `.git/` local metadata | Initialized an empty `main` repository because none existed. No files were staged; no historical commits were recovered and no remote was configured. |
| Existing `.venv` | Installed both local packages in editable mode plus their declared runtime/development dependencies, using its own Python interpreter. Existing ImageIO/FFmpeg, NumPy, Pillow, psutil, and pip versions were retained. |
| `docker-compose.yml` | Restricted published ports to `127.0.0.1`; connected `API_PORT`/`WEB_PORT` to host mappings; added database/API health checks and healthy dependency ordering. Kept the existing named database volume. |
| `apps/web/next.config.ts` | Explicitly set the tracing root to the web directory. This removes the duplicate-lockfile warning while retaining the `standalone/server.js` layout expected by the Dockerfile. The empty root lockfile was preserved. |
| `apps/web/Dockerfile` | Changed future dependency installation from `npm install` to lockfile-based `npm ci`. The Docker image was not rebuilt during this check. |
| `.github/workflows/ci.yml` | Added Ruff to both Python jobs and changed the web job to `npm ci`. Workflow structure was checked locally; hosted GitHub Actions was not run. |
| Root README, handoff, roadmap, reference analysis, and phase index | Updated current status and reproduction instructions while keeping earlier evidence separate. Corrected the incomplete earlier assessment of installed video tooling. |

The FastAPI application, edge health helper, web page/layout/CSS, tests, Python manifests, frontend package manifest/lockfiles, master specification, and supplied reference assets were preserved. The project still contains no authentication, tenant schema, camera ingestion, or AI model integration.

### Technologies explained simply

- **WSL 2** supplies the Linux environment used by Docker Desktop. It was installed already; starting Docker activated its existing `docker-desktop` distribution.
- **Docker Compose** runs the existing database, API, and web containers together. Containers can be replaced while a named database volume remains attached. The volume is the persistent storage that must be protected.
- **Readiness checks** test whether PostgreSQL accepts connections and whether the API answers `/health`. They improve startup order; they do not prove tenant security or make the API health endpoint database-aware.
- **A Python virtual environment** keeps this project's Python packages separate from global Python. Editable installation lets tests import the existing source without changing `PYTHONPATH` or copying application code.
- **Git ignore rules** stop matching untracked files from being added by ordinary Git commands. They do not encrypt files, scan every possible secret, or prevent someone from forcing an addition.
- **`npm ci`** installs the versions already recorded in the lockfile when a later approved build/CI job runs. Changing that command did not upgrade or install frontend packages during this check.

### Step-by-step execution flow

1. Read `AGENTS.md`, the unchanged master specification, handoff, source/configuration, and earlier results. Saved a SHA-256 baseline of existing non-generated project files.
2. Confirmed that WSL 2 and Docker/Compose were installed, but Docker Desktop and its Linux distribution were stopped. Git was absent and `.venv` lacked the API/test dependencies.
3. Started the installed Docker Desktop with `docker desktop start --detach`; no WSL/Docker installation, reset, or update was needed.
4. Inspected the three existing containers and the existing database volume, then started the database/API/web without building images. Verified live HTTP responses and read-only SQL before changing container configuration.
5. Added `.gitignore`, initialized Git, and verified ignored/visible paths before staging anything. No files were staged or committed.
6. After installation approval, ran `.venv\Scripts\python.exe -m pip install --quiet --upgrade-strategy only-if-needed -e 'services/api[dev]' -e 'services/edge-agent[dev]'`. Ran `pip check`, the existing tests, and Ruff using this repaired environment.
7. Reviewed npm's existing audit findings and package metadata without installing, upgrading, overriding, or fixing npm packages. Repaired frontend tracing and future CI/build commands; reran frontend checks.
8. Prepared localhost-only bindings and readiness checks; validated Compose. After separate approval, verified the original volume mapping and applied `docker compose up -d --no-build --pull never --wait --wait-timeout 60`.
9. Rechecked actual port bindings, health status, live endpoints/static assets, PostgreSQL table/row state, and volume identity. Updated this phase record and the related documentation. Phase 2 remains unstarted.

### Actual environment and test results

| Check | Actual result |
| --- | --- |
| WSL installation | **PASS:** WSL 3.0.3.0, Linux kernel 6.18.54.1-1; default WSL version 2 |
| WSL distribution | **PASS:** existing `docker-desktop` distribution runs as version 2 after Docker starts |
| Docker Engine / Compose | **PASS:** server 29.9.2 responds; Compose v5.6.1; configuration validation returns exit 0 |
| Existing stack | **PASS:** existing local images reused; database and API healthy; web running. The web has no configured health check and was verified with HTTP requests. |
| Published ports after approved recreation | **PASS:** only `127.0.0.1:3000`, `127.0.0.1:8000`, and `127.0.0.1:5432`; no all-interface mappings remain |
| PostgreSQL | **PASS:** server 16.15, `pg_isready` accepting connections, explicit read-only SQL successful |
| Database preservation | **PASS:** same `restaurent_startup_postgres_data` volume, creation time `2026-11-06T16:18:11Z`, same mount destination; only public `alembic_version`, with zero rows before and after |
| API-to-database connectivity | **PASS:** existing API container connected using its configured URL and completed `SELECT 1` in a read-only transaction. This is a diagnostic check, not implemented application data access. |
| Alembic current/heads | **PASS as inspection:** container `alembic current` and local `alembic heads` return exit 0 with no revision. No migration upgrade was run and no tenant tables exist. |
| Live API health | **PASS:** HTTP 200, `status=ok`, UTC timestamp |
| Live demo endpoint | **PASS:** HTTP 200, `demo=true`, four synthetic tables |
| Live frontend | **PASS:** HTTP 200 with `DEMO MODE`; all six referenced CSS/JavaScript assets return HTTP 200 |
| Project environment | **PASS:** pip installation exit 0 and `pip check` reports no broken requirements; imports resolve from the project `.venv` without `PYTHONPATH` overrides |
| API tests | **PASS:** 2 tests in 1.22 seconds; one Starlette/HTTPX deprecation warning |
| Edge tests | **PASS:** 2 tests in 0.08 seconds |
| Python Ruff | **PASS:** both service checks exit 0 |
| Frontend lint/types/build | **PASS:** lint, local `tsc --noEmit --incremental false`, and production build exit 0. Duplicate-lockfile warning is gone; `next lint` deprecation remains. |
| Frontend lockfile consistency | **PASS:** name, version, dependencies, and devDependencies match `package.json`; no npm manifest/lockfile changes |
| Standalone layout | **PASS:** local build creates `apps/web/.next/standalone/server.js` after the tracing-root fix |
| CI structure | **PASS locally:** Python jobs include Ruff and web uses `npm ci`; remote CI and new Dockerfile image builds are **NOT VERIFIED** |
| Git initialization | **PASS:** local `main`, zero commits, zero tracked/staged files, zero remotes |
| Git ignore checks | **PASS:** 16 actual/hypothetical sensitive/generated paths ignored; four required source/template/lockfile/spec paths remain eligible |
| Candidate secret-pattern scan | **PASS within its limits:** no reviewed private-key, AWS/GitHub token, or authenticated-RTSP signature in the 44 then-eligible text files. This is not a complete secret audit. Actual `.env` was absent. |
| Documentation links | **PASS:** 27 local file/section links resolve across the nine reviewed documents |
| Project-file preservation | **PASS:** 44 baseline non-generated files compared; only the ten expected configuration/documentation files changed, `.gitignore` was added, and no baseline files were removed. Application behavior source, tests, manifests/lockfiles, master specification, and reference assets retain their original hashes. Git metadata, `.venv`, caches, dependencies, and install metadata are excluded from this manifest check. |
| npm audit | **UNRESOLVED:** exit 1, eight affected package entries: one high and seven moderate; no npm changes applied |

### Repaired Python versions and compatibility limits

The existing project interpreter is Python 3.14.0. Within the manifest's allowed ranges, pip resolved FastAPI 0.162.0, Pydantic 2.14.3, pydantic-settings 2.16.2, SQLAlchemy 2.1.8, Alembic 1.20.1, psycopg/psycopg-binary 3.3.8, Uvicorn 0.54.0, pytest 8.4.2, Ruff 0.17.4, and HTTPX 0.28.1. Both local project packages remain version 0.1.0. pip remains 25.2.

Pre-existing ImageIO 2.38.1, imageio-ffmpeg 0.8.1, NumPy 2.5.4, Pillow 13.0.0, and psutil 7.2.2 were retained. Their presence is not a claim of an implemented video pipeline or another video inspection. The earlier handoff's decoder assessment was incomplete; the reference documentation now says so.

The running API image uses Python 3.12.16; the web image uses Node v22.23.4. Host Node remains v26.13.0. No interpreter was installed or replaced. The tested foundation works in these environments, but future inference-library compatibility and fully reproducible Python locking remain separate work.

### Windows 11 run and test instructions

Run these from PowerShell after Docker Desktop is installed and started. They reuse this project's existing images and Python/frontend dependencies. Do not substitute commands that delete volumes or reset databases.

```powershell
Set-Location E:\Restaurent_startup
docker desktop start --detach
docker compose config --quiet
docker compose up -d --no-build --pull never --wait --wait-timeout 60
docker compose ps

.\.venv\Scripts\python.exe -m pip check

Push-Location services/api
& ..\..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
& ..\..\.venv\Scripts\python.exe -m ruff check --no-cache .
& ..\..\.venv\Scripts\python.exe -m alembic heads
Pop-Location

Push-Location services/edge-agent
& ..\..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
& ..\..\.venv\Scripts\python.exe -m ruff check --no-cache .
Pop-Location

Push-Location apps/web
npm run lint
& .\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
npm audit --package-lock-only --ignore-scripts --json
Pop-Location

git status --short --branch
git check-ignore -v -- .env .venv/Scripts/python.exe apps/web/node_modules/next/package.json
```

Open `http://localhost:3000`, `http://localhost:8000/health`, and `http://localhost:8000/v1/demo/tenant`. The app remains synthetic. The named volume survives normal container recreation; avoid `down -v`, volume removal/pruning, database reset scripts, or migration upgrades during a simple environment check. Raw `docker inspect`/full resolved Compose output can contain credentials; use limited fields or `config --quiet` when sharing diagnostics.

### npm findings and recommended safe next actions

The current frontend audit still reports PostCSS 8.4.31 as high, Next.js 15.5.29 as moderate through PostCSS, and six moderate entries in the minimatch/typescript-eslint chain. These are eight affected package entries, with shared underlying advisories. No exploit or application-specific reachability test was run.

| Finding | Review result and recommendation |
| --- | --- |
| PostCSS | Next.js 15.5.29 pins PostCSS 8.4.31. Registry metadata currently lists PostCSS 8.5.32; its Node engine range supports the current Node versions, but compatibility with this Next.js build has not been tested. Prefer an upstream compatible fix. If unavailable, propose a narrowly scoped PostCSS 8 override in a separately approved change, then require a fresh audit, lint/type/build checks, CSS/asset requests, and runtime verification before accepting it. Do not treat that candidate as already safe or applied. |
| Minimatch | Installed nested minimatch is 10.2.6; the upstream advisory identifies 11.0.1 as patched. The current latest typescript-estree 8.72.1 declares `^10.2.2`, excluding 11.x. Prefer an upstream compatible dependency update; forcing a major minimatch override needs separate compatibility review and approval. |
| Audit major-upgrade suggestion | npm suggests Next.js 16.4.5 for part of the tree. This is a major framework migration and remains unapproved. Do not run `npm audit fix --force` or change framework majors as part of environment repair. |

References: [PostCSS upstream advisory](https://github.com/postcss/postcss/security/advisories/GHSA-6g55-p6wh-862q), [minimatch upstream advisory](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249). The full advisory inventory remains in [the handoff](../CODEX_HANDOFF.md#npm-dependency-findings). Versions and audit results are dated observations, not a promise about future releases.

### Remaining warnings, limitations, and pending decisions

- `next lint` is deprecated. It still passes with the current Next.js 15 setup. A reviewed ESLint CLI/config migration should accompany the eventual dependency maintenance; no codemod or new lint dependency was installed here.
- Starlette 1.10.0 warns that its TestClient's HTTPX compatibility path is deprecated and mentions `httpx2`. The existing manifest declares HTTPX, and all tests pass. Changing this test dependency needs a reviewed compatibility change; no undeclared package was added to silence the warning.
- Python dependency ranges resolve newer packages than the historical Anaconda environment. There is no complete Python lock/constraint strategy yet. CI targets Python 3.12 while the repaired local environment is 3.14.
- Docker Desktop must be running. This work started the installed application but did not change Windows service startup policy, WSL installation, update settings, or require a reboot.
- Existing Docker images were reused. The local tracing-root fix was built/tested on the host; the changed Dockerfile/CI installation instructions have not been exercised in a new image build or hosted CI run.
- The app still has public synthetic routes, fixed development credentials, no authentication/tenant enforcement, no database models, and no real camera processing. Local-only bindings reduce network exposure; they do not make this production-ready.
- Alembic still takes its URL from `alembic.ini`, and the API still ignores `APP_ENV`/`DEMO_MODE` settings. Adding secure application configuration and approved tenant/auth behavior remains future scoped work. No database password was rotated because doing that against an existing volume needs a deliberate coordinated change.
- Git now exists, but there is no reviewed first commit, remote, or off-machine backup. Ignore rules do not protect already tracked files, forced additions, or secrets embedded in otherwise ordinary source files. Review the staged diff and exclude real credentials before each future commit.
- Only read-only SQL inspection and the empty migration state were verified; no migration upgrade, downgrade, backup/restore, fresh-machine startup, browser automation, hardware, model accuracy, legal/privacy compliance, or customer deployment was tested.
- Before Phase 2, review the dependency-maintenance approach and choose identity/session design, the role/location-grant matrix, database isolation strategy, safe test-database provisioning, and the master schema-scaffolding boundary. These decisions are documented in the handoff; none has been silently implemented.

### Problems encountered and solutions

| Problem | Solution and verification |
| --- | --- |
| Docker engine unavailable because Desktop was stopped | Started the existing installation; WSL distribution, engine, original containers, HTTP, and SQL checks passed. |
| PostgreSQL rejected the very first readiness probe immediately after startup | A subsequent read-only SQL connection succeeded. Added health checks and `service_healthy` dependencies so approved Compose startup now waits for readiness. |
| `.venv` lacked project/test packages | Obtained permission, installed only the declared project dependencies locally, and passed `pip check`, all tests, and Ruff. |
| pip printed cache-deserialization warnings | pip ignored those cache entries and completed with exit 0. Did not delete caches or change global pip; dependency checks passed. |
| Duplicate lockfiles caused inferred-root warnings | Kept both existing files and explicitly set the web tracing root; lint/type/build passed without that warning and the standalone server layout was verified. |
| Windows quoting broke an initial volume-guard format expression | The guard stopped before applying the container change. Switched to parsing limited mount JSON, revalidated the same named volume, then performed the approved recreation. |
| No Git protection existed | Added ignore rules before initialization; verified 16 ignored and four required eligible paths, empty staging/history, and a limited secret-pattern scan. |

### Phase 1 maintenance summary and approval gate

The existing Phase 1 system now runs locally with the original database volume intact. Its small API, static DEMO page/assets, edge helper tests, lint/type checks, and production build pass. Git protection, project-local Python tooling, startup readiness, and localhost-only ports are in place. The npm findings and recorded deprecation/configuration limitations remain visible rather than being hidden by forced upgrades.

This completes the requested environment/repository check. It does not implement or approve Phase 2. Stop here for founder review and approval before any next milestone or unapproved dependency migration.

## Git checkpoint configuration cleanup: 2026-11-07

### Objective and current approval boundary

While preparing the first local checkpoint, the security scan found embedded development database credentials in `.env.example`, `docker-compose.yml`, and `services/api/alembic.ini`. The founder chose to hold the commit for cleanup. No commit has been created during this preparation; the revised staged files require a new explicit approval.

This is configuration maintenance. No Python/TypeScript application behavior, database schema, dependency version, Docker container, or database content was modified. No file was deleted, no remote was created or changed, and no push was attempted.

### Files and technologies

- `.env.example` now leaves `POSTGRES_USER` and `POSTGRES_PASSWORD` empty and supplies only a credential-free database URL. It is a safe template; actual `.env` files remain ignored.
- `docker-compose.yml` requires local username/password variables instead of embedding values. It forwards `PGUSER`, `PGPASSWORD`, and `PGDATABASE` to the API. Existing volume names, localhost port bindings, and readiness settings are retained.
- `services/api/alembic.ini` uses `postgresql+psycopg://db` without a username, password, or database name. Psycopg/libpq supplies omitted connection values from the standard PostgreSQL environment variables, so `migrations/env.py` needs no code changes.
- A new ignored `.env` preserves the existing local database settings. Byte-identical original copies of the three configuration files are retained in a private ignored subdirectory of `.secrets/`. The template and report contain no actual credential values.
- `.gitignore` now also excludes generated `next-env.d.ts`. README, handoff, roadmap, and index explain the revised configuration and verification boundary.

The local `.env` and backup files contain plaintext development settings; Git exclusion is not encryption. Environment-based password handling is a local development mechanism. PostgreSQL recommends considering password files because process environments can be visible on some operating systems. Production secret management remains separate work. See the official [PostgreSQL environment-variable documentation](https://www.postgresql.org/docs/current/libpq-envars.html) and [Psycopg connection documentation](https://www.psycopg.org/psycopg3/docs/api/connections.html).

### Execution flow and Windows instructions

1. Preserve the three original configuration files under ignored `.secrets/` and verify their hashes.
2. Preserve their current local values in ignored `.env`; do not rotate credentials or alter the existing database.
3. Replace versioned values with blank template fields, required variable references, and a credential-free Alembic URL.
4. Validate Compose locally without applying it to Docker. Verify the rendered environment matches the preserved local settings, including the same volume name and loopback ports. Keep full rendered output private because it contains resolved credentials.
5. Validate SQLAlchemy's parsed connection arguments and perform a read-only connection through the existing localhost database using the private PostgreSQL variables. Only connection diagnostics and `SELECT 1` are used; no migration or data modification is performed.
6. Review and stage the sanitized files with the source/documentation. Scan the actual Git index, then request approval before creating the local commit.

From the repository root in PowerShell:

```powershell
# Uses the existing private .env; prints no resolved credentials.
docker compose config --quiet

Push-Location services/api
& ..\..\.venv\Scripts\python.exe -m alembic heads
Pop-Location

git check-ignore -v -- .env .secrets/verification-only apps/web/next-env.d.ts
git diff --cached --name-only
```

For a fresh checkout, copy `.env.example` to a new `.env` and supply local username/password values before any approved startup. Preserve an existing `.env`. For an existing database volume, keep its current credentials; changing the environment file alone does not update the database role. Do not rebuild/recreate containers or run migration upgrades as part of this Git-only cleanup.

### Actual results and limits

| Check | Actual result |
| --- | --- |
| Local preservation | **PASS:** original three files backed up with matching hashes; existing local values preserved in ignored `.env` |
| Compose rendering | **PASS:** database/API credential references resolve to the preserved local values; URL has no embedded credentials; original volume name and localhost bindings retained |
| Empty-template behavior | **PASS:** rendering with the blank template fails instead of silently supplying a default password |
| SQLAlchemy/Psycopg argument check | **PASS:** sanitized Alembic URL specifies host `db` and no user/password/database arguments, allowing the standard private PostgreSQL variables to supply them |
| Read-only driver validation | **PASS:** credential-free localhost URL and private PostgreSQL variables complete `SELECT 1`; `transaction_read_only` is confirmed `on` |
| Alembic configuration | **PASS:** `alembic heads` exits 0; there are still no migration revisions |
| Revised staging/security review | **PASS:** 43 source/configuration/documentation files staged; no matching secret patterns or forbidden private/generated paths in the Git index. Credential fields are blank in the template or required variable references in Compose. Actual `.env`, private backups, dependencies, generated files, and footage remain ignored. This signature review is not a complete security audit. |
| Documentation and file preservation | **PASS:** 29 local documentation links resolve. Against the 45 original non-generated project files, only the nine intended configuration/documentation files changed; none was deleted and application behavior source remains unchanged. Private local files, Git metadata, and caches are outside this comparison. |
| Container/dependency mutation | **NONE:** no container start/stop/recreation/build, image pull, package installation/upgrade, or SQL data/schema modification |
| Fresh Docker build/start with sanitized files | **NOT VERIFIED:** existing containers keep their earlier configuration/image; applying the new credential wiring is outside this Git-only task |
| Commit and Phase 2 | **NOT STARTED:** explicit commit approval is still required; no Phase 2 feature is implemented |

### Summary

The checkpoint can now include sanitized startup configuration instead of omitting it. Private local values and original files remain available outside Git. The source is ready for another staged-file review; a commit, container update, or subsequent phase must not be inferred from this cleanup.
