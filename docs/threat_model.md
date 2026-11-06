# Threat Model

**Status:** Phase 0 threat-model baseline; controls below are implementation requirements.
**Scope:** MVP edge agent, cloud API, dashboard, database, and authorized restaurant video inputs.

This document describes target protections and future verification, not a completed security assessment. Current source has public synthetic/health routes and foundation code; authentication, tenant/location enforcement, device security, and most operational controls are not implemented. No customer data or real cameras should be onboarded on this basis. See [CODEX_HANDOFF.md](CODEX_HANDOFF.md#7-dependency-findings-technical-debt-and-security-risks) for dated dependency findings, existing risks, and verification limits.

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
