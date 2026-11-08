# Phase 4 Git checkpoint review

**Review date:** 2026-11-08, Asia/Dhaka. Verification artifacts store UTC times.
**Branch:** `main`.
**Existing parent commit:** `899f74368b9487ae1c33e0d0c0e511e37b396f36` (`docs: verify phase 3 GitHub checkpoint`).
**Requested local commit message:** `chore: phase 4 verified video calibration checkpoint`.
**Publication outcome:** The founder separately approved the 48-file local commit and its normal fast-forward push. Checkpoint `143831395429785a2a5647b7317aafc0fe4fdea7` (`chore: phase 4 verified video calibration checkpoint`) is on local/GitHub `main`; remote publication and the clean working tree were verified at completion. The requested message, manifest, tests and approval gates below preserve the original preparation record. Later Phase 5 work is not part of this commit and has no commit/push authorization.

## What this checkpoint saves

Phase 4 adds the native local video input and camera calibration system: actual synthetic MP4 decode/preview, webcam and restricted RTSP adapters, reader supervision/cleanup, explicit temporary preview permission, visual polygon editing, persistent revision/audit records and additive migrations 0005/0006. Existing floor states and occupancy behavior stay separate from video. See [PHASE_04.md](phase_explanations/PHASE_04.md) for the full explanation.

The founder reports successful video playback, preview authorization and reloading polygon **Revision 7** after browser refresh. Fresh read-only database/API checks independently found Revision 7 and preserved it. Git will save the program that loads that polygon; the database record itself stays in the private local database, outside Git.

## Fresh verification

| Check run for this checkpoint | Actual result |
| --- | --- |
| Complete API/edge Python suite | **333 passed, one existing warning, 69.43 seconds**, all 262 earlier tests retained; no skips on this Windows host |
| PostgreSQL integration/security tests | Passed against the existing separately marked isolated tmpfs test database; no application database selected by these tests |
| Python lint/dependencies | Ruff and `pip check` passed |
| Local editor and Compose | JavaScript syntax and quiet Compose validation passed |
| Frontend | Lint, TypeScript and production build passed |
| Running stack read-only checks | API health/readiness, web sign-in and local setup reachable; anonymous local frame denied; A/B calibration reads rejected both directions; authorized A API returns Revision 7 |
| Application preservation | All 427 current public records, ten user rows and all saved polygons unchanged; `.env`, Git configuration and existing commit unchanged; no original eligible file deleted |
| Prior browser demonstration | Nine implementation-time groups retained as historical evidence; not rerun because the script saves new polygon revisions and changes test preview grants |

The Python warning remains the existing Starlette/HTTPX TestClient deprecation; `next lint` also remains deprecated. No suggested replacement package was installed. The existing physical-camera, bundled-codec, deployment and security limits are unchanged. The earlier npm audit recorded eight affected entries (one high/seven moderate); no fresh vulnerability audit/remediation is claimed here. The preserved weak legacy DB administrator credential still requires reviewed rotation before public/pilot use. This checkpoint is not a deployment approval.

## Security and excluded material

The review checks all Git-eligible source files against private credential values and secret patterns, then scans the exact staged blobs. It checks staged paths, text-only content and Git file modes, and verifies that working files match their staged copies. Actual credentials are never printed in reports or included in this document.

The working-tree scan covers **123 eligible text files** with no actionable secret matches. Exact staged review covers **48 files: 30 additions, 18 modifications and no file deletions**, with no actionable secret matches; all **20 private/generated path exclusions** are checked. One cosmetic whitespace notice remains: the already applied Phase 4 SQL migration ends with an extra blank line. Its bytes are preserved; no functional SQL or other application source was edited for this review.

The following stay excluded: `.env` and local overrides; `.secrets/` and credential/account files; private database records/dumps/backups; raw/synthetic video files and recordings; `.venv/`; `node_modules/`; `.next/`; build output, caches, logs, screenshots and private verification artifacts. The repository's existing blank `.env.example` template is unchanged and is not part of this staged change set. The reviewed helpers load private values at runtime; they contain no fixed demo password or camera credential.

No application source was edited during checkpoint preparation. The code listed below is the already completed Phase 4 implementation. Documentation records this fresh review and the founder's manual result. Existing migrations 0001–0004 and business data are preserved. No files were deleted, dependency installed, container changed, remote changed, commit created, push attempted or Phase 5 work started.

## Complete reviewed file list

The list below records the exact reviewed stage set; the status and security results are updated after index verification. `M` means an existing tracked file changed; `A` means a new file is being added.

| Change | File |
| --- | --- |
| M | `README.md` |
| M | `apps/web/app/settings/page.tsx` |
| A | `apps/web/app/settings/preview-permissions.tsx` |
| M | `docs/CODEX_HANDOFF.md` |
| A | `docs/PHASE_04_CHECKPOINT.md` |
| A | `docs/PHASE_04_DEPENDENCY_REVIEW.md` |
| A | `docs/PHASE_04_IMPLEMENTATION_PLAN.md` |
| M | `docs/api_contract.md` |
| M | `docs/architecture.md` |
| M | `docs/implementation_plan.md` |
| M | `docs/phase_explanations/PHASE_03.md` |
| A | `docs/phase_explanations/PHASE_04.md` |
| M | `docs/phase_explanations/README.md` |
| M | `docs/threat_model.md` |
| A | `scripts/prepare_phase4_demo.py` |
| A | `scripts/verify_phase4_browser.py` |
| M | `services/api/Dockerfile` |
| A | `services/api/migrations/sql/0005_calibration.sql` |
| A | `services/api/migrations/versions/0005_calibration.py` |
| A | `services/api/migrations/versions/0006_preview_deadline.py` |
| A | `services/api/requirements-runtime-lock.txt` |
| A | `services/api/src/restaurant_api/calibration.py` |
| M | `services/api/src/restaurant_api/main.py` |
| M | `services/api/src/restaurant_api/management.py` |
| M | `services/api/src/restaurant_api/models.py` |
| M | `services/api/src/restaurant_api/routes.py` |
| M | `services/api/src/restaurant_api/schemas.py` |
| A | `services/api/tests/test_calibration.py` |
| M | `services/api/tests/test_database_isolation.py` |
| M | `services/api/tests/test_route_inventory.py` |
| M | `services/edge-agent/pyproject.toml` |
| A | `services/edge-agent/requirements-phase4-windows.txt` |
| A | `services/edge-agent/src/restaurant_edge/capture.py` |
| A | `services/edge-agent/src/restaurant_edge/cli.py` |
| A | `services/edge-agent/src/restaurant_edge/cloud_client.py` |
| A | `services/edge-agent/src/restaurant_edge/companion.py` |
| A | `services/edge-agent/src/restaurant_edge/process_guard.py` |
| A | `services/edge-agent/src/restaurant_edge/rtsp_gateway.py` |
| A | `services/edge-agent/src/restaurant_edge/secret_store.py` |
| A | `services/edge-agent/src/restaurant_edge/source_config.py` |
| A | `services/edge-agent/src/restaurant_edge/static/editor.js` |
| A | `services/edge-agent/src/restaurant_edge/static/index.html` |
| A | `services/edge-agent/src/restaurant_edge/static/style.css` |
| A | `services/edge-agent/src/restaurant_edge/video_sources.py` |
| A | `services/edge-agent/tests/test_cloud_client.py` |
| A | `services/edge-agent/tests/test_companion.py` |
| A | `services/edge-agent/tests/test_process_guard.py` |
| A | `services/edge-agent/tests/test_video.py` |

## Approval and publication sequence

1. Review the staged list and approve the exact local checkpoint/message. Until then, retain staged changes without creating a commit.
2. After approval, recheck the staged secret scan and create the local commit with the requested message. Verify its hash, branch, contents, clean status and private-file exclusions.
3. Ask for separate approval before pushing that exact commit to the existing GitHub remote. Do not change remotes or force-push. If the remote has diverged, report that before making integration changes.
4. Only after approved push, compare the remote `refs/heads/main` hash with the local commit and report the result. Local remote-tracking references alone are not proof of GitHub publication.
5. Stop before Phase 5.
