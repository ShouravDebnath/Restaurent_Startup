# Threat Model

**Status:** Phase 0 threat-model baseline with Phase 2 authentication/tenancy controls implemented and tested locally; later controls remain requirements.
**Scope:** MVP edge agent, cloud API, dashboard, database, and authorized restaurant video inputs.

This is not a completed external security assessment. Phase 2 implements local Argon2id/server sessions, exact-origin/CSRF controls, persistent login throttling, explicit role/location authorization, restricted PostgreSQL runtime access, RLS, immutable ownership/composite references, safe errors/metadata, and protected atomic audits. Real PostgreSQL tests verify both HTTP and direct database boundaries. See [PHASE_02.md](phase_explanations/PHASE_02.md) for actual results and limits. Public synthetic/health routes contain no customer database rows. Device/video security, production TLS/secret storage, MFA/recovery, external review, and most operational controls remain unverified or later work. No real customer/camera onboarding is approved on this basis.

The current npm audit still reports 8 affected entries (1 high, 7 moderate). No dependency upgrade or forced fix was applied. RLS relies on server-established identity and deliberately privileged migration/helper owners; it is not a defense against every application or administrator compromise. Retention cleanup, trusted proxy IP/rate-limit policy, load/concurrency/abuse testing, and non-root production images remain hardening work.

The existing database administrator password is weak and remains unchanged under the explicit preservation rule. The API uses a separate generated restricted credential. Administrator credential rotation requires a reviewed, separately authorized procedure before public/pilot use; do not publish the existing local database configuration.

## Assets

- Tenant identity, memberships, roles, and organization data.
- Table state history, staff tasks, audit records, and analytics.
- Edge device credentials and camera source references.
- Camera video and calibration polygons.
- Availability and health signals used for operational decisions.
- Database backups, logs, exports, and optional diagnostics.

## Trust boundaries

1. Restaurant LAN and camera/NVR to edge agent.
2. Edge agent to cloud over outbound authenticated TLS.
3. Browser to API and SSE stream.
4. API service to PostgreSQL.
5. Company support/admin users to tenant data.
6. Demo data versus customer data.

The browser is never trusted to enforce tenant or role boundaries. The edge payload is never trusted to choose its organization or location. Raw video is not trusted to prove cleanliness or service completion.

## Main threats and controls

| Threat | Control | Verification |
| --- | --- | --- |
| Cross-tenant record disclosure | Central authorization dependency, explicit location checks, direct tenant IDs, negative tests | Integration tests with guessed IDs and altered bodies |
| Device impersonation or reassignment | Separate device credentials, pairing table, revocation, server-side location mapping | Revoked and wrong-location event tests |
| Camera credential leakage | Encrypted local secret store, redacted logs, no browser response field | Log scan and API response tests |
| Public CCTV exposure | Edge initiates outbound connections; no inbound camera port requirement | Deployment and network review |
| Event replay or duplicate task creation | Unique event ID, idempotent transaction, bounded event age policy | Duplicate and out-of-order tests |
| Stale camera implies availability | Health threshold forces UNKNOWN and stops availability implication | Camera interruption test |
| Malicious or malformed event batch | Typed schema, size/rate limits, state transition validation, audit logging | Validation and fuzz/property tests |
| Session theft or privilege escalation | Mature identity/session mechanism, secure cookies, MFA for admins where available, role checks | Auth integration tests and review |
| Overexposure through exports/SSE | Same authorization as normal routes; scoped query and stream | Cross-tenant export/stream tests |
| Privacy harm from video retention | Local inference by default, no cloud raw video, explicit diagnostic policy | Network capture and retention test |
| Incorrect AI claim | UNKNOWN and REVIEW paths, staff confirmation for ready, confidence labels | State-machine tests and UI review |
| Supply-chain/model license violation | Pin dependencies, record model and weight licenses, human approval gate | Dependency/license review before pilot |
| Unsafe admin/support access | No default video access, time-limited audited support access | Audit log and permission tests |

## Abuse cases

- A user modifies `organization_id`, `location_id`, `table_id`, or an action body to target another tenant.
- A revoked edge device replays an old valid event.
- A device claims a table from a different location.
- A stale stream causes an old AVAILABLE observation to remain visible as current.
- A duplicate departure creates multiple open cleaning tasks.
- A diagnostic upload silently becomes default video storage.
- A model or weight is used commercially without license approval.
- Logs or frontend payloads expose RTSP passwords.

## Privacy requirements

Do not implement facial identification, audio recording, emotion inference, covert employee scoring, or identity matching. Use authorized footage only. Provide customer notice, retention/deletion policy, access control, and legal review before pilots. Store metrics and transitions rather than raw detections where possible.

## Security gates before pilot

- All tenant and role authorization tests pass.
- Device revocation and wrong-location tests pass.
- TLS, secret handling, log redaction, backup access, and retention are reviewed.
- Network verification confirms no raw video leaves the edge by default.
- Dependency/model licenses are documented.
- Incident contact, credential rotation, and restore procedures are documented.
- Legal review covers CCTV, employment/privacy notices, contracts, and cross-border access.

This document is a design baseline, not a certification or legal opinion.
