# Initial API Contract

**Status:** Phase 2 authentication/configuration APIs implemented; later workflow/analytics/edge routes below remain planned.
**Version:** v1

Phase 2 adds persistent configuration APIs with typed schemas, cookie sessions, role/location authorization, PostgreSQL RLS, audits, and safe protected-route errors. `GET /health`, database-backed `GET /ready`, and the hard-coded public synthetic `GET /v1/demo/tenant` remain distinct. The demo route never selects tenant rows and can be disabled with `DEMO_MODE=false`. Generated documentation/OpenAPI remain available. See [PHASE_02.md](phase_explanations/PHASE_02.md) for actual evidence and limitations.

All routes return typed JSON schemas. All times are ISO 8601 UTC unless a response explicitly says it is display-local. Every location route performs backend authorization; hidden frontend controls are not an authorization boundary.

## Authentication and identity

- `POST /v1/auth/session`: local email/password login; exact allowed Origin required; returns CSRF token in JSON and a host-only HttpOnly session cookie. Does not return the session token in JSON.
- `GET /v1/auth/csrf`: authenticated retrieval of the session-bound CSRF token.
- `DELETE /v1/auth/session`: authenticated logout; revoke the server-side session and clear the cookie. Requires Origin and X-CSRF-Token.
- `GET /v1/me`: return the user, enabled memberships, permitted organizations, and permitted locations.

Human sessions are implemented; edge-device credentials/pairing/revocation remain later work and will be separate. Protected mutations require exact allowed Origin and X-CSRF-Token, in addition to the session cookie. Sessions expire after 30 minutes idle or 8 hours total by default. Resource responses never include password hashes or session tokens. Account provisioning is an explicit administrator command, not public signup; managed MFA, recovery, and email verification are unavailable.

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
- **Planned:** `POST /v1/tables/{table_id}/actions`: staff submits `acknowledge`, `start_cleaning`, `mark_ready`, or `out_of_service`.
- **Planned:** `GET /v1/locations/{location_id}/tasks`: paginated staff tasks, sorted by age and filtered by status.
- **Planned:** `GET /v1/locations/{location_id}/stream`: authorized SSE stream for state, task, and health changes.

Action requests must include an expected current revision or state where needed, so conflicting manual operations produce a useful response rather than silently overwriting one another.

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

Phase 2 route/session/isolation/audit checks pass in real PostgreSQL tests. Device/event/analytics checks below remain future acceptance criteria and are not reported as passed.

- A Restaurant A token cannot read or mutate Restaurant B records.
- Altering organization or location fields in a request does not bypass authorization.
- A device paired to Location A cannot ingest events for Location B.
- Duplicate event posts have one durable effect.
- Pagination, date boundaries, and location time zones are tested.
- OpenAPI examples are generated from typed request and response models.
