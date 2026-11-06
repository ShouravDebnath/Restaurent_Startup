# Implementation Plan

**Status:** Phases 0 and 1 foundations exist; the 2026-11-07 environment check verifies the local Phase 1 runtime. Phase 2 has not started.
**Rule:** Complete and verify one phase before beginning the next.

Use [CODEX_HANDOFF.md](CODEX_HANDOFF.md) for the project handoff and pending product decisions, and the [latest Phase 1 environment report](phase_explanations/PHASE_01.md#pre-phase-2-environment-and-repository-check-2026-11-07) for current runtime/repository evidence. Docker was unavailable during the earlier handoff; the later check restored and verified the existing stack. This roadmap describes intended milestones, not completed features.

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

The [complete Phase 2 handoff checklist](CODEX_HANDOFF.md#9-phase-2-requirements-and-acceptance-criteria) includes explicit location grants, role checks, safe camera metadata, typed schemas, audits, real migrations, positive/negative authorization cases, and phase documentation. Identity/session design, database isolation strategy, and the minimum-schema relationship to later device/event/task entities must be settled in the approved Phase 2 proposal. No Phase 2 implementation is authorized by this document.

## Phase 3: simulated dashboard

Build the DEMO floor view, table states, timers, tasks, staff actions, SSE or justified equivalent, offline indicators, accessibility labels, and mobile layout.

**Exit:** Two demo tenants show separate end-to-end workflows without video.

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
2. Identity provider and admin MFA approach.
3. Supported camera/NVR and edge hardware list.
4. Detector/weight license and commercial obligations.
5. Deployment and support partner.
6. Video/diagnostic retention, notices, and deletion process.
7. Database row-level security decision.
8. Initial thresholds and accuracy gates after labeled data.

## Current blockers

- The Markdown blueprint and `references/SR.mp4` are present. The master specification is byte-identical to the Markdown blueprint. A separate PDF was not found and is not required to read the available specification.
- MP4 header inspection confirmed duration and dimensions. Visual frames were not re-reviewed during the handoff; earlier visual findings remain attributed to `docs/reference_analysis.md`. The reel is not authorized pilot/evaluation evidence by itself.
- The November 7 check started the existing Docker installation and verified localhost HTTP, database readiness, read-only SQL, API-to-database connectivity, and Alembic current-state inspection. The database still contains only an empty `alembic_version` table. No migration upgrade or tenant schema was created; a fresh clean-machine installation and rebuilt images were not tested.
- The project `.venv` was repaired using founder-approved local package/dependency installation. All four starter tests and Python lint pass. Package versions are not fully locked, and the resolved Starlette test stack emits an HTTPX deprecation warning. Host Python 3.14/Node 26 differ from Docker/CI Python 3.12/Node 22.
- npm audit still reports 8 affected packages (1 high, 7 moderate); no npm upgrades or overrides were applied. Explicit frontend tracing configuration removes the duplicate-lockfile warning. Deprecated `next lint` remains for later reviewed migration.
- Git and `.gitignore` now exist. No files are staged or committed, and no remote is configured; earlier history and hosted CI results remain unavailable. A reviewed first commit/backup is still pending.
- Approved Compose changes restrict published ports to localhost and add database/API readiness checks. The original PostgreSQL volume was preserved. Later Git preparation removes embedded credentials from the versioned template/Compose/Alembic settings and preserves local values in ignored `.env` and `.secrets/` files. That file cleanup has not been applied to the existing containers. Unused `APP_ENV`/`DEMO_MODE` behavior, Alembic's separate URL setting, and production secret management remain future configuration work; this setup is not production-hardened.
- Identity/session choice, explicit location permissions, database isolation, schema scaffolding, and safe test-database provisioning remain decisions for the Phase 2 proposal. Hardware, model licensing, consent, real metrics, and external services remain unverified for later phases.

See the [handoff](CODEX_HANDOFF.md) for exact commands, outcomes, risk details, and the approval gate. Phase 2 remains unstarted.
