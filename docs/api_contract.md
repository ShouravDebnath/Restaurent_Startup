# Initial API Contract

**Phase 5 local additions:** optional `--ai-debug` enables scoped local analysis configuration GET/PUT, explicit start/stop, status and bounded event reads under `/local/v1/analysis/`. These reuse the local cookie, exact Host/Origin, CSRF/body limits, eligible role/location, explicit camera permission and reader ownership. Only synthetic sources are authorized. Managers approve initial profiles, detector changes and threshold changes; stale configuration or zone revisions return 409. Missing/unapproved models return 503 without downloading. A privately provisioned RF-DETR Nano entry now supports actual CPU inference; the held YOLOX artifact remains absent. These APIs never write cloud occupancy or send frames to the cloud. [Route details and limits](phase_explanations/PHASE_05.md#local-apis-and-security-boundaries). Actual synthetic model integration is verified; real-person evaluation remains pending.

**Phase 4 additions:** `POST/GET /v1/locations/{location}/cameras/{camera}/preview-grants`, `POST .../preview-grants/{grant}/revoke`, `GET .../preview-authorization` and `GET /v1/locations/{location}/table-zones/{zone}/revisions`. Consent mutations require enabled manager/admin role, explicit location access, Origin and CSRF; viewers additionally require an eligible setup role and their own current grant. Passive authorization returns only scoped IDs, opaque source reference, server time, expiry and effective session deadline. List endpoints are paginated (limit 1–100). Zone POST/PUT accept optional `request_key` and `view_metadata`; existing expected-revision/409 behavior remains, and key reuse with another payload returns 409. The loopback companion has its own authenticated `/local/v1/` routes and local JPEG responses; the cloud API has no video-upload/relay endpoint. See [complete API/flow details](phase_explanations/PHASE_04.md#database-safety-records-and-apis).

**Status:** Phase 2 configuration/auth, Phase 3 synthetic workflow/SSE, Phase 4 calibration/preview-permission metadata and Phase 5 protected local shadow APIs implemented. Device event ingestion/analytics remain planned; no cloud AI state ingestion is included.
**Version:** v1

Phase 2 adds persistent configuration APIs with typed schemas, cookie sessions, role/location authorization, PostgreSQL RLS, audits, and safe protected-route errors. `GET /health`, database-backed `GET /ready`, and the hard-coded public synthetic `GET /v1/demo/tenant` remain distinct. The demo route never selects tenant rows and can be disabled with `DEMO_MODE=false`. Generated documentation/OpenAPI remain available. See [PHASE_02.md](phase_explanations/PHASE_02.md) for actual evidence and limitations.

JSON routes return typed schemas; SSE frames carry versioned typed operational events. All times are ISO 8601 UTC unless a response explicitly says it is display-local. Every location route performs backend authorization; hidden frontend controls are not an authorization boundary.

## Authentication and identity

- `POST /v1/auth/session`: local email/password login; exact allowed Origin required; returns CSRF token in JSON and a host-only HttpOnly session cookie. Does not return the session token in JSON.
- `GET /v1/auth/csrf`: authenticated retrieval of the session-bound CSRF token.
- `DELETE /v1/auth/session`: authenticated logout; revoke the server-side session and clear the cookie. Requires Origin and X-CSRF-Token.
- `GET /v1/me`: return the user, enabled memberships, permitted organizations, and permitted locations.

Human sessions are implemented; edge-device credentials/pairing/revocation remain later work and will be separate. Protected mutations require exact allowed Origin and X-CSRF-Token, in addition to the session cookie. Sessions expire after 30 minutes idle or 8 hours total by default. Resource responses never include password hashes or session tokens. Account provisioning is an explicit administrator command, not public signup; managed MFA, recovery, and email verification are unavailable.

Phase 3 GET/HEAD reads and SSE checks use passive validation and never refresh idle time. Successful protected mutations count as activity; absolute expiry is unchanged. Streams recheck expiry/user/membership/location access in short transactions and close on loss of access. See [PHASE_03.md](phase_explanations/PHASE_03.md).

## Implemented organization and configuration routes

| Methods | Route | Scope |
| --- | --- | --- |
| GET, POST | `/v1/organizations` | List enabled memberships' organizations; authenticated user creates a new organization as owner |
| GET, PATCH | `/v1/organizations/{org_id}` | Enabled member reads; owner/admin changes name |
| GET, POST | `/v1/organizations/{org_id}/locations` | List explicitly permitted locations; owner/admin creates and receives an explicit grant |
| GET, PATCH | `/v1/locations/{location_id}` | Explicit location access; owner/admin updates metadata |
| GET, POST | `/v1/organizations/{org_id}/memberships` | Owner/admin lists or adds an existing provisioned user with role and explicit location IDs |
| PATCH | `/v1/organizations/{org_id}/memberships/{member_id}` | Owner/admin changes role/enabled/grants; only owner changes owner permissions; last-owner/self-disable protections apply |
| GET, POST | `/v1/locations/{location_id}/tables` | Permitted users list; owner/admin/manager creates |
| GET, PATCH | `/v1/locations/{location_id}/tables/{table_id}` | Scoped read; owner/admin/manager changes label/seats |
| GET, POST | `/v1/locations/{location_id}/cameras` | Scoped read; owner/admin/manager/installer creates safe metadata |
| GET, PATCH | `/v1/locations/{location_id}/cameras/{camera_id}` | Scoped read; authorized configurator changes safe metadata |
| GET, POST | `/v1/locations/{location_id}/table-zones` | Scoped read; owner/admin/manager/installer creates normalized zone data |
| GET, PUT | `/v1/locations/{location_id}/table-zones/{zone_id}` | Scoped read/update; update requires expected_revision and rejects stale saves with 409 |
| GET | `/v1/organizations/{org_id}/audit-logs` | Owner/admin reads permitted organization/location audit rows |
| GET | `/v1/locations/{location_id}/audit-logs` | Explicit location and owner/admin/manager role required |

Audit lists accept `limit` (1–100, default 50) and nonnegative `offset`. Ownership is server-assigned from the authorized path; request bodies reject extra organization/location/state fields and resource reparenting. Foreign camera/table references are rejected even when the user can access both locations. No resource-delete routes exist. OpenAPI at `/openapi.json` is the executable field/type reference; session-cookie security is documented there. Configuration/audit changes are committed atomically before successful responses.

## Location/table operations and later workflow boundary

- `GET /v1/locations/{location_id}/tables`: Phase 2 returns label/seats, current state, UTC state-entry/creation times, and ownership IDs. Confidence/observed camera health are not implemented. Camera/zone metadata use the separate routes above.
- `POST /v1/locations/{location_id}/tables`: manager creates a table.
- `PUT /v1/locations/{location_id}/table-zones/{zone_id}`: installer or manager saves a normalized polygon and calibration revision.
- **Implemented:** `POST /v1/tables/{table_id}/actions`: staff acknowledges, starts cleaning or explicitly confirms ready; manager/admin only blocks/reopens.
- **Implemented:** `GET /v1/locations/{location_id}/tasks`: age-sorted RESET tasks, optional status filter, `limit` 1–100, `offset` 0–100000.
- **Implemented:** `GET /v1/locations/{location_id}/stream`: authorized SSE; `Last-Event-ID` overrides an initial `after` cursor. Cursor is `location UUID:revision`, never a credential. Invalid/foreign/ahead cursors require reloading (409).
- **Implemented:** `GET /v1/locations/{location_id}/dashboard`: consistent tables/active tasks/publication cursor, server UTC time, authorized location/role, DEMO/control flags, truncation flags (500 tables/100 tasks).
- **Implemented:** `GET /v1/locations/{location_id}/activity`: safe operational history, scoped optional table filter and bounded pagination. Does not expose private membership/security audits to staff.
- **Implemented:** `POST /v1/locations/{location_id}/demo/events`: arrive/depart/vacant/source_offline/source_resume, requiring DEMO_MODE plus a synthetic assigned location and manager/admin role.

Action requests must include an expected current revision or state where needed, so conflicting manual operations produce a useful response rather than silently overwriting one another.

Implemented bodies require `action`, nonnegative `expected_revision` and UUID `request_key`; staff actions may include `task_id`, strict boolean `confirmed`, and predefined `reason` code. Demo bodies additionally require a same-location `table_id`. Extra ownership/state fields are rejected. Same-key/same-payload retry returns the original committed result; changed payload/stale revision returns 409. Out-of-service reason codes are maintenance/reserved/safety/other. Ready confirmation requires CLEANING or initial UNKNOWN with current ONLINE/VACANT demo information. Reopen returns UNKNOWN. Source failure preserves manual states/timestamps but marks source information unavailable; only unconfirmed observations become UNKNOWN.

New event/task/receipt tables are scoped by backend checks and RLS. Controlled actions commit state/task/event/audit/receipt atomically, with ordered location revisions. SSE sends `change`, `heartbeat`, `session_expired`, `access_lost` or `unavailable`; it reads at most 100 events per batch, with two-second heartbeat and per-process limits of four streams/user and 32 total. It does not hold a database transaction between frames. Browser reconnect obtains a fresh snapshot; Last-Event-ID replay is independently supported and tested. The fixed Next.js proxy forwards streams incrementally without the ordinary ten-second lifetime.

## Analytics — planned, not implemented

- `GET /v1/locations/{location_id}/analytics?from=...&to=...`: occupancy duration, state durations, reset delay, completed resets, and data-quality gaps.
- `GET /v1/locations/{location_id}/analytics.csv?from=...&to=...`: same authorized aggregate data as CSV.

Date filters are interpreted in the location IANA time zone, then converted to UTC for querying. Missing-camera periods and estimated values are labeled.

## Edge ingestion — planned, not implemented

- `POST /v1/edge/events`: authenticated device submits a bounded batch of versioned events.
- `POST /v1/edge/heartbeat`: authenticated device submits health, last-frame time, source status, and agent version.

The server derives organization and location from the authenticated device pairing. It rejects a claimed table, camera, or location that is not mapped to that device. Event IDs are unique; duplicate delivery returns an idempotent success result and does not create another task or state effect. Unknown event types and unsupported schema versions return actionable validation errors.

## Event envelope — future contract example

```json
{
  "event_id": "evt_demo_001",
  "schema_version": 1,
  "edge_device_id": "edge_demo_1",
  "camera_id": "cam_demo_1",
  "table_id": "table_demo_4",
  "event_type": "table.state_changed",
  "previous_state": "OCCUPIED",
  "new_state": "RESET_PENDING",
  "occurred_at": "2026-11-05T14:10:30Z",
  "confidence": 0.92,
  "evidence": "stable_vacancy_after_occupied"
}
```

`organization_id` and `location_id` may be accepted for diagnostics, but server-side device mapping is authoritative and mismatches are rejected or ignored according to the final security decision. Raw detections and identities are not part of the cloud event contract.

## Error contract

Use a stable shape:

```json
{
  "error": {
    "code": "forbidden",
    "message": "You do not have access to this location.",
    "request_id": "req_demo_001"
  }
}
```

Do not disclose whether an inaccessible guessed ID exists. Protected routes use `401` for missing/invalid authentication, `403` for unauthorized actions/CSRF, `404` for hidden or missing resources, `409` for conflicts/constraints, `422` for validation, `429` for login throttling, and `503` for database unavailability/unsafe runtime configuration. Validation errors do not echo submitted passwords, URLs, or raw input. The error envelope above describes the implemented protected routes; unknown/framework routes are not resource APIs.

## API acceptance checks

Phase 2 and synthetic Phase 3 route/session/isolation/audit/retry/stream checks pass in real PostgreSQL tests. Real device ingestion and analytics checks below remain future criteria. See the Phase 3 explanation for actual commands/counts and limitations.

- A Restaurant A token cannot read or mutate Restaurant B records.
- Altering organization or location fields in a request does not bypass authorization.
- A device paired to Location A cannot ingest events for Location B.
- Duplicate event posts have one durable effect.
- Pagination, date boundaries, and location time zones are tested.
- OpenAPI examples are generated from typed request and response models.
