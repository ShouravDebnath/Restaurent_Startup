# Database Migrations

Phase 2 adds real, additive PostgreSQL migrations after founder approval of the session and row-security architecture.

- `0001`: tenancy, private identity/session storage, camera/table/zone configuration, audits, and row-security policies.
- `0002`: immutable ownership, safe membership/grant administration, and supporting permission functions.
- `sql/0001_*.sql` and `sql/0002_ownership.sql` are immutable parts of those revisions. Future changes need a new revision.
- `env.py` uses SQLAlchemy model metadata. The management command supplies an administrative connection privately; the running API has no migration credentials.
- The template now renders generated operations. The Phase 1 template contained only `pass` and silently omitted them.

From PowerShell at the project root, after the database is running:

```powershell
.\.venv\Scripts\python.exe scripts/backup_phase2_database.py
.\.venv\Scripts\python.exe -m restaurant_api.management migrate
.\.venv\Scripts\python.exe -m restaurant_api.management provision
```

Do not reset the database or remove volumes. Downgrades deliberately raise an error; forward corrective migrations are the supported approach. The custom PostgreSQL DDL uses an online connection; offline `alembic upgrade --sql` is not supported or verified for these revisions. Use the explicit management command rather than the credential-free INI URL as a host connection shortcut. See [PHASE_02.md](../../../docs/phase_explanations/PHASE_02.md) for setup, verification, preservation evidence, and limitations.
