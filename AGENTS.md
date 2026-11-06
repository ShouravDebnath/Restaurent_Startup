# Engineering Rules

Read `docs/MASTER_SPEC.md` before implementing product behavior.

- Work one milestone at a time and report actual verification results.
- Use synthetic or explicitly authorized footage only.
- Keep raw video local by default; never add facial recognition, audio monitoring, or automatic cleanliness claims.
- Enforce tenant and location authorization in the backend, not only in the UI.
- Use UTC for stored events and the location IANA time zone for display and analytics.
- Mark unsupported hardware, unverified metrics, and missing external services explicitly.
- Keep secrets out of Git, logs, browser responses, and test fixtures.

## Phase Documentation Rule

- After completing every development phase, automatically create or update its explanation in `docs/phase_explanations/`.
- Use separate files: `PHASE_00.md`, `PHASE_01.md`, `PHASE_02.md`, and so on.
- Each explanation must contain the phase overview and objectives, implemented features, created or modified files and their purposes, technologies used and their explanations, step-by-step execution flow, Windows 11 run and test instructions, actual testing results and remaining limitations, problems encountered and solutions, and a phase summary.
- Write explanations in beginner-friendly English with practical examples.
- Maintain `docs/phase_explanations/README.md` as an index.
- Never claim untested functionality is working.
- Update documentation whenever later changes affect previous phases.
- Always explain the completed phase in chat.
- Stop after each development phase and wait for founder approval before proceeding.
