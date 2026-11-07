# Phase 2 architecture proposal

**Date:** 2026-11-07 (Asia/Dhaka).
**Status:** Approved by the founder in both decision replies on 2026-11-07; implemented with local verification in [PHASE_02.md](phase_explanations/PHASE_02.md).
**Authority:** [MASTER_SPEC.md](MASTER_SPEC.md), [AGENTS.md](../AGENTS.md), and the [Phase 2 acceptance checklist](CODEX_HANDOFF.md#9-phase-2-requirements-and-acceptance-criteria).

The founder authorized Phase 2, then explicitly approved both recommended choices, the scoped dependency installation, and the database/test/backup/application-rebuild execution plan before implementation. The alternatives and conditional wording below preserve the proposal as reviewed. Current implementation evidence and limitations are in the phase explanation; the pre-implementation baseline below is historical.

## 1. Current evidence

The repository was clean on branch `main` at checkpoint `6808a81b7339f241701eb03552d952827872f168` before this proposal. The five requested project documents and the current API, migration scaffolding, web app, dependency declarations, and Compose configuration were inspected.

Fresh checks on November 7:

| Check | Actual result |
| --- | --- |
| Existing Compose containers | Database and API running and healthy; web running |
| Existing API `/health` and `/v1/demo/tenant` | HTTP 200; demo explicitly synthetic |
| Existing web root | HTTP 200 |
| Read-only PostgreSQL inspection | Transaction read-only confirmed; only `public.alembic_version`, with zero rows |
| Existing database login | Superuser and `BYPASSRLS`; unsuitable for an application relying on RLS |
| API and edge starter tests together | 4 passed, 1 existing TestClient/httpx deprecation warning |
| Ruff for both Python services | Passed |
| Web TypeScript and lint | Passed; existing `next lint` command deprecation notice remains |

Commands included `docker compose ps --format json`, project `.venv` Python running `pytest services/api/tests services/edge-agent/tests --import-mode=importlib -q`, `ruff check services/api services/edge-agent`, the installed TypeScript compiler with `--noEmit`, and `npm run lint` in `apps/web`. HTTP checks and database inspection used Python; credentials were read privately and not printed. A fresh web production build was not run during this architecture review. No schema, application code, containers, or database contents were changed.

The existing routes do not use PostgreSQL, and no authentication or tenant isolation currently exists. Passing these starter checks is a baseline, not evidence of Phase 2 security.

## 2. Authentication choice

| Option | Benefit | Cost or limitation |
| --- | --- | --- |
| **Recommended for this local Phase 2: application-managed passwords and server-side sessions** | Runs locally without an external identity account; immediate revocation and direct automated tests | We must implement and maintain session, password, throttling, and CSRF controls; no managed MFA, verified email, or account-recovery service |
| Managed OpenID Connect identity provider | Provider can supply account recovery, MFA, and identity lifecycle features | Founder must choose and configure a provider; requires an external service and an additional integration/dependency decision |

The recommendation is a Phase 2 foundation for local development. It is not approval to onboard real customers or deploy publicly. A managed provider remains a possible later approved change; it would use provider subject identifiers while retaining our own tenant permissions.

If the recommended option is approved:

- Hash passwords with Argon2id through the maintained `argon2-cffi` library, with explicit parameters meeting OWASP guidance. Never store or log plaintext passwords. Accept long passphrases, reject oversized inputs, and use generic login errors and persistent login throttling.
- Generate unpredictable opaque session tokens. Store only a digest of each session token in PostgreSQL, with user, creation/last-use times, idle expiry, absolute expiry, and revocation information. Proposed defaults: 30-minute idle expiry and 8-hour absolute expiry. Recheck user and membership status on protected requests.
- Use a host-only, `HttpOnly`, explicitly `SameSite` session cookie. Require `Secure` cookies with HTTPS outside explicitly configured local development. Do not expose the session token to frontend JavaScript or store it in browser local storage.
- Protect login and authenticated mutations against CSRF with an explicit allowed-origin check and a session-bound CSRF token for authenticated changes. Cookie attributes alone are insufficient. Logout revokes the server session and clears the cookie; login rotates any previous session.
- Use a fixed Next.js server proxy for the browser's same-origin `/api/...` requests. The proxy talks to the configured FastAPI service, forwards the necessary cookies/CSRF information, and does not accept an arbitrary upstream URL. FastAPI remains responsible for authentication and permissions; it does not trust a user ID or role supplied by the browser or proxy headers.
- Provision local/demo accounts through an explicit administrator command. Generate demo passwords at execution time and write them only to an ignored private file. No default passwords in source, documentation, logs, or fixtures. No public signup, password reset, email verification, or MFA is included in this choice; these limitations must remain visible.

**Installation approval requested:** add `argon2-cffi>=25.1,<26` and its required dependencies to the API project, install them in this project's `.venv`, and include them in the rebuilt API image. They are currently absent. The Python 3.14-compatible library is MIT licensed. Existing time-zone data is available locally; declare `tzdata` for Windows portability if needed by the implementation. No global installation, npm upgrade, or unrelated dependency change is proposed.

## 3. Database-isolation choice

| Option | Benefit | Cost or limitation |
| --- | --- | --- |
| **Recommended: shared PostgreSQL schema, centralized API permissions, and PostgreSQL row-level security (RLS)** | API checks permissions, while the database also restricts tenant rows; constraints protect relationships | More migration/role setup and direct database tests; requires a restricted runtime database login |
| Shared schema with API permissions and constraints only | Simpler setup and fewer database policies | An omitted API query filter can expose tenant data; lacks the additional database row barrier |

RLS means that PostgreSQL itself filters which records an application transaction may read or change. It complements role/action checks in FastAPI. It does not replace those checks or defend against every form of application compromise.

If the recommended option is approved:

- Keep the existing PostgreSQL 16 instance and volume. Use a restricted, non-owner runtime login without superuser, `BYPASSRLS`, role-creation, schema-creation, or migration privileges. Keep administrative/migration credentials outside the running API container.
- Make administrative role provisioning an explicit command, not an action available through the browser. Store generated local runtime credentials only in ignored private configuration. Do not rotate or delete the existing database administrator account or data.
- Apply deny-by-default RLS to tenant-scoped records. Establish authenticated identity and authorized organization/location context per transaction, using transaction-local settings so pooled connections do not retain another request's scope. Missing or invalid context must fail closed.
- Derive context from verified sessions and database memberships/grants. Request IDs select a resource to authorize; they never establish permission by themselves. Check enabled memberships and explicit location grants, and cover both existing-row visibility and new/changed-row ownership in policies.
- Keep identity/password/session storage separate from tenant resource access. Use narrowly scoped authentication lookups and deliberately scoped membership/grant access so authentication can occur without opening all tenant rows. Any privileged helper must have a fixed search path, minimal privileges, and dedicated tests.
- Put organization and location ownership on relevant rows and use composite foreign keys/unique constraints to reject foreign camera/table/zone relationships. Resource update schemas cannot reparent records to another tenant/location.
- Audit successful sensitive mutations in the same transaction. Restrict audit reads and disallow API modification or deletion of audit history. Store safe structured details, never raw request bodies, passwords, session tokens, or camera credentials.
- Test with the actual restricted application login, not only the administrative login. Verify both HTTP access prevention and direct SQL behavior, including a deliberately missing application tenant filter and reuse of pooled connections.

PostgreSQL explicitly documents that superusers and `BYPASSRLS` roles bypass RLS. Simply adding policies while keeping the current application login would not provide the intended protection.

## 4. Roles and explicit location grants

Use one enabled membership per user/organization, with a constrained role value and separate explicit location grants. A user can belong to several organizations. No role implies permission to another organization. Organization administration and permission to read location resources are distinct.

| Role | Organization administration | Resources at explicitly granted locations |
| --- | --- | --- |
| Owner | Organization settings, location creation, memberships and grants; ownership changes require owner authority | Read and configure tables, cameras, and zones; read permitted audits |
| Organization admin | Organization settings, location creation, non-owner memberships and grants; cannot promote to owner or change owners | Same location configuration rights as owner |
| Manager | No membership/role/grant management | Read resources and configure tables, cameras, and zones; read location audits |
| Floor staff | No administration | Read necessary location/table configuration; no configuration or audit changes |
| Installer | No membership/role/grant management | Read necessary configuration; configure camera metadata and table zones; cannot manage staff or grant permissions |

Location creation explicitly grants the creator access to the new location. Owners/admins may deliberately assign location grants within their organization, including their own, and those changes are audited. They do not automatically read every location merely because they have an administrative role. Lower roles cannot change memberships or grants. Prevent removal/demotion of the last enabled owner.

Platform/support accounts receive no blanket tenant access. A separate support-access workflow is outside Phase 2. Human sessions are separate from future edge-device credentials.

## 5. Schema and phase boundary

Create SQLAlchemy models and additive Alembic revisions for:

- Organizations: ID, name, plan metadata, creation time. Plan metadata does not activate billing.
- Locations: organization ownership, name, validated IANA time zone, optional address.
- Users and local identity credentials: normalized unique email, display name, enabled status, credential hash, optional future provider subject.
- Memberships and explicit location grants: user/organization, constrained role, enabled status, relationships that cannot cross organizations.
- Authentication sessions and login-throttling records needed for the approved session mechanism.
- Camera metadata: location ownership, label, safe opaque local source reference, and clearly unconfigured status. Do not accept camera passwords or credential-bearing URLs, connect streams, or claim a camera is online without evidence.
- Tables: location ownership, label, optional seats, canonical six-state vocabulary, UTC state-entry time. New tables start `UNKNOWN`; configuration APIs cannot fabricate `AVAILABLE` or implement workflow transitions.
- Table zones: table/camera ownership, normalized 0-1 polygon, calibration revision, source resolution; reject mismatched locations and invalid geometry. This is a data/configuration API, not the later video drawing tool.
- Audit records: actor, organization, optional location scope, action, UTC timestamp, allowlisted details.

**Proposed reconciliation with the master schema:** defer edge-device, event-history, and staff-task tables to their respective later migrations. Cameras will not have a fictional device association now; add the actual device foreign key with device enrollment later. Document this as a deliberate Phase 2 scope decision. No ingestion, video processing, workflow actions, SSE, analytics, billing, or state engine is included.

## 6. API and frontend integration

Provide typed `/v1` APIs for session entry/logout/CSRF, `/me`, authorized organization/location discovery and configuration, owner/admin membership and location-grant management, table configuration, camera metadata, table-zone configuration, and protected audit reads. Scope every implemented list/read/create/update route and test it. Account provisioning remains an explicit local administrator command rather than public signup.

Use strict request models, consistent safe error envelopes, UTC responses, validated IANA zones, and bounded audit pagination. Return 401 for missing/invalid sessions, 403 for insufficient actions within a visible scope, and indistinguishable 404 responses for inaccessible or nonexistent resource IDs. Reject altered ownership fields, foreign nested IDs, self-promotion, and stale zone revisions. Do not expose credential/hash/session fields through API models or generated examples. Resource deletion endpoints are not needed for this milestone; disable memberships or sessions where appropriate.

Add a minimal sign-in/sign-out flow, an authorized organization/location selector, and protected configuration screens for the Phase 2 entities. All data must come through the real API and persist in PostgreSQL. UI visibility is a convenience, not an authorization boundary. Keep the Phase 1 synthetic demo and health behavior available and clearly labeled. The interactive floor, state timers, staff tasks, and simulated workflow dashboard belong to Phase 3.

## 7. Migration, runtime, and test execution

Approval of the recommended database option would authorize the following concrete operations:

1. Build and review additive Alembic migrations, role provisioning, and synthetic seeding commands. Do not use `drop_all`, resets, volume removal, destructive downgrades, or automatic production seeding.
2. Start a separate disposable PostgreSQL test container using the already installed PostgreSQL 16 image, with no mount of the existing database volume. All test initialization and teardown must be limited to that explicitly identified synthetic test instance.
3. Verify migrations from an empty test database and preservation of preexisting sentinel data in that test instance. Test upgrading twice and seeding twice. Stop if unexpected existing schema/data conflicts appear.
4. Run real PostgreSQL-backed authentication, permission, constraint, audit, and session tests; extend CI to exercise PostgreSQL rather than silently substituting SQLite.
5. Back up the existing development database to an ignored private location, then apply only the verified additive revisions and explicit synthetic seed. Preserve all preexisting records and the original volume. Do not print credentials or backup contents.
6. Rebuild/recreate the API and web containers for the approved Phase 2 changes, using existing project software and the approved project dependencies. Keep ports local-only and retain PostgreSQL data. A brief application interruption is expected.
7. Test through the running frontend/API/database path, rerun existing API/edge tests and affected lint/type/build checks, and record exact results and limitations.

Security tests must cover every protected resource route with Restaurant A/B users, same-organization users with different location grants, all roles, guessed IDs, altered bodies, foreign relationships, inactive memberships/users, expired/revoked/invalid sessions, CSRF, login throttling, cookie settings, tenant-scoped audits, and rejected secret-bearing camera references. Include positive authorized cases so a system that rejects everything cannot pass. Test permission revocation on an existing session and database context cleanup between requests.

At phase completion, write the full [required phase explanation](../AGENTS.md#phase-documentation-rule) in `phase_explanations/PHASE_02.md`, update the index and affected handoff/architecture/API/Phase 1 documentation, preserve historical results, and map actual evidence to P2-01 through P2-12. Stop after Phase 2 for founder approval. No new Git commit or remote operation is implied by this proposal.

## 8. Remaining limits and sources

Neither choice resolves the previously reported npm vulnerabilities automatically. No breaking upgrade or `npm audit fix --force` is authorized. Public deployment, real restaurant onboarding, production TLS, administrator MFA/account recovery, external security review, and later camera/device controls remain separate gates. We must not describe local passing tests as a production security certification.

Primary guidance consulted for the proposed controls:

- [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html): Argon2id and work factors.
- [argon2-cffi usage](https://argon2-cffi.readthedocs.io/en/stable/howto.html) and [package metadata](https://pypi.org/project/argon2-cffi/): maintained password hashing, Python compatibility, license, and installation scope.
- [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html): cookie attributes, session lifecycle, and token protection.
- [OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html): explicit CSRF defenses for cookie authentication.
- [OWASP authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html): least privilege, deny by default, and checks on every request.
- [PostgreSQL row-security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html): policy behavior and superuser/owner bypass. The project remains on PostgreSQL 16; this proposal does not upgrade it.

These sources informed the recommendation. The founder approved the proposed session lifetimes, role matrix, schema boundary, and local execution plan. Implementation uses verified transaction-local user identity and derives each row's organization/location permission through enabled memberships and explicit grants, alongside API scope filters. No external identity provider, later-phase device/task/event schema, or public deployment was authorized.
