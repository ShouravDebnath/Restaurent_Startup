# Restaurant AI Monitoring

Privacy-first restaurant table operations SaaS. Phase 1 provides the repository foundation, a static DEMO page, health endpoints, and a public synthetic demo response. Authentication, tenant isolation, real camera access, and AI inference are not implemented yet. The web page does not fetch API data, and the API does not access PostgreSQL.

## Documentation and current status

- [Codex project handoff](docs/CODEX_HANDOFF.md): startup vision, actual implementation, independent verification, risks, roadmap, and Phase 2 requirements.
- [Master specification](docs/MASTER_SPEC.md): product authority and development milestones.
- [Implementation plan](docs/implementation_plan.md): milestone sequence and current blockers.
- [Phase explanations and index](docs/phase_explanations/README.md): beginner-friendly phase records.

The 2026-11-07 pre-Phase 2 check restored the existing Docker stack, repaired the project `.venv` with founder-approved project dependencies, initialized Git, and added ignore rules. The four starter tests, Python lint, frontend lint/types/build, live HTTP checks, and read-only PostgreSQL checks passed. Published ports are restricted to this PC, and database/API readiness checks are configured. The existing database volume was retained. See the [latest Phase 1 environment report](docs/phase_explanations/PHASE_01.md#pre-phase-2-environment-and-repository-check-2026-11-07) for actual results, warnings, and approvals. Phase 2 has not started.

## Repository layout

- `apps/web`: Next.js dashboard shell.
- `services/api`: FastAPI cloud API and demo tenant endpoint.
- `services/edge-agent`: Python edge-agent package placeholder.
- `packages/contracts`: versioned shared contract notes.
- `docs`: specification, architecture, API, threat model, and implementation plan.
- `references`: supplied blueprint and reference reel; do not treat the reel as accuracy evidence.

## Local setup

The proposed Git checkpoint includes a sanitized `.env.example`, `docker-compose.yml`, and `services/api/alembic.ini`. Real local values belong in the ignored `.env` file. Compose supplies database credentials using `PGUSER`, `PGPASSWORD`, and `PGDATABASE`, so the versioned database URLs contain no credentials. Original local configuration copies are preserved under ignored `.secrets/`. The generated `next-env.d.ts` is excluded; Next.js regenerates it.

1. Preserve an existing `.env`. For a fresh installation, copy `.env.example` to `.env` and fill in `POSTGRES_USER` and `POSTGRES_PASSWORD`. Keep the current values for an existing database volume; editing environment values alone does not rotate an existing database password. The template intentionally leaves these fields empty and Compose refuses to render/start without them.
2. Start Docker Desktop. For the existing local images, use `docker compose up -d --no-build --pull never --wait --wait-timeout 60`. A fresh image build uses `docker compose up --build --wait` and installs image dependencies; obtain installation approval when required.
3. Open `http://localhost:3000` for the web shell.
4. Check `http://localhost:8000/health` for the API.
5. Check `http://localhost:8000/v1/demo/tenant` for synthetic demo data.

Node.js/npm and Docker are required for the full stack. Python tests can run independently from `services/api` and `services/edge-agent`.

These are development setup instructions. The earlier handoff was documentation-only; the later environment check started existing software, installed only approved Python project dependencies, and applied approved container configuration changes. The subsequent Git preparation only sanitizes files; it does not apply this new credential wiring to existing containers. Compose preserves the named PostgreSQL volume and publishes its ports on `127.0.0.1`. `API_PORT` and `WEB_PORT` configure the host ports. Use synthetic or explicitly authorized inputs only. Do not delete volumes, reset databases, or install software without permission. This remains a development setup with public synthetic routes and local environment-based credentials; production secret management and a fresh container build/start with the sanitized configuration are not verified by Git preparation.

## Verification commands

From PowerShell at the repository root, use the repaired project environment:

```powershell
Push-Location services/api
& ..\..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
& ..\..\.venv\Scripts\python.exe -m ruff check --no-cache .
Pop-Location

Push-Location services/edge-agent
& ..\..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
& ..\..\.venv\Scripts\python.exe -m ruff check --no-cache .
Pop-Location

Push-Location apps/web
npm run lint
& .\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
Pop-Location

.\.venv\Scripts\python.exe -m pip check
docker compose config --quiet
docker compose ps
```

These commands are Phase 1 checks. They do not prove camera compatibility, AI accuracy, production security, or deployment readiness.

The November 6 handoff's Anaconda commands remain historical evidence. The current project `.venv` works without `PYTHONPATH` overrides because both local packages are installed in editable mode. CI and future web image builds use `npm ci` with the existing lockfile; this check did not install or upgrade npm packages or rebuild Docker images.

Remaining findings: npm audit reports 8 affected package entries (1 high, 7 moderate), `next lint` is deprecated, and the newly resolved Python test stack emits a Starlette/HTTPX deprecation warning. Git was initialized on local `main` without commits or a remote during the environment check; use `git status` and `git log` for the current checkpoint state. `.gitignore` protects environment files, credential files, dependencies, caches, databases, footage, and model artifacts while allowing secret-free templates and lockfiles for review. The private `.env` and configuration backups must remain outside Git. Environment-based database passwords are a local development mechanism, not a production secret-management solution. Ignore rules do not detect secrets embedded in source or prevent forced additions; review each future commit.
