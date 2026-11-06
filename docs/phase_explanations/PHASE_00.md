# Phase 00: Specification Freeze

## Phase overview and objectives

Phase 00 turned the product idea into a written engineering plan before application code was built. The main objective was to make the product boundaries clear: what the system should do, what it must never claim, how restaurant data is separated, and how future phases will be tested.

The phase deliberately created documentation only. It did not create a web application, database tables, camera integration, or AI model.

## Features implemented

- Preserved the complete product blueprint as `docs/MASTER_SPEC.md`.
- Defined the edge-agent and cloud architecture.
- Defined the initial API routes and event shape.
- Defined privacy, security, and tenant-isolation threats.
- Created a milestone-by-milestone implementation plan.
- Defined the safe table states, including `UNKNOWN` and `RESET_PENDING`.
- Recorded that vision alone must not claim a table is clean.

## Files created or modified

- `docs/MASTER_SPEC.md`: complete product specification and build playbook.
- `docs/architecture.md`: explains the web, API, database, and local edge-agent boundaries.
- `docs/api_contract.md`: defines planned API routes, event data, errors, and authorization expectations.
- `docs/threat_model.md`: lists important assets, trust boundaries, threats, and controls.
- `docs/implementation_plan.md`: lists Phases 0 through 10, exit criteria, tests, and decisions requiring approval.

No application source files were created in this phase.

## Technologies used and why

- Markdown: keeps requirements easy for a beginner and easy for coding tools to search.
- Architecture diagrams: show how restaurant cameras, the local edge agent, the cloud API, database, and dashboard will connect.
- FastAPI, Next.js, PostgreSQL, SQLite, Docker Compose, and SSE were selected as the planned stack, but they were not implemented or tested in Phase 00.

## Step-by-step execution flow

1. Read the supplied restaurant monitoring blueprint.
2. Identify the MVP: table occupancy, stable states, reset tasks, staff confirmation, analytics, and tenant separation.
3. Separate MVP features from later features such as queue monitoring and predictions.
4. Record non-goals: facial recognition, audio monitoring, covert surveillance, and automatic cleanliness claims.
5. Define the edge-to-cloud data flow.
6. Define API and security boundaries.
7. Define the later implementation phases and their acceptance tests.
8. Validate that the five Phase 00 documents existed and contained the required concepts.

## How to run and test on Windows 11

Phase 00 has no application runtime. From PowerShell, inspect the documents with:

```powershell
Get-ChildItem .\docs -File
Get-Content .\docs\architecture.md
Get-Content .\docs\api_contract.md
Get-Content .\docs\threat_model.md
Get-Content .\docs\implementation_plan.md
```

A text/editor diagnostic check reported no errors for all five Markdown files.

## Actual testing results and remaining limitations

**Passed:**

- Five Phase 00 documents existed.
- `MASTER_SPEC.md` was non-empty.
- Required headings and safety/tenant concepts were present.
- Editor diagnostics reported no errors.

**Limitations:**

- No software behavior was tested because no application existed yet.
- At the time Phase 00 was completed, the reference video was not yet available in the workspace.
- No camera, database, authentication, browser, or AI behavior was verified.

## Problems encountered and solutions

**Problem:** The workspace started empty.

**Solution:** Created the documentation foundation first, using the supplied blueprint as the source of truth.

**Problem:** The initial reference video was not available during Phase 00.

**Solution:** Marked video-specific conclusions as `NOT VERIFIED` instead of guessing. The later video analysis is recorded in `docs/reference_analysis.md` and Phase 01 documentation.

## Phase summary

Phase 00 completed the planning gate. The project now has a clear target, safety rules, architecture, API direction, security model, and implementation sequence. No product feature was falsely presented as working. Phase 01 was then started only after this planning foundation existed.
