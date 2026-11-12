# Restaurant AI Monitoring Architecture

**Phase 7 checkpoint verification — 2026-11-12:** Fresh complete regression passes **650 tests**, zero skips, plus **eleven browser groups** and frontend/Python checks. The founder verified A02 totals and opened its CSV in Excel. All 615 current baseline records, credentials/calibrations and the database volume are preserved. [The exact 55-file checkpoint review](PHASE_07_CHECKPOINT.md) records security findings and separate commit/push approval gates. Earlier 636/210-test results below remain historical.

**DEMO Analytics correction — 2026-11-12:** Reporting now reads corroborated DEMO transition/task history in addition to canonical reviewed sessions. This is a read-only projection, confined to synthetic DEMO reports and deduplicated against canonical sessions. It preserves all source records and original visit starts; no schema change or fake device evidence. [Verification](phase_explanations/PHASE_07.md#a02-demo-analytics-correction--2026-11-12).

**Phase 7 resumed implementation — 2026-11-12:** The founder approved the reviewed-workflow plan. [PHASE_07.md](phase_explanations/PHASE_07.md) records implemented suggestions, physical staff confirmation, protected task/correction history, compatible v2 evidence and analytics/CSV. Final verification passes **636 tests** and **ten browser groups**, including interrupted-export protection in the prepared Linux web image. After separate founder approval, exact additive `0009` and restricted grants are applied and matching local API/web/TLS code is active. All 580 original records and protected credentials/calibrations remain preserved; existing locations remain OFF. Existing data/credentials/calibrations are preserved; no new dependencies, commit, push, public deployment or Phase 8. Earlier proposal-only statements retain their dated historical meaning.

**Current Phase 6 boundary:** [The Phase 6 record](phase_explanations/PHASE_06.md) documents implemented manager-approved device pairing, signed TLS metadata batches, replay protection, restricted database ingestion, durable SQLite buffering/recovery, processing leases and scoped dashboard health. Migrations 0007/0008 are included in published checkpoint `fd983c7a656ab36f031db2900ef15a3da1362cbe`. Device observations remain shadow estimates and cannot write normal operational states or mark tables ready. Raw frames and camera/private-device credentials remain local. The [approved Phase 7 plan](PHASE_07_IMPLEMENTATION_PLAN.md) is implemented and verified locally; separately approved `0009` and matching services are active, with existing locations OFF. The phase-specific boundaries below describe what each earlier phase added.

**Phase 5 boundary (historical addition):** [The work record](phase_explanations/PHASE_05.md) adds bounded original-BGR handoff, sibling inference supervision, private seating revisions and a deterministic local shadow state engine. The separately approved RF-DETR Nano checkpoint is exported locally to static FP32 ONNX and runs through the existing CPU runtime; graph optimization is disabled after measured numerical comparison. The large export toolchain is isolated from the working `.venv`. Local routes retain human/camera authority, exact origin/CSRF, role/location scope and synthetic-only input; managers approve model changes. Passive metadata/preview does not extend idle sessions. Actual generated-video/model/browser integration is verified; representative person/restaurant accuracy remains pending. No PostgreSQL schema/canonical state write, DEMO event posting, device identity or outbox was added. The broader edge/cloud architecture below remains the product target.

**Phase 4 boundary:** [The phase explanation](phase_explanations/PHASE_04.md) records a Windows-native loopback companion, a supervised video-only decoder and a single latest-frame mailbox. A per-human API session revalidates role/location/explicit camera consent and idle/absolute deadlines. Only IDs, permissions, geometry and audits cross the API boundary; frames and CCTV credentials stay local. A narrow literal-private-IP RTSP/TCP gateway injects Windows-store credentials and rejects other destinations. Additive 0005/0006 provide immutable complete calibration revisions, audited preview grants and a passive session deadline helper. The existing dashboard/SSE never receives camera occupancy in this phase. Physical webcam/RTSP interoperability, independent codec audit and native exploit sandboxing are unverified.

**Status:** Phases 0–6 are implemented within documented local/synthetic scope and published. Representative AI accuracy and physical hardware remain unverified; reviewed operational AI integration, analytics and CSV exports are implemented and verified Phase 7 work, activated locally after separate migration approval; existing locations remain OFF.
**Source:** `docs/MASTER_SPEC.md`

Current source includes local Argon2id authentication, revocable server sessions, strict scoped configuration APIs, explicit memberships/location grants, backend authorization plus RLS, atomic audits, and a DEMO dashboard with saved states/tasks/history and SSE. Phase 4 adds local video readers and camera credential storage; Phase 5 adds isolated local shadow inference; Phase 6 adds secure device enrollment, durable metadata synchronization and separate shadow/health updates. Phase 7 adds opt-in human-reviewed operational integration and analytics in source; production occupancy validation and billing remain planned. See [PHASE_06.md](phase_explanations/PHASE_06.md) for transport evidence, [PHASE_05.md](phase_explanations/PHASE_05.md) for inference limits and [PHASE_03.md](phase_explanations/PHASE_03.md) for dashboard behavior. Phase 7 preserves these boundaries through a separately approved and tested opt-in human workflow; no existing location is automatically enrolled.

## Implemented Phase 3 workflow

Phase 7 extends this path with OFF-by-default reviewed bindings, atomic
receipt-to-suggestion derivation and a human-only operational decision function.
Canonical sessions and numbered task attempts retain correction history. A
manager can reconcile a changed source without inventing a new visit or timer.
Version-2 evidence is negotiated over the existing durable signed transport;
old v1 messages remain unchanged. Per-table freshness is independent of device
heartbeats and human camera preview. The new analytics service uses UTC interval
math and IANA buckets, separate workflow/evidence/DEMO/legacy bases, bounded
manager APIs and reauthorized CSV. See [the full workflow/data flow and
limits](phase_explanations/PHASE_07.md). Local activation is complete after separate founder approval; existing locations remain OFF.

The browser loads a consistent PostgreSQL snapshot through the fixed Next.js proxy, then subscribes to an authenticated location stream. A controlled database action function checks current location/role, expected revision and duplicate key, then commits state/task/event/audit/receipt together. Staff cannot generally update table state/configuration columns. Location publication locks preserve committed event order. All new operational tables have RLS and composite scoped references.

GET/SSE reads use passive session validation and cannot refresh idle expiry. Streams use short transactions between bounded replay batches and two-second heartbeats, with disconnect cleanup and per-process admission limits. Active CSRF-protected mutations refresh idle activity but never absolute expiry. The proxy streams incrementally with separate connection/read deadlines; reconnect refreshes the snapshot. Browser selection changes cancel previous reads/streams and clear previous location data.

Synthetic inputs require enabled DEMO_MODE, a marked synthetic location and an assigned manager/admin. They are explicit inputs, not an automatic background simulation or real video frames. Source failure makes unconfirmed observations UNKNOWN while preserving manually confirmed ready/cleaning/blocked states and timestamps, as the founder approved. Offline-source readiness is not counted as currently verified; browser outages show STALE and pause actions. Reopening requires a new ready confirmation. No actual camera-health or measured-confidence claim is made.

## Implemented Phase 2 request boundary

```mermaid
flowchart LR
    B[Browser configuration screens] --> N[Same-origin Next.js API proxy]
    N --> A[FastAPI: verify session and CSRF]
    A --> P[Check membership, role and location grant]
    P --> D[Restricted PostgreSQL connection]
    D --> R[Row-level security and ownership constraints]
    R --> T[Permitted records and atomic audit writes]
```

The proxy uses a fixed server-side upstream and forwards cookies/CSRF without trusting client identity headers. Session tokens stay in HttpOnly cookies, with only token digests in the private database schema. Transaction-local `app.user_id` comes from the verified session; row policies derive permissions from enabled database memberships/grants. Request IDs never establish permission. Strict API filters and composite foreign keys prevent cross-location associations, and ownership triggers prevent reparenting.

Runtime uses a non-owner, non-superuser login without `BYPASSRLS` or migration powers. Administrative migration credentials stay outside the running API. Privileged helper functions have fixed search paths and restricted execution grants. Local HTTP cookies are development-only; non-development settings require Secure cookies and HTTPS allowed origins. Managed MFA/recovery and production hardening remain open.

Revisions 0001/0002 create organizations, locations, users, sessions/throttle records, memberships/grants, camera/table/zone metadata, and audits. The founder approved deferring devices/events/tasks and the camera-device foreign key to later migrations. No raw video is read or uploaded by Phase 2.

## Scope

The MVP is a modular monolith with three deployable parts:

1. `apps/web`: Next.js and TypeScript dashboard.
2. `services/api`: FastAPI application with PostgreSQL and Alembic.
3. `services/edge-agent`: Python process that reads an authorized MP4, webcam, or RTSP source, performs local detection, maintains table state, and queues minimal events in SQLite.

Docker Compose is the initial local and pilot packaging mechanism. Microservices, Kubernetes, continuous cloud video, and distributed training are out of scope.

## Data flow

```text
Authorized camera or MP4
  -> edge VideoSource
  -> sampled frames
  -> replaceable PersonDetector
  -> normalized table-zone association
  -> deterministic TableStateEngine
  -> SQLite outbox
  -> authenticated HTTPS event batches
  -> FastAPI validation and idempotent persistence
  -> PostgreSQL current state and history
  -> SSE dashboard updates
```

The edge sends table state transitions, health, confidence, timestamps, and quality metadata. Raw video stays local by default. Any diagnostic clip path requires explicit authorization, encryption, narrow access, and retention limits.

## Ownership boundaries

### Edge agent

- Keeps camera credentials out of the browser and cloud logs.
- Decodes frames and drops stale backlog frames.
- Uses normalized polygons and documented anchor-point association.
- Applies temporal filtering, hysteresis, manual override precedence, and stale-camera UNKNOWN behavior.
- Writes each outgoing event to SQLite before attempting delivery.
- Uses device credentials scoped to exactly one location.

### API

- Authenticates users and devices.
- Resolves organization and location permissions on every request.
- Validates event schema, device/location pairing, timestamps, and idempotency.
- Persists state transitions, tasks, audit records, and health.
- Publishes authorized location updates over SSE.
- Never trusts organization identifiers supplied by an edge event over server-side device mapping.

### Web

- Displays only API-authorized data.
- Shows DEMO data explicitly when in demo mode.
- Provides floor view, task actions, setup/calibration, analytics, administration, and offline/stale indicators.
- Does not connect directly to RTSP sources or receive camera passwords.

## Canonical state rules

- `UNKNOWN`: stale, offline, occluded, or insufficient confidence.
- `AVAILABLE`: visually unoccupied and confirmed ready.
- `OCCUPIED`: stable person evidence.
- `RESET_PENDING`: an occupied session became reliably vacant.
- `CLEANING`: staff is actively resetting the table.
- `OUT_OF_SERVICE`: manager-blocked table.

Vision alone never changes `RESET_PENDING` to `AVAILABLE`. Camera failure never changes a table to `AVAILABLE`. Manual actions and their precedence rules are audited.

## Persistence

PostgreSQL stores organizations, locations, users, memberships, devices, cameras, tables, zones, events, tasks, and audit logs. Important tenant-scoped records carry `organization_id` where practical. All event timestamps are UTC; analytics convert boundaries using the location IANA time zone.

SQLite is an edge-only durable outbox. Event IDs are unique in the cloud. Retries are safe and may replay a request without duplicating effects.

## Real-time behavior

SSE is the initial one-way transport from API to authorized dashboards. The initial page load comes from a normal API query, then the client applies location-scoped state/task events. Reconnect uses `Last-Event-ID` or a fresh snapshot; stale data is visibly marked.

## Explicit non-goals

No facial recognition, audio, emotion detection, covert staff surveillance, service-time claims without trusted inputs, automatic cleanliness claims, public CCTV exposure, or unapproved footage.

## Open decisions for human approval

- Production identity lifecycle, administrator MFA/account recovery, and any later managed-provider migration. Local Argon2id/server sessions were approved and implemented in Phase 2.
- First supported camera/NVR compatibility list.
- Detector and weight licenses for commercial use.
- Exact deployment hardware and supported operating system.
- Continued review/hardening of the chosen backend authorization plus PostgreSQL RLS approach; that architecture decision is resolved for Phase 2.
- Diagnostic video retention and legal/customer notice language.
