# Codex Project Handoff: Restaurant AI Monitoring

**Handoff date:** 2026-11-06, using the founder's Asia/Dhaka calendar.  
**Scope:** Documentation and independent verification of the existing project.  
**Current development status:** Phases 0–2 implemented and locally verified; stop for founder review before Phase 3. The original November 6 inspection below is preserved as history.
**Main product authority:** [MASTER_SPEC.md](MASTER_SPEC.md), which is byte-identical to the supplied [Master Blueprint](../references/Restaurant_AI_Codex_Master_Blueprint.md) at this inspection.

> **Fresh pre-Phase 3 review — 2026-11-07:** All **152 tests passed again**, with one existing warning, in 13.05 seconds. Python lint/compatibility and frontend lint/type/build checks passed; authenticated proxy read/isolation/logout checks passed. Docker was initially stopped and the existing services were started without rebuilding or replacing them. Earlier interactive browser/backup-restore results remain historical. npm still reports 8 affected packages (1 high/7 moderate), and the weak legacy administrator password remains unresolved. See the [new evidence](phase_explanations/PHASE_02.md#pre-phase-3-review-2026-11-07), [safe local checkpoint manifest awaiting approval](PHASE_02_CHECKPOINT.md), and [detailed Phase 3 proposal](PHASE_03_IMPLEMENTATION_PLAN.md). No application behavior was changed; no Phase 3 implementation or commit/push was performed in this review.

> **Current Phase 2 update — 2026-11-07:** The founder explicitly approved Phase 2 and both [architecture choices](PHASE_02_ARCHITECTURE_PROPOSAL.md) before implementation. Current source now has PostgreSQL tenancy/configuration models, additive migrations 0001/0002, local Argon2id/server sessions, roles and explicit location grants, backend authorization plus RLS, atomic audits, synthetic seeds, and connected sign-in/configuration screens. The final Python run passed 152 tests, with real PostgreSQL cross-tenant/direct-SQL checks; running-stack and Edge browser checks pass. The existing DB container and original volume are retained, with a private backup restored in an isolated test database. See [PHASE_02.md](phase_explanations/PHASE_02.md) for complete evidence, files, startup commands, limitations, and P2-01–P2-12 mapping. No live dashboard, video, inference, device sync, analytics, or billing was started.

> **How to read the older material:** Sections describing the November 6 architecture, files, feature gaps, environment, and verification preserve that inspection snapshot. Their statements about missing authentication/models, empty migrations, unavailable Docker, and missing Git history are historical and superseded by the updates above. Current risks still include 8 npm findings, test/lint deprecations, production identity/security operations, and unimplemented later features. Do not use an old “not started” or “not verified” entry as the current Phase 2 status.

> **Later environment update — 2026-11-07:** This handoff preserves the November 6 inspection snapshot. The subsequent [Phase 1 environment/repository check](phase_explanations/PHASE_01.md#pre-phase-2-environment-and-repository-check-2026-11-07) started Docker, verified the existing stack and read-only PostgreSQL access, repaired `.venv` with approved dependencies, initialized Git/ignore rules, restricted published ports to localhost, added readiness checks, and removed the duplicate-lockfile warning. CI/web image instructions now use `npm ci`. Earlier missing-environment findings below are historical, not current blockers. npm findings and other documented limitations remain; no Phase 2 work was started.

> **Git preparation and completed checkpoint — 2026-11-07:** The founder held the first proposal for configuration cleanup, then approved the revised 43-file local commit. The resulting checkpoint is `6808a81b7339f241701eb03552d952827872f168` on `main`, message `chore: phase 1 verified foundation checkpoint`. The [cleanup record](phase_explanations/PHASE_01.md#git-checkpoint-configuration-cleanup-2026-11-07) remains historical. Phase 2 later rebuilt the sanitized API/web images and applied restricted runtime credential wiring. Phase 2 changes are uncommitted; no remote was added/changed and nothing was pushed.

This document records a handoff from the previous assistant. It does not authorize another development phase. No application code, dependency versions, or database contents were changed during the handoff. No existing files were deleted and no dependencies were installed.

## 1. Startup vision and product boundaries

The founder is building an international restaurant operations SaaS business from Bangladesh, with US restaurants as the first intended customers. SaaS means that many restaurant businesses use one maintained software platform, while each business has private accounts, locations, cameras, configuration, and data. This project is intended to become a commercial product, with measurable operational value and authorized pilots before billing or scaling.

The central promise is to help staff see occupied tables, available tables, and tables that may need attention without watching CCTV all day. Existing compatible CCTV/IP cameras would feed a computer at the restaurant, called the **edge device**. That computer would estimate table occupancy locally and send small status events to the cloud. Continuous customer video would stay local by default.

The intended MVP includes:

- Authorized MP4, webcam, and RTSP camera inputs, with a documented compatibility list.
- Manually configured table regions, visible-person detection, and stable table states.
- A live floor view with labels, timers, health information, and clear uncertainty indicators.
- A reset-pending task after guests leave, followed by staff confirmation that the table is ready.
- Occupancy, table-turnover, and reset-delay reports based on recorded events.
- Separate restaurant organizations and locations, secure human/device access, and audit records.
- Durable offline event delivery and a complete synthetic demo that needs no real CCTV.

For example, Table 4 would become `OCCUPIED` after stable evidence of seated guests. After they leave and a vacancy grace period passes, it would become `RESET_PENDING`. Staff would start cleaning and confirm readiness. An empty camera region alone would never prove the table is clean.

| Planned state | Meaning |
| --- | --- |
| `UNKNOWN` | The camera is stale/offline, the view is blocked, or evidence is insufficient |
| `AVAILABLE` | The table is unoccupied and confirmed ready through an allowed path |
| `OCCUPIED` | Stable visual evidence indicates occupants |
| `RESET_PENDING` | Guests have left and staff attention may be needed |
| `CLEANING` | Staff have started resetting the table |
| `OUT_OF_SERVICE` | A manager has blocked the table |

These are product rules, not an implemented state machine. The current demo response contains examples of only four of these states.

Later product versions may add queue waiting times where tracking is reliable, POS/reservation integration, push notifications, multi-camera handling, and predictions after enough labeled history. The specification's later-product labels “Phase 2” and “Phase 3” are separate from its **development milestones 0–10**. Development Phase 2 covers authentication/tenancy and is now implemented; the next milestone, if approved, is the simulated dashboard.

The product excludes facial recognition, customer identity matching, audio monitoring, emotion analysis, covert employee scoring, unauthorized camera access, and automatic cleanliness claims. A seated-duration alert cannot prove someone has not been served without a trusted manual or POS event.

Commercial validation also matters: customer interviews, an understandable labeled concept demo, written pilot permission, measured reliability, evidence of willingness to pay, and repeatable installation. Prices and schedules in the blueprint are hypotheses and planning targets. No paying customers, approved payment provider, real installation, accuracy result, or production compliance was verified during this handoff.

## 2. Review inputs and evidence labels

The review covered `AGENTS.md`, the root README, the master specification and reference blueprint, architecture, API contract, implementation plan, threat model, reference analysis, both phase explanations, and the phase index. It also covered all existing application source, starter tests, package manifests and lockfiles, Docker files, Compose configuration, CI configuration, and migration scaffolding.

Use these labels when interpreting this handoff:

| Label | Meaning |
| --- | --- |
| **Implemented** | Source or configuration exists and was inspected |
| **Verified now** | A named check was run successfully during this handoff |
| **Historical report** | An earlier assistant recorded a result; it is not automatically a current result |
| **Blocked / not verified now** | A check could not be completed in the available environment |
| **Planned** | A requirement exists, but the functionality is absent |

The workspace has no `.git` metadata and `git status` cannot identify a branch, commit, or working-tree changes. Consequently, this handoff cannot verify repository history, prior approvals, or remote CI runs. A before/after SHA-256 file manifest is used to check the documentation-only boundary instead. Generated caches, installed dependency directories, and package-install metadata are excluded from that comparison.

### Reference video limitation

`references/SR.mp4` is present. Reading its MP4 headers without decoding frames confirmed approximately **84.6408 seconds**, **480×1068** video dimensions, and **18,040,039 bytes**. No video was uploaded or audio monitored.

Visual frame inspection was not repeated. The original decoder-availability assessment was incomplete: the November 7 inventory found `imageio-ffmpeg` already installed in the project `.venv`. No later frame/audio review was performed during these environment checks. The earlier codec, frame-rate, and scene descriptions remain attributed to [reference_analysis.md](reference_analysis.md). The promotional reel supplies visual inspiration; it supplies no measured AI accuracy, camera compatibility, or production evidence. Future inference/evaluation still requires synthetic or explicitly authorized footage and recorded provenance.

## 3. Architecture: current system and intended system

**Historical snapshot:** “current” in this section means the November 6 inspection. The Phase 2 update above supersedes those implementation gaps.

### Current execution flow

```text
Browser -> Next.js static foundation page with DEMO MODE text

HTTP client -> FastAPI /health -> process status and current UTC time
HTTP client -> FastAPI /v1/demo/tenant -> hard-coded synthetic response

Python caller -> edge health helper -> not_configured and UTC heartbeat time

Compose configuration -> separate web, API, and PostgreSQL services
                        (not running/reachable during this handoff)
```

The web page does not fetch the demo endpoint or query the database. The API imports no database session/model layer and makes no PostgreSQL queries. Compose environment variables and service definitions do not by themselves establish application data integration. `/health` is a process liveness response; it does not check database readiness.

### Intended architecture

```text
Authorized local camera or MP4
  -> video decoder and sampled frames
  -> replaceable, license-reviewed person detector
  -> normalized table polygons
  -> deterministic table-state engine
  -> durable local SQLite outbox
  -> outbound authenticated TLS event batches
  -> FastAPI authorization, validation, and idempotent persistence
  -> PostgreSQL table history, current state, tasks, and audit records
  -> authorized SSE updates and dashboard queries
```

The cloud remains a modular monolith: one FastAPI backend and one Next.js frontend, with a separate local Python edge process. Microservices, Kubernetes, and continuous cloud video are outside the MVP design. Human sessions and edge-device credentials must be separate. A device will be paired to one location; server-side pairing will determine its allowed organization and location.

All stored events must use UTC. Display and analytics boundaries must use the restaurant location's IANA time zone, including daylight-saving changes. The current API produces UTC timestamps and a synthetic `America/New_York` label; it does not yet store events or implement local-time analytics.

## 4. Existing technologies and important files

**Historical snapshot:** this file inventory describes the November 6 baseline. The current Phase 2 file inventory is in its explanation.

Versions below describe this inspected workspace. They are not a guarantee that a fresh installation will resolve the same versions.

| Technology | Purpose and current state |
| --- | --- |
| Next.js 15.5.29 | Builds the static foundation page; standalone output is configured |
| React / React DOM 19.3.1 | Render the page; versions recorded in the frontend lockfile |
| TypeScript 5.9.3 | Frontend type checking; strict mode is configured |
| Plain CSS | Current page styling; Tailwind is recommended by the blueprint but is not installed here |
| ESLint 9.39.5 / eslint-config-next 15.5.29 | Existing frontend lint setup; `next lint` is deprecated |
| FastAPI 0.136.3 / Pydantic 2.12.4 | API framework and typed response models in the available Anaconda environment |
| Uvicorn 0.48.0 | Available API server; no live server was started for this handoff |
| SQLAlchemy 2.0.43 / Alembic 1.17.2 | Available migration tools; models and application database access are absent |
| pydantic-settings 2.12.0 | Available and declared as a dependency; no settings class is implemented |
| PostgreSQL `16-alpine` | Configured Compose image; server version and contents were not inspected now |
| psycopg | Declared API database driver; absent from the Anaconda verification environment |
| pytest 8.4.2 / Ruff 0.12.0 / HTTPX 0.28.1 | Existing Python test, lint, and API test-client tools |
| Docker CLI 29.9.2 / Compose v5.6.1 | Installed tools; the configured Linux engine could not be reached |
| Node.js v26.13.0 / npm 11.20.0 | Installed host tools; Docker and CI target Node 22 |
| Python 3.13.9 | Existing Anaconda interpreter used for successful Python checks; Docker and CI target Python 3.12 |
| Python 3.14.0 project `.venv` | Exists but lacks pytest and the API development dependencies needed for these checks |
| OpenCV/FFmpeg, ONNX Runtime, SQLite outbox, SSE, Playwright | Planned application capabilities/tooling, not implemented product features |

The Python manifests specify version ranges rather than a locked complete environment. Frontend manifest ranges and exact lockfile versions also serve different purposes. Test success with preinstalled packages is not a clean-install verification.

| File or area | Purpose and actual implementation |
| --- | --- |
| `services/api/src/restaurant_api/main.py` | App factory, three response models, `/health`, and `/v1/demo/tenant` |
| `services/api/tests/test_health.py` | Two tests: health response and explicitly synthetic four-table response |
| `services/api/migrations/` and `alembic.ini` | Alembic environment/template; no revision files; model metadata is `None` |
| `services/api/pyproject.toml` and Dockerfile | Declared API/tooling dependencies and Python 3.12 container instructions |
| `services/edge-agent/src/restaurant_edge/health.py` | `EdgeHealth`, initial unconfigured health, and a UTC heartbeat helper |
| `services/edge-agent/tests/test_health.py` | Two tests: initial unconfigured state and timezone-aware heartbeat |
| `apps/web/app/` | Static page, HTML layout, metadata, and CSS; no floor map or API client |
| `apps/web/package.json`, lockfile, and configuration | Frontend commands, dependency resolutions, TypeScript, ESLint, and standalone build settings |
| `docker-compose.yml` | Database, API, web, published development ports, and named database volume; no edge service |
| `.github/workflows/ci.yml` | Proposed GitHub Actions execution of starter Python tests and web lint/build |
| `.env.example` | Development template; its presence does not mean every variable is consumed by code |
| `packages/contracts/README.md` | Contract placeholder; no executable shared contract package |
| `docs/` and `references/` | Requirements, target design, historical explanations, blueprint, and promotional reference |

## 5. Completed work and remaining functionality

**Historical snapshot:** statuses in this section describe the November 6 inspection, before the subsequently approved Phase 2 implementation.

### Phase 0: documentation foundation

The specification, architecture, initial API/event direction, threat model, and phased implementation plan exist. Inspection confirms the master specification matches the reference blueprint. Human decisions listed in those documents remain open unless separately recorded. Documentation completion does not prove security controls or product behavior are implemented.

### Phase 1: repository foundation

Implemented source includes the web shell, typed API responses, a synthetic organization/location with four hard-coded tables, the edge health helper, four starter tests, migration scaffolding, Docker/Compose files, and a CI workflow.

The demo endpoint is public, stateless, and synthetic. Its timestamps are generated again on each request. It is not a database seed, occupancy history, or durable timer. There is only one example organization. The word “isolated” in earlier descriptions must not be interpreted as tested tenant enforcement.

| Capability | Current status |
| --- | --- |
| Static DEMO page, synthetic API responses, edge health helper | Implemented; relevant checks verified now |
| PostgreSQL/Compose/Alembic foundation | Configuration implemented; configuration/offline checks passed; connected behavior blocked now |
| Previously running containers, database SQL connectivity, `alembic_version`, HTTP 200 | Historical reports in Phase 1; not independently confirmed now |
| Users, sessions, memberships, location permissions, roles, audit records | Planned for Phase 2; absent |
| Persisted tenant/location/camera/table/zone records | Planned for Phase 2; absent |
| Tenant isolation, including two restaurants | Planned and untested; no enforcing code exists |
| API-backed floor map, timers, tasks, staff controls, SSE | Planned across Phases 3 and 7; absent |
| Video input, calibration, detection, table-state engine | Planned for Phases 4 and 5; absent |
| Device pairing, offline outbox, secure cloud synchronization | Planned for Phase 6; absent |
| Analytics, exports, deployment hardening, evaluation, billing | Planned for later phases; absent |

No real CCTV system, AI quality metric, physical hardware compatibility, or production deployment was verified.

## 6. Independent verification during this handoff

Checks below were rerun for the documentation execution. Existing packages were used; no installation, upgrade, online migration, database reset, or container startup was performed.

| Check | Result and practical meaning |
| --- | --- |
| API `pytest -q -p no:cacheprovider` | **PASS:** 2 tests, 0.62 seconds; in-process TestClient responses, not a running network server |
| Edge `pytest -q -p no:cacheprovider` | **PASS:** 2 tests, 0.02 seconds; helper behavior, not camera processing |
| Ruff `check --no-cache .` in both Python services | **PASS:** both checks returned exit 0 |
| Frontend `npm run lint` | **PASS:** exit 0; framework deprecation and multiple-lockfile warnings still printed |
| Frontend local `tsc --noEmit --incremental false` | **PASS:** exit 0 |
| Frontend `npm run build` | **PASS:** isolated same-drive copy compiled, checked lint/types, and generated static pages; exit 0 |
| `docker compose config --quiet` | **PASS:** exit 0; configuration syntax only |
| `docker compose ps --format json` | **BLOCKED:** exit 1; configured Docker engine pipe was unavailable |
| GET checks to localhost ports 8000 and 3000 | **NOT REACHABLE:** health, demo tenant, and web URLs all refused connection |
| PostgreSQL connection, table contents, connected migrations | **NOT VERIFIED:** engine unavailable; no database contents were read or changed |
| `alembic heads` and revision inventory | **PASS as inspection:** no heads and zero revision files; this does not prove a schema exists |
| `alembic upgrade head --sql` | **PASS as offline configuration check:** exit 0; emitted bookkeeping SQL only, including `DROP TABLE alembic_version`; SQL was not executed |
| Project `.venv` pytest availability | **UNAVAILABLE:** `No module named pytest`; successful tests used Anaconda instead |
| npm lockfile audit | **FINDINGS:** exit 1; 8 affected packages, detailed below |
| Blueprint equality and video header inspection | **PASS:** exact blueprint match and video metadata described above |

The offline Alembic result is especially limited: an empty revision graph can produce successful output without creating any application schema. Do not pipe its output into a database or interpret it as a successful tenant migration.

### Build isolation and retained artifacts

The fresh build ran at `E:\restaurant-handoff-verification-82c134497f704fc294e42e493515f86f\apps\web`. Source/configuration files and the lockfiles were copied there, and a directory junction reused the existing `node_modules`; nothing was installed. Build output stayed outside the application source tree. Inspection/build artifacts were retained because deleting existing files was outside this task's authorization.

During the earlier planning inspection, a temporary build on the C: drive failed because webpack could not resolve a cross-drive node_modules path. A same-drive build passed, and the fresh handoff build also passed. The cross-drive failure was a verification-setup limitation, not evidence of an application compiler defect. No Docker image build or running browser smoke test is implied by the successful local build.

### Windows 11 reproduction using existing dependencies

These commands show the environment actually used. The Anaconda path is specific to this machine. They do not install anything or apply database migrations.

```powershell
Set-Location E:\Restaurent_startup\services\api
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
& 'C:\ProgramData\anaconda3\python.exe' -m pytest -q -p no:cacheprovider
& 'C:\ProgramData\anaconda3\python.exe' -m ruff check --no-cache .
& 'C:\ProgramData\anaconda3\python.exe' -m alembic heads
& 'C:\ProgramData\anaconda3\python.exe' -m alembic upgrade head --sql

Set-Location E:\Restaurent_startup\services\edge-agent
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
& 'C:\ProgramData\anaconda3\python.exe' -m pytest -q -p no:cacheprovider
& 'C:\ProgramData\anaconda3\python.exe' -m ruff check --no-cache .

Set-Location E:\Restaurent_startup\apps\web
$env:NEXT_TELEMETRY_DISABLED = '1'
npm run lint
& '.\node_modules\.bin\tsc.cmd' --noEmit --incremental false
npm audit --package-lock-only --ignore-scripts --json

Set-Location E:\Restaurent_startup
docker compose config --quiet
docker compose ps --format json
```

The production-build result above came from the isolated copy, not a source-tree build. Normal installation/startup instructions remain in the root README as a future setup procedure; they were not executed here. Restoring a controlled development environment and retesting the full stack is recommended before Phase 2 implementation, with separate permission for any required installation or system changes.

## 7. Dependency findings, technical debt, and security risks

**Current resolution note:** Phase 2 resolves the old missing authentication/model/migration/tenant-boundary entries, adds safe private runtime configuration and applied images, and verifies the existing volume/database path. Current remaining limits and the fresh 8-entry npm audit are in [PHASE_02.md](phase_explanations/PHASE_02.md#remaining-limitations-and-technical-debt). The table below is the preserved original risk assessment, not a claim those resolved gaps remain absent.

### npm dependency findings

`npm audit --package-lock-only --ignore-scripts --json` reported **8 affected package entries: 1 high and 7 moderate**, with no critical, low, or informational entries. Several entries are consequences of the same dependency chain; this is not eight independent demonstrated exploits.

| Package | Locked version | npm severity | Reported dependency relationship |
| --- | --- | --- | --- |
| `postcss` | 8.4.31 | High | Transitive dependency associated with Next.js |
| `next` | 15.5.29 | Moderate | Direct dependency flagged through PostCSS |
| `minimatch` | 10.2.6 in typescript-estree's nested dependencies | Moderate | Affects the lint-tool dependency chain |
| `@typescript-eslint/typescript-estree` | 8.72.1 | Moderate | Flagged through minimatch |
| `@typescript-eslint/parser` | 8.72.1 | Moderate | Flagged through typescript-estree |
| `@typescript-eslint/type-utils` | 8.72.1 | Moderate | Flagged through typescript-estree/utils |
| `@typescript-eslint/utils` | 8.72.1 | Moderate | Flagged through typescript-estree |
| `@typescript-eslint/eslint-plugin` | 8.72.1 | Moderate | Flagged through parser/type-utils/utils |

The audit listed these underlying advisories:

- PostCSS CSS serialization issue: [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93).
- PostCSS file-read/information-disclosure issue: [upstream GHSA-6g55-p6wh-862q](https://github.com/postcss/postcss/security/advisories/GHSA-6g55-p6wh-862q).
- PostCSS incomplete source-map fix: [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp).
- PostCSS source-map path traversal: [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849).
- Minimatch pattern amplification: [upstream GHSA-g3hv-75wg-m249](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249).

The upstream PostCSS and minimatch advisories were consulted during the handoff review. The other links are references returned by npm audit. No exploit was run and application-specific reachability was not established. Audit output suggested a major Next.js upgrade for part of the dependency tree; this is not an approved remediation plan. No `audit fix`, override, lockfile rewrite, or upgrade was applied. Python dependencies, container images, and model licenses were not comprehensively security-scanned during this handoff.

### Known issues and boundaries

| Finding | Consequence and next action |
| --- | --- |
| No authentication or tenant/location authorization | Expected Phase 2 gap and a blocker for customer data. Public demo data must remain synthetic until backend enforcement exists. |
| No database models, revision files, seed routine, or DB-backed endpoints | Existing demo records are not persisted. Phase 2 needs a tested schema and authorization-aware access layer. |
| `.git` and root `.gitignore` absent | Commit provenance/remote history cannot be checked. Review repository recovery and ignore rules before versioning secrets, environments, caches, or artifacts. No Git initialization was performed. |
| Project `.venv` lacks development dependencies; host/Docker/CI versions differ | Current test success does not reproduce a fresh environment. Choose a supported toolchain and obtain installation permission if needed. |
| Docker engine and local services unavailable | Current full-stack startup, SQL connectivity, and connected migration claims remain unverified. Diagnose the existing engine without resetting databases or volumes. |
| Alembic uses the URL in its INI file and has `target_metadata=None` | It does not read `DATABASE_URL` from the environment; model discovery and runtime configuration need future work. Connection strings must remain out of logs and reports. |
| `DEMO_MODE`, `APP_ENV`, and configurable-port intent are not fully wired | Demo route and environment label are hard-coded; template port variables do not control the fixed Compose mappings. No operational demo-disable control currently exists. |
| Fixed development database credentials and published ports in Compose | This is a local development setup, not a safe production configuration. Database, API, and web bindings are not explicitly limited to loopback. Do not deploy it unchanged. |
| Compose startup dependencies lack readiness health checks | Starting containers would not prove the database is ready. `/health` also does not test it. |
| Frontend says it is connected to a synthetic boundary, but makes no API calls | Treat the text as foundation copy, not integration evidence. API-backed UI belongs to Phase 3. |
| Demo state timestamps reset on every request; only four states are represented | No real occupancy timer, state history, six-state engine, or workflow exists. |
| Empty root lockfile plus frontend lockfile | Next.js infers a workspace root and prints a warning. Review workspace/tracing configuration later without deleting files during this handoff. |
| `next lint` is deprecated | Future framework upgrades need a reviewed lint-command migration. No codemod was executed. |
| Web Dockerfile and CI use `npm install`; Python dependencies are broad ranges | Reproducibility needs review. The presence of a lockfile alone does not prove immutable CI installation. |
| CI configuration is narrower than the proposed strategy | Python jobs run starter tests, not Ruff, database, isolation, browser, or security suites. Web build checks types, but no dedicated browser tests exist. Hosted CI execution is unverified. |
| Shared contracts are notes only | Typed API resource contracts and future versioned edge-event validation still need implementation in the relevant milestones. |
| Four starter tests have narrow assertions | They do not establish tenancy, roles, offline behavior, exact UTC offset, camera safety, or production readiness. The heartbeat test checks timezone awareness rather than specifically asserting UTC offset. |
| No implemented security/operations controls for real deployment | TLS deployment, mature sessions/MFA, rate limits, secret storage/redaction, device revocation, backups/restores, retention, and incident procedures require their assigned implementation and tests. |
| No authorized pilot evidence or model decision | Supported hardware, license obligations, accuracy, latency, false alerts, and legal/customer notices remain unresolved. |

Some findings are expected future-phase work rather than regressions. They are recorded so future contributors cannot mistake scaffolding or promotional text for production capability. Secret-signature inspection during planning found no matching reviewed token/private-key patterns in the inspected source/doc subset; this was not a complete secret audit and says nothing about unavailable Git history. No secret values are reproduced in this handoff.

## 8. Future development roadmap: Phases 0–10

The authoritative sequence is section 17 of the master specification and [implementation_plan.md](implementation_plan.md). Every milestone ends with verification, its own phase explanation, founder review, and a stop before the next phase.

| Phase | Required outcome | Acceptance gate and current status |
| --- | --- | --- |
| 0 — Specification freeze | Requirements, architecture, API direction, threat model, implementation plan, visible open decisions | Documents exist; reviewed now. Historical completion and approval are recorded in phase notes, not independently proven through Git history. |
| 1 — Repository foundation | Web/API/edge packages, Compose/PostgreSQL/Alembic setup, demo, tests, CI, startup instructions | Foundation implemented and locally verified; historical environment blockers resolved. Starter tests preserved/passed in Phase 2. |
| 2 — Tenancy and authentication | Persistent entities, secure sessions, roles, organization/location authorization, audits, two synthetic tenants | **Implemented/locally verified.** All tested negative cases blocked in the final 152-test run; connected runtime/browser checks pass. See PHASE_02.md. |
| 3 — Simulated dashboard | DEMO floor map, six states, timers, tasks, staff actions, SSE, offline labels, accessible mobile layout | Two demo restaurants have different end-to-end workflows without video. **Planned.** |
| 4 — Video input and calibration | MP4/webcam/authorized RTSP adapters, timestamps, sampling, reconnect/stale handling, secure local preview, persistent polygons | Authorized MP4 works, calibration survives restart, and disconnects appear as health failures. **Planned.** |
| 5 — Detector and state engine | License-reviewed detector, person-to-zone mapping, thresholds, hysteresis, manual precedence, authorized local debug overlays | Deterministic arrival/departure/occlusion/staff-crossing/low-confidence/outage/override/resume tests pass; no invented accuracy. **Planned.** |
| 6 — Edge synchronization | SQLite outbox, one-location device pairing, TLS batches, deduplication, retry/backoff, restart replay, heartbeat, revocation | Restart and a 15-minute outage preserve events; duplicate posts have one effect; wrong-location/revoked devices fail; out-of-order delivery is tested. **Planned.** |
| 7 — Workflow and analytics | One reset task per relevant session, acknowledgment/cleaning/ready controls, audits, occupancy/reset metrics, CSV, IANA-zone boundaries | Complete occupied-to-reset-to-cleaning-to-available workflow and correct reports, including missing-camera periods and overrides. **Planned.** |
| 8 — Pilot hardening | Production-like packaging, secrets, metrics/log redaction, backup/restore, dependency/security checks, installer/pairing runbook, authorized onboarding | Technician/reviewer can reproduce installation, restore, and security checks; external review still required. **Planned.** |
| 9 — Measured evaluation | Authorized labeled clips, reproducible configurations/model versions, state confusion matrix and precision/recall, UNKNOWN coverage, false reset alerts, latency | Real pilot results can be reproduced and weaknesses prioritized. **Planned; no metrics exist.** |
| 10 — Commercial SaaS | After Phase 9 approval: flagged billing, onboarding, subscriptions, limits, metering, support/account lifecycle | Billing/webhook/cancellation tests and actual payment-provider approval for the intended company. **Planned.** |

The blueprint's initial quality targets include at least 90% state accuracy on a diverse independently labeled pilot set, less than 5 seconds from received edge event to dashboard, no more than one false reset alert per table-shift, and all negative tenant tests blocked. These are **unverified targets**, with per-state results and UNKNOWN coverage required; they are not present product performance.

## 9. Phase 2 requirements and acceptance criteria

This section preserves the full Phase 2 requirements prepared by the handoff. The founder later approved the design and implementation; [PHASE_02.md](phase_explanations/PHASE_02.md#acceptance-mapping-and-summary) maps every acceptance item to actual evidence. Statements below about choices to settle describe the original planning gate, which is now resolved by the approved architecture record.

### Required behavior and data

1. **Organizations and locations:** persist independent restaurant organizations and their locations. Every location has its parent organization and valid IANA time zone. Tables belong to exactly one location.
2. **Users, memberships, roles, and explicit location permissions:** persist user identity, enabled organization memberships, and permitted roles/locations. Cover organization admin/owner, location manager, floor staff, and installer responsibilities from the master specification. Platform support/admin access must not imply unrestricted tenant or video access. Choose exact grants in the approved Phase 2 design.
3. **Authentication:** use a mature identity provider or secure session mechanism; implement the selected session entry/callback and `/v1/me` or its approved equivalent. Missing, invalid, expired/revoked credentials and disabled memberships must not authorize protected requests. Human identity must remain separate from later device credentials. Record admin MFA support and limitations.
4. **Camera metadata:** persist location-scoped labels/status and safe source references. Do not expose passwords, authenticated RTSP URLs, or add camera ingestion. A browser only receives safe metadata.
5. **Tables and zones:** persist table identity/labels, optional seats, state fields needed by later phases, and camera/table zone relationships. Use the canonical six-state vocabulary. Save normalized polygon points in the 0–1 range with source resolution and calibration revision, and validate referenced camera/table location consistency. The drawing UI and vision state machine remain later work.
6. **Backend authorization:** derive access from authenticated identity, enabled membership, role, and explicit location permission. Scope both queries and mutations. Supplied organization/location IDs, nested references, and resource reparenting must not escape that scope. Hiding buttons is insufficient.
7. **Authenticated APIs and typed schemas:** provide the entity-management/resource routes required by the approved Phase 2 design. Keep `/v1` naming, generated OpenAPI, safe errors, least-privilege actions, and the intended API contract. No CRUD route design beyond existing specification examples has been approved by this handoff.
8. **Audit records:** persist tenant-scoped actor/action/time/details for sensitive configuration, membership/role changes, and relevant authorization-sensitive operations. Protect audit access and exclude secrets. Later workflow actions must use this foundation when implemented.
9. **Migrations and synthetic seeds:** add real Alembic revisions and model metadata for the approved entities, use environment-driven safe configuration, and seed at least two separate synthetic tenants with location/user/resource examples. Preserve existing data; test migrations against a separately authorized disposable test database, never an existing restaurant database.
10. **Adversarial automated tests:** test positive authorized behavior and negative organization/location/role paths, guessed IDs, changed request bodies, foreign referenced resources, and identity/privilege changes. Do not stop at checking UI filters.

### Master data-model reconciliation before coding

The Phase 2 proposal must account for these minimum fields from master section 9, alongside its typed API and database validation:

| Phase 2 entity | Minimum field/relationship checklist |
| --- | --- |
| Organizations | ID, name, plan metadata, creation time; a plan field does not implement billing |
| Locations | ID, organization ID, name, IANA time zone, optional address |
| Users | ID, email, display name, identity-provider identifier appropriate to the chosen identity mechanism |
| Memberships and permission representation | User ID, organization ID, role, enabled flag, and explicit permitted locations; choose and document the location-grant structure |
| Cameras | ID, location ID, label, safe source reference, status, and an explicit decision for the later edge-device reference |
| Tables | ID, location ID, label, optional seats, canonical current state, and UTC state-entry time |
| Table zones | ID, table ID, camera ID, normalized polygon, revision/calibration version, and source resolution |
| Audit logs | ID, actor type/ID, organization ID, action, UTC occurrence time, and safe details |

Role and location-permission enforcement must exist even if the chosen schema represents roles as values rather than a separate roles table. These fields are requirements to reconcile in the next proposal, not migrations created by this handoff.

Master section 9 lists organizations, locations, users, memberships, edge devices, cameras, tables, zones, events, staff tasks, and audit logs as the minimum eventual data model. Its Phase 2 milestone explicitly names the tenancy/authentication entities, camera/table/zone schemas, and audits; device synchronization and event/task behavior are assigned to later milestones.

The Phase 2 implementation proposal must explicitly settle whether later entities need inert schema scaffolding now, especially the camera-to-device reference, or will arrive through later migrations. Do not silently omit a master requirement, create unrelated later workflows, or label a choice founder-approved. Membership storage must also represent explicit location access even though the minimum table list does not name a dedicated grants table.

### Phase 2 acceptance checklist

| ID | Required evidence before Phase 2 can be declared complete |
| --- | --- |
| P2-01 | Real migrations create the approved schema in an authorized test database; relationships, tenant ownership, and normalized polygons validate correctly. No existing database is reset. |
| P2-02 | Two seeded synthetic restaurant organizations have distinct locations, users/memberships, cameras, tables, and zones. Data persists rather than being rebuilt in the response. |
| P2-03 | Valid sessions identify the correct user and permitted organizations/locations. Missing/invalid/expired or revoked sessions and disabled memberships cannot use protected routes. |
| P2-04 | Restaurant A cannot list, read, create within, update, delete through any provided mutation, or otherwise access Restaurant B resources, even with valid guessed IDs. Add tests for every implemented resource route. |
| P2-05 | Altered organization/location fields, cross-location camera/table links, nested foreign IDs, and role/membership updates cannot grant unauthorized access. |
| P2-06 | A user restricted to one location cannot use another location in the same organization; authorized multi-location access works only with explicit grants. |
| P2-07 | Staff, installer, manager, and organization-admin permissions match the approved role matrix; lower roles cannot modify grants or escalate privileges. |
| P2-08 | Sensitive successful changes produce appropriately scoped audit records with UTC times and safe details. Users cannot read another tenant's audits. |
| P2-09 | OpenAPI request/response models and documented errors match actual protected endpoints. Unauthorized responses do not reveal another tenant's records or secret fields. |
| P2-10 | Existing health/demo behavior is preserved or any approved demo-safety adjustment is documented; starter lint, type, build, and test checks still pass. No customer data is served through the public synthetic demo route. |
| P2-11 | Backend tenant-isolation tests pass with 100% of negative cases blocked. Report actual commands/results and any unavailable identity service or database checks. |
| P2-12 | Create `phase_explanations/PHASE_02.md` with all required explanation sections, update the index and affected prior docs, explain the phase to the founder, and stop for approval. |

No billing, live dashboard implementation, camera connection, inference model, event synchronization, or production deployment is included in development Phase 2. Phase 2 alone will not complete the product.

## 10. Pending decisions and recommended next steps

### Phase 2 decisions now resolved

- Local Argon2id passwords and revocable server sessions approved/implemented; no external identity provider. Managed MFA, recovery, and email verification remain unavailable and need later decisions before real onboarding.
- Owner/admin/manager/staff/installer roles, enabled memberships, explicit grants, and no default platform/support override approved/implemented.
- Backend authorization plus PostgreSQL RLS with a restricted runtime login approved/implemented. Devices/events/tasks and camera-device association are deliberately deferred to later migrations.
- Project-only Argon2 dependencies approved/installed; no global installation or npm dependency upgrade. Dependency pinning/remediation and host/container version alignment remain maintenance decisions.
- Separate synthetic PostgreSQL testing, private backup/isolated restore, additive migrations, and idempotent seeds approved/executed; original volume/data retained.

### Decisions required before later pilot or commercial work

- Reviewed rotation of the preserved weak legacy database administrator password; the new API runtime credential is separate and generated. Do not rotate the old account without approval and a recovery plan.
- Brand/domain, company jurisdiction, initial US segment and pilot geography.
- Authorized video provenance, retention/deletion, customer notices/contracts, and appropriate external legal/security review.
- Supported camera/NVRs, edge operating systems/CPU/GPU capacity, installation technician, and support responsibilities.
- Detector software and weight licenses, exact model/configuration versions, and commercial obligations.
- Hosting, TLS, secret management, backups/restores, monitoring, incident contacts, and remote support access.
- Measured alert thresholds, operating limits, unknown-state coverage, evaluation dataset, and pilot quality gates.
- Payment-provider eligibility for the intended Bangladesh-based company, pricing validation, installation/support costs, and later billing approval.

Recommended next steps after Phase 2:

1. Review [PHASE_02.md](phase_explanations/PHASE_02.md), test both synthetic accounts locally, and keep private credentials/backups outside Git.
2. Decide any next local Git checkpoint separately; Phase 2 was not committed or pushed automatically.
3. Review npm findings and production identity/operational risks before pilot/public exposure; approve any dependency migration separately. Do not run a forced major upgrade.
4. Approve Phase 3 explicitly before simulated floor/timer/task/SSE work. No later phase is authorized by completing this handoff or Phase 2.

## 11. Handoff documentation changes and completion

**Historical snapshot:** this is the November 6 documentation-only completion record, preserved for traceability. Current Phase 2 completion and remaining risks are linked at the top.

| Document | Handoff change |
| --- | --- |
| `CODEX_HANDOFF.md` | Complete project understanding, current evidence, limitations, risks, roadmap, and Phase 2 checklist |
| Root `README.md` | Accurate synthetic-data description, current verification caveat, and documentation entry points |
| `architecture.md`, `api_contract.md`, `threat_model.md` | Explicit target-design labels so planned behavior is not mistaken for implemented controls |
| `implementation_plan.md` | Current phase status, corrected reference-asset availability, current blockers, and Phase 2 handoff link |
| `reference_analysis.md` | Separate historical visual analysis from the current metadata-only verification |
| `phase_explanations/PHASE_01.md` | Preserve earlier reports and add current verification, limits, and reproduction guidance |
| `phase_explanations/README.md` | Handoff link and precise current phase status |

Documentation verification checks local links and claimed source/runtime boundaries, compares the original Phase 1 explanation with the retained historical record, and checks the before/after manifest for changes outside the approved Markdown files. This handoff is not a new numbered development phase, so it creates no Phase 2 completion document.

### Actual documentation verification results

- **PASS:** 22 local Markdown file/section links resolve in the nine changed documents.
- **PASS:** 11 source/status assertions confirm the two product routes, static frontend, four-table synthetic response, absent API database layer, empty migration graph, unconfigured model metadata, unchanged blueprint equality, and unstarted Phase 2/documentation boundary.
- **PASS:** Compared all 43 baseline non-generated files: eight existing Markdown files changed, this handoff was added, and no files were removed. No application source, configuration, manifests, lockfiles, or reference assets changed.
- **PASS:** Removing the newly inserted evidence banner leaves the complete original Phase 1 explanation as an unchanged prefix, followed by the new handoff section. The Phase 00 explanation and both blueprint copies remain unchanged.
- **LIMIT:** Generated caches, installed dependencies, and package-install metadata are excluded from the file-manifest comparison. A limited signature scan of changed documents found no matching reviewed private-key/token/authenticated-RTSP patterns; this does not establish complete secret absence or production security.

**Founder-facing conclusion:** The written plan and starter foundation are in place. The small automated checks and frontend build pass. The full stack cannot currently be confirmed because Docker is unavailable, and the actual monitoring product has not been implemented yet. The next feature milestone is secure multi-tenant backend work, with decisions and tests recorded above. Stop here for founder review; Phase 2 remains unstarted.
