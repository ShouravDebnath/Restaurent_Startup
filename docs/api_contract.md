# Initial API Contract

**Status:** Target v1 contract defined in Phase 0; the resource routes below are planned.
**Version:** v1

Current product routes are only `GET /health` and `GET /v1/demo/tenant`, plus FastAPI's generated documentation/OpenAPI routes. Both product routes are public; the demo data is hard-coded and synthetic. No authentication, tenant enforcement, database-backed resource routes, standard error envelope, or edge-event ingestion exists yet. Statements below are requirements for later implementation. See [CODEX_HANDOFF.md](CODEX_HANDOFF.md#9-phase-2-requirements-and-acceptance-criteria) for the Phase 2 boundary; Phase 2 has not started.

All routes return typed JSON schemas. All times are ISO 8601 UTC unless a response explicitly says it is display-local. Every location route performs backend authorization; hidden frontend controls are not an authorization boundary.

## Authentication and identity

- `POST /v1/auth/session`: establish a session through the selected identity provider.
- `GET /v1/me`: return the user, enabled memberships, permitted organizations, and permitted locations.

Human sessions and edge device credentials are separate. Device credentials are scoped to one paired location and can be revoked.

## Location and table operations

- `GET /v1/locations/{location_id}/tables`: list current table state, state timestamp, confidence, camera health, and zone metadata where authorized.
- `POST /v1/locations/{location_id}/tables`: manager creates a table.
- `PUT /v1/locations/{location_id}/table-zones/{zone_id}`: installer or manager saves a normalized polygon and calibration revision.
- `POST /v1/tables/{table_id}/actions`: staff submits `acknowledge`, `start_cleaning`, `mark_ready`, or `out_of_service`.
- `GET /v1/locations/{location_id}/tasks`: paginated staff tasks, sorted by age and filtered by status.
- `GET /v1/locations/{location_id}/stream`: authorized SSE stream for state, task, and health changes.

Action requests must include an expected current revision or state where needed, so conflicting manual operations produce a useful response rather than silently overwriting one another.

## Analytics

- `GET /v1/locations/{location_id}/analytics?from=...&to=...`: occupancy duration, state durations, reset delay, completed resets, and data-quality gaps.
- `GET /v1/locations/{location_id}/analytics.csv?from=...&to=...`: same authorized aggregate data as CSV.

Date filters are interpreted in the location IANA time zone, then converted to UTC for querying. Missing-camera periods and estimated values are labeled.

## Edge ingestion

- `POST /v1/edge/events`: authenticated device submits a bounded batch of versioned events.
- `POST /v1/edge/heartbeat`: authenticated device submits health, last-frame time, source status, and agent version.

The server derives organization and location from the authenticated device pairing. It rejects a claimed table, camera, or location that is not mapped to that device. Event IDs are unique; duplicate delivery returns an idempotent success result and does not create another task or state effect. Unknown event types and unsupported schema versions return actionable validation errors.

## Event envelope

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

Do not disclose whether an inaccessible guessed ID exists. Use `401` for missing/invalid authentication, `403` for authenticated but unauthorized access, `404` where resource existence must not be disclosed, `409` for state conflicts, and `422` for schema validation.

## API acceptance checks

- A Restaurant A token cannot read or mutate Restaurant B records.
- Altering organization or location fields in a request does not bypass authorization.
- A device paired to Location A cannot ingest events for Location B.
- Duplicate event posts have one durable effect.
- Pagination, date boundaries, and location time zones are tested.
- OpenAPI examples are generated from typed request and response models.
