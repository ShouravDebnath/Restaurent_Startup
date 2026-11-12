# Initial API Contract

**Phase 7 checkpoint verification — 2026-11-12:** Fresh complete regression passes **650 tests**, zero skips, plus **eleven browser groups** and frontend/Python checks. The founder verified A02 totals and opened its CSV in Excel. All 615 current baseline records, credentials/calibrations and the database volume are preserved. [The exact 55-file checkpoint review](PHASE_07_CHECKPOINT.md) records security findings and separate commit/push approval gates. Earlier 636/210-test results below remain historical.

**DEMO Analytics correction — 2026-11-12:** Calculation version 2 includes corroborated original DEMO scenario tasks in DEMO summaries. JSON/CSV fields and authorization remain compatible. Canonical reviewed sessions take precedence; other bases and production reports do not receive scenario totals. [Exact behavior and tests](phase_explanations/PHASE_07.md#a02-demo-analytics-correction--2026-11-12).

**Phase 7 resumed implementation — 2026-11-12:** The founder approved the reviewed-workflow plan. [PHASE_07.md](phase_explanations/PHASE_07.md) records implemented suggestions, physical staff confirmation, protected task/correction history, compatible v2 evidence and analytics/CSV. Final verification passes **636 tests** and **ten browser groups**, including interrupted-export protection in the prepared Linux web image. After separate founder approval, exact additive `0009` and restricted grants are applied and matching local API/web/TLS code is active. All 580 original records and protected credentials/calibrations remain preserved; existing locations remain OFF. Existing data/credentials/calibrations are preserved; no new dependencies, commit, push, public deployment or Phase 8. Earlier proposal-only statements retain their dated historical meaning.

**Current Phase 6 additions:** Secure device pairing, signed metadata ingestion, heartbeats and manager-controlled bindings/processing/revocation are implemented in published checkpoint `fd983c7a656ab36f031db2900ef15a3da1362cbe`. [PHASE_06.md](phase_explanations/PHASE_06.md) records exact routes, tests and limits. Normal AI messages update separate shadows/health, not operational states or tasks. [Phase 7](phase_explanations/PHASE_07.md) adds the implemented reviewed workflow and report contracts below; separately approved local migration/activation is complete with existing locations OFF. Older phase-specific additions below retain their original scope.

**Phase 5 local additions:** optional `--ai-debug` enables scoped local analysis configuration GET/PUT, explicit start/stop, status and bounded event reads under `/local/v1/analysis/`. These reuse the local cookie, exact Host/Origin, CSRF/body limits, eligible role/location, explicit camera permission and reader ownership. Only synthetic sources are authorized. Managers approve initial profiles, detector changes and threshold changes; stale configuration or zone revisions return 409. Missing/unapproved models return 503 without downloading. A privately provisioned RF-DETR Nano entry now supports actual CPU inference; the held YOLOX artifact remains absent. These APIs never write cloud occupancy or send frames to the cloud. [Route details and limits](phase_explanations/PHASE_05.md#local-apis-and-security-boundaries). Actual synthetic model integration is verified; real-person evaluation remains pending.

**Phase 4 additions:** `POST/GET /v1/locations/{location}/cameras/{camera}/preview-grants`, `POST .../preview-grants/{grant}/revoke`, `GET .../preview-authorization` and `GET /v1/locations/{location}/table-zones/{zone}/revisions`. Consent mutations require enabled manager/admin role, explicit location access, Origin and CSRF; viewers additionally require an eligible setup role and their own current grant. Passive authorization returns only scoped IDs, opaque source reference, server time, expiry and effective session deadline. List endpoints are paginated (limit 1–100). Zone POST/PUT accept optional `request_key` and `view_metadata`; existing expected-revision/409 behavior remains, and key reuse with another payload returns 409. The loopback companion has its own authenticated `/local/v1/` routes and local JPEG responses; the cloud API has no video-upload/relay endpoint. See [complete API/flow details](phase_explanations/PHASE_04.md#database-safety-records-and-apis).

**Status:** Phase 2 configuration/auth, Phase 3 synthetic workflow/SSE, Phase 4 calibration/preview-permission metadata, Phase 5 protected local shadow APIs and Phase 6 secure device metadata synchronization are implemented. Analytics/CSV and reviewed AI-to-operational workflow are implemented and locally verified Phase 7 contracts; separately approved `0009`/runtime grants and matching services are active, with existing locations OFF. No raw-video upload or normal AI-to-operational state mutation is included.
**Version:** v1

Phase 2 adds persistent configuration APIs with typed schemas, cookie sessions, role/location authorization, PostgreSQL RLS, audits, and safe protected-route errors. `GET /health`, database-backed `GET /ready`, and the hard-coded public synthetic `GET /v1/demo/tenant` remain distinct. The demo route never selects tenant rows and can be disabled with `DEMO_MODE=false`. Generated documentation/OpenAPI remain available. See [PHASE_02.md](phase_explanations/PHASE_02.md) for actual evidence and limitations.

JSON routes return typed schemas; SSE frames carry versioned typed operational events. All times are ISO 8601 UTC unless a response explicitly says it is display-local. Every location route performs backend authorization; hidden frontend controls are not an authorization boundary.

## Authentication and identity

- `POST /v1/auth/session`: local email/password login; exact allowed Origin required; returns CSRF token in JSON and a host-only HttpOnly session cookie. Does not return the session token in JSON.
- `GET /v1/auth/csrf`: authenticated retrieval of the session-bound CSRF token.
- `DELETE /v1/auth/session`: authenticated logout; revoke the server-side session and clear the cookie. Requires Origin and X-CSRF-Token.
- `GET /v1/me`: return the user, enabled memberships, permitted organizations, and permitted locations.

Human sessions and separate Phase 6 device identities are implemented. Protected human mutations require exact allowed Origin and X-CSRF-Token, in addition to the session cookie; signed device requests use their own authentication and never impersonate a human. Sessions expire after 30 minutes idle or 8 hours total by default. Resource responses never include password hashes or session tokens. Account provisioning is an explicit administrator command, not public signup; managed MFA, recovery, and email verification are unavailable.

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

## Analytics — Phase 7 implemented and activated locally

- `GET /v1/locations/{location_id}/analytics?from=...&to=...`: occupancy duration, state durations, reset delay, completed resets, and data-quality gaps.
- `GET /v1/locations/{location_id}/analytics.csv?from=...&to=...`: same authorized aggregate data as CSV.

Date filters are interpreted in the location IANA time zone, then converted to UTC for querying. Missing-camera periods and estimated values are labeled.

Phase 7 report routes require manager/admin role plus an explicit location grant.
`from` is inclusive and `to` exclusive, both local calendar dates. Optional
`group=day|hour`, `table_id` and `basis=CONFIRMED_WORKFLOW|DEMO|LEGACY|ESTIMATED_EVIDENCE`
are validated. Limits are 31 days, 100 tables, 20,000 output rows, 100,000 input
records per category and an eight-second SQL deadline. The current single API
process admits one active report/export per user and four total (429 otherwise).
JSON includes `as_of`, `cursor`, `time_zone`, `calculation_version`, `synthetic`,
bucket rows, denominator/coverage fields, session/reset summary and limitations.
Null means insufficient data. Completed-duration averages use whole valid
sessions ending in range; bucket state-time totals are clipped to the range.

CSV is private/no-store with a server-generated attachment filename, one metadata
row and table/bucket rows. It rechecks passive session/manager/location authority
per chunk. API Content-Length and the end-to-end `X-Report-Bytes`/browser size
check detect interrupted delivery even when the web proxy uses chunked transfer. Unsafe labels
are normalized for export and prefixed `Text: `; saved labels remain unchanged.
Separate JSON/CSV requests have separate cutoffs and may include different commits.

## Phase 7 reviewed human workflow

These routes are implemented and locally verified. The separately approved
reviewed `0009` migration, restricted grants and matching local application code
are active; existing locations remain OFF.

| Route | Contract |
| --- | --- |
| GET `/v1/locations/{id}/workflow` | Staff scope; coherent `mode`, `policy_revision`, `server_time`, `cursor`, table contexts and pending suggestions with truncation flags |
| GET `/v1/locations/{id}/workflow-suggestions` | Staff scope; `limit` 1–100, UUID `after` keyset and allowlisted status |
| GET/PUT `/v1/locations/{id}/workflow-policy` | Manager scope; change needs `mode`, `expected_revision`, `request_key`, up to 64 `bindings` and strict `rules`; enabling initially requires DEMO + synthetic location |
| POST `/v1/locations/{id}/workflow-suggestions/{suggestion}/decisions` | Staff confirm/dismiss; requires table/proposal expected revisions, UUID request key, physical `confirmed` flag for confirmation and allowlisted dismissal reason |
| POST `/v1/tables/{id}/workflow-actions` | Staff `ready`; manager-only `correct_departure`, `correct_arrival`, `reconcile_source`; expected revision, request key, physical check, and current session/reason for manager actions |

An absent policy is OFF. Qualified signed evidence creates suggestions only.
Only the permitted human decision updates the operational table/task. Conflicts
and stale versions return 409; same-key/same-body retries return the committed
result. An out-of-scope resource remains 404. These actions preserve CSRF/origin,
idle/absolute expiry, tenant RLS, protected states and one-task-per-session rules.
Existing Phase 3 actions retain their original behavior for unenrolled tables;
their legacy ready/DEMO paths cannot bypass an enrolled table's checks.

After v2 negotiation, only new queued events use `packages/contracts/evidence_protocol.py`:
strict transition/snapshot type, original scope/context, policy revision/digest,
finite bounded sample/coverage/gap/age fields and honest quality/nullable scores.
HIGH positive evidence and HIGH/MEDIUM reviewed vacancy evidence still require
their full temporal/freshness/context gates; LOW/UNCERTAIN never qualifies.
No frame/box/identity/credential fields are allowed. Existing v1 bytes and safe
shadow behavior stay unchanged. A heartbeat is not occupancy evidence.

CSV responses include `X-Report-Bytes`, the exact decoded CSV byte count, plus
API Content-Length and private/no-store headers. The Next.js proxy forwards
the custom count even when it uses chunked HTTP delivery. The report UI verifies
the complete blob against that bounded count before offering a file; absent or
mismatched counts fail without saving. Other clients must enforce the same check.

## Edge ingestion — implemented Phase 6 metadata boundary

- `POST /v1/edge/pairings` and `POST /v1/edge/pairings/proof`: bounded bootstrap and signed proof of key possession; neither grants restaurant access without manager approval.
- `POST /v1/edge/events`: authenticated device submits a bounded batch of versioned shadow events; `/v1/edge/batches` is a compatible name for the same handler/store. Signatures bind the exact requested path.
- `POST /v1/edge/heartbeat`: authenticated device submits bounded health and receives scoped configuration and a finite processing lease.
- `GET /v1/locations/{location_id}/devices`: scoped human view; setup metadata is manager-only.
- `POST /v1/locations/{location_id}/devices/commands`: manager/admin, explicit location grant, CSRF and revision checks for approval, assignment, processing, rotation and revocation.

The server derives authority from the verified device pairing and active scoped bindings. It rejects foreign table/camera/location claims, verifies signatures/timestamps/replay rules and enforces body/batch limits. Durable receipts deduplicate retries. Valid owned events with unsupported schema/type/state receive per-item rejection and a fresh-context/UNKNOWN boundary, rather than silently becoming valid state changes. The installed strict version-1 contract includes context identifiers but no numeric confidence/duration summary. See `packages/contracts/device_protocol.py`, its mirrored API/edge definitions and [the Phase 6 record](phase_explanations/PHASE_06.md). Normal AI events affect shadows only; the reset-task fixture is narrowly restricted to approved synthetic isolated tests.

## Event envelope — historical target illustration, not the installed wire format

The original design example below is preserved as history. Its IDs, field names and confidence value are illustrative; it is not a valid current version-1 request or a measured confidence/accuracy result. Use the strict typed contract and current route tests for actual requests. The implemented Phase 7 v2 schema and compatibility checks are described above; separately approved local activation is complete; public/pilot activation remains blocked.

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

In the implemented protocol, organization/location/camera/table identifiers must match the authenticated scoped bindings; mismatches are rejected, not trusted or silently ignored. Raw frames, detection boxes, person identities and credentials are excluded from the cloud contract.

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

The latest Phase 6 verification recorded 529 passing cases, including prior route/session/isolation/audit/retry/stream checks and signed device transport, replay, ordering, duplicate prevention and isolated recovery checks. These are historical results, not tests rerun for planning. Phase 7 analytics/date/export checks pass within its 636-test final verification; separately approved local activation also passes A/B authorization, OFF-default, SSE, CSV and CA-verified TLS checks. See the phase explanations for actual commands/counts and limitations; synthetic transport tests do not establish real-person AI accuracy.

- A Restaurant A token cannot read or mutate Restaurant B records.
- Altering organization or location fields in a request does not bypass authorization.
- A device paired to Location A cannot ingest events for Location B.
- Duplicate event posts have one durable effect.
- Pagination, date boundaries, and location time zones are tested.
- OpenAPI examples are generated from typed request and response models.
