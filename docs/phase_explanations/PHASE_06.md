# Phase 6: secure, durable communication from the restaurant computer

> **Phase 7 compatibility — 2026-11-12:** Approved [Phase 7](PHASE_07.md) extends the existing dashboard and signed transport with opt-in human-reviewed workflow, compatible v2 metadata and reports. It preserves the original DEMO/v1 contracts, manual precedence, session deadlines and synthetic-only AI limitations. Phase 7 verification passes 636 tests and ten browser groups; separately approved additive `0009` and matching local services are active. Original records, credentials and calibrations are preserved, and existing locations remain OFF. Earlier phase-specific test/status statements below are historical.

**Publication and next planning step - 2026-11-11:** After separate founder approvals, the 68-file checkpoint was committed and pushed as `fd983c7a656ab36f031db2900ef15a3da1362cbe`; independent GitHub lookup matched local and tracking `main`, with a clean tree. Secrets were excluded and files/data preserved. The [Phase 7 proposal](../PHASE_07_IMPLEMENTATION_PLAN.md) is documentation only; the 529-test and six-browser-group results below are retained Phase 6 evidence, not newly run planning checks. Earlier pending commit/push wording is the pre-publication snapshot. No Phase 7 implementation or public/pilot activation is included.

**Git checkpoint preparation - 2026-11-11:** [The 68-file checkpoint review](../PHASE_06_CHECKPOINT.md) records the exact candidate manifest, sensitive-file exclusions and previously completed verification below. This preparation changes documentation and the Git index only; commit and push require separate approvals. No application, dependency or database change is included in checkpoint preparation.

The checkpoint's explicit strict staged whitespace review reports 119 cosmetic
trailing-space findings in the frozen generated `0007` SQL and intentional
Markdown line breaks. The earlier CRLF-aware review below did not report these;
it must not be read as a stricter staged check. The exact applied migration is
preserved and these findings are disclosed in the checkpoint review.

**Implemented:** 2026-11-08. **Reverified:** 2026-11-11. **Scope:** local development and synthetic video only.
**Status:** Implemented and verified for local development and synthetic transport:
**529 tests passed**, plus six real browser checks in the resumed verification. Both additive migrations were
separately approved and applied. The separately approved commit/push is recorded
above; public deployment and Phase 7 implementation remain unauthorized. Final results below must be read with their
stated scope; historical failures are retained.

## Overview and objectives

The restaurant computer is called the **edge device**. It reads video and runs
the detector locally. The backend supplies accounts and the shared dashboard.
This phase connects them without sending customer video to the backend.

The exact master requirement is an SQLite outbox before transmission, pairing to
one location, authenticated TLS batches, server-side location checks, duplicate
protection, retries and restart replay, heartbeat/offline UI, and tests for a
15-minute outage, ordering and revoked credentials. See the approved
[implementation plan](../PHASE_06_IMPLEMENTATION_PLAN.md) and
[master specification](../MASTER_SPEC.md#phase-6---reliable-edge-to-cloud-synchronization).

For example, event E17 means a local engine produced a possible table transition.
The computer saves E17 first, then sends it. If the response disappears, it sends
the same E17 again with a new signed request. The backend keeps one receipt and
does not repeat its effects. Delivery reliability does not prove that the AI saw
the table correctly.

## Implemented components

### Device identity, pairing and separate permissions

Each device generates an Ed25519 private key in the current Windows user's
Credential Locker. Its JSON identity file contains only the public key, key ID
and full SHA-256 fingerprint. There is no plaintext key fallback. Other operating
systems and unattended service accounts are not verified key-storage targets.

Pairing starts with a ten-minute public challenge. The device proves possession
of its key. A manager/admin with an explicit location grant compares the complete
64-character fingerprint and approves it. The approved identity belongs to one
organization and location; it cannot submit another location in a batch.

The settings page supports approval, reviewed camera/table bindings, separate
processing enable/disable, key rotation and device revocation. Rotation requires
a proved new fingerprint, retains the same device and queue identities, and gives
the old key at most ten minutes of overlap. Keys expire after 90 days. Revocation
and ingestion serialize on the device row, so a request after committed
revocation cannot apply an effect.

Pairing does **not** grant human camera preview. Phase 4 preview consent, human
session deadlines and its fail-closed local companion remain separate.

### Signed HTTPS transport

The device client uses one fixed HTTPS origin, certificate/hostname verification,
no redirects or environment proxies, bounded timeouts and response sizes, and no
human password/cookie. Machine endpoints are refused by the browser proxy.

RFC 9421 signatures cover method, authority, exact target URI, content type,
content digest and key ID. The reviewed library verifies the digest of the exact
received bytes. Requests carry creation/expiry times, a nonce and the application
tag. The backend checks signatures before returning receipt information, persists
nonce uniqueness, rejects replay, and rechecks device status under its lock.

Requests have at most a two-minute signature lifetime and bounded clock skew.
Messages are limited to 128 KiB and 100 events; JSON duplicate keys, nonfinite
numbers, ambiguous headers, compression and unknown fields are refused. Camera
URLs, pixels, bounding boxes, private keys and arbitrary diagnostic text have no
place in the event contract. Signed metadata is still untrusted AI evidence.

Pairing is bounded per peer and globally; authenticated request nonces bound
device request rates. These controls do not replace a future public reverse
proxy, deployment review or external penetration test.

### Durable queue and processing checkpoint

Python's built-in SQLite stores immutable event bytes, UUIDs, stream sequence,
payload hashes, retry schedules, acknowledgements and a local engine checkpoint.
The queue uses rollback-journal **DELETE** mode and **synchronous=EXTRA**, verified
by reading the settings back. EXTRA requests the strongest rollback-journal sync
behavior available here; it is not a guarantee against faulty storage hardware.

One process/thread owns a queue. An OS file lock rejects a second owner. A cloned
state engine proposes a transition; the queue commits the event and checkpoint
together before that candidate becomes visible. A full disk, corrupt database,
wrong device identity or failed commit pauses processing rather than discarding
pending events. Queue limits are 100,000 pending events, 256 MiB of database pages
and a 16 MiB free-space reserve.

Retries preserve event IDs/content and use a fresh request nonce/signature.
Backoff starts at roughly two seconds, grows exponentially and is capped with
jitter. The entire acknowledgement must match IDs, sequences and hashes before
local status changes. Rejected entries are retained for review. Delivered rows
are retained too; automatic compaction/retention is not implemented.

After restart, the queue survives but processing evidence is rebuilt. A saved
checkpoint is not treated as fresh camera evidence, and a saved file cannot
restore permission. `device-sync` can deliver a saved queue without opening video.

### Offline processing lease

A manager must approve the synthetic source's camera, table zones, seating-profile
revision/digest and model digest, then separately enable processing. An online
heartbeat issues a one-hour development lease. The running process uses monotonic
time and an independent local guard so a blocked sender cannot keep capture/
inference alive after expiry. Clock reversal fails closed. Every process restart
requires fresh online authorization before capture opens.

During an outage within that lease, local shadow inference can use the last
protected manual snapshot. That snapshot is not claimed to include staff actions
made while disconnected. Reconnection checks configuration and newer human
revisions; changed policy/geometry cannot silently become live evidence.

An offline device cannot receive immediate revocation. Its local processing can
continue until its remaining lease expires. The server rejects revoked delivery
immediately after revocation commits. This one-hour local-development tradeoff is
approved; it is not pilot/public deployment approval.

### Backend receipts, ordering and human precedence

Additive migration `0007` creates eleven metadata tables and controlled
database functions. Nine public tables hold devices, public keys, assignments,
table bindings, receipts, shadow estimates, health, machine audits and location
notifications. Two private tables hold pairing challenges and replay nonces.
No video, camera password or device private key is stored there.

Separately approved `0008` adds two shadow-context fields and the terminal
rejection behavior required by the plan. A valid owned envelope with unsupported
version/type/state receives an explicit rejection receipt containing safe identity
and hash information only. The affected shadow becomes UNKNOWN. Events from that
same context stay history until fresh generation/context arrives. Malformed JSON,
missing identity fields and unknown/private fields still refuse the whole batch.

Composite foreign keys and row-level security enforce organization/location
scope. The application login has read-only table privileges for the new metadata;
controlled functions perform writes. It cannot read the private pairing schema or
call the internal publication/fixture helpers directly. Machine requests establish
a separately verified transaction-local device context, never a fake human user.

The resumed database check also compares the installed ingestion function with
the reviewed `0008` SQL body. RLS is enabled on all nine new public tables.
`FORCE ROW LEVEL SECURITY` is not enabled: database owners and superusers can
bypass these policies. The runtime login must remain a non-owner, non-superuser
without BYPASSRLS; direct-write/private-schema denial and cross-tenant tests
verify that application boundary. These rules do not protect against a
compromised database administrator.

One active device owns a camera, and one active primary binding owns a table.
Manager configuration changes advance epochs/revisions. Retired bindings and old
receipts remain history. Initial limits are four configured cameras and 64 table
bindings per device; the actual runner supports **one active camera at a time**.

The backend stores out-of-order events but advances only a contiguous stream
cursor. Gaps are bounded to 1,000 events. A reused UUID with different content or a
reused sequence with another event is rejected. Old observations, changed
configuration and newer staff decisions remain history rather than moving the
current shadow estimate backward. Currentness uses a 30-second event threshold.

`AI_SHADOW` never modifies operational tables or creates staff tasks. The separate
`SYNTHETIC_WORKFLOW_TEST` adapter additionally requires DEMO mode, a synthetic
location, an approved fixture device/binding, fixed fixture events **and an
explicitly named isolated test database**. It cannot run in the business database.
It proves one actual reset task after a synthetic arrival/departure and repeated
delivery, without going through browser DEMO controls or impersonating staff.
Cleaning, manager blocks and newer manual confirmations retain precedence.

### Health and dashboard

Heartbeats report only allowlisted camera/inference health, queue count, frame
age, inference time and memory. Device contact is different from browser contact.
A server-clock monitor publishes an offline notification after 45 seconds without
device contact. Unknown, disconnected, stopped and degraded information is shown
explicitly. Old shadow estimates display UNKNOWN/stale.

Device notifications and table events share the location's durable revision
counter. SSE reads both in order, with the existing authorization/session recheck
on every batch and reconnect. Passive viewing, device heartbeats and SSE do not
extend human idle or absolute session expiry. The dashboard health panel is
separate from the operational floor map; its read is a separate scoped snapshot.

### Implemented API contracts

The original proposal's route names were provisional. The implemented service
combines related operations into a smaller set of strictly validated contracts:

| Method and path | Purpose and permission |
| --- | --- |
| POST `/v1/edge/pairings` | Bounded public bootstrap; a public key and challenge do not grant restaurant access |
| POST `/v1/edge/pairings/proof` | Signed proof of possession of that pairing key |
| POST `/v1/edge/events` | Blueprint event-batch endpoint; active device signature, exact target binding, TLS and tenant checks |
| POST `/v1/edge/batches` | Compatible name for the same event handler and deduplication store |
| POST `/v1/edge/heartbeat` | Signed health update; returns scoped configuration and the finite processing lease |
| GET `/v1/locations/{location_id}/devices` | Human session plus explicit location access; manager-only setup metadata |
| POST `/v1/locations/{location_id}/devices/commands` | Manager/admin plus location grant, CSRF and revision checks; approve, assign, processing, rotate or revoke |
| Existing location `/stream` | Human-authorized live invalidation, with idle and absolute session expiration |

The resumed review added the blueprint `/events` route to the existing protected
handler and changed the sender to use it. `/batches` remains compatible. Requests
must be signed for the exact path used; a signature for one name cannot be moved
to the other. Receipts and duplicate protection are shared across both names.
There is no separate general event-history browser or paginated history endpoint
in this phase. Durable receipts and machine audits exist in PostgreSQL; the
dashboard exposes current health and shadows. A supported history UI/API and
retention tools remain future work.

## Technologies and why they are used

| Technology | Purpose |
| --- | --- |
| Existing Python, OpenCV, ONNX Runtime and RF-DETR Nano | Reuse local synthetic video/CPU inference; no new model download |
| SQLite / Python `sqlite3` | Durable local metadata before a network send |
| Cryptography 50.0.2 | Reviewed Ed25519 primitives and development certificate generation |
| HTTP Message Signatures 3.0.0 / HTTP-SF 1.5.0 | Standard signature/digest and structured-field handling |
| Existing HTTPX | Separate certificate-verified device client |
| Existing FastAPI, PostgreSQL, SQLAlchemy and Alembic | Scoped APIs, receipts, constraints, RLS and additive migrations |
| Existing Next.js, TypeScript and SSE | Manager controls and live health display |
| Windows Credential Locker | Keep the private device key out of files/browser responses |
| Existing Docker and installed Microsoft Edge | Isolated database restart and real browser checks |

The founder separately approved exactly the three new runtime packages in the
[dependency review](../PHASE_06_DEPENDENCY_REVIEW.md). The working environment and
Linux API image pass native signature/digest and dependency checks. Original API
package versions are preserved; there are exactly three additions. No global
install, npm upgrade, new detector weights or new build tool in the working
`.venv` occurred. The API image retains its existing isolated package-build step;
temporary build-backend tooling is not an added runtime distribution.

## Created/modified files and purposes

| Files | What they do |
| --- | --- |
| `packages/contracts/device_protocol.py`, `device_signatures.py` | Canonical bounded metadata and signature contract; identical package mirrors are tested |
| API `edge_protocol.py`, `edge_signatures.py` | Deployable backend copies of those contracts |
| API `edge_models.py`, migrations `0007_edge_schema.py` / `0008_rejected_context.py`, their SQL files | New metadata, constraints, scoped authorization, controlled effects and rejection/context boundary |
| API `edge_routes.py` | Machine pairing/batches/heartbeat and human manager APIs |
| API `edge_tls.py`, `edge_monitor.py` | Local TLS listener and bounded offline notification worker |
| API `database.py`, `main.py`, `settings.py`, `management.py`, migration `env.py`, `workflow.py` | Separate identity context, routers/lifecycle/feature flag, restricted grants, model discovery and ordered SSE |
| API `models.py` | Correct the outdated model-module description |
| Edge `device_identity.py`, `outbox.py`, `device_client.py` | Protected keys, durable storage, signatures, acknowledgements/retry and processing lease |
| Edge `durable_engine.py`, `device_runner.py`, `cli.py` | Commit barrier, separately leased one-camera background processor, pairing/run/sync commands |
| Edge `video_sources.py`, `test_video_pacing.py` | Fix delayed-first-read MP4 catch-up compression; keep original timing assertions |
| Edge `device_protocol.py`, `device_signatures.py` | Deployable edge copies of the shared contracts |
| New `test_device_foundation.py`, `test_device_recovery.py`, API `test_edge_*.py` | Queue, crypto, lease, scope, ordering, native model, real TLS/outage and actual DB restart checks |
| Existing API `test_database_isolation.py`, `test_route_inventory.py` | Expect the new additive head and require negative coverage of every new route |
| Web `dashboard/edge-health.tsx`, `settings/device-permissions.tsx` | Scoped health/shadow display and explicit manager setup controls |
| Web dashboard/settings pages, `preview-permissions.tsx`, proxy route and CSS | Wire new panels, retain separate human preview, block machine proxying and wrap fingerprints on mobile |
| API/edge `pyproject.toml`, approved requirements manifests, API runtime lock/Dockerfile, Compose | Exact approved additions, existing-version preservation and explicit local feature activation |
| `.github/workflows/ci.yml` | Make both project packages available to API/edge integration tests; hosted execution remains unverified and no private model is downloaded |
| `scripts/freeze_phase6_schema.py`, `rehearse_phase6_migration.py`, `prepare_phase6_tls.py`, `verify_phase6_browser.py` | Frozen new DDL, isolated restored-backup rehearsal, private development TLS and actual browser walkthrough |
| This explanation, index, handoff, README, roadmap and Phase 5 follow-up | Current instructions/status and historical evidence |

Private backups, certificates, device identity/queue, runtime setup, benchmark and
test reports remain in ignored `.secrets/`. Browser profiles stay in `.cache/`.
Existing video, model weights, credentials and seating revisions are not added to
Git. No existing files are deleted.

## Step-by-step execution flow

1. Generate a local key and prove the pairing challenge over verified HTTPS.
2. A location manager compares the complete fingerprint and approves the device.
3. The manager binds calibrated tables, a reviewed seating profile and model;
   separately enables synthetic processing.
4. A fresh online heartbeat supplies configuration and the one-hour lease.
5. The runner checks private source/profile/model files against that approval,
   then starts the existing supervised reader and inference worker.
6. Stable shadow transitions pass through the durable engine: SQLite commits
   event + checkpoint, then the candidate state becomes visible locally.
7. The sender signs a bounded batch. PostgreSQL authenticates its key/device,
   rejects replay, saves/deduplicates receipts and reconciles ordered shadows.
8. A durable location notification reaches the authorized browser via SSE.
9. During an outage the queue grows; retries retain original IDs. On reconnection
   the sender receives matching receipts. New staff/configuration decisions win.
10. On lease expiry or shutdown, native processing stops. Queued metadata stays
    available for authorized delivery; a restart does not restore the old lease.

## Windows 11 run and test instructions

Use PowerShell in `E:\Restaurent_startup`. The approved environment already has
the packages; these commands do not install anything. Keep private files private.

```powershell
Set-Location E:\Restaurent_startup
$env:EDGE_SYNC_ENABLED = 'true'
docker compose start db
docker compose up -d --no-deps --no-build api web
```

Open <http://localhost:3000/settings> or <http://localhost:3000/dashboard> and sign
in using the existing private synthetic account file. Never paste its passwords
into documentation, screenshots, chat, scripts or a Git commit.

Run the approved local HTTPS listener in a separate PowerShell window:

If verification already has a listener on port 8443, use it rather than starting a
second copy. This is a local process, not an installed Windows service. Start the
command below when that listener is unavailable.

```powershell
.\.venv\Scripts\python.exe -m restaurant_api.edge_tls `
  --cert .secrets/phase6/tls/server.pem `
  --key .secrets/phase6/tls/server-key.pem --env-file .env
```

The listener binds only `127.0.0.1:8443`. Its private development certificate
expires after seven days; its CA after 30 days. To renew, generate a **new private
directory**, review the new CA and change the explicit device trust/config paths.
Do not overwrite keys or globally trust the development CA.

```powershell
# New installations only: choose unused private paths; do not replace existing files.
.\.venv\Scripts\python.exe scripts/prepare_phase6_tls.py --output .secrets/phase6/new-tls
.\.venv\Scripts\python.exe -m restaurant_edge.cli device-init --identity .secrets/phase6/new-device.json
.\.venv\Scripts\python.exe -m restaurant_edge.cli device-pair `
  --identity .secrets/phase6/new-device.json --api https://127.0.0.1:8443 `
  --ca .secrets/phase6/tls/ca.pem --request .secrets/phase6/new-pairing.json
```

Repeat `device-pair` with the same request file to poll within the ten-minute
pairing window. In settings select the correct location, approve its full public
fingerprint, bind the reviewed synthetic camera/table and hashes, then enable
processing. The local runner configuration stores only local paths and public
IDs, not passwords. The existing demo configuration is `.secrets/phase6/runner.json`.

```powershell
.\.venv\Scripts\python.exe -m restaurant_edge.cli device-run `
  --settings .secrets/phase6/runner.json --seconds 22
.\.venv\Scripts\python.exe -m restaurant_edge.cli device-sync `
  --settings .secrets/phase6/runner.json
```

The runner configuration fields are `api`, `ca`, `identity`, `profiles`, `models`,
`sources`, `camera_id`, `source_reference`, `outbox`. Relative file paths resolve
from that configuration file's directory. Use the existing authorized registry,
profile and reviewed model catalog. A mismatched hash/revision must be reviewed,
not bypassed by editing queued events.

```powershell
$env:RFDETR_TEST_CATALOG = (Resolve-Path .secrets/phase5/models/catalog.json).Path
.\.venv\Scripts\python.exe -m pytest services/api/tests services/edge-agent/tests `
  -q -p no:cacheprovider --tb=short

# Explicit full outage test; takes at least 15 minutes. Synthetic metadata only.
$env:PHASE6_OUTAGE_SECONDS = '900'
.\.venv\Scripts\python.exe -m pytest `
  services/api/tests/test_edge_https.py::test_real_tls_offline_recovery `
  -q -p no:cacheprovider --tb=short
Remove-Item Env:PHASE6_OUTAGE_SECONDS

.\.venv\Scripts\python.exe -m ruff check --no-cache services/api services/edge-agent
Set-Location apps/web
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm.cmd run lint
npm.cmd run build
```

The suite refuses an unmarked business test database. Its default existing private
test-server manifest is `.secrets/phase2-test.json`; the Phase 6 verification also
used an explicitly isolated restored database. Native-model tests need the
already-approved private catalog; without it opt-in native tests are explicitly
unverified/skipped, not automatically downloaded. All native tests must be enabled
for the complete local count below. Run CPU/native suites and browser inference
sequentially; multiple simultaneous model workers are not a supported capacity.

## Resumed final verification - 2026-11-11

This review continued the existing implementation. Docker Desktop and the
retained containers were stopped at the beginning; the existing installation and
containers were started. The original database was not recreated, restored over
or migrated again. No new dependency, footage, model download or npm upgrade was
introduced. Two narrow Phase 6 corrections were necessary: the blueprint event
route and prompt publication of changed device health.

The master blueprint specifies `POST /v1/edge/events`; the earlier implementation
used `/v1/edge/batches`. Both now use the same protected handler, and the edge
sender uses `/events`. The old name remains compatible. Tests prove shared
deduplication, signature binding to the exact path, replay rejection, revoked-key
rejection and location isolation. The matching API image was rebuilt and checked
before replacing only the API service; the loopback TLS listener was restarted.
The database container and volume remained in place.

The first browser run failed to see RUNNING even though its private runner log
confirmed real inference. The runner previously reported health only every 15
seconds: readiness at that boundary could be missed by a 22-second demonstration.
A new deterministic test reproduced STOPPED-only heartbeats despite RUNNING
analysis. The runner now reports camera/inference health changes as the loop
observes them, rate-limiting transition attempts to one per second while retaining
its regular 15-second heartbeat. This is not a real-time network-latency guarantee.
The new test failed before this correction and passed afterward. Browser waits,
native run durations, model startup limits and existing assertions were not
weakened. The separate initial cold/loading performance limitation remains.

| Fresh check | Actual result |
| --- | --- |
| Existing business database | Head `0008`; zero differences between models and schema; restricted login is neither superuser nor RLS-bypassing |
| Restored-backup rehearsal | New isolated test database, retained private 0007 backup, upgrade to 0008 run twice: all **555 records preserved**, zero model differences; business database untouched |
| Original data/credentials/calibrations | All **533 original record IDs and protected row values**, **10 users/password records**, cloud **Revision 7**, four private seating files including **Revision 1**, original DB container/volume and `.env` preserved; only the documented notification/login counters change |
| First resumed full suite | **525 passed / one failed**, one warning, **333.32 seconds**: native runner still LOADING at the unchanged 12-second stop, with no inference sample |
| Focused native and route/security checks | **39 passed**, one warning, **44.04 seconds**, with original assertions and time limits retained |
| Complete suite before the health correction | **528 passed**, one warning, **206.32 seconds**; followed by the browser failure that exposed missing prompt health publication |
| Health-boundary regression and affected checks | The new deterministic case failed on the old implementation; **51 affected tests passed**, one warning, **44.73 seconds**, after the correction |
| Final complete suite | **529 passed**, **1 existing warning**, **200.80 seconds**; includes all original 445, actual RF-DETR synthetic inference, TLS, authorization, pairing/rotation/revocation, ordering/deduplication, crashes and actual isolated database/API restart; no skips |
| Actual PostgreSQL/API restart and duplicate task effects | Fresh isolated named-volume restart retained **two receipts and exactly one synthetic reset task** after replay. The test container/volume were retained; the business database was not restarted by this test |
| Fresh 900-second outage request | Listener actually unavailable for **900.001 seconds**; **16 durable events**, **33 failed sends**, original IDs retained and all delivered after reopening the queue/reconnecting; zero duplicate receipts or shadow-mode tasks |
| Actual RF-DETR synthetic background runner | RUNNING, latest one-result sample **668.53 ms**, queue empty, UNKNOWN without people, operational table unchanged; not an accuracy/FPS benchmark |
| Browser integration | **Six installed-Edge groups passed** against the active stack: existing approval/binding preserved, native CPU/HTTPS/SSE RUNNING, mobile fit, stopped/degraded health and isolation/proxy denial |
| Frontend/static/build | TypeScript, ESLint, production build, Ruff and Compose validation passed; native API-image signature/body-tamper and host/image dependency checks passed |
| Dependency advisories | Fresh OSV checks: no listed advisories for the three approved additions. Broader host/API inventory (63 package/version pairs) flags six pip issues and one pytest issue; aliases are not extra issues. npm still reports **8 affected packages (1 high, 7 moderate)**. See the [dependency review](../PHASE_06_DEPENDENCY_REVIEW.md#broader-installed-package-audit---2026-11-11); no upgrade performed |
| Repository/security | **197 Git-eligible files** scanned for known secret values and credential/token patterns; no forbidden private files or actionable matches. Ignore checks, local Markdown links, CRLF-aware whitespace check and no-deletion check passed. Branch remains `main`; nothing staged, committed or pushed |

The initial model-loading failure is retained, not treated as fixed by a passing
rerun. It occurred after restarting the environment; its exact cause was not
isolated. The focused native case and final full suite passed without increasing
timeouts, changing assertions or skipping tests. Cold-start/load sensitivity
remains a performance limitation requiring controlled measurement before a
pilot. The independent native worker-exit failure from November 8 also remains
historical evidence with an unproven cause.

The full outage uses synthetic event metadata and the existing compatible batch
route; the final HTTPS tests and sender exercise the blueprint `/events` route.
Both share the same ingestion and receipt implementation. An outage recovery
test proves transport/recovery, not the quality of detections. No representative
person clip, physical camera or restaurant occupancy accuracy was evaluated.

Fresh evidence, private test reports and logs remain under ignored
`.secrets/phase6-implementation/`. No secret values, private video or model weights
are copied into documentation. Earlier results below are dated November 8
history, not additional current passes. No Phase 7 or public/pilot deployment
was started. Git commit and push still require separate founder approval.

The newly identified pip/test-tool advisories need a separately reviewed,
approved remediation. Version matches are not evidence of an exploit, and the
pytest advisory concerns UNIX temporary directories. Do not silently upgrade
pip, move to pytest 9, change CI constraints or treat the Windows pass as a Linux
security certification. Existing npm and credential-rotation gates remain.

## Actual verification and retained failures

The following table records the original **2026-11-08** verification. Use the
resumed section above for fresh November 11 results.

| Check | Actual result / scope |
| --- | --- |
| Fresh pre-change baseline | All 445 earlier tests passed, one existing warning |
| Original MP4 timing assertions + new delayed/reopen cases | Five selected cases passed; no old assertion weakened or skipped |
| Queue/signature foundation | 30 passed, including forced process exit after commit and during an unfinished transaction |
| Lease/commit/retry unit checks | Ten included in the final suite, including expiry during a blocked sender and freshly computed health age |
| Expanded API security | 34 included in the final suite: earlier 33-test targeted pass plus stale-health/retired-binding coverage |
| Dashboard/security/route integration group | 128 passed before the final additions |
| Real HTTPS certificate/digest/short outage | Two passed after fixing certificate and connection shutdown issues |
| Full 900-second outage request | Actual offline duration **1,530.643 seconds**, 13 durable events, 27 failed send attempts, all original IDs delivered, zero duplicate receipts and zero shadow-mode tasks |
| Actual PostgreSQL + API restart | Passed on a NEW labeled persistent test volume: two receipts, exactly one actual fixture reset task after replay; original business DB untouched by this test |
| Real RF-DETR + synthetic MP4 + TLS runner | Passed; CPU RUNNING, latest final-suite sample **343.96 ms**, zero pending, UNKNOWN without people, operational table unchanged. Actual business-lab browser run latest sample **307.62 ms**; these are individual samples, not throughput/accuracy claims |
| Native Windows key storage | Actual Credential Locker round trip passed; identity file contains no private key |
| Dependency/image checks | Host/image `pip check`, Linux/Windows native signature/body-digest round trips passed; API adds exactly the approved three packages with no original version change |
| Database safety | Restored-backup rehearsals: 533 original records before 0007; 555 current records before 0008; zero model differences. Both approved migrations preserved their pre-migration records. Final original business/password/calibration/seating checks passed |
| Frontend | Type check, lint and Docker production build passed; **six installed-Edge browser groups passed again against 0008**, including real HTTPS/SSE, mobile fit and shutdown/degraded health |
| Full final regression | **526 passed, one existing Starlette/HTTPX warning, 132.90 seconds**. All earlier 445 cases retained; no skipped native cases in this opted-in local run |
| Repository/static review | Ruff and host/image dependency checks passed; 197 eligible files reviewed with known-secret/context scanning, no forbidden files or exposed credential assignments; no files staged, committed or deleted |

The long outage deliberately disabled the real loopback listener. The interruption
exceeded 900 seconds; the extra elapsed time was not isolated as a separate root
cause. The report records measured time and actual event count, not an invented
precisely 15-minute interval or a sustained throughput benchmark. No physical camera, customer
clip or real-person accuracy test was part of it.

Problems found and corrections:

- The original MP4 reader used file-start catch-up pacing. A delayed first frame
  could compress the next gap. Pacing now uses the preceding delivered frame;
  new fake-clock regressions include first-read delay, a later stall and reopening.
  The original Phase 5 failed timing run remains historical evidence.
- New queue JSON boundary tests initially generated a Windows filename longer
  than the OS allows. Explicit short pytest case names fixed setup; assertions
  remained unchanged.
- Python 3.14 rejected the first development certificate for missing authority
  key identifiers. Add issuer/subject identifiers and required usages; retain
  strict certificate verification. An idle TLS connection delayed shutdown, so
  the device client closes request connections and uses bounded listener shutdown.
- One full run had **513 passed / one failed** because Phase 6 tests added grants
  to the original Phase 2 discovery fixture. Separate synthetic test restaurants
  fixed the pollution; the original access assertion was not changed.
- The restart harness first mistook PostgreSQL's temporary init socket for TCP
  readiness. It now proves an actual connection. A random published Docker port
  changed on restart, so the new test uses a fixed, verified loopback port.
- A later run had **516 passed / one native worker-exit failure**, while a separate
  browser model run also ended early. These runs overlapped. The affected original
  native test passed separately; the cause of the simultaneous native exits is not
  proven. Final verification is sequential; no timeouts/assertions were weakened.
- The first browser health wait was shorter than the 15-second heartbeat cadence.
  Its bounded wait now covers that cadence. Previously approved device settings
  are preserved on rerun instead of replaying a consumed pairing request.
- Final contract review added `0008` for per-item owned-event rejection and fresh
  context. It was rehearsed and separately approved before business execution;
  the existing `0007` was not rewritten. Health now recomputes actual frame age
  and withholds stale/retired-context shadows.
- A broad credential scan initially matched ordinary occurrences of a short
  legacy word. Long secret values were checked directly; short common values were
  reviewed as literal credential assignments. No private value was printed or
  copied into Git. The weak administrator credential remains a deployment gate.
- A detached listener startup was blocked by automatic approval review. The
  approved loopback listener was started in a managed tool session instead.

## Data preservation, limitations and deployment gates

The private backup, original database volume/container, user/password records,
existing business rows, cloud calibration Revision 7 and private seating Revision
1 must remain preserved. New Phase 6 metadata/audits/authentication sessions may be
appended during approved synthetic verification. The final preservation report
compares original row values, not just table counts. All 533 original record IDs
remain, including all ten users/password hashes and four private seating files.
Two expected activity counters changed: location revisions advanced by exactly
the number of new device notifications, and real browser sign-ins updated login
rate-limit attempts/window times. These are verified exceptions; original staff
decisions, table records, geometry and other original row values are unchanged.
Migrations 0001-0006, master specification, `.env` and Git configuration are unchanged.

Real-person detection precision/recall, table-assignment accuracy, restaurant
occupancy accuracy and transition quality remain **unverified**. No representative
authorized person footage is available. `SR.mp4` remains unauthorized. Synthetic
transport and model execution do not validate customer-facing AI claims.

Physical webcam/RTSP equipment, multi-camera simultaneous inference, Linux/service
key storage, arbitrary layouts and production capacity are not validated. One
latest inference number is not a sustained FPS or end-to-end latency guarantee.
The under-five-second receipt-to-dashboard target still needs a representative
measured deployment benchmark.

This is local development TLS, not production website HTTPS. The documented npm
high/moderate findings, weak preserved administrator password, missing managed
MFA/recovery/email lifecycle, non-root/container hardening and external security
review remain deployment gates. Rotate credentials under the existing reviewed
procedure before pilot/public use; no rotation or breaking upgrade occurred here.

Malformed envelopes or unknown/private fields are rejected as a batch and retained
locally for review. Owned invalid version/type/state events get terminal receipts;
invalid raw content is not stored server-side. Originals are never silently dropped
or rewritten. Missing sequence gaps can hold later durable receipts pending. Queue
corruption/disk exhaustion requires review without automatic deletion/reset.
Automatic retention/compaction, retired-key/nonce cleanup and operational recovery
for a lost Windows key/queue are not implemented. Plan these before sustained use.

The SQLite settings and process/restart tests do not certify physical power-loss,
disk-controller or storage-device durability. A tampered/compromised OS or backend
runtime remains outside the protection offered by API identity context and RLS.
Native codecs/model binaries still need deployment review; advisory checks are
dated evidence rather than a vulnerability-free guarantee.

## Phase summary

Phase 6 adds protected device identity, separately approved processing permission,
durable metadata delivery, ordered duplicate-safe receipts, offline/restart
recovery and scoped dashboard health. The real AI path remains shadow-only.
The final checks above passed within their stated local/synthetic scope. Stop for
founder review here. Phase 7, commits and pushes require separate approval.
