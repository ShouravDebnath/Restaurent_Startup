# Phase 5 synthetic AI detection Git checkpoint

> **Later publication outcome — 2026-11-08:** The founder separately approved this exact 53-file local commit and its normal fast-forward push. Commit `ae19ec81f342d17730ddd48845a5862a2d56a99a` was created with the requested message; independent `ls-remote` verification confirmed the same hash on GitHub `refs/heads/main`, local `main` and `origin/main`. Git was clean, with zero ahead/behind commits; exclusions and no-file-deletion checks passed. The pending-approval wording below preserves the preparation snapshot. This outcome does not validate real-person/restaurant accuracy or resolve the intermittent MP4 timing issue. The subsequent [Phase 6 proposal](PHASE_06_IMPLEMENTATION_PLAN.md) is planning only.

**Review date:** 2026-11-08, Asia/Dhaka; verification timestamps use UTC.
**Branch:** `main`.
**Parent commit:** `143831395429785a2a5647b7317aafc0fe4fdea7` (`chore: phase 4 verified video calibration checkpoint`).
**Requested commit message:** `chore: phase 5 synthetic AI detection checkpoint`.
**Approval status:** preparation only; the founder must approve the exact staged set before committing. Pushing requires a separate approval afterward. No commit or push is authorized yet.

This checkpoint saves the existing Phase 5 code, safe configuration, dependency locks, attribution, tests and documentation. It is **not full Phase 5 validation, representative restaurant evaluation or a deployment approval**. No Phase 6 work is included.

## Manual evidence and its limits

The founder reports that RF-DETR Nano ran on CPU, synthetic preview played, local seating **Revision 1** was saved, the lab showed **RUNNING**, a latest processing result was approximately **396 ms**, a Lab Table stayed **UNKNOWN** without person evidence, and Phase 4 calibration **Revision 7** was preserved. These are manual observations, not an independently repeated benchmark or an accuracy measurement. [PHASE_05.md](phase_explanations/PHASE_05.md#founder-manual-verification-and-checkpoint-review--2026-11-08) records them separately from automated results.

No authorized real-person recording is available. `SR.mp4` and other existing recordings remain unopened. Positive person detection, representative false positives/negatives, seated/occluded-person quality, table assignment and restaurant occupancy accuracy remain **unverified**. Synthetic/fake-box tests must not be described as real-world validation. AI results remain local shadow observations and cannot overwrite operational dashboard states or staff decisions.

## Fresh checkpoint verification

| Check | Actual result |
| --- | --- |
| Initial full run, overlapping the frontend build | **444 passed, 1 failed, 1 warning**, 105.92 seconds; retained as a failed historical run |
| Separate rerun of the affected 5/20 FPS pacing cases | **2 passed**, 1.20 seconds |
| Complete suite rerun without overlapping the frontend build | **445 passed, 0 failed, 0 skipped, 1 warning**, 94.62 seconds; completed 2026-11-08 at 09:54:32 UTC |
| Further independent MP4 pacing investigation | **10 runs × 2 cases = 20 passes**; the same unchanged assertions ran each time |
| Frontend and static checks | Frontend lint, TypeScript, production build, Ruff, `pip check`, both local JavaScript syntax checks and quiet Compose validation **passed** |

The first failure was `test_real_mp4_different_frame_rates_and_monotonic_pacing[5]`. Its two-frame span was about **148.41 ms**, just below the assertion's **150 ms** lower bound. Inspection found an intermittent timing/expectation mismatch in existing MP4 playback: `OpenCVSource` schedules frames relative to file opening, while this assertion measures the gap relative to the first delivered frame. A delayed first read can shorten that gap as playback catches up. This is not evidence of a Phase 5 detector regression; both the pacing implementation and test are byte-equivalent to the Phase 4 checkpoint after newline normalization.

A separate diagnostic using a newly generated two-frame clip reproduced this mechanism without changing the application or test. With no injected delay, the gap was **198.811 ms**. With a deliberate **70 ms** delay before the first read, delivery times were approximately **77.703 ms** and **200.833 ms** after opening, giving a **123.130 ms** gap. Both frames and media positions remained correct and ordered. This supports classifying the original failure as intermittent and load-sensitive; it does not prove the exact scheduler event in the first failed run. **The timing assertion remains unchanged and may recur under load. No pacing fix is claimed.** A separately scoped future decision should clarify catch-up versus minimum inter-frame spacing and retain meaningful timing coverage.

No test was weakened, removed or skipped. The one remaining warning is the existing Starlette/HTTPX deprecation warning; no installation was performed to suppress it. The passing full rerun and the initial failure are both retained in private evidence.

No dependency install/upgrade, model acquisition, retraining, benchmark rerun or system/container modification was needed for checkpoint preparation. Earlier six/seven-group browser and ten-minute CPU results in the phase explanation remain historical and were not rerun for this checkpoint.

The suite selects the retained isolated PostgreSQL test database, whose name is checked before migrations/seeding; it does not target the restaurant database. `RFDETR_TEST_CATALOG` is set to the approved private catalog so the four actual-model cases run rather than skip. Raw footage is generated geometric data, and simulated boxes/authority remain separately identified.

## Database and private-data preservation

The pre-checkpoint read-only baseline contains **429 public records**, **10 user rows**, saved calibration including **Revision 7**, and **four private seating-related files**, including one Revision 1 profile record. The earlier 427-row implementation baseline predates one preview grant and its audit entry; those two rows already existed when this checkpoint review began. Compare against the new post-manual-test baseline, without rewriting earlier historical reports.

The post-test read-only comparison **passed**: every captured business/user/polygon record and all four local profile files match the pre-checkpoint baseline. Revision 7 and the Revision 1 seating profile remain present. All original eligible files are still present; application/scripts, installed dependency versions, `.env`, Git configuration and parent HEAD are unchanged during this review. Only documentation was edited for checkpoint preparation; the Phase 5 application changes already existed before this review. Git saves application behavior, not the private database, model artifacts or saved seating-profile contents. Those files remain in their existing local locations and are not supplied by a fresh clone.

## Security review and exclusions

The working-tree scan checks Git-eligible files against privately loaded credential values and credential patterns without printing them. The final scan must also inspect the **exact staged blobs**, file modes and paths, and compare staged content with the reviewed working copies. Model checksums and public license/source URLs identify artifacts; they are not passwords or authorization tokens.

Excluded material includes `.env`/local overrides, `.secrets/`, private credentials/accounts/session data, camera sources/credentials, native `.pth`/`.pt`/Safetensors/ONNX assets and sidecars, recordings/raw/synthetic MP4, database records/backups, seating profile data, `.venv/`, the isolated exporter under `.cache/`, `node_modules/`, `.next/`, generated caches/build output/logs/screenshots and private verification evidence. Full Apache attribution/license texts and hash-locked requirement **text files** are safe checkpoint content; actual downloaded packages and weights are excluded.

The IDE context included a credential value. It was not copied into project documentation or the staged set. Known-value checks include the private credential files. The checkpoint does not rotate credentials; handle rotation separately before shared/pilot deployment. The existing weak administrator credential, earlier npm findings (one high/seven moderate, historical audit), native-library audit gaps and deployment hardening remain unresolved. No fresh vulnerability audit or security certification is claimed.

**Final staged review:** all **53 staged files** passed the exact-blob scan against **54 privately collected credential candidates** and credential/path patterns, with **zero findings**. The broader working-file scan covered **158 Git-eligible files**. All **23 ignore probes** and **141 local documentation links/anchors** passed. Every staged entry is a regular text file, its content matches the reviewed working copy after newline normalization, and the staged set matches the manifest below. `git diff --cached --check` passed. No deletion, unstaged tracked change or untracked Git-eligible file remains outside this reviewed set. Ignored private files remain local. These bounded automated checks plus review reduce accidental disclosure risk; they are not a guarantee against every possible secret.

## Complete reviewed file list

`A` means a new Git file; `M` means an existing file changed. The **53-file** manifest below contains **18 modified** files and **35 new** files. It is generated from the explicit reviewed candidate set and checked against the Git index. No file deletion is allowed. Safe documentation updates to Phase 4 preserve historical results and explain later Phase 5 compatibility; they do not change earlier application behavior.

| Change | Path |
| --- | --- |
| M | `.gitignore` |
| M | `README.md` |
| M | `docs/CODEX_HANDOFF.md` |
| M | `docs/PHASE_04_CHECKPOINT.md` |
| M | `docs/PHASE_04_IMPLEMENTATION_PLAN.md` |
| A | `docs/PHASE_05_CHECKPOINT.md` |
| A | `docs/PHASE_05_DEPENDENCY_REVIEW.md` |
| A | `docs/PHASE_05_IMPLEMENTATION_PLAN.md` |
| A | `docs/PHASE_05_RFDETR_REVIEW.md` |
| M | `docs/api_contract.md` |
| M | `docs/architecture.md` |
| M | `docs/implementation_plan.md` |
| M | `docs/phase_explanations/PHASE_04.md` |
| A | `docs/phase_explanations/PHASE_05.md` |
| M | `docs/phase_explanations/README.md` |
| M | `docs/threat_model.md` |
| A | `scripts/benchmark_phase5_rfdetr.py` |
| A | `scripts/evaluate_phase5_intervals.py` |
| A | `scripts/export_phase5_rfdetr.py` |
| A | `scripts/verify_phase5_browser.py` |
| A | `scripts/verify_phase5_rfdetr_browser.py` |
| M | `services/edge-agent/pyproject.toml` |
| A | `services/edge-agent/requirements-phase5-rfdetr-export-windows.txt` |
| A | `services/edge-agent/requirements-phase5-windows.txt` |
| A | `services/edge-agent/src/restaurant_edge/analysis.py` |
| A | `services/edge-agent/src/restaurant_edge/analysis_config.py` |
| A | `services/edge-agent/src/restaurant_edge/analysis_metrics.py` |
| A | `services/edge-agent/src/restaurant_edge/analysis_routes.py` |
| A | `services/edge-agent/src/restaurant_edge/association.py` |
| M | `services/edge-agent/src/restaurant_edge/capture.py` |
| M | `services/edge-agent/src/restaurant_edge/cli.py` |
| M | `services/edge-agent/src/restaurant_edge/cloud_client.py` |
| M | `services/edge-agent/src/restaurant_edge/companion.py` |
| A | `services/edge-agent/src/restaurant_edge/detectors/__init__.py` |
| A | `services/edge-agent/src/restaurant_edge/detectors/base.py` |
| A | `services/edge-agent/src/restaurant_edge/detectors/factory.py` |
| A | `services/edge-agent/src/restaurant_edge/detectors/onnx_detector.py` |
| A | `services/edge-agent/src/restaurant_edge/detectors/rfdetr.py` |
| A | `services/edge-agent/src/restaurant_edge/evaluation.py` |
| A | `services/edge-agent/src/restaurant_edge/state_engine.py` |
| A | `services/edge-agent/src/restaurant_edge/static/analysis.html` |
| A | `services/edge-agent/src/restaurant_edge/static/analysis.js` |
| M | `services/edge-agent/src/restaurant_edge/static/editor.js` |
| M | `services/edge-agent/src/restaurant_edge/static/index.html` |
| A | `services/edge-agent/tests/test_analysis_api.py` |
| A | `services/edge-agent/tests/test_analysis_domain.py` |
| A | `services/edge-agent/tests/test_analysis_evaluation.py` |
| A | `services/edge-agent/tests/test_analysis_metadata.py` |
| A | `services/edge-agent/tests/test_analysis_workers.py` |
| A | `services/edge-agent/tests/test_rfdetr_adapter.py` |
| A | `services/edge-agent/tests/test_rfdetr_real.py` |
| A | `services/edge-agent/third_party/RFDETR.md` |
| A | `services/edge-agent/third_party/RFDETR_LICENSE.txt` |

## Approval and publication procedure

1. Finish verification and exact staged-secret/index review; show the founder this complete manifest and actual results.
2. Ask for explicit approval of the local commit using the requested message. Do not commit while waiting.
3. After approval, recheck that the index still matches the reviewed set, commit locally and verify hash, branch/status and exclusions.
4. Ask separately before pushing that exact commit to the existing `origin/main`; do not create/modify a remote or force-push.
5. After an approved normal push, use a read-only remote lookup to verify that GitHub `refs/heads/main` equals the approved local commit. Report synchronization and stop; do not begin Phase 6.
