# Phase 6 verified edge synchronization Git checkpoint

**Prepared:** 2026-11-11, Asia/Dhaka. This is the pre-commit review snapshot.
**Branch:** `main`.
**Parent:** `ae19ec81f342d17730ddd48845a5862a2d56a99a` (published Phase 5 checkpoint).
**Requested message:** `chore: phase 6 verified edge synchronization checkpoint`.
**Approval gate:** stage the reviewed set, show it to the founder and obtain
explicit approval before committing. After the local commit is verified, obtain
separate approval before a normal fast-forward push to the existing GitHub
`origin/main`. This preparation does not approve a commit, push or deployment.

## What this checkpoint saves

The existing Phase 6 implementation, safe configuration, exact approved package
manifests, forward migrations, automated tests and documentation. It includes
fingerprint pairing, protected device identity, signed HTTPS metadata, SQLite
durability/retries/recovery, duplicate-safe receipts, scoped shadow estimates and
dashboard health. The blueprint event route, prompt health publication and MP4
pacing corrections are included. AI cannot override operational staff decisions.
The [phase explanation](phase_explanations/PHASE_06.md) is the detailed walkthrough.

Only documentation and the Git index change during checkpoint preparation. No
application edits, dependency installation, container changes, credential rotation,
database write, file deletion or Phase 7 work is included.

## Reviewed verification evidence

The following results are from the completed **2026-11-11 verification**, reviewed
for this checkpoint. They were not rerun or relabeled as new checkpoint test runs.

| Check | Recorded result |
| --- | --- |
| Final complete suite | **529 passed**, no skips, one existing Starlette/HTTPX warning, **200.80 seconds**; all original 445 retained |
| Real browser walkthrough | Six groups passed: approved identity/binding preserved, CPU inference/HTTPS/SSE, mobile fit, shutdown/degraded health and tenant/proxy denial |
| Network outage and restart | Actual **900.001-second** listener outage; all **16 durable events** delivered with original IDs, **33 failed send attempts**, zero duplicate receipts or shadow operational tasks |
| Actual isolated PostgreSQL/API restart | Two receipts and exactly one synthetic reset task after replay; retained new test volume, original business DB untouched |
| Builds/static/dependencies | Frontend types/lint/production build, Ruff, Compose and host/image dependency checks passed; native image signature/body-tamper check and original-version preservation passed |
| Existing database | Migrations 0007/0008 already applied; head **0008**, installed ingestion body matches reviewed SQL, zero model differences, RLS enabled on nine new public tables |
| Preserved data | **533 original records**, ten user/password records, calibration **Revision 7**, seating **Revision 1**/four local profile files, original DB container/volume, credentials, old migrations and master preserved |

The original rows are compared by value, not only counts. Allowed activity changes
are location revision increments equal to new device notifications and login
attempt/window counters. The read-only preservation check passed again during
checkpoint preparation; no database write was used for this check.

The first resumed suite had **525 passes / one native LOADING failure**. An
intermediate 528-test pass was followed by a browser health failure. A deterministic
regression reproduced the missed health update, and the correction passed 51
affected cases and the final complete suite/browser walkthrough. Those failures
are retained in the phase explanation; assertions/time limits were not weakened.
Cold-start/load sensitivity and the older unexplained native-worker exit remain
limitations, not fixed merely by a subsequent pass.

## Security scope and exclusions

**Formatting finding:** an explicit strict staged whitespace check reports
**119 trailing-space warnings**: 116 in the generated, already-applied
`0007_edge_schema.sql` and three intentional Markdown hard line breaks in the
approved implementation plan. The frozen migration's SHA-256 still matches the
reviewed/applied artifact. These cosmetic findings are disclosed for approval;
the strict check is not described as a pass. The migration and application
source are preserved rather than rewritten during checkpoint preparation.

Scan all Git-eligible files and the **exact staged blobs** for known private
credential/key values and credential patterns. Check index modes, manifest equality,
newline-normalized working/index content, whitespace, ignore probes, documentation
links and no deletions before requesting approval. Private scan reports stay under
ignored `.secrets/phase6-checkpoint/`; no actual secret is printed in a report.

Exclude real `.env` files/overrides, `.secrets/`, private keys/certificates, pairing
and runner setup, credentials/sessions/tokens, source registries, model weights and
sidecars, all recordings/synthetic MP4, SQLite queues, databases/backups, calibration
and seating contents, virtual environments, dependencies, generated frontend output,
logs, screenshots and caches. Existing blank `.env.example` and textual dependency
hashes are safe templates/provenance, not credentials or downloaded assets.

Git saves source and instructions, not the private installation. A new checkout
must privately provision credentials, authorized model assets, device keys and
runtime/calibration files. This checkpoint does not make those local assets public
or supply a production-ready deployment.

**Final staged review:** the exact **68-file** index matches the manifest and
reviewed working copies after newline normalization. All **198 Git-eligible
working files and 198 index blobs** passed the known-credential/private-key/token
scan with no findings. Every index entry is a regular text file. All **39 ignore
probes** and **216 local documentation file links** passed; the blank environment
template remains available to Git. No deletion, unstaged tracked change or
untracked Git-eligible file remains outside the reviewed set. `.env`, Git
configuration and parent HEAD are unchanged. The strict whitespace findings
disclosed above remain; they are not a clean-check claim. These bounded checks
reduce disclosure risk and do not constitute a full external security review.

Known limitations: real-person detection/table-assignment/restaurant accuracy and
physical CCTV remain unverified. Native startup/load sensitivity, one-active-camera
capacity, local-only TLS/lease, missing general paginated event history and retention
tools remain documented. The weak preserved administrator credential, eight npm
findings (one high/seven moderate), pip/pytest advisories and external deployment
security work remain unresolved. See the [dependency review](PHASE_06_DEPENDENCY_REVIEW.md)
and [credential rotation procedure](DATABASE_CREDENTIAL_ROTATION.md). No public/pilot
deployment or real AI operational activation is approved.

## Complete reviewed file list

**68 files: 28 modified and 40 new.** `M` means an existing Git file changed;
`A` means a new Git file. No deletions are included. The checkpoint manifest itself
is one of the 40 new files. Before approval this list must exactly match the index.

| Change | Path |
| --- | --- |
| M | `.github/workflows/ci.yml` |
| M | `README.md` |
| M | `apps/web/app/api/[...path]/route.ts` |
| A | `apps/web/app/dashboard/edge-health.tsx` |
| M | `apps/web/app/dashboard/page.tsx` |
| M | `apps/web/app/globals.css` |
| A | `apps/web/app/settings/device-permissions.tsx` |
| M | `apps/web/app/settings/page.tsx` |
| M | `apps/web/app/settings/preview-permissions.tsx` |
| M | `docker-compose.yml` |
| M | `docs/CODEX_HANDOFF.md` |
| M | `docs/PHASE_05_CHECKPOINT.md` |
| A | `docs/PHASE_06_CHECKPOINT.md` |
| A | `docs/PHASE_06_DEPENDENCY_REVIEW.md` |
| A | `docs/PHASE_06_IMPLEMENTATION_PLAN.md` |
| A | `docs/PHASE_06_MIGRATION_REVIEW.md` |
| M | `docs/implementation_plan.md` |
| M | `docs/phase_explanations/PHASE_05.md` |
| A | `docs/phase_explanations/PHASE_06.md` |
| M | `docs/phase_explanations/README.md` |
| A | `packages/contracts/device_protocol.py` |
| A | `packages/contracts/device_signatures.py` |
| A | `scripts/freeze_phase6_schema.py` |
| A | `scripts/prepare_phase6_tls.py` |
| A | `scripts/rehearse_phase6_migration.py` |
| A | `scripts/verify_phase6_browser.py` |
| M | `services/api/Dockerfile` |
| M | `services/api/migrations/env.py` |
| A | `services/api/migrations/sql/0007_edge_schema.sql` |
| A | `services/api/migrations/sql/0007_edge_security.sql` |
| A | `services/api/migrations/sql/0008_rejected_context.sql` |
| A | `services/api/migrations/versions/0007_edge_schema.py` |
| A | `services/api/migrations/versions/0008_rejected_context.py` |
| M | `services/api/pyproject.toml` |
| A | `services/api/requirements-phase6-linux.txt` |
| M | `services/api/requirements-runtime-lock.txt` |
| M | `services/api/src/restaurant_api/database.py` |
| A | `services/api/src/restaurant_api/edge_models.py` |
| A | `services/api/src/restaurant_api/edge_monitor.py` |
| A | `services/api/src/restaurant_api/edge_protocol.py` |
| A | `services/api/src/restaurant_api/edge_routes.py` |
| A | `services/api/src/restaurant_api/edge_signatures.py` |
| A | `services/api/src/restaurant_api/edge_tls.py` |
| M | `services/api/src/restaurant_api/main.py` |
| M | `services/api/src/restaurant_api/management.py` |
| M | `services/api/src/restaurant_api/models.py` |
| M | `services/api/src/restaurant_api/settings.py` |
| M | `services/api/src/restaurant_api/workflow.py` |
| M | `services/api/tests/test_database_isolation.py` |
| A | `services/api/tests/test_edge_database_restart.py` |
| A | `services/api/tests/test_edge_https.py` |
| A | `services/api/tests/test_edge_native_runner.py` |
| A | `services/api/tests/test_edge_transport.py` |
| M | `services/api/tests/test_route_inventory.py` |
| M | `services/edge-agent/pyproject.toml` |
| A | `services/edge-agent/requirements-phase6-windows.txt` |
| M | `services/edge-agent/src/restaurant_edge/cli.py` |
| A | `services/edge-agent/src/restaurant_edge/device_client.py` |
| A | `services/edge-agent/src/restaurant_edge/device_identity.py` |
| A | `services/edge-agent/src/restaurant_edge/device_protocol.py` |
| A | `services/edge-agent/src/restaurant_edge/device_runner.py` |
| A | `services/edge-agent/src/restaurant_edge/device_signatures.py` |
| A | `services/edge-agent/src/restaurant_edge/durable_engine.py` |
| A | `services/edge-agent/src/restaurant_edge/outbox.py` |
| M | `services/edge-agent/src/restaurant_edge/video_sources.py` |
| A | `services/edge-agent/tests/test_device_foundation.py` |
| A | `services/edge-agent/tests/test_device_recovery.py` |
| A | `services/edge-agent/tests/test_video_pacing.py` |

## After separate approvals

After local-commit approval, recheck the exact staged content and create the
requested commit on `main`. Verify its parent, file manifest, message and clean
working tree. Do not add any new file silently to the approved set.

Then ask separately for permission to push that exact commit to the existing
`origin/main`. Before a normal fast-forward push, inspect the remote tip without
changing its configuration. Stop for review if the remote has unrelated changes;
never force push. After an approved push, independently compare GitHub
`refs/heads/main`, local `main` and tracking `origin/main`, plus Git status.
No remote configuration is created or changed by this checkpoint procedure.
