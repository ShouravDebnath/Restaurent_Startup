# Phase 03: interactive restaurant dashboard with simulation

> **Phase 4 compatibility — 2026-11-08:** The final expanded suite passes 333 tests, retaining all 262 Phase 3 cases. The running existing floor view/SSE was checked through the browser for connection >12 seconds and offline/reconnect; original table states/records remain unchanged. Local input/calibration, grants and revision history now exist in [PHASE_04.md](PHASE_04.md), but the dashboard still uses controlled DEMO observations and never derives occupancy from footage. Earlier 10-group workflow/restart results remain their dated Phase 3 evidence, not new Phase 4 runs. Stop before Phase 5.

**Date:** 2026-11-07, Asia/Dhaka.
**Status:** Implemented and verified locally. The subsequent approved Phase 4 extension is documented separately; completion-time records below remain historical.
**Authority:** [Master section 17, Phase 3](../MASTER_SPEC.md#phase-3---first-working-dashboard-with-simulation) and the [approved implementation plan](../PHASE_03_IMPLEMENTATION_PLAN.md).

**Current Git status — later review on 2026-11-07:** Existing commit `3342c427d7cf4339041e31fd804ac629351ed731` (`V1`) already saves Phase 3 and was confirmed on GitHub `origin/main`. The [fresh verification/checkpoint review](../PHASE_03_CHECKPOINT.md) proposes only documentation changes, with separate approval required for a new local commit and its push. Earlier completion-time Git/cleanup results below remain historical.

## Overview and objectives

Phase 2 supplied private restaurant workspaces and configuration. Phase 3 makes the dining-room workflow usable: a floor view, six table states, persistent timers, cleaning tasks, staff actions, safe activity history, and authorized live updates. It runs with synthetic events and needs no video.

For example, a manager simulates guests arriving at A01. The table becomes OCCUPIED. Simulated departure creates RESET_PENDING and one task. Staff acknowledge the task, start cleaning, and explicitly confirm the table ready. Other permitted browsers at Restaurant A see the updates. Restaurant B receives none of A's information.

All synthetic locations display **DEMO — simulated information**. There is no camera processing, detector, measured AI confidence, device enrollment/synchronization, operational analytics/export, or billing in this milestone. The floor arrangement is a responsive grid, not a measured floor plan or camera polygon editor.

## Founder-approved decisions

1. Only owners, organization administrators and managers can block/reopen tables. Floor staff can acknowledge, start cleaning and confirm ready. Installers can read operational information but cannot operate tables.
2. GET/HEAD reads and SSE checks validate sessions without refreshing idle time. Successful authenticated mutations count as activity. Neither extends absolute session expiry.
3. Simulation requires all three: server DEMO_MODE enabled, an explicitly synthetic location, and an assigned manager/admin role. The feature flag alone cannot make an ordinary location a demo.
4. Existing npm findings are accepted for restricted local development. No major dependency upgrade, forced audit fix, override, or public deployment is authorized.
5. Existing database credentials remain unchanged. [The rotation procedure](../DATABASE_CREDENTIAL_ROTATION.md) must be reviewed/executed before pilot/public deployment.
6. Source failure preserves manually confirmed AVAILABLE, CLEANING and OUT_OF_SERVICE states and their timestamps. Source health is separate: the UI says offline/unavailable and does not count an unverified table as currently ready. Unconfirmed automatic observations fall back to UNKNOWN.

This last decision supersedes the original proposal's broader source-failure fallback. Reopening a blocked table returns UNKNOWN; it requires a new permitted ready-confirmation path.

## Implemented features and practical behavior

### Floor dashboard and mobile staff view

Open `/dashboard` after signing in. The existing `/settings` page links to it. A protected restaurant/location selector uses your permitted identity discovery; demo dining rooms are selected by default when present. A bookmarked location is accepted only if it appears in the user's permitted locations.

The page shows table counts, labels, seats, state text/icons/colors, state duration, source information, a selected-table panel, oldest-first tasks, and the last 30 safe location events. Staff actions are large labeled buttons. Manager controls and demo observations are visible only for the relevant roles. API/database checks remain authoritative even if someone bypasses the UI.

The floor and task panes stack on narrow screens. Table buttons support keyboard activation and selected-state labels. Text/icons accompany colors. Timer updates do not continuously announce themselves to screen readers. This is local usability coverage, not a complete accessibility certification.

| State | Meaning |
| --- | --- |
| UNKNOWN | Reliable occupancy information is unavailable or initial ready confirmation is missing |
| AVAILABLE | Staff/explicit demo setup confirmed ready, with source conditions shown separately |
| OCCUPIED | The current synthetic observation represents seated guests |
| RESET_PENDING | An occupancy session ended and staff attention may be needed |
| CLEANING | Staff started preparing the table |
| OUT_OF_SERVICE | An authorized manager blocked the table |

Timers derive from saved UTC `state_since` and `occupied_since`, with a server-time reference in the browser. Refresh does not create a new state timestamp. Clock/history display uses each location's IANA time zone. A timer measures recorded state duration; it does not establish when food was ordered or whether service occurred. During interrupted updates, the page labels information last-known and pauses actions/current availability.

### Cleaning tasks, safe transitions and retries

- A departure after occupancy creates one RESET task for that table session. Database constraints also permit at most one active reset task for a table.
- Acknowledge changes the task, not the table's readiness. Start cleaning requires RESET_PENDING and an active task.
- Mark ready requires an explicit confirmation, CLEANING or initial UNKNOWN, and current ONLINE/VACANT synthetic source information. Offline, unknown or occupied evidence rejects readiness.
- A current synthetic observation remains effective until the next explicit demo input. These are controlled scenarios, not camera frames or real camera heartbeats. No claim of visual freshness or AI accuracy is made.
- Guests returning resolve the obsolete reset task and begin a new occupancy session. Completed/cancelled tasks remain as history.
- Manager block records a predefined operational reason; arbitrary text/passwords are not accepted as reasons. It resolves any active task with an explicit reason.
- Each action carries an expected table revision and random request key. Stale operations return 409. Repeating the same key/payload returns the original result once; changing the payload conflicts.
- The browser retains the same request after an uncertain network result and offers **Retry the same request**. It does not invent another key that could repeat an already-committed action.

### PostgreSQL persistence and authorization

New forward revisions 0003/0004 add operational fields, location publication state, table events, RESET tasks, and action receipts. Existing migrations 0001/0002 are unchanged. Event confidence is nullable and remains absent/unknown in simulation; no measured accuracy is invented.

`location_operations` stores the explicit synthetic marker and publication revision. Events include organization/location/table, ordered location revision, actor, source, UTC occurrence/ingestion times, schema version, previous/new state and allowlisted details. Tasks retain acknowledgement/start/completion times and resolution. Receipts preserve a successful response for duplicate protection.

All new tables have RLS and same-location/tenant relationships. The restricted runtime can select permitted operational records but cannot directly write event/task/receipt rows. Direct table INSERT/UPDATE grants are narrowed to configuration columns. A controlled database function validates scope, current role, action fields, transition, expected revision and request identity, and writes state/task/event/audit/receipt atomically. It rechecks permission after lock waits. Its owner is privileged, so it explicitly performs authorization; RLS alone is not assumed to constrain a SECURITY DEFINER owner.

Action locking uses table then location. Location publication revision is serialized through commit, so another table's later event cannot overtake an uncommitted earlier cursor. Table label/seat changes publish invalidations as well. One snapshot SQL statement reads tables/tasks and cursor consistently. No SSE connection holds an idle database transaction.

The database and service still trust authenticated service-established identity. Arbitrary application/database credential compromise is outside what these RLS tests prove. Continued function/policy review and external testing remain necessary.

### APIs and event streaming

| Method and path | Purpose |
| --- | --- |
| GET `/v1/locations/{location_id}/dashboard` | Consistent scoped tables/tasks, role, DEMO/control flags, server time and cursor |
| GET `/v1/locations/{location_id}/tasks` | Status-filtered task history with bounded pagination |
| GET `/v1/locations/{location_id}/activity` | Safe operational events; optional scoped table filter and bounded pagination |
| POST `/v1/tables/{table_id}/actions` | Acknowledge/start/confirm ready/block/reopen |
| POST `/v1/locations/{location_id}/demo/events` | Gated arrive/depart/vacant/source-offline/source-resume inputs |
| GET `/v1/locations/{location_id}/stream` | Authorized location SSE; validated Last-Event-ID or initial `after` cursor |

Snapshot limits are 500 tables and 100 active tasks, with explicit truncation flags and a UI warning. Task/activity pages allow at most 100 records. Event replay fetches at most 100 rows per batch. There is no history-deletion/retention job in this phase.

The fixed same-origin Next.js proxy forwards cookies, CSRF and the replay header. Normal HTTP requests retain their timeout. Streams have a bounded connection/header deadline, incremental output, browser cancellation and a 15-second upstream read deadline. Backend heartbeats run every two seconds. Browser contact older than 15 seconds is stale; reconnect uses a fresh authorized snapshot. The backend also supports direct Last-Event-ID replay, tested over real HTTP.

Each stream batch/heartbeat obtains a short checked database transaction, revalidates current session/user/membership/location grant, reads a bounded batch, and closes before yielding/waiting. Passive reads use `peek_session`; active mutations use the existing activity-refreshing resolver. Expired sessions send session_expired and close; lost location access sends access_lost. The client clears protected data. Tokens never appear in URLs, event payloads or browser storage.

Connection admission is limited to four per user and 32 total **per API process**, with idempotent release on disconnect/completion. Shared multi-process/proxy quotas, long-term load and deployment limits are still production work. Selection changes close the old stream, cancel reads, clear data and reject late responses from the previous selection.

## Files created or modified and their purposes

| File/area | Purpose |
| --- | --- |
| `services/api/src/restaurant_api/models.py` | Operational table fields and new location/event/task/receipt models |
| `workflow_schemas.py` | Strict dashboard, task, event, staff/demo action and result contracts |
| `workflow.py` | Snapshot/history/action APIs, bounded durable SSE and connection admission |
| `security.py` | Passive versus active session validation |
| `management.py` | Restricted configuration-column grants, operational read/function grants and explicit dashboard seed command |
| `dashboard_seed.py` | Repeatable new synthetic dining rooms and six-state scenarios without resetting existing tables/accounts |
| `main.py` | Register dashboard routes while preserving health/readiness/public static demo |
| `migrations/versions/0003_dashboard.py`, `0004_task_kind.py`; `migrations/sql/0003_dashboard_*.sql` | Additive schema, passive session function, scoped policies, controlled actions and ordered publication |
| `services/api/tests/test_dashboard.py` | Workflow, permissions, isolation, expiry, retry, concurrency and persistence tests |
| `test_dashboard_transport.py` | Real Uvicorn/HTTP SSE reconnect/expiry/transaction tests |
| `tests/dashboard_support.py`, `tests/conftest.py` | Shared isolated fixtures and redacted runtime-generated test account representations |
| Existing `test_database_isolation.py`, `test_route_inventory.py` | Keep every original case; advance expected migration head, recognize earlier column-permission denial, and extend route coverage inventory |
| `apps/web/app/dashboard/page.tsx`, `types.ts` | Interactive responsive dashboard, safe reconnect/actions/retry, timers and typed view data |
| `apps/web/app/api/[...path]/route.ts` | Stream-specific forwarding/cancellation without changing the fixed upstream boundary |
| `apps/web/app/page.tsx`, `app/settings/page.tsx`, `globals.css` | Current DEMO landing/dashboard navigation and accessible responsive floor/staff styling |
| `scripts/verify_phase3_browser.py` | Installed-Edge checks in three isolated profiles, with ignored screenshots/report |
| `scripts/verify_phase3_restart.py` | Explicit local API restart, persisted session/event replay and same-request retry check |
| `scripts/verify_phase2_browser.py` | Preserve original-location assertions while permitting the new additive demo location |
| This explanation, phase index, plan, handoff, architecture/API notes, root README, affected earlier phase notes | Current behavior/evidence while retaining historical records |
| `docs/DATABASE_CREDENTIAL_ROTATION.md` | Future approved administrator/application credential rotation and recovery procedure; not executed |

No new library was added. Frontend manifests/lockfiles and existing credentials remain unchanged. API/web images use existing Dockerfiles and declared dependencies; the rebuilt API resolved FastAPI 0.162.1 while the host environment has 0.162.0. No major dependency upgrade or global software install was performed.

## Technologies and execution flow

Next.js/React/TypeScript render the browser workspace. Plain CSS provides layout and focus/state styling. FastAPI/Pydantic validate requests and responses. SQLAlchemy handles scoped reads, PostgreSQL provides durable transactions/constraints/RLS, and Alembic records forward schema changes. StreamingResponse and browser EventSource provide SSE without a new broker or service. Docker Compose packages the existing local stack. pytest, HTTPX, Uvicorn, Ruff, TypeScript and installed Microsoft Edge verify the layers.

Step by step: sign in → discover assigned locations → load a consistent dashboard snapshot → subscribe to that location → manager sends an explicit DEMO input or staff submits a CSRF-protected action → backend/session and database function validate it → state/task/event/audit/receipt commit together → SSE notifies only permitted clients → browser reloads the authoritative snapshot → another restaurant remains separate.

## Windows 11 run instructions

From PowerShell in `E:\Restaurent_startup`, preserve the existing `.env` and private credential file. Do not print their contents in shared output.

For an already configured Phase 3 stack:

```powershell
docker compose up -d --no-build --pull never --wait --wait-timeout 60
docker compose ps
```

Open `http://localhost:3000/sign-in`. Privately read the `a_owner`, `a_staff`, or `b_owner` entry in `.secrets/phase2-demo-credentials.json`. Sign in, then choose **Open dashboard** or open `http://localhost:3000/dashboard`. Select **DEMO A Dining Room** or **DEMO B Dining Room**. Use separate browser profiles/private windows to compare accounts; ordinary tabs share cookies.

Managers open a table's **DEMO scenario controls**. Try Guests arrive, Guests leave, Show vacant and Source offline. Staff use the task panel and selected-table buttons. To initialize UNKNOWN, Show vacant first, then explicitly confirm ready. Reopen returns UNKNOWN. No camera should be connected for this demonstration.

Applying this milestone to an existing Phase 2 checkout requires the reviewed backup/migration/provision/seed/image sequence:

```powershell
# Installed project .venv and Docker must already be available.
.\.venv\Scripts\python.exe scripts/backup_phase2_database.py
.\.venv\Scripts\python.exe -m restaurant_api.management migrate
.\.venv\Scripts\python.exe -m restaurant_api.management provision
# Existing Phase 2 seed/credentials must be present. This adds new demo dining rooms.
.\.venv\Scripts\python.exe -m restaurant_api.management seed-dashboard
docker compose build api web
docker compose up -d --no-build --pull never --no-deps --wait --wait-timeout 60 api web
```

On a fresh checkout, first follow Phase 2 private configuration/bootstrap instructions and run its explicit synthetic `seed` command. `seed-dashboard` reads those existing account IDs, adds new locations/tables/grants, and writes only a new ignored `.secrets/phase3-demo-layout.json`. It does not reset passwords, existing states, timers or histories. Repeating setup preserves staff changes. Migrations never automatically run on API startup; downgrades are disabled. Do not install missing software or change credentials without the required permission.

## Windows 11 test instructions

```powershell
.\.venv\Scripts\python.exe scripts/start_phase2_test_db.py
.\.venv\Scripts\python.exe -m pytest services/api/tests services/edge-agent/tests --import-mode=importlib -q
.\.venv\Scripts\python.exe -m ruff check services/api services/edge-agent scripts
.\.venv\Scripts\python.exe -m pip check
Push-Location apps/web
npm run lint
.\node_modules\.bin\tsc.cmd --noEmit
npm run build
Pop-Location
docker compose config --quiet
.\.venv\Scripts\python.exe scripts/verify_phase3_browser.py
# Optional explicit recovery check: briefly restarts only the local API.
.\.venv\Scripts\python.exe scripts/verify_phase3_restart.py
```

The historically named Phase 2 test-server script also supports these tests. It uses a cached PostgreSQL image, tmpfs and a private localhost port, never the original application volume. Integration tests reject database names outside the test prefix and do not silently skip. Network stream tests start an isolated loopback Uvicorn server; they do not use a fully buffered TestClient to pretend streaming works.

The browser verifier deliberately changes synthetic demo tables and appends their history; it expects the documented initial available table or a previously completed verification workflow. It never resets data on a failed run. Keep its profiles/screenshots/reports private in ignored `.cache/` and `.secrets/` folders. It uses installed Edge and existing Python websockets, not a new browser installation.

## Actual verification results

This table preserves the original implementation run. The later GitHub-preparation review below records fresh tests and supersedes the earlier uncommitted/no-remote status; earlier tests are not silently treated as current evidence.

| Check | Actual result |
| --- | --- |
| Full Python regression/security run | **262 passed, 1 existing warning in 51.96 seconds**, project Python 3.14 and real isolated PostgreSQL; no skips |
| Original coverage preservation | Collection confirms **152 original cases plus 110 new Phase 3 cases**; all original test files remain. Migration-head/earlier permission-denial expectations were updated, not removed |
| Restaurant/location/role boundaries | Original 46 and new 12 both-direction cross-restaurant route cases pass; anonymous, same-restaurant ungranted location, nested ownership/task IDs, manager/staff/installer and disabled permissions are rejected correctly |
| Workflow/concurrency/idempotency | Full reset cycle, duplicate departure, task uniqueness/completion, concurrent same/different-key writes, different-table event order, stale revisions, forged bodies, safe ready confirmation and atomic failure rollback pass |
| Session and streaming | Passive GET/batch checks do not change last_seen; active action refreshes only idle activity. Idle/absolute/revoked/user/membership/grant failures close streams. Real HTTP Last-Event-ID replay and no-idle-database-transaction checks pass |
| Migrations and preservation | Rehearsed restore of a private pre-Phase 3 backup; forward head **0004**, zero model differences. All **57 original business rows** remain unchanged in both the restored rehearsal and application database. All ten original demo user rows/password hashes/enabled flags match the backup |
| Running stack | API/web images built and started; DB/API healthy, web responds. Original DB container `88e44ea5a3bd` and `restaurent_startup_postgres_data` retained; all published ports still loopback. Existing health/readiness/public demo preserved |
| Phase 2 runtime/browser compatibility | Existing running-stack verifier passes **7 groups**; installed-Edge settings/create/update/isolation verifier passes **8 groups**, with no JavaScript exceptions |
| Phase 3 browser flow | **10 groups pass** across A administrator, A staff and B administrator profiles: authorized redirects/data, DEMO/HttpOnly behavior, staff workflow and A-to-A updates, B isolation, persistent timer/reload, manual-state/source safety, long-lived proxy stream, offline/reconnect, keyboard/mobile and logout |
| Actual API restart recovery | **4 groups pass** through the running Next.js proxy: committed event before/after restart, persisted human session, Last-Event-ID replay and one-effect retry using the same request key. Only the API was restarted; DB/volume untouched |
| Clock/time-zone cases | Actual dashboard timer remains correct with the client clock ten minutes ahead. Actual history rendering handles New York's repeated DST hour and Asia/Dhaka using temporary client-only date fixtures; no historical database timestamps were changed |
| Frontend checks | Host lint/TypeScript/production build pass; final Node 22 Docker build also compiles, checks lint/types and builds `/dashboard`. Existing next-lint deprecation remains |
| Python/Compose checks | Ruff and pip check pass; Compose quiet validation passes. pip check is not a Python vulnerability audit |
| Source/secrets | All 12 running API package source files match workspace; known generated private values are absent from Git-eligible source and private/generated-path ignore probes pass. No known demo password was detected in API/web logs. The weak legacy common-text caveat remains |
| Final documentation/repository check | All 91 local documentation links/anchors resolve. Review of 92 Git-eligible files against 35 known private values found no matches; all 13 sensitive/generated-path ignore probes pass. All 76 original files remain; Git configuration and the Phase 2 checkpoint are unchanged |
| Final targeted migration recheck | After removing only trailing SQL whitespace, the preservation/repeatable-seed test passes again: 1 passed, 1 existing warning in 2.07 seconds. SQL tokens are unchanged; this is a repeated case, not another unique test |
| Temporary test-server cleanup | Removed only the marked Phase 3 tmpfs test container after verifying it had no volume/bind mounts. The application database container/volume, private backups and verification reports remain intact |

The original backup was `.secrets/backups/phase2-before-20261107T143615Z-d51d308d.dump`; a second archive was taken immediately before application migration at `151137Z`. Both remain private. The historical backup helper's phase2 filename prefix does not change what was backed up. Browser/runtime checks deliberately add/change synthetic records and append their history. Original records were not erased to make tests pass. Extra configured demo tables are permitted alongside the six seeded examples.

Desktop/mobile screenshots and reports remain in ignored `.cache/` and `.secrets/` folders. The tests are local evidence; no hosted CI, clean-machine installation, full browser matrix, real hardware, production load, independent security audit or measured AI accuracy is claimed.

The final private preservation report confirms head 0004, zero model differences, 57 unchanged original business rows and ten unchanged original demo user rows/password hashes. The disposable test server is now stopped/removed. Run `scripts/start_phase2_test_db.py` before a future integration-test run; it preserves the old private manifest and creates a new isolated server when the old container is absent.

## GitHub preparation and fresh verification — 2026-11-07

The repository was clean at the start of this review: no modified, staged or eligible untracked files. The existing `V1` commit already contained the 39-file Phase 3 implementation. `git ls-remote --heads origin refs/heads/main` confirmed that GitHub and local `main` both pointed to `3342c427d7cf4339041e31fd804ac629351ed731`. This was a read-only check; no commit, push, history rewrite or remote change was performed.

Freshly executed checks:

- Full backend/edge suite: **262 passed, 1 existing warning in 52.90 seconds**, including all original 152 cases. A new marked, isolated PostgreSQL tmpfs server was used; the application volume was not used for the security tests.
- Installed-Edge dashboard verifier: **10 groups passed** again, including A/B isolation, staff workflow, SSE, timers/clock skew, offline recovery, manual-state protection, mobile/keyboard and logout. It appends only explicit synthetic demo activity.
- Actual API restart verifier: **4 groups passed** again. The API briefly restarted; committed events, a human session and one-effect retry survived. Database container and volume were unchanged.
- Ruff, `pip check`, frontend lint, TypeScript, production build and quiet Compose validation passed again. Existing Starlette/HTTPX and next-lint deprecations remain. No packages were installed/upgraded, and no application source or dependency manifest was changed.
- Read-only preservation check: all **57 original business rows**, migration head 0004, private `.env`, original database container and named volume are preserved. The earlier ten-user/password-hash backup comparison remains historical; it was not repeated against a restored backup in this review.
- Working-tree review covered 92 tracked files at the initial clean state and 37 known private values. Historical review covered **135 unique blobs across all three reachable commits**. No known-value, credential-context, provider-token/private-key, literal-hash or sensitive-path matches were found. All 13 ignore probes pass. The legacy administrator password/common-text caveat still applies; this is not proof that every possible secret format can be detected.
- Cleanup removed only the review's marked tmpfs test container, after confirming it had no volume/bind mounts. Application database/volume, project files and private reports/backups remain. The documentation checkpoint was prepared for approval on 2026-11-08, Asia/Dhaka, after the review crossed local midnight.

The existing workflow configures hosted CI, but its GitHub run status was not checked here. Local verification and a matching remote commit do not prove hosted CI passed. The [checkpoint manifest](../PHASE_03_CHECKPOINT.md) lists the six documentation files proposed for a new review checkpoint; the implementation is already on GitHub. Existing npm findings and the required pre-pilot/public credential rotation remain unresolved. No Phase 4 work was started.

## Problems encountered and solutions

- Narrowed database INSERT grants initially rejected new nullable ORM columns. Marked their NULL defaults as database defaults, retaining narrow grants, then reran all original tests successfully. Reparenting is now rejected by column permission before the earlier ownership trigger; its negative test still verifies rejection.
- The larger suite reused one synthetic account enough to hit the real login throttle. Network tests now get distinct provisioned synthetic accounts; application throttling was not weakened. A failed test exposed one generated disposable-test credential in diagnostic formatting. That isolated account was disabled, and test accounts now redact their representation. Real project/demo credentials were not printed or changed.
- A shared test fixture initially passed an existing UUID object to the string-only constructor. Normalized that boundary and reran the affected tests before the full suite.
- Phase 2 GET authentication updated idle time. Added a passive resolver and tested HTTP/SSE expiry separately from active mutations, preserving absolute expiry.
- The old proxy timeout was suitable for short JSON calls but broke persistent streams. Added incremental streaming and bounded header/idle deadlines with cancellation and replay-header forwarding.
- Browser network-loss testing found a delay before stale detection. Added offline/online event handling to pause immediately and reconnect from a fresh snapshot. Multi-profile keyboard automation required explicit page focus and trusted Enter text; the actual native table controls then passed. The earlier settings verifier also adds legitimate synthetic tables, so the dashboard verifier checks the six seeded IDs rather than wrongly requiring an exact total of six.

## Remaining limitations and phase summary

- This is a local DEMO, not a camera installation, AI evaluation, public release or compliance certification. Confidence is unmeasured. Real frame freshness, detector timing, device credentials/outbox/sync and analytics remain later phases.
- The documented npm findings remain: eight affected entries, one high/seven moderate in the last audit. No fix/override or major upgrade was applied. The administrator password is unchanged and requires approved rotation before pilot/public use. Production identity/MFA/recovery, TLS, secret operations, non-root images, monitoring, retention and external security review remain open.
- Python compatibility is checked, not a complete Python/container vulnerability audit. Broad version ranges and host/container patch/toolchain differences remain reproducibility debt. Existing Starlette/HTTPX and next-lint deprecations remain.
- Stream limits are per process; distributed limits, long-duration load, fully automated multi-browser coverage, a formal accessibility audit and clean-machine installation are not established. Recorded timing is an observed test result, not an SLA.
- Role changes are enforced on every mutation; visible controls and non-table configuration metadata can need a snapshot refresh. The JSON proxy's body-size rejection follows buffering, so production ingress/body limits still need review. Large floors/task histories do not have complete UI pagination; truncation is explicit and paginated history APIs remain available.
- The event/task models support this demo workflow. General task categories, full edge event ordering/reconciliation, production retention/deletion and analytical exports are not implemented early.
- At initial implementation completion, Phase 2 checkpoint `62ad22996f6e369c9116028ba0266ed3102b2e94` was retained and Phase 3 was uncommitted. The later GitHub review above confirms Phase 3 in existing `3342c42` on local/GitHub `main`. Its new documentation checkpoint still requires explicit local-commit and then push approvals.

Phase 3 now demonstrates separate restaurants, durable simulated table/task history, protected staff actions and live updates. All original functionality and records are preserved within the verified scope. Stop for founder review before any Phase 4 work.
