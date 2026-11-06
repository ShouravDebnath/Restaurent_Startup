# Restaurant AI Monitoring Architecture

**Status:** Target architecture defined in Phase 0; Phase 1 foundation only is implemented.
**Source:** `docs/MASTER_SPEC.md`

The responsibilities and pipeline below describe the intended MVP. Current source contains a static web shell, two synthetic/health API routes, an edge health helper, and database/container scaffolding. It does not yet implement authentication, database-backed resources, camera processing, synchronization, or SSE. The web page does not call the API. See [CODEX_HANDOFF.md](CODEX_HANDOFF.md) for current evidence and blockers; Phase 2 has not started.

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

- Identity provider and session implementation.
- First supported camera/NVR compatibility list.
- Detector and weight licenses for commercial use.
- Exact deployment hardware and supported operating system.
- Database row-level security versus application authorization plus security tests.
- Diagnostic video retention and legal/customer notice language.
