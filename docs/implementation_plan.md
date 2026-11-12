# Implementation Plan

**Phase 7 checkpoint verification — 2026-11-12:** Fresh complete regression passes **650 tests**, zero skips, plus **eleven browser groups** and frontend/Python checks. The founder verified A02 totals and opened its CSV in Excel. All 615 current baseline records, credentials/calibrations and the database volume are preserved. [The exact 55-file checkpoint review](PHASE_07_CHECKPOINT.md) records security findings and separate commit/push approval gates. Earlier 636/210-test results below remain historical.

**Phase 7 Analytics correction — 2026-11-12:** The founder's A02 test exposed a gap between the original DEMO scenario and the new reviewed-session summaries. This is fixed with a read-only projection, preserving original timestamps and all records. Current verification: 210 relevant tests, eleven browser groups and exact deployed A02 JSON/CSV/browser checks. [Explanation](phase_explanations/PHASE_07.md#a02-demo-analytics-correction--2026-11-12). No Phase 8 or new full native-suite result is claimed.

**Phase 7 completed locally — 2026-11-12:** [PHASE_07.md](phase_explanations/PHASE_07.md) records implemented suggestions, physical staff confirmation, protected task/correction history, compatible v2 evidence and analytics/CSV. Final verification passes **636 tests** and **ten browser groups**. Separately approved additive `0009`, restricted grants and matching local API/web/TLS services are active; all 580 original records and protected credentials/calibrations remain preserved and existing locations stay OFF. No new dependencies, commit, push, public deployment or Phase 8. Earlier proposal-only statements retain their dated historical meaning.

**Status:** Phase 6 is published as `fd983c7a656ab36f031db2900ef15a3da1362cbe`, after separate commit/push approvals and verified synchronization on 2026-11-11. Its recorded verification is 529 passing tests and six browser groups; these were not rerun for the Phase 7 proposal. Earlier phases, records and calibrations remain preserved. [Approved Phase 7](PHASE_07_IMPLEMENTATION_PLAN.md) is implemented and locally verified, with separately approved `0009` and matching services active and existing locations OFF; see [the actual record](phase_explanations/PHASE_07.md). Real-person accuracy, startup sensitivity and deployment security remain gated. No new commit/push or public deployment is authorized by planning.
**Rule:** Complete and verify one phase before beginning the next.

The [Phase 5 checkpoint review](PHASE_05_CHECKPOINT.md) preserves manual synthetic evidence, the fresh 445-test pass, initial intermittent timing failure and reviewed files. Its later publication outcome records separate commit/push approvals and matching GitHub/local hashes. The [approved Phase 6 plan](PHASE_06_IMPLEMENTATION_PLAN.md) preserves the design; [the Phase 6 explanation](phase_explanations/PHASE_06.md) records its implementation and subsequent verification. Delivery tests do not validate real-person or restaurant accuracy.

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

**Implemented:** [PHASE_03.md](phase_explanations/PHASE_03.md) documents the responsive DEMO floor/staff views, six saved states, timers, reset tasks, protected actions, controlled database mutation function, durable ordered events/audits, restricted synthetic scenarios and authenticated SSE. Founder decisions preserve manual states during source failure and prohibit passive idle refresh. Additive revisions 0003/0004 preserve prior records. The expanded suite passes 262 tests, including the original 152; final runtime/browser evidence is recorded in that explanation. Phase 4 has subsequently been approved and implemented; its actual results are below.

The [detailed Phase 3 plan](PHASE_03_IMPLEMENTATION_PLAN.md) records the approved requirements, architecture choices, implementation sequence and acceptance criteria. The [pre-Phase 3 review](phase_explanations/PHASE_02.md#pre-phase-3-review-2026-11-07) and [checkpoint manifest](PHASE_02_CHECKPOINT.md) preserve preparation history; the checkpoint was approved and created as `62ad229` before the separately approved Phase 3 implementation.

## Phase 4: local video and calibration

Implement MP4, webcam, and authorized RTSP adapters; reconnect and stale-frame behavior; configurable sampling; local preview; normalized polygon calibration; persistence and tests.

**Exit:** Authorized MP4 playback and calibration work; disconnects are visible as health failures.

**Implemented/verified — 2026-11-08:** [The approved plan](PHASE_04_IMPLEMENTATION_PLAN.md) and [Phase 4 explanation](phase_explanations/PHASE_04.md) cover native Windows MP4/webcam/restricted RTSP sources, supervised capture/reconnect, explicit human preview grants, private local canvas editing, diagnostics, full revision history and additive migrations 0005/0006. Actual synthetic MP4/browser/database integration is verified: 333 tests (all earlier 262), nine browser groups, isolated backup restore and preservation of all 347 original public rows/ten users. Physical webcam/RTSP hardware is unverified. Raw pictures stay local; camera footage never changes floor occupancy in this phase. Seven approved project additions preserve all earlier package versions; setuptools was declined. Stop for founder review; detection/sync remain Phases 5/6.

## Phase 5: detector and state engine

**Real-model follow-up — 2026-11-08:** After separate checkpoint/toolchain approvals, RF-DETR Nano is acquired, verified, exported offline and connected through the replaceable detector and protected local lab. The existing runtime is preserved; conversion tools are isolated. [PHASE_05.md](phase_explanations/PHASE_05.md) records hashes, 445-test results, six actual-model browser groups plus seven prior groups, Windows commands and measured CPU limitations. Only geometric/generated footage was used. Positive person recall, real seating assignment and restaurant occupancy accuracy remain pending; no cloud state writes or Phase 6. The earlier partial snapshot below is historical.

**Partial implementation — 2026-11-08:** The founder subsequently approved the proposal and three exact CPU runtime additions, but held downloading weights until licensing is clarified and limited footage to synthetic. [PHASE_05.md](phase_explanations/PHASE_05.md) records separate seating revisions, association/state logic, supervised internal frame handling, secured local shadow controls and 413 passing tests (all 333 original cases unchanged). Actual MP4/browser and process tests use simulated authority/detector outputs where stated. No pretrained inference, restaurant accuracy, actual YOLOX benchmark, database migration or cloud state write is claimed; Phase 5 exit criteria are not met. The planning paragraph below preserves the prior planning task.

Add a replaceable, license-reviewed detector; person-to-zone association; confidence thresholds; temporal filtering; deterministic transitions; manual precedence; local debug overlays only.

**Exit:** State-machine tests cover arrival, departure, occlusion, staff crossing, low confidence, outage, manual override, and resume. No invented accuracy claim.

**Planning only — 2026-11-08:** [The detailed Phase 5 proposal](PHASE_05_IMPLEMENTATION_PLAN.md) researches pretrained models and exact-license gates, a CPU/ONNX local shadow workflow, seating association profiles, uncertainty/manual precedence, authorized datasets, development metrics and milestones. The current proposal requires no PostgreSQL migration or canonical dashboard state writes; secure device/cloud integration remains Phase 6. No package/model installation, training, footage processing or application change was performed for this proposal. The last 333-test checkpoint result remains historical, not a new planning test run.

## Phase 6: edge synchronization

**Implemented 2026-11-08; reverified 2026-11-11:** [PHASE_06.md](phase_explanations/PHASE_06.md)
records 529 passing tests, six browser groups, actual HTTPS/outage/restart recovery,
duplicate-safe synthetic tasks, separately approved additive migrations and data
preservation. AI stays shadow-only; Phase 7 and deployment gates remain closed.
The dated proposal paragraph below is historical.

Implement SQLite outbox, authenticated batches, device pairing, retries/backoff, restart replay, heartbeat, idempotency, revocation, and device-offline UI.

**Exit:** Outages and restarts preserve events, duplicate sends have one effect, and revoked devices are rejected.

**Planning only — 2026-11-08:** [The complete Phase 6 proposal](PHASE_06_IMPLEMENTATION_PLAN.md) covers one-location fingerprint pairing, separate device credentials, signed HTTPS batches, a durable SQLite outbox, ordering/retries/recovery, finite offline processing permission, health and scoped SSE/dashboard integration. AI output remains shadow by default; a restricted synthetic fixture tests actual task uniqueness without live AI activation. The proposal records installed SQLite WAL precautions and unresolved Phase 5 pacing/accuracy gates. No application change, dependency installation, migration, commit or push is authorized by planning.

## Phase 7: workflow and analytics

**Approved implementation — 2026-11-12:** Human-reviewed suggestions, scoped
staff/manager decisions, correction-preserving task attempts, v2 evidence and
daily/hourly analytics/CSV exist. [The implementation record](phase_explanations/PHASE_07.md)
contains actual checks and limitations; [business migration](PHASE_07_MIGRATION_REVIEW.md)
was separately approved and is applied as exact `0009` with restricted grants and matching local services. Existing locations remain OFF. All 580 original records and protected files/credentials are preserved. Earlier planning text below is historical. No public
activation, Phase 8, commit or push is included.

**Planning only - 2026-11-11:** [The complete Phase 7 proposal](PHASE_07_IMPLEMENTATION_PLAN.md) traces the exact master requirements, existing task/edge contracts, assisted human review, compatible evidence summaries, corrections, source-aware analytics/CSV, migration safety and 18 acceptance checks. Unverified AI cannot independently mark a table ready or run unattended operational updates. No Phase 7 functionality, migration, installation or new test result is claimed.

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
- The project `.venv` includes approved Argon2 dependencies. The Phase 3 suite passes 262 tests, including all 152 earlier cases and the four original starter tests. The API image now constrains its original runtime versions; host/edge versions are not fully locked; the Starlette test stack emits an HTTPX deprecation warning. Host Python 3.14/Node 26 differ from Docker/CI Python 3.12/Node 22.
- npm audit still reports 8 affected packages (1 high, 7 moderate); no npm upgrades or overrides were applied. Explicit frontend tracing configuration removes the duplicate-lockfile warning. Deprecated `next lint` remains for later reviewed migration.
- Git checkpoints `6808a81`, `62ad229`, `3342c42`, `899f743` and `1438313` are preserved in history. Phase 5 checkpoint `ae19ec81f342d17730ddd48845a5862a2d56a99a` and Phase 6 checkpoint `fd983c7a656ab36f031db2900ef15a3da1362cbe` were committed/pushed after separate approvals, with matching remote hashes verified. Phase manifests preserve preparation history. This Phase 7 planning task does not commit/push anything, and hosted CI results were not checked.
- Compose now applies restricted runtime credentials and database-backed readiness; the API enforces `APP_ENV`, cookie/origin requirements, and `DEMO_MODE`. Administrative secrets stay outside API runtime. Private values/backups remain ignored, and `.dockerignore` protects build contexts. Production secret storage, non-root images, TLS, admin MFA/recovery, and external review remain open.
- The preserved legacy database administrator password is weak. The approved plan forbids rotating it in this phase; obtain approval for a reviewed rotation before public/pilot use. Runtime/demo credentials are separately generated and private.
- Identity/session, grants/RLS, safe tests and the Phase 3 synthetic event/task/SSE workflow are implemented. Synthetic video/calibration are verified in Phase 4. Phase 5 has real approved RF-DETR inference through the local shadow pipeline; representative person/restaurant evaluation remains pending. Physical hardware/codecs, customer footage consent, deployment metrics and external services remain unverified. Phase 6 local/synthetic transport is verified; Phase 7 human-reviewed workflow and analytics are implemented and locally verified with existing locations OFF; Phases 8-10 are not implemented.

See [PHASE_05.md](phase_explanations/PHASE_05.md) for inference commands/results, [PHASE_04.md](phase_explanations/PHASE_04.md) for calibration/hardware limits and [PHASE_06.md](phase_explanations/PHASE_06.md) for transport verification. Earlier results remain dated history. [Phase 7](PHASE_07_IMPLEMENTATION_PLAN.md) is proposed only; stop for founder review before implementation.
