# Phase 7 verified workflow and analytics Git checkpoint

**Review snapshot:** 2026-11-12, Asia/Dhaka; evidence uses UTC.
**Branch:** `main`.
**Parent:** `fd983c7a656ab36f031db2900ef15a3da1362cbe` (published Phase 6).
**Requested message:** `chore: phase 7 verified workflow and analytics checkpoint`.
This document records the preparation snapshot. Creating the local commit and
pushing it to existing `origin/main` each require separate founder approval.
No commit or push has happened at this snapshot; publication is verified only
after those approvals, using the actual local/tracking/GitHub hashes.

## Scope and founder manual evidence

This checkpoint includes the approved Phase 7 human-reviewed arrival/departure
workflow, protected staff cleaning/manager corrections, one task per session,
atomic audits, compatible v2 metadata, daily/hourly analytics and secure CSV.
It includes the A02 reporting correction: original DEMO scenario events/tasks
now contribute to DEMO summaries through read-only calculations. Canonical
reviewed sessions, production/legacy/evidence bases and original timestamps
remain separate. No artificial sessions, device evidence or backfill is written.

The founder reports successful manual verification of A02 OCCUPIED ->
RESET_PENDING -> CLEANING -> AVAILABLE, one completed occupied session, one
completed reset, **1.8 min cleaning** and **4.1 min departure to ready**. The CSV
was downloaded and opened in **Microsoft Excel**. That ordinary Excel opening
is now founder-verified; malicious-label spreadsheet save/reopen round trips
and other spreadsheet applications remain unverified. A02's older November 7
synthetic arrival is deliberately preserved, so its full visit is long.

See [the complete explanation](phase_explanations/PHASE_07.md),
[approved plan](PHASE_07_IMPLEMENTATION_PLAN.md) and
[applied migration review](PHASE_07_MIGRATION_REVIEW.md).

## Fresh verification for this checkpoint

- **650 tests passed**, **zero skipped**, one existing Starlette/httpx
  deprecation warning, **259.19 seconds**. This reruns all API/edge tests,
  including all original 529 Phase 6 cases, the A02 regressions, real RF-DETR
  CPU inference on generated footage, signed HTTPS, authorization, concurrency,
  restart recovery, temporal logic, time zones and CSV protection. Tests and
  native/evidence thresholds were not weakened.
- **Eleven installed Edge browser groups passed** through the prepared Linux
  production web image, real API and a new isolated PostgreSQL database.
  Both the reviewed AI workflow and the original DEMO A02 sequence/report/CSV
  pass, with tenant/role denials, stale/offline recovery, retry idempotency,
  mobile layout and incomplete-download rejection. Constructed evidence and
  synthetic video do not establish real-person or restaurant occupancy accuracy.
- Frontend lint, sequential TypeScript check and production build pass. Python
  Ruff and `pip check` pass. Next lint and Starlette/httpx deprecations remain.
- All **615 checkpoint-baseline records**, including the migration-version row,
  remain unchanged. Original task/event/user/session rows, seven protected
  credential/configuration/seating files, PostgreSQL role password verifiers,
  calibration Revision 7, seating Revision 1 and original DB container/volume
  are preserved. Head remains `0009`, with **zero** model/schema differences.
  The running API matches all **25** source files in the candidate package.
- Comparison with the earlier A02 investigation found only expected later
  authentication changes before this checkpoint began: two login buckets'
  attempts/window times advanced and one older session was revoked. No row
  was missing. A fresh baseline was captured and all its rows stayed unchanged
  throughout this checkpoint verification.
- A read-only GitHub lookup matched existing `origin/main` to the parent above.
  No remote was created/modified and no push was performed during preparation.

The strict staged whitespace check passes with no warnings. During checkpoint
preparation, only documentation was edited; the application/test/configuration
files match the reviewed starting inventory and the passing regression run.

## Security review and remaining deployment blockers

The custom scan covers all Git-eligible working files, the complete Git index
and **366 reachable history blobs**, checking known private credential/token/
device-key values, common token/private-key patterns, binary/private paths and
ignore rules. No actionable secret or forbidden path was found. Initial flags
were inspected with masked output and were ordinary unquoted password variable
forwarding, such as a function receiving a variable. Literal values, credentials
in URLs/configuration and long known secrets remain checked. After staging, the
exact index contents are scanned again and compared with this reviewed list.
This is a custom review, not a guarantee against unknown or encoded secrets;
no standalone scanner was installed.

The exclusions include `.env`, `.secrets/`, actual/demo passwords, private device
and TLS keys, `.venv`, the isolated exporter, `node_modules`, `.next`, logs,
generated output, databases/backups, recordings and model weights. Blank
templates, source, tests, migrations and documentation are the intended files.

Fresh OSV checks cover **105 public package/version combinations** across the
working environment, API image and isolated exporter. pip 25.0.1/25.2 retain six
distinct GHSA findings plus aliases; pytest 8.4.2 retains one GHSA plus alias.
npm audit reports **eight affected packages: one high, seven moderate**. These
are advisory findings, not fixed vulnerabilities or a public-deployment approval.
No packages were installed/upgraded and no automatic audit fix was run.

The preserved weak legacy DB administrator password requires separately reviewed
rotation before pilot/public use. Production TLS, MFA/recovery, hardening,
independent security review, native-code/container auditing and representative
footage/hardware evaluation remain gates. Historical intermittent native freshness
failures remain documented even though this full run passed. No real-person AI
accuracy, public/pilot deployment, Phase 8 or GitHub CI success is claimed.

## Complete reviewed file list

**55 files: 29 added, 26 modified, zero deleted.** `A` means added; `M` modified.
These are the exact candidate paths; staging and commit approvals must match them.

| Change | Path |
| --- | --- |
| M | `README.md` |
| A | `apps/web/app/analytics/page.tsx` |
| M | `apps/web/app/api/[...path]/route.ts` |
| M | `apps/web/app/dashboard/page.tsx` |
| A | `apps/web/app/dashboard/workflow-review.tsx` |
| A | `apps/web/app/dashboard/workflow-types.ts` |
| M | `apps/web/app/globals.css` |
| M | `docs/CODEX_HANDOFF.md` |
| M | `docs/PHASE_06_CHECKPOINT.md` |
| A | `docs/PHASE_07_CHECKPOINT.md` |
| A | `docs/PHASE_07_IMPLEMENTATION_PLAN.md` |
| A | `docs/PHASE_07_MIGRATION_REVIEW.md` |
| M | `docs/api_contract.md` |
| M | `docs/architecture.md` |
| M | `docs/implementation_plan.md` |
| M | `docs/phase_explanations/PHASE_03.md` |
| M | `docs/phase_explanations/PHASE_05.md` |
| M | `docs/phase_explanations/PHASE_06.md` |
| A | `docs/phase_explanations/PHASE_07.md` |
| M | `docs/phase_explanations/README.md` |
| A | `packages/contracts/evidence_protocol.py` |
| A | `scripts/freeze_phase7_schema.py` |
| A | `scripts/rehearse_phase7_migration.py` |
| A | `scripts/verify_phase7_browser.py` |
| M | `services/api/migrations/env.py` |
| A | `services/api/migrations/sql/0009_workflow_schema.sql` |
| A | `services/api/migrations/sql/0009_workflow_security.sql` |
| A | `services/api/migrations/versions/0009_reviewed_workflow.py` |
| A | `services/api/src/restaurant_api/analytics.py` |
| A | `services/api/src/restaurant_api/analytics_domain.py` |
| A | `services/api/src/restaurant_api/analytics_scenarios.py` |
| M | `services/api/src/restaurant_api/edge_models.py` |
| M | `services/api/src/restaurant_api/edge_routes.py` |
| A | `services/api/src/restaurant_api/evidence_protocol.py` |
| M | `services/api/src/restaurant_api/main.py` |
| M | `services/api/src/restaurant_api/management.py` |
| M | `services/api/src/restaurant_api/models.py` |
| A | `services/api/src/restaurant_api/workflow_models.py` |
| A | `services/api/src/restaurant_api/workflow_review.py` |
| M | `services/api/tests/test_database_isolation.py` |
| M | `services/api/tests/test_edge_database_restart.py` |
| A | `services/api/tests/test_phase7_analytics_api.py` |
| A | `services/api/tests/test_phase7_analytics_domain.py` |
| A | `services/api/tests/test_phase7_evidence.py` |
| A | `services/api/tests/test_phase7_native.py` |
| A | `services/api/tests/test_phase7_scenario_analytics.py` |
| A | `services/api/tests/test_phase7_workflow.py` |
| M | `services/api/tests/test_route_inventory.py` |
| M | `services/edge-agent/src/restaurant_edge/analysis.py` |
| M | `services/edge-agent/src/restaurant_edge/device_runner.py` |
| M | `services/edge-agent/src/restaurant_edge/durable_engine.py` |
| A | `services/edge-agent/src/restaurant_edge/evidence_protocol.py` |
| A | `services/edge-agent/src/restaurant_edge/evidence_window.py` |
| M | `services/edge-agent/src/restaurant_edge/outbox.py` |
| A | `services/edge-agent/tests/test_phase7_evidence_delivery.py` |

## Approval and post-commit checks

The founder must approve this exact staged set before the local commit.
Before committing, recheck the staged fingerprint and secret scan, branch and
parent, preserved private configuration, and absence of unexpected work.
After committing, verify the hash, requested message, unchanged approved blobs,
no deletions and a clean working tree. Ask separately before a normal push to
existing `origin/main`; never force-push. After an approved push, independently
verify local HEAD, tracking `origin/main` and GitHub's branch tip match.
