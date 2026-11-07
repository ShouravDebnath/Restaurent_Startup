# Phase 02: multi-restaurant database, authentication, and authorization

**Verification date:** 2026-11-07, Asia/Dhaka.
**Status:** Implemented and verified for local development; founder review is the next gate. Phase 3 has not started.
**Approved design:** [Architecture decision record](../PHASE_02_ARCHITECTURE_PROPOSAL.md). The founder explicitly approved local Argon2id authentication, project-only dependencies, backend permissions plus PostgreSQL RLS, restricted database access, additive migrations, synthetic seeds, isolated tests, backup, and application image rebuilds.

## Overview and objectives

Phase 1 was a working shell with a public, hard-coded demo. Phase 2 gives the application a real database and separates each restaurant's data. It adds sign-in and configuration screens, not live CCTV monitoring.

For example, Restaurant A and Restaurant B can use the same application and PostgreSQL server. A manager at A can read only the locations explicitly assigned to that person. Knowing a B table's ID does not grant access to it. The server checks permission, and the database also checks which rows the authenticated user may access.

The authoritative requirements are [master section 17](../MASTER_SPEC.md) and [P2-01 through P2-12](../CODEX_HANDOFF.md#phase-2-acceptance-checklist). All earlier Phase 1 reports remain historical records, rather than being counted as current Phase 2 verification.

## Implemented features

### Database and ownership

- Organizations represent independent restaurant businesses. Each has a name, creation time, and development plan metadata; this does not implement billing.
- Locations belong to an organization and store a name, optional address, and validated IANA time zone such as `America/New_York` or `Asia/Dhaka`.
- Users have a normalized unique email, display name, enabled flag, and Argon2id password hash. The private `identity` schema also stores sessions and login-throttling counters.
- Memberships connect a user to an organization, with a role and enabled flag. Separate location grants specify exactly which locations are accessible. One person can have explicit memberships in several organizations.
- Camera metadata stores a label and optional opaque local reference. It rejects URLs and passwords. Every Phase 2 camera is `NOT_CONFIGURED`; no camera connection is attempted.
- Tables store labels, optional seats, state, and the UTC state-entry time. New records start `UNKNOWN`. The database recognizes all six canonical states, but configuration APIs do not let a user invent readiness or operate a state machine.
- Table zones connect a table and camera in the same location. They store a simple polygon of 3–64 distinct normalized points, source dimensions, and a revision. Invalid, empty, crossing, and foreign-location polygons/references are rejected. Saving a stale revision returns 409.
- Audit records store the actor, organization, optional location, action, UTC time, and safe details. Membership changes include the assigned role, enabled flag, and explicit location IDs. Passwords, session tokens, camera credentials, and raw request bodies are not audit details.

Composite foreign keys are database rules that ensure related records share the same organization and location. Ownership-update triggers prevent moving an existing resource into another tenant or location. There are no resource-deletion APIs in this milestone. Memberships and sessions can be disabled/revoked without deleting records.

Device registration, a camera-to-device foreign key, table events, and staff tasks are deliberately deferred to later migrations, as approved. No fictional device association or later-phase workflow was added.

### Sign-in and sessions

Passwords are hashed with `argon2-cffi` using Argon2id, 19 MiB memory, two iterations, and one parallel lane. A hash is a one-way password check; it is not a plaintext password or a reversible encrypted password.

After successful login, the server generates a random opaque session token. PostgreSQL stores its SHA-256 digest, not the token itself. The browser receives the token only in a host-only `HttpOnly`, `SameSite=Strict` cookie. JavaScript does not receive the session token in JSON or local storage. Default limits are 30 minutes idle and 8 hours total. Login rotates the old session, logout revokes it, and disabled users or expired/revoked credentials cannot authenticate.

Non-development configuration requires secure cookies and exact HTTPS origins. Local development deliberately uses HTTP on this PC and a non-Secure development cookie. This is not a public-deployment configuration.

Mutations require an exact allowed `Origin` and a CSRF token derived from the current session. CSRF protection stops another website from making an unwanted authenticated change through the browser's cookie. Login itself requires the allowed origin. Persistent 15-minute login buckets limit attempts per normalized email and network peer; failed logins commit their counters even though authentication fails. Unknown, disabled, and incorrect-password accounts use generic errors.

Account provisioning is an explicit administrator command. There is no public signup, email verification, managed MFA, or online password-reset/recovery flow. Demo passwords are generated at execution time and saved only in an ignored private file. Tests generate their own credentials; they do not embed password values in source fixtures.

### Roles and location access

| Role | Organization-level abilities | At explicitly granted locations |
| --- | --- | --- |
| Owner | Organization/location administration; memberships and grants; ownership assignment | Read and configure tables, cameras, zones; permitted audit access |
| Organization admin | Organization/location administration and non-owner memberships/grants; cannot change owner permissions | Same configuration abilities as owner |
| Manager | No membership, role, or grant management | Read resources, configure tables/cameras/zones, read location audits |
| Floor staff | No administration | Read permitted resources; no configuration changes or audit access |
| Installer | No membership, role, or grant management | Read configuration and manage camera metadata/zones; cannot register/edit tables |

An owner/admin does not automatically see every location. Such a person can deliberately assign an explicit grant within their organization, including to themselves; the change is audited. Creating a location explicitly grants its creator access. The last enabled owner cannot be removed/demoted, and the API requires another owner to change your own role or disable your membership. Platform/support users have no automatic tenant access or support override.

### Two authorization layers

1. FastAPI obtains the user from a valid server-side session, checks enabled membership and role, and scopes resource lookups to the requested organization/location. It rejects altered ownership fields and foreign nested IDs.
2. PostgreSQL row-level security (RLS) checks the authenticated user's memberships and explicit location grants for each row. An omitted application tenant filter still cannot expose an unauthorized restaurant's rows.

The runtime connection uses a separate non-owner login with no superuser, `BYPASSRLS`, database/role creation, schema creation, table deletion, truncation, or migration powers. The API refuses privileged runtime connections. The private identity tables are not directly readable by that login. Narrow functions provide credential/session/profile lookups and controlled organization/location creation, with fixed search paths and explicit execution grants.

The transaction-local setting is the verified `app.user_id`. Policies derive organization/location permission from each row's ownership and current database grants; the API also filters the requested scope. No browser-supplied tenant context establishes permission. This realizes the approved transaction-scoping design without trusting separately supplied organization/location settings. Transaction-local identity clears when the transaction ends, including when a pooled connection is reused.

Privileged migration/administrative access remains outside the running API container. RLS protects the restricted runtime role; administrators and policy owners remain privileged. Compromise of service/database credentials or arbitrary SQL execution is not made harmless by RLS. Do not present this as a production security certification.

### Frontend integration

The original Phase 1 landing page remains, with a link to restaurant settings. `/sign-in` and `/settings` now provide real login/logout, authorized restaurant/location selection, organization/location settings, table configuration, camera metadata, zone configuration, membership/grant administration, and recent permitted activity.

Browser requests go to the same-origin Next.js `/api/v1/...` proxy. Its upstream address is fixed by server configuration; it does not trust identity headers or accept an arbitrary target URL. FastAPI makes the actual access decisions. The proxy passes session cookies and CSRF information without exposing database credentials. Responses containing application data use `Cache-Control: no-store`.

Role-based controls help users see relevant actions, while backend checks remain authoritative. A user whose permissions change may need a reload to refresh visible controls; the API enforces current permissions immediately. Audit times use the record's location IANA zone; organization-wide records use UTC. The UI is configuration only: no floor-map simulation, live timers, staff task workflow, SSE, video drawing/preview, or inference.

## Created/modified files and their purposes

Paths below are relative to the repository root.

| Files | Purpose |
| --- | --- |
| `services/api/src/restaurant_api/models.py` | SQLAlchemy entities, ownership relationships, unique/check constraints |
| `settings.py`, `database.py` in that package | Environment validation, restricted runtime connections, UTC sessions, request transactions |
| `security.py` | Password verification, session identity, CSRF, reusable role/location checks |
| `schemas.py` | Strict typed requests/responses, email/time-zone/polygon validation; no credential fields in resource responses |
| `routes.py` | Auth, identity, organization, location, membership, table, camera, zone, and audit APIs |
| `management.py` | Explicit prepare/migrate/provision/seed/create-user commands; private administrative access |
| `main.py` | Route registration, safe error envelopes, no-store/security headers, OpenAPI cookie authentication, `/ready`; retains `/health` and synthetic demo |
| `services/api/migrations/versions/0001_*.py`, `0002_ownership.py`; `migrations/sql/0001_*.sql`, `0002_ownership.sql` | Immutable additive schema, functions, policies, ownership protections |
| `services/api/migrations/env.py`, `script.py.mako`, `README.md` | Model discovery, supplied migration connection, corrected generated-operation template, safe migration instructions |
| `services/api/pyproject.toml` | Approved Argon2 dependency; FastAPI minimum 0.121 for transactions that finish before the response; Windows time-zone data |
| `services/api/tests/conftest.py`, `__init__.py`, `test_security.py`, `test_sessions.py`, `test_database_isolation.py`, `test_configuration_api.py`, `test_route_inventory.py` | Real PostgreSQL fixtures and authentication/authorization/migration/configuration/security coverage |
| `apps/web/app/api/[...path]/route.ts` | Fixed server-side API proxy, cookie forwarding, no-store behavior, bounded proxy payload |
| `apps/web/app/sign-in/page.tsx`; `app/settings/page.tsx`, `forms.tsx`, `types.ts` | Login and protected configuration interface with typed data |
| `apps/web/app/page.tsx`, `layout.tsx`, `globals.css` | Preserve landing page; settings link, metadata, responsive forms and accessible controls |
| `apps/web/.dockerignore`, `services/api/.dockerignore` | Exclude private environment files, dependency folders, caches, and generated output from build contexts |
| `.env.example`, `docker-compose.yml` | Blank private runtime template, separate application credentials, allowed origins/cookie settings, database-backed readiness, internal proxy address |
| `.github/workflows/ci.yml` | Disposable PostgreSQL service for API integration tests; isolated CI trust authentication is not used in the application stack |
| `scripts/start_phase2_test_db.py`, `backup_phase2_database.py` | Isolated local test server; private pre-migration backup and archive inspection |
| `scripts/verify_phase2_runtime.py`, `verify_phase2_browser.py` | Repeatable running-stack checks and installed Edge browser checks using synthetic accounts only |
| This explanation, phase index, root README, handoff, architecture, API contract, threat model, implementation plan, Phase 1 note, contracts note, approved proposal | Current instructions, architecture decisions, evidence, scope, historical/current distinction, limitations |

The edge-agent source, master specification, supplied blueprint, footage, and existing npm package/lockfile versions were preserved. Private `.env`, generated account files, backup archives, browser profiles, and test manifests remain outside Git.

## Technologies explained

- **PostgreSQL 16:** the durable database. RLS and constraints provide an additional barrier around restaurant/location records.
- **SQLAlchemy:** Python classes and queries for database records. It does not replace authorization.
- **Alembic:** a numbered history of database changes. Revisions 0001 and 0002 add structures and protections without resetting data.
- **FastAPI/Pydantic:** typed HTTP routes and request validation. OpenAPI documents actual routes and session-cookie security.
- **Argon2id and opaque sessions:** expensive password hashes plus revocable server-side login records. JWTs and browser local-storage authentication were not added.
- **Next.js/React/TypeScript:** interactive configuration forms and a server proxy; authorization stays in FastAPI/PostgreSQL.
- **Docker Compose:** retains the existing PostgreSQL volume and runs rebuilt API/web images with ports restricted to localhost.
- **pytest, HTTPX, Ruff, TypeScript, ESLint:** security/regression tests and source checks. Installed Edge plus its local debugging protocol verifies real browser behavior without installing a browser testing package.

## Step-by-step execution flow

1. Read the permanent rules, master specification, handoff, roadmap, architecture, and source. Rechecked Phase 1 rather than assuming past results still applied.
2. Presented alternatives and obtained both required architecture/install/execution approvals before authentication or isolation implementation.
3. Created models, strict schemas, additive migrations, restricted-role provisioning, session controls, APIs, and isolated PostgreSQL security tests.
4. Ran migrations twice and seeds twice in test databases. Verified preservation of an existing synthetic sentinel table/row and an empty Phase 1-style migration table.
5. Created a private custom-format backup of the existing development database, inspected its archive, and restored it successfully into a separate test database. Reconfirmed the original development database still had only its empty migration table before upgrading.
6. Applied migrations to the existing database, provisioned the restricted application login, and explicitly seeded two synthetic restaurants. No existing records were deleted or reset.
7. Added the minimal frontend, rebuilt API/web images, and recreated only those application containers. The existing database container and original named volume were retained.
8. Ran running-stack and real-browser checks, fixed errors, reran affected tests, reviewed screenshots, and updated documentation. No Git commit/push or later-phase feature was performed.

During a normal request, the browser sends its cookie to Next.js; the fixed proxy forwards it to FastAPI; the server validates the stored session; PostgreSQL receives transaction-local user identity; API checks and RLS restrict the operation; successful sensitive changes append an audit record in the same transaction; then the response returns without secret fields. The transaction completes before a successful response is sent.

## Windows 11 run instructions

Run PowerShell from `E:\Restaurent_startup`. The existing `.venv`, Docker Desktop, WSL 2, and project dependencies were used. No global Python/npm software was installed. The API image uses Python 3.12; local tests used Python 3.14. Browser checks use the existing Microsoft Edge installation. A completely fresh Windows machine was not tested.

### Existing configured project

Your current stack is configured and running. Open `http://localhost:3000/sign-in`. Open `.secrets/phase2-demo-credentials.json` **locally** for the `a_owner` or `b_owner` account. Keep that file private; do not paste its contents into chat, logs, or Git. Use separate browser profiles/private windows when comparing simultaneous sessions. Two tabs in one profile share the cookie.

To start already-built application images later:

```powershell
docker compose up -d --no-build --pull never --wait --wait-timeout 60
docker compose ps
```

### Bootstrap a checkout or apply reviewed forward migrations

Preserve an existing `.env`. On a new checkout only, copy `.env.example` to `.env` and privately supply database administrator values. Keep the current database credentials for an existing volume; environment edits alone do not rotate a PostgreSQL password. Install missing project dependencies only with the required permission. Do not run the following as a database reset.

```powershell
.\.venv\Scripts\python.exe -m restaurant_api.management prepare
docker compose up -d db

# For an existing database, take a private backup BEFORE an upgrade.
.\.venv\Scripts\python.exe scripts/backup_phase2_database.py
.\.venv\Scripts\python.exe -m restaurant_api.management migrate
.\.venv\Scripts\python.exe -m restaurant_api.management provision

# Explicit local synthetic data only; not an automatic application startup step.
.\.venv\Scripts\python.exe -m restaurant_api.management seed
docker compose up -d --build api web
```

`prepare` adds missing private runtime settings without connecting to the database. `migrate` applies reviewed additive revisions with administrator access. `provision` grants limited runtime access without replacing an existing role password. `seed` is repeatable and preserves existing data/passwords; if its original private credential file is lost, it fails for manual recovery rather than resetting accounts. `create-user` interactively asks for an email, display name, and hidden 15–128 character passphrase; an owner/admin can then assign that existing account to a restaurant through the UI/API.

`APP_DB_USER`/`APP_DB_PASSWORD` are used by the API's private `PGUSER`/`PGPASSWORD`; `POSTGRES_USER`/`POSTGRES_PASSWORD` remain for database administration. Do not print full `docker compose config` or `docker inspect` output because resolved environments contain private values. `docker compose config --quiet` validates without printing them. Custom web ports also require a matching exact `ALLOWED_ORIGINS` setting.

Downgrades are intentionally disabled. Correct mistakes through a reviewed forward migration; do not use `drop_all`, delete a volume, or reset a database. The custom migration DDL requires an online connection; offline migration SQL generation is not supported/verified.

## Windows 11 test instructions

```powershell
# Creates/reuses only an explicitly marked isolated test container, with tmpfs data.
# The postgres:16-alpine image must already be available; the script never pulls it.
.\.venv\Scripts\python.exe scripts/start_phase2_test_db.py
# The script waits until its isolated PostgreSQL server is accepting connections.
.\.venv\Scripts\python.exe -m pytest services/api/tests services/edge-agent/tests --import-mode=importlib -q
.\.venv\Scripts\python.exe -m ruff check services/api services/edge-agent scripts
.\.venv\Scripts\python.exe -m pip check

Push-Location apps/web
npm run lint
.\node_modules\.bin\tsc.cmd --noEmit
npm run build
Pop-Location

# Running stack, explicit synthetic seed, and private credentials must already exist.
.\.venv\Scripts\python.exe scripts/verify_phase2_runtime.py
.\.venv\Scripts\python.exe scripts/verify_phase2_browser.py
docker compose config --quiet
```

Integration tests refuse database names outside the `phase2_security_test` prefix. They never substitute SQLite and do not silently skip database verification. With no authorized test server, they fail with setup instructions. Local tests read an ignored test manifest; CI sets `PHASE2_TEST_ADMIN_URL` for its isolated PostgreSQL service. Do not point that setting at restaurant data. Integration tests create new synthetic records/databases/roles in the test instance; its disposable data is not the original development volume. Runtime/browser verification intentionally adds synthetic tables to Restaurant A, so they remain visible afterward.

After verification, the agent removed only the explicitly labeled, separate tmpfs test container. The original application database/volume and API/web services remain running. The private test manifest remains as a record; the start script safely preserves that old manifest and creates a fresh isolated server when rerun.

## Actual verification results

| Check | Actual result |
| --- | --- |
| Final Python regression/security run | **152 passed, 1 existing warning**, 11.54 seconds, using project Python and real PostgreSQL |
| Cross-restaurant API coverage | **46/46 scoped operation cases blocked**: 23 operations in each direction, plus nested-ID/ownership/foreign-grant tests |
| Missing authentication | All 23 scoped operations and five protected identity/discovery operations reject anonymous access |
| Same-organization location/role checks | Restricted locations, owner/admin/manager/staff/installer actions, explicit multi-organization grants, disabled membership/user, and escalation tests pass |
| Sessions and CSRF | Invalid/forged/expired/idle/revoked sessions, rotation, stolen-copy logout, exact origin, missing/invalid/non-ASCII CSRF, generic errors, persistent throttling, secure production-cookie configuration pass |
| Database isolation | Restricted-role direct SQL without application filters is scoped; foreign writes/reparenting and foreign zone references are blocked; pooled connection identity clears; identity-table reads/destructive privileges denied |
| Migrations/model metadata | Empty/preexisting test database upgrade, repeated upgrade, sentinel preservation, repeated seed pass; Alembic check reports no new upgrade operations |
| Existing database preservation | Private backup inspected/restored in isolated test database; original volume `restaurent_startup_postgres_data`, created `2026-11-06T16:18:11Z`, retained; original DB container retained; development head `0002` |
| Synthetic development data | Two organizations, four locations, ten users/memberships, twelve grants, four cameras/zones; four seeded tables plus additional verification-created tables |
| Python lint and installed dependency consistency | Ruff passed; `pip check` reported no broken requirements |
| Web checks | TypeScript and ESLint passed; production builds succeeded locally and in Docker; new CSS warning corrected and clean Docker build verified |
| Running frontend/API/database | Seven verification groups pass through Next.js and the actual restricted API/database connection |
| Actual Edge browser | Eight groups pass: redirect, A login/selectors, table form, desktop/mobile layout, logout/B login, A table hidden from B, foreign fetch 404, B logout; no JavaScript exceptions |
| Source/runtime consistency | Running API package hashes match workspace source; all ports remain on `127.0.0.1` |
| Git and file preservation | No commit/push/remote change; existing checkpoint retained; no existing file deleted; private environment/credentials/backups, dependencies, generated files, and footage excluded |
| npm audit | **8 affected entries: 1 high, 7 moderate, 0 critical**; versions unchanged and no forced fix/upgrade applied |
| Hosted CI / fresh machine / public production | **Not verified**; CI workflow updated but not pushed/run remotely; no fresh-machine or public-deployment claim |

The final Python command above includes the original four starter tests. The first broader run had an installer audit-permission failure; the issue was corrected and the final full run passed. A later route-coverage test initially inspected FastAPI's internal router list incorrectly; it now checks the published OpenAPI routes and passes. Earlier passing counts are intermediate records, not substituted for the final result.

## Problems encountered and solutions

- **Privileged original database login:** RLS would be bypassed by the original superuser connection. Created a separate restricted application login, removed administrative credentials from API runtime wiring, and added a runtime safety check plus a regression test.
- **Empty migration generation:** the Phase 1 Mako template always emitted `pass`, even when Alembic found new tables. Corrected the template, inspected the generated revision, and verified the real schema in isolated PostgreSQL before touching the existing database.
- **PostgreSQL percent operators in raw DDL:** the driver interpreted `%` in polygon/policy SQL as parameter syntax. Executed static migration DDL with `no_parameters` and verified transactional retries. Initial failed attempts rolled back in the test database.
- **Generated JSONB type reference:** Alembic rendered an unqualified `Text()` under this dependency combination. Corrected it to `sa.Text()` before the revision was applied successfully.
- **Installer audit append:** ORM `RETURNING` attempted to read an audit row from a role that could write the entry but could not read history. Switched the audit insert to an inline insert with no returned private row; kept audit read restrictions and reran role tests.
- **Failed-login counter rollback:** request transactions normally roll back on authentication errors. Commit only the throttle counters before password validation so repeated failed logins remain limited.
- **Frontend browser timing:** the first browser check checked the table list before its reload completed. Updated the check to await the actual rendered row; verified persistent creation and both restaurant sessions.
- **CSS compatibility warning:** replaced `align-items: end` with `flex-end`; subsequent Docker build completed without that warning.

## Remaining limitations and technical debt

- The legacy database administrator password is weak and coincides with a common project label. It was deliberately preserved because the approved plan forbids rotating that existing account. The API now uses a separate generated runtime password; no administrative credential assignment/file was added to Git or passed to the API. Treat reviewed administrator credential rotation and recovery/backup planning as required before public/pilot use. A plain substring scan flags ordinary project text for that legacy value; this is distinct from an embedded credential assignment, but it confirms the old password is guessable. New generated runtime/demo/test secrets were checked against Git-eligible files and were absent.
- This is a tested local authentication/tenancy foundation, not an independently reviewed production release. Production TLS, secret storage/rotation, deployment hardening, non-root application images, monitoring, account recovery, admin MFA, email verification, and external security review remain open. There is no public signup or support override.
- npm still reports the previously identified PostCSS/Next.js and ESLint/minimatch dependency findings. npm suggests a major Next.js upgrade for part of the graph; it was not approved/applied. A compatible upstream update or narrowly reviewed/tested override needs separate maintenance approval before public/pilot exposure. No `npm audit fix --force` was run.
- `next lint` is deprecated. Starlette emits a TestClient/httpx deprecation warning; no unapproved `httpx2` installation was performed. Python dependencies/base images are not fully locked, and host/Docker versions differ. `pip check` checks dependency compatibility, not known security advisories; a complete Python vulnerability scan was not performed.
- Login peer throttling sees the fixed proxy's network peer, without trusting arbitrary forwarded client-IP headers. This is deliberately conservative for local development; production proxy/IP attribution, distributed limits, abuse recovery, capacity, and denial-of-service testing need review. Throttling records and expired/revoked sessions have no retention-cleanup job yet.
- RLS trusts server-established identity and deliberately privileged administrative helper owners. It does not prevent all damage if administrator/service credentials or the application are compromised. Helper functions and policies need continued review when adding entities/routes. Broader concurrency/load/fuzz testing and an external penetration test were not performed.
- Frontend TypeScript contracts are maintained manually. The shared contracts directory still has no generated executable package. Browser coverage is a local Edge smoke test, not a full browser/device/accessibility matrix. Metadata labels/addresses are ordinary user text; external exports or embedding need their own safety review.
- Readiness validates the restricted database connection and installed security functions; full operational metrics/monitoring and public deployment remain later work. Demo mode only controls the public synthetic demo route; it does not automatically seed data or create real monitoring.
- No real camera, video, detector, device enrollment/sync, task workflow, live floor map, analytics, billing, accuracy metrics, hardware compatibility, or privacy/legal compliance has been implemented or verified in this phase. Existing reference footage was not processed.

## Acceptance mapping and summary

| Requirement | Evidence |
| --- | --- |
| P2-01 | Revisions 0001/0002, sentinel preservation, model consistency, polygon/foreign-key tests |
| P2-02 | Repeatable private synthetic seed; two persisted restaurants with separate users/locations/cameras/tables/zones |
| P2-03 | Session, expiry, revocation, user/membership status, cookie and CSRF tests |
| P2-04 | Both-direction scoped-route tests, real-ID/nested-ID cases, direct SQL policies, running-stack/browser checks |
| P2-05 | Strict body schemas, immutable ownership, composite references, foreign grant and role-escalation tests |
| P2-06 | Explicit grants, restricted same-organization location tests, multi-location owner and multi-organization user tests |
| P2-07 | Approved role matrix and positive/negative route tests; no blanket platform access |
| P2-08 | Atomic protected audit writes/reads, explicit permission-change details, safe UTC data and rollback tests |
| P2-09 | Typed OpenAPI, session-cookie security metadata, consistent safe errors, no input echo |
| P2-10 | Original four starter tests retained/passed; health/demo/landing page preserved; lint/types/build pass |
| P2-11 | All tested negative cases blocked in the final real-PostgreSQL run; limitations reported above |
| P2-12 | This explanation, phase index, affected previous/current docs, and founder-facing explanation; stop for approval |

Phase 2 now provides persistent, separately authorized restaurant workspaces and a working local sign-in/configuration path. It does not yet monitor a dining room. Review this phase and the remaining security-maintenance decisions before approving any next milestone. Phase 3 remains unstarted.

## Pre-Phase 3 review (2026-11-07)

This is a new verification pass requested after Phase 2 completion. The earlier 11.54-second run, seven runtime groups and eight Edge browser groups above remain historical results. They were not silently reused as current evidence. No application source/configuration, package versions, existing migration, or restaurant business record was changed during this review. Only documentation was updated; private verification artifacts stay ignored.

### Fresh commands and outcomes

| Check performed in this review | Actual result |
| --- | --- |
| Required reading/source review | Read AGENTS, master specification, handoff, implementation plan and relevant architecture/API/security/migration/frontend/test code; matched the next milestone to master section 17 |
| Docker initially unavailable | Docker Desktop/WSL distribution were stopped; first isolated-test startup failed safely. Started installed Docker Desktop and used `docker compose start --wait --wait-timeout 60` for the three existing containers; no rebuild, pull, container replacement or volume reset |
| `python scripts/start_phase2_test_db.py` using project `.venv` | Created a separately labeled localhost-only PostgreSQL 16 test container from the cached image, with tmpfs data; no project volume attached |
| `python -m pytest services/api/tests services/edge-agent/tests --import-mode=importlib -q` | **152 passed, 1 warning in 13.05 seconds**; no skipped tests |
| Fresh negative security coverage within that run | All 46 scoped cross-restaurant cases (23 operations in each direction), 23 scoped anonymous cases, five protected identity/discovery cases, and the existing location/role/session/CSRF/direct-SQL/migration-preservation checks passed |
| `python -m ruff check services/api services/edge-agent scripts` | Passed without changing files |
| `python -m pip check` | No broken requirements; this is dependency compatibility, not a vulnerability audit |
| `npm run lint`; local `tsc.cmd --noEmit`; `npm run build` in `apps/web` | All passed using installed packages; Next.js 15.5.29 production build completed. Existing `next lint` deprecation remains |
| `npm audit --json` | Completed with exit 1 because findings remain: **8 affected packages, 1 high and 7 moderate; zero critical**. No dependency fixes/overrides applied |
| Compose/read-only runtime | `docker compose config --quiet` passed. Existing DB and API healthy; web HTTP responds (it has no configured Docker healthcheck). All three published ports remain bound to 127.0.0.1 |
| HTTP checks | `/health`, `/ready`, `/v1/demo/tenant`, landing page, sign-in and settings HTML all return 200. HTML 200 alone is not proof of authenticated UI behavior |
| Authenticated running-stack review through Next.js | Six groups passed: anonymous denial; three synthetic logins/cookie/scoped identity; A/B own reads with foreign reads blocked both ways; permitted configuration/audit reads with no-store; staff audit/location denial; logout/revocation for every review session |
| Running API source | All nine package Python source files match the existing API image byte-for-byte |
| Migration/model/catalog consistency | Disposable test and existing development databases both at `0002`; Alembic model comparison reports zero differences in the isolated database. Read-only development catalog checks confirm eight RLS-enabled tenant tables and no superuser/BYPASSRLS/create-database/create-role flags on the application login |
| Git/sensitive data | Final staged-blob scan covered all 76 indexed files, compared 24 generated/private secret values, found no actionable assignment/key/token/URL/private-value matches, and passed 13 ignore probes. The 54 changed files match the [checkpoint manifest](../PHASE_02_CHECKPOINT.md); zero deletions, unstaged changes or eligible untracked files. The weak legacy common-text caveat in the manifest still applies |
| Documentation and preservation | All 73 relative document links/anchors and `git diff --cached --check` pass. All 43 files from the original checkpoint still exist; only five existing documentation files and two new documentation files changed during this review. Source/configuration hashes, original master/blueprint, Git configuration and HEAD are unchanged |

Login/logout verification necessarily creates/updates authentication session and throttling records. It did not create/edit restaurant tables, locations, cameras, memberships or grants. The two existing runtime/browser scripts were not rerun because they deliberately create synthetic business records. Their prior browser interaction results remain historical; a new interactive browser flow, clean-machine setup, hosted CI, production deployment and external penetration test were not performed here.

The unchanged original DB container is `88e44ea5a3bd`, using `restaurent_startup_postgres_data`. Existing API/web containers were started, not replaced. The isolated test instance is removed only after verifying its test label, tmpfs storage and absence of the application volume; the original three services and data volume are preserved.

### Findings, proposed checkpoint and next gate

The existing Phase 2 security/functional suite still passes. This supports the local authentication/configuration milestone; it does not establish production readiness. The weak legacy administrator password, npm findings, deprecations, dependency locking/advisory-scan gap, proxy-IP throttling limitations, production identity/TLS/secret operations and broader concurrency/browser testing remain open as described above. A source-pattern hit in a camera rejection test was reviewed: it constructs an invalid URL with a fresh runtime-generated synthetic secret and verifies no echo; it embeds no real camera password.

The local Phase 2 commit is **prepared for approval, not created**. Branch remains `main`, with existing Phase 1 HEAD `6808a81b7339f241701eb03552d952827872f168`. The [checkpoint manifest](../PHASE_02_CHECKPOINT.md) gives the complete staged file set and proposed commit message. Commit only after the founder explicitly approves; do not push or change a remote.

The [detailed Phase 3 proposal](../PHASE_03_IMPLEMENTATION_PLAN.md) records exact requirements, technologies, transitions/roles, safe additive data changes, SSE/proxy/revocation design, security/dependency gates, implementation steps and acceptance criteria. It is documentation only. No dashboard simulation, task/event schema, stream route, video, or later-phase functionality was implemented. Stop for founder approval.
