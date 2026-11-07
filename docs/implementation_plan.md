# Implementation Plan

**Status:** Phases 0–3 implemented; Phase 3 local verification recorded in its explanation. Stop for founder review before Phase 4.
**Rule:** Complete and verify one phase before beginning the next.

Use [CODEX_HANDOFF.md](CODEX_HANDOFF.md) for the startup handoff and historical inspection, [PHASE_02.md](phase_explanations/PHASE_02.md) for current implementation/evidence, and the earlier [Phase 1 environment report](phase_explanations/PHASE_01.md#pre-phase-2-environment-and-repository-check-2026-11-07) as a historical maintenance record. Only phases explicitly marked implemented below are completed; later milestones remain planned.

The later-product labels “Phase 2” and “Phase 3” in master section 4.2 refer to expansion versions. The numbered development phases below follow master section 17; development Phase 2 is tenancy and authentication.

## Phase 0: specification freeze

- Preserve the full blueprint as `docs/MASTER_SPEC.md`.
- Review architecture, API boundaries, threat model, states, tenant model, and test strategy.
- Record human decisions about identity, camera compatibility, model licensing, deployment hardware, privacy, and pilot geography.
- No application features.

**Exit:** Founder approves the plan and unresolved decisions are visible.

## Phase 1: repository foundation

Create the monorepo structure, Next.js/TypeScript web app, FastAPI service, PostgreSQL/Alembic setup, Python edge-agent package, Docker Compose, environment template, health endpoints, CI, starter tests, and synthetic demo data. No real CCTV or inference. The existing demo is one public hard-coded organization/location response, not a database seed or tested tenant boundary.

**Exit:** Clean checkout starts locally with documented commands, health page works, and starter tests pass.

## Phase 2: tenancy and authentication

Implement organizations, locations, users, memberships, roles, cameras, tables, zones, audit records, migrations, authenticated routes, seed data, and adversarial tenant-isolation tests.

**Exit:** Two seeded tenants are isolated by backend enforcement.

**Implemented/verified:** real additive migrations 0001/0002; ten seeded users across two synthetic organizations/four locations; Argon2id and revocable cookie sessions; CSRF/throttling; approved roles and explicit location grants; strict metadata/configuration APIs, immutable ownership/composite foreign keys, restricted runtime login plus PostgreSQL RLS, atomic audits, and connected configuration screens. The final Python run passed 152 tests, including both-direction API and direct-database isolation tests. See [actual results](phase_explanations/PHASE_02.md#actual-verification-results).

The [complete Phase 2 checklist](CODEX_HANDOFF.md#9-phase-2-requirements-and-acceptance-criteria) is mapped to evidence in the phase explanation. The founder approved the [local-session/RLS architecture](PHASE_02_ARCHITECTURE_PROPOSAL.md), role matrix, safe test/backup/migration procedure, and deferral of device/event/task schema and camera-device association. This approval does not authorize Phase 3, public deployment, or a later dependency migration.

## Phase 3: simulated dashboard

Build the DEMO floor view, table states, timers, tasks, staff actions, SSE or justified equivalent, offline indicators, accessibility labels, and mobile layout.

**Exit:** Two demo tenants show separate end-to-end workflows without video.

**Implemented:** [PHASE_03.md](phase_explanations/PHASE_03.md) documents the responsive DEMO floor/staff views, six saved states, timers, reset tasks, protected actions, controlled database mutation function, durable ordered events/audits, restricted synthetic scenarios and authenticated SSE. Founder decisions preserve manual states during source failure and prohibit passive idle refresh. Additive revisions 0003/0004 preserve prior records. The expanded suite passes 262 tests, including the original 152; final runtime/browser evidence is recorded in that explanation. Phase 4 remains unstarted.

The [detailed Phase 3 plan](PHASE_03_IMPLEMENTATION_PLAN.md) records the approved requirements, architecture choices, implementation sequence and acceptance criteria. The [pre-Phase 3 review](phase_explanations/PHASE_02.md#pre-phase-3-review-2026-11-07) and [checkpoint manifest](PHASE_02_CHECKPOINT.md) preserve preparation history; the checkpoint was approved and created as `62ad229` before the separately approved Phase 3 implementation.

## Phase 4: local video and calibration

Implement MP4, webcam, and authorized RTSP adapters; reconnect and stale-frame behavior; configurable sampling; local preview; normalized polygon calibration; persistence and tests.

**Exit:** Authorized MP4 playback and calibration work; disconnects are visible as health failures.

## Phase 5: detector and state engine

Add a replaceable, license-reviewed detector; person-to-zone association; confidence thresholds; temporal filtering; deterministic transitions; manual precedence; local debug overlays only.

**Exit:** State-machine tests cover arrival, departure, occlusion, staff crossing, low confidence, outage, manual override, and resume. No invented accuracy claim.

## Phase 6: edge synchronization

Implement SQLite outbox, authenticated batches, device pairing, retries/backoff, restart replay, heartbeat, idempotency, revocation, and device-offline UI.

**Exit:** Outages and restarts preserve events, duplicate sends have one effect, and revoked devices are rejected.

## Phase 7: workflow and analytics

Connect transitions to one task per occupancy session, staff workflow, audit log, hourly/daily metrics, CSV export, time zones, missing-camera labels, and manual override tests.

**Exit:** Occupied -> reset pending -> cleaning -> available is visible and correctly reported.

## Phase 8: pilot hardening

Prepare production-like Compose, secrets handling, metrics, redacted logs, backups/restores, dependency checks, security tests, pairing instructions, and installer runbook. Do not call it production compliant without external review.

**Exit:** A technician and reviewer can reproduce installation, security, and restore checks.

## Phase 9: measured evaluation

Build authorized-clip labeling and evaluation tools. Report confusion matrix, per-state precision/recall, UNKNOWN coverage, false reset alerts per table-shift, latency, source identifiers, and model/config versions.

**Exit:** Pilot results are reproducible and weaknesses are prioritized without fabricated metrics.

## Phase 10: commercial SaaS

Only after Phase 9 and approval: add billing behind a feature flag, onboarding, subscription state, limits, usage metering, support tools, account lifecycle, webhook idempotency, and payment-provider eligibility review.

**Exit:** Billing and account lifecycle pass integration tests and provider approval exists.

## Test strategy

- Unit: state transitions, polygon association, timers, task deduplication, event validation, time-zone boundaries.
- Integration: API authorization, migrations, idempotent ingestion, device pairing, SSE authorization, analytics queries.
- Edge: MP4 fixtures, reconnects, stale frames, SQLite restart replay, queue ordering, no credential logging.
- E2E: sign-in/demo tenant, floor map, staff actions, analytics, offline banner, responsive layout.
- Security: negative cross-tenant tests, guessed IDs, altered request bodies, revoked devices, export/stream isolation.
- Evaluation: manually labeled authorized footage only, with reproducible configs and artifacts.

## Decisions requiring founder approval

1. First customer segment and US pilot geography.
2. Production identity lifecycle/admin MFA/account recovery; Phase 2 local sessions are chosen.
3. Supported camera/NVR and edge hardware list.
4. Detector/weight license and commercial obligations.
5. Deployment and support partner.
6. Video/diagnostic retention, notices, and deletion process.
7. External review and production hardening of the chosen backend authorization plus PostgreSQL RLS.
8. Initial thresholds and accuracy gates after labeled data.

## Current limitations and later gates

- The Markdown blueprint and `references/SR.mp4` are present. The master specification is byte-identical to the Markdown blueprint. A separate PDF was not found and is not required to read the available specification.
- MP4 header inspection confirmed duration and dimensions. Visual frames were not re-reviewed during the handoff; earlier visual findings remain attributed to `docs/reference_analysis.md`. The reel is not authorized pilot/evaluation evidence by itself.
- Phase 2 migrations, restricted runtime database access, rebuilt API/web images, and the running frontend/database path are now verified locally. A clean-machine installation and public production deployment are not verified. The original volume and database container were preserved, with a private backup restored in an isolated test database.
- The project `.venv` includes approved Argon2 dependencies. The Phase 3 suite passes 262 tests, including all 152 earlier cases and the four original starter tests. Package versions are not fully locked; the Starlette test stack emits an HTTPX deprecation warning. Host Python 3.14/Node 26 differ from Docker/CI Python 3.12/Node 22.
- npm audit still reports 8 affected packages (1 high, 7 moderate); no npm upgrades or overrides were applied. Explicit frontend tracing configuration removes the duplicate-lockfile warning. Deprecated `next lint` remains for later reviewed migration.
- Git checkpoints `6808a81` and `62ad229` exist on local `main`; Phase 3 changes remain uncommitted for review. No remote was added/changed or pushed. Hosted CI is configured for isolated PostgreSQL but has not run remotely.
- Compose now applies restricted runtime credentials and database-backed readiness; the API enforces `APP_ENV`, cookie/origin requirements, and `DEMO_MODE`. Administrative secrets stay outside API runtime. Private values/backups remain ignored, and `.dockerignore` protects build contexts. Production secret storage, non-root images, TLS, admin MFA/recovery, and external review remain open.
- The preserved legacy database administrator password is weak. The approved plan forbids rotating it in this phase; obtain approval for a reviewed rotation before public/pilot use. Runtime/demo credentials are separately generated and private.
- Identity/session, grants/RLS, safe tests and the Phase 3 synthetic event/task/SSE workflow are implemented. Hardware, model licensing, consent, video, real metrics and external services remain unverified. No Phase 4–10 feature is implemented.

See [PHASE_03.md](phase_explanations/PHASE_03.md) for current commands, outcomes, risk details and limitations. Stop for founder review; Phase 4 requires separate approval.
