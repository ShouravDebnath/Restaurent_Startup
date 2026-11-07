# Database credential rotation before a pilot

**Status:** Procedure only. No existing database credential was changed in Phase 3.

The founder approved preserving the current credentials for local development. The legacy database administrator password is weak. Rotation is a required gate before public or pilot deployment, alongside TLS, production secret storage and the other security work in the [Phase 3 explanation](phase_explanations/PHASE_03.md). The API uses a separate restricted application account.

## Prepare a reviewed maintenance window

1. Obtain explicit approval for rotation and any necessary container restart/recreation. Identify the intended local database and its existing named volume. Never delete a volume or initialize a replacement database to change a password.
2. Record the existing administrator/application **role names** and which private services use them. Keep private configuration in the password manager/secret store; do not paste it into chat, Git, screenshots or tickets. Do not print full Compose configuration or container environments.
3. Take a new private backup using `python scripts/backup_phase2_database.py` from the project virtual environment. Its historical filename prefix does not affect backup contents. Verify its archive and rehearse restoration in an isolated instance. Ordinary database dumps do not back up PostgreSQL role definitions; privately record the required role/privilege recovery procedure too.
4. Prepare a unique strong random administrator password in a password manager. Review access to `.env`, `.secrets/`, backups and host/container administration. Retain the current working application and a separate administrative session during verification.

## Change the password without placing it in a command

Open an interactive administrative psql session inside the existing database container:

```powershell
docker compose exec db sh -lc 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Confirm privately that the connected user/database are the intended ones. In psql, enter:

```text
\password
```

This changes the connected role's password and asks for the new value interactively. Enter it through the hidden prompts. Do not use a literal `ALTER ROLE ... PASSWORD '...'` command, a URL, shell argument, PowerShell transcript, or copied terminal output containing the password. Preserve the existing administrative session until a separate new connection works.

Update `POSTGRES_PASSWORD` only in the private environment/secret store to the same new value. **Editing the environment alone does not rotate a PostgreSQL password on an existing volume.** Conversely, changing the database password leaves the old value in an already-created container's environment. During the approved window, refresh the database container's private configuration while retaining its existing volume, and verify recovery/health before restarting dependent services. This is a future approved operation, not a command executed by Phase 3.

Verify a genuinely authenticated new TCP connection with the new password using a hidden interactive prompt or a private in-process credential loader. A local socket connection or `pg_isready` alone may not prove password authentication. Avoid connection URLs or exception dumps that reveal credentials.

## Verify and recover safely

- Check database connectivity, `/ready`, sign-in, dashboard reads, a permitted synthetic staff action, logout, and an isolation rejection. Confirm the restricted application role remains non-owner/non-superuser and has no `BYPASSRLS` or migration privileges.
- The administrator change must not accidentally replace `APP_DB_PASSWORD`. Rotating the application login is a separate coordinated operation: change that role privately, update its secret, recreate only the API as required, and verify access. The existing `management provision` command deliberately does not reset existing role passwords and is not a rotation command.
- If a new connection fails, use the retained authorized administrative session to correct the role/configuration through hidden prompts. Do not erase data, restore a whole database just to change a password, or weaken authentication to regain access. Escalate to the reviewed local administrator recovery process if necessary.
- Confirm old credentials no longer authenticate over TCP, private files remain excluded from Git/build contexts, no secret appeared in logs/history, and backup/monitoring procedures still work. Store the new secret in the approved store and retire obsolete private copies according to the retention policy.

Record the date, role names, services checked and results, **never password values or hashes**, in a maintenance record. A successful password rotation alone does not make the application ready for public deployment.
