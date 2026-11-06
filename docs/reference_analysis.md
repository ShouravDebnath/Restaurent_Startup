# Reference Analysis

**Inputs reviewed:** `references/Restaurant_AI_Codex_Master_Blueprint.md` and `references/SR.mp4`

**Evidence note:** The video findings below are the previous Phase 1 inspection record. During the 2026-11-06 documentation handoff, the file's MP4 headers independently confirmed approximately 84.6408 seconds, 480×1068 dimensions, and 18,040,039 bytes. Frames, codecs, audio, and frame rate were not re-inspected with a decoder. The later 2026-11-07 environment inventory found `imageio-ffmpeg` already installed in `.venv`, correcting the earlier incomplete decoder-availability assessment. No audio monitoring or video upload was performed. See [CODEX_HANDOFF.md](CODEX_HANDOFF.md#reference-video-limitation) for evidence limits. Future model use requires synthetic or explicitly authorized footage and provenance; the reel establishes no evaluation accuracy.

## Video findings

- Duration: 84.64 seconds.
- Format: vertical 480x1068 H.264 video with AAC audio at approximately 41.87 FPS.
- The reel is a social-media concept/promotion, not a controlled product test.
- Representative scenes show restaurant dining areas, green polygon/table overlays, table labels such as `T03 FREE` and `T06 FREE`, a ceiling camera, a stylized table-monitoring interface, a waiting-queue/next-free-table concept, and presenter segments.
- Some scenes are clearly stylized or synthetic, including modeled people and dashboard compositions. The reel does not establish detection accuracy, camera compatibility, latency, tenant isolation, privacy behavior, or cleaning confirmation.

## Product implications

Phase 1 should establish the platform foundation and a synthetic tenant, not reproduce promotional visuals as production claims. Later UI work can borrow the useful visual language: an at-a-glance floor map, readable table labels, state colors paired with text, timers, camera health, and a task-oriented operational view.

The reel suggests additional concepts such as queue monitoring and next-free-table prediction. The master specification correctly places these outside the MVP core. They must not block the first vertical slice.

## Safety and truthfulness boundary

The overlays should be treated as visual inspiration only. The product must show `DEMO` or `UNKNOWN` when data is simulated, stale, or uncertain. A vacant visual region is not proof that a table is clean or ready. No face identity, audio, individual tracking, or unapproved footage should be implemented.

## Open verification items

- Obtain written authorization and provenance for any future pilot footage.
- Evaluate detection against manually labeled clips, not promotional scenes.
- Confirm camera angle coverage and normalized polygon calibration on each supported installation.
- Measure state accuracy, false reset alerts, update latency, and offline behavior after the edge pipeline exists.
