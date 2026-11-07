# Phase 2 local Git checkpoint: review and file manifest

**Prepared:** 2026-11-07, Asia/Dhaka.
**Status:** Prepared for explicit founder approval; no Phase 2 commit has been created.
**Branch:** `main`. Current HEAD: `6808a81b7339f241701eb03552d952827872f168` (the approved Phase 1 checkpoint).
**Proposed commit message:** `chore: phase 2 verified tenancy checkpoint`.

This checkpoint saves the existing Phase 2 implementation and its fresh review, plus a documentation-only [Phase 3 proposal](PHASE_03_IMPLEMENTATION_PLAN.md). Saving that proposal does not implement or authorize Phase 3. See the [fresh verification record](phase_explanations/PHASE_02.md#pre-phase-3-review-2026-11-07): 152 tests passed, one warning, 13.05 seconds; lint/type/build/compatibility and authenticated running-stack read/isolation/logout checks passed.

## Safety checks and limitations

- Only the 54 explicitly listed files below are proposed: 21 modified tracked files and 33 new files. Other original tracked files remain in the repository but are unchanged.
- The review changed documentation only. All existing application source, configuration, dependencies, migration files, and the master specification were preserved. No existing file was deleted.
- `.env`, `.secrets/phase2-demo-credentials.json`, other private credential/test manifests, backup archives, virtual environments, `node_modules`, `.next`, caches, database data and raw footage are excluded. Actual files and representative ignore paths were checked. The blank `.env.example` is intentional and safe to include.
- The final staged-blob review covers all 76 indexed files, compares 24 private/runtime/demo/test secret values, and checks credential assignments, private-key/token patterns and embedded credential URLs: no actionable matches. All 13 private/generated-path ignore probes pass. `git diff --cached --check` passes; the index matches this 54-file list with zero deletions, unstaged changes or eligible untracked files. Review staged blobs again before committing; ignore rules alone cannot prevent an embedded secret or a forced addition.
- One URL-pattern hit in a rejection/redaction test was reviewed: the test creates its synthetic secret randomly at runtime. No actual CCTV credential is embedded.
- **Legacy administrator password caveat:** the preserved weak password coincides with common project-label text, which appears as ordinary source/documentation text. Its administrative assignment and private file are excluded, but an exact substring search is not zero. Do not mistake a clean generated-secret/assignment scan for evidence that the old password is strong or entirely absent as ordinary text. Obtain approval for a reviewed private administrator-password rotation before public/pilot use. Do not print the value.
- npm still reports eight affected package entries (one high/seven moderate); no dependency upgrade or override was applied. Python compatibility checks are not a Python vulnerability audit. Local verification is not a production security certification.
- The original development DB container/volume and existing restaurant business records were preserved. Review logins/logout update authentication records only; write/security/migration tests ran in a separate disposable PostgreSQL instance.
- No remote was created or modified; nothing was pushed. Git configuration and HEAD remain unchanged while approval is pending. Commit approval is required by the founder's explicit instruction, separately from any Phase 3 or dependency-maintenance approval.

## Complete proposed commit file list

| Change | File |
| --- | --- |
| Modified | `.env.example` |
| Modified | `.github/workflows/ci.yml` |
| Modified | `apps/web/.dockerignore` |
| New | `apps/web/app/api/[...path]/route.ts` |
| Modified | `apps/web/app/globals.css` |
| Modified | `apps/web/app/layout.tsx` |
| Modified | `apps/web/app/page.tsx` |
| New | `apps/web/app/settings/forms.tsx` |
| New | `apps/web/app/settings/page.tsx` |
| New | `apps/web/app/settings/types.ts` |
| New | `apps/web/app/sign-in/page.tsx` |
| Modified | `docker-compose.yml` |
| Modified | `docs/api_contract.md` |
| Modified | `docs/architecture.md` |
| Modified | `docs/CODEX_HANDOFF.md` |
| Modified | `docs/implementation_plan.md` |
| New | `docs/PHASE_02_ARCHITECTURE_PROPOSAL.md` |
| New | `docs/PHASE_02_CHECKPOINT.md` |
| New | `docs/PHASE_03_IMPLEMENTATION_PLAN.md` |
| Modified | `docs/phase_explanations/PHASE_01.md` |
| New | `docs/phase_explanations/PHASE_02.md` |
| Modified | `docs/phase_explanations/README.md` |
| Modified | `docs/threat_model.md` |
| Modified | `packages/contracts/README.md` |
| Modified | `README.md` |
| New | `scripts/backup_phase2_database.py` |
| New | `scripts/start_phase2_test_db.py` |
| New | `scripts/verify_phase2_browser.py` |
| New | `scripts/verify_phase2_runtime.py` |
| New | `services/api/.dockerignore` |
| Modified | `services/api/migrations/env.py` |
| Modified | `services/api/migrations/README.md` |
| Modified | `services/api/migrations/script.py.mako` |
| New | `services/api/migrations/sql/0001_prologue.sql` |
| New | `services/api/migrations/sql/0001_security.sql` |
| New | `services/api/migrations/sql/0002_ownership.sql` |
| New | `services/api/migrations/versions/0001_phase_2_tenancy_authentication_.py` |
| New | `services/api/migrations/versions/0002_ownership.py` |
| Modified | `services/api/pyproject.toml` |
| New | `services/api/src/restaurant_api/database.py` |
| Modified | `services/api/src/restaurant_api/main.py` |
| New | `services/api/src/restaurant_api/management.py` |
| New | `services/api/src/restaurant_api/models.py` |
| New | `services/api/src/restaurant_api/routes.py` |
| New | `services/api/src/restaurant_api/schemas.py` |
| New | `services/api/src/restaurant_api/security.py` |
| New | `services/api/src/restaurant_api/settings.py` |
| New | `services/api/tests/__init__.py` |
| New | `services/api/tests/conftest.py` |
| New | `services/api/tests/test_configuration_api.py` |
| New | `services/api/tests/test_database_isolation.py` |
| New | `services/api/tests/test_route_inventory.py` |
| New | `services/api/tests/test_security.py` |
| New | `services/api/tests/test_sessions.py` |

## After approval

Recheck the staged tree against this list and repeat the staged-secret/diff checks. If a file changes, review it before committing. Create only the local commit with the message above, then verify `git status`, branch, new hash, no deletion entries, and continued private-file exclusions. Record the result in chat. Never push or configure a remote as part of this checkpoint.

While approval is pending, staged files are not a saved Git commit. The current recoverable commit remains the Phase 1 hash above. Do not begin Phase 3.
