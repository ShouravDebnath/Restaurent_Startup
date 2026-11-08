# Phase Explanations

This folder explains each completed development phase in beginner-friendly English. The explanations record what was actually built, how to run it on Windows 11, what tests really passed, and what remains unverified.

Start with the [Codex project handoff](../CODEX_HANDOFF.md) for the complete project understanding, dated independent verification, known risks, roadmap, and Phase 2 requirements. The documentation handoff is not a new numbered development phase. Earlier test reports are retained as historical records; current limitations are identified separately.

| Phase | Document | Status |
| --- | --- | --- |
| 00 | [PHASE_00.md](PHASE_00.md) | Completed |
| 01 | [PHASE_01.md](PHASE_01.md) | Foundation verified locally on 2026-11-07; environment/repository fixes complete, dependency warnings remain |
| 02 | [PHASE_02.md](PHASE_02.md) | Implemented/verified; saved in local checkpoint `62ad229`; original 152 tests retained in Phase 3 |
| 03 | [PHASE_03.md](PHASE_03.md) | Fresh verification: 262 tests, 10 dashboard-browser groups, 4 restart groups; existing `3342c42` confirmed on GitHub; retained by Phase 4 regression |
| 04 | [PHASE_04.md](PHASE_04.md) | Local synthetic video/calibration verified: 333 tests, nine browser groups; checkpoint `1438313` published after separate approvals; physical cameras unverified |
| 05 | [PHASE_05.md](PHASE_05.md) | Real RF-DETR CPU/synthetic workflow implemented: 445 tests, six real-model browser groups plus seven prior groups; representative person/restaurant evaluation pending |

**Phase 5 checkpoint review — 2026-11-08:** [The complete checkpoint manifest](../PHASE_05_CHECKPOINT.md) records founder-reported synthetic verification, seating Revision 1, preserved calibration Revision 7, a fresh **445-test pass** and frontend/static checks. The initial 444-pass/one-failure MP4 timing run remains documented; independent reruns pass and a separate diagnostic explains the remaining timing sensitivity without weakening tests. The current 429 business records, ten users and private seating data are preserved. Real-person/restaurant accuracy is unverified; Phase 5 is not fully validated. Local commit and push require separate approvals.

**RF-DETR implementation — 2026-11-08:** After separate founder download/installation approvals, the official Nano checkpoint is verified, exported locally and integrated with the protected synthetic shadow lab. The [current Phase 5 explanation](PHASE_05.md) records actual hashes, numerical comparison, 445-test results, Windows instructions and CPU/evaluation limitations. The existing runtime, restaurant database and Revision 7 are preserved. No Phase 6, commit or push was started; the earlier review-only statements below preserve their approval history.

**RF-DETR Nano review — 2026-11-08:** [The acquisition and integration proposal](../PHASE_05_RFDETR_REVIEW.md) records official model-specific Apache-2.0 terms, exact artifacts/digests, the proposed 65-package isolated exporter and CPU/security/evaluation limits. No weights were downloaded or packages installed; the dry run cached package archives for review. The founder permits only synthetic footage; no authorized person recording is available. Earlier tests remain dated implementation evidence, not new review test results.

**Phase 5 work — 2026-11-08:** [The approved plan](../PHASE_05_IMPLEMENTATION_PLAN.md) now has a [partial implementation record](PHASE_05.md). The founder approved three project-only runtime packages but held model acquisition pending licensing clarification and allowed only synthetic footage. Fresh 333-test baseline and expanded 413-test run passed. Phase 5 remains incomplete; no pretrained inference or real-world validation is claimed. The original planning verification is preserved in the proposal.

**Phase 4 checkpoint preparation — 2026-11-08:** The founder manually verified synthetic playback, authorization and Revision 7 reload. Fresh checkpoint tests pass all 333 cases and frontend/static checks; read-only checks preserve Revision 7 and the current database. [The complete checkpoint manifest](../PHASE_04_CHECKPOINT.md) lists the proposed staged files and separate commit/push approval gates. The earlier nine browser groups remain dated implementation evidence.

A phase explanation must be updated if later work changes the behavior or limitations of that phase.

**Phase 4 implementation — 2026-11-08:** [The approved local video/calibration plan](../PHASE_04_IMPLEMENTATION_PLAN.md) is implemented; [PHASE_04.md](PHASE_04.md) records features, files, Windows commands, actual results and hardware/security limits. Phase 3 checkpoint `899f743` was committed and pushed after separate approvals, with publication verified; the older pending-approval record below is historical.

Before Phase 3, the [fresh Phase 2 review](PHASE_02.md#pre-phase-3-review-2026-11-07) reran all 152 tests successfully. The founder approved the [54-file checkpoint](../PHASE_02_CHECKPOINT.md), saved as `62ad229` on `main`, and subsequently approved [Phase 3 and its architecture decisions](../PHASE_03_IMPLEMENTATION_PLAN.md). Use [PHASE_03.md](PHASE_03.md) for current dashboard behavior and verification. The checkpoint manifest retains its pre-commit preparation record.

The [2026-11-07 pre-Phase 2 environment check](PHASE_01.md#pre-phase-2-environment-and-repository-check-2026-11-07) records the approved Python repair and container hardening, actual tests, database preservation, Git protection, and pending security recommendations. It is Phase 1 maintenance, not Phase 2 implementation.

The [Git checkpoint configuration cleanup](PHASE_01.md#git-checkpoint-configuration-cleanup-2026-11-07) preserves the first preparation record. Checkpoints `6808a81` (Phase 1) and `62ad229` (Phase 2) are ancestors of `3342c42` (`V1`), which already saves Phase 3 and was confirmed on GitHub `origin/main`. The [Phase 2 authentication/isolation design](../PHASE_02_ARCHITECTURE_PROPOSAL.md) remains the foundation. The [Phase 3 checkpoint review](../PHASE_03_CHECKPOINT.md) records fresh verification and six proposed documentation files awaiting local-commit approval, followed by a separate push approval. That checkpoint review predates the separately approved Phase 4 implementation; current Phase 4 results are above.
