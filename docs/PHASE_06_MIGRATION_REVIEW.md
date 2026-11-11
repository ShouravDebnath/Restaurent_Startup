# Phase 6 migration review

**Resumed read-only check - 2026-11-11:** The retained business database is already at 0008 with zero model/schema differences. No business migration was rerun. The retained private 0007 backup was restored into a new isolated test database; applying 0008 twice preserved all 555 restored records with zero model differences. Original business/password/calibration/seating and container/volume checks passed again.

**Execution update:** The founder approved `0007` and API/web activation. The
existing database was migrated successfully; all 533 original records and
Revision 7 were preserved. The original review below is historical. The small
`0008` follow-up was separately approved and applied, preserving all 555 current
pre-migration records. Final head is `0008`; the original requests below are historical.

Prepared 2026-11-08. The original risk/approval requests below are retained; the
execution update above and final phase explanation record the later outcomes.

## Concrete change

Apply additive revision `0007` after the existing `0006`. It creates **11 new
metadata tables**: nine public device/assignment/receipt/shadow/health/audit/
notification tables and two pairing/nonce tables in the private `edge_private`
schema. It adds narrowly controlled database functions and row-level security.
It does not rewrite earlier migrations, alter table calibration geometry, change
passwords, delete records, remove containers/volumes, or activate real AI actions.

The restricted application login receives read access to the new public tables
and execution of the reviewed public entry functions. It receives no private
schema access and no direct device/operational table update rights. Internal
publication and fixture helpers are excluded from its execution grants.

AI observations remain separate shadow records. The synthetic workflow adapter
additionally refuses to execute outside an explicitly named isolated test database,
even when a synthetic device and location are approved.

## Rehearsal completed

The existing database was backed up privately and the archive listing inspected.
Its SHA-256 is `f6c4d29d235c3917e97e3f47750095b6defc00e1ef4ec21142e8fe79cfecefe5`.
The archive and restore manifests stay under ignored `.secrets/` paths.

The latest rehearsal restored the backup into a **new database on the marked
isolated test server**, applied the migration twice and compared the resulting
schema with the models. **All 533 preexisting records**, including authentication
records, were preserved; there were **zero model/schema differences**. This is a
larger count than the earlier 429 public business rows plus ten users because the
backup comparison includes the other private authentication tables as well.

Actual integration checks cover forged tenant/location/camera references,
fingerprint pairing, revoked/rotated/expired keys, replay and tampering, ordered
receipts, shadow-only effects, human precedence, private-schema/direct-write denial,
and one actual reset task after concurrent duplicate synthetic deliveries.
See the final phase explanation for the full, dated test results; the initial
regression fixture-isolation failure remains recorded there.

## Risks and execution safeguards

1. New foreign keys and functions need brief PostgreSQL metadata locks. Apply in
   one transaction with a five-second lock timeout; if a lock cannot be obtained,
   stop rather than wait indefinitely or terminate other sessions.
2. A successful migration has no automatic downgrade. Preserve the private backup
   and all original tables. Restoring the business database would require a new,
   separately reviewed decision; never automatically restore over current data.
3. The API/web images contain the new code. Verify native signatures, dependency
   versions and `pip check` in the API image before replacing the API/web services.
   Replacement briefly interrupts browser requests. Do not recreate the database
   service or its volume.
4. Enable device synchronization explicitly for local development. Keep all
   published ports on loopback. A separate host TLS listener uses a private
   development CA and the restricted application database login; it does not
   install trust globally or expose a public service.
5. Recheck all original row values, users/password hashes, cloud calibration
   Revision 7 and private seating files after migration. New metadata is allowed;
   existing credentials and business data must be preserved.
6. The old weak administrator credential and documented npm findings remain
   deployment blockers. This approval does not authorize rotation, upgrades,
   customer footage, public/pilot deployment, Git commit/push or Phase 7.

## Approval scope

The requested approval is limited to applying `0007` and its restricted runtime
grants to the existing local database, enabling the local device feature, and
replacing the API/web services with the verified images while retaining the
existing database container/volume. Any material migration change requires a new
rehearsal and review before execution.

## Separate follow-up approval: revision 0008

The final contract review found one gap: the approved plan requires a durable
per-item rejection when an event has valid owned identity fields but an unsupported
version/type/state. The first implementation refused that entire batch. This is
corrected in code and isolated tests; the existing database was held at
`0007` during review. It is now on `0008` after separate approval.

`0008` adds two fields to the new `edge_shadows` table: nullable source-generation
UUID and a false-by-default fresh-context flag. It replaces only the controlled
ingestion function. A rejected owned event saves minimal safe IDs, payload hash
and a fixed reason, advances its ordered receipt boundary, and makes the affected
shadow UNKNOWN. Further events from that rejected context stay history until a
fresh generation/context arrives. Malformed envelopes and unknown/private fields
still refuse the entire request; invalid raw fields are never persisted.

No old migration is rewritten. No business/calibration/password row or video is
changed or deleted. The same transaction and five-second lock timeout apply. The
API needs its matching rebuilt image; restarting its HTTP/TLS listeners briefly
interrupts requests. The database container and volume remain in place.

A **new backup of the current 0007 database**, including new synthetic device
setup, was restored to another isolated database. Its SHA-256 is
`3b816d2d7a0fadac189d95bb9c8e4b239b935c744ac2529ee395e7c773029271`.
The follow-up ran twice there: **all 555 existing records were preserved and model
comparison found zero differences**. Owned-invalid version/type/state tests cover
terminal receipts, safe stored payload, same-context blocking, fresh-context
recovery and retry deduplication. The full pre-follow-up sequential suite passed
518 tests; final follow-up regression results belong in the phase explanation.

Requested scope: apply `0008` to the existing local database and activate its
matching API/TLS code. No additional dependencies, credential rotation, public
deployment, commit, push or Phase 7 are included. This is a separate request
because the prior permission explicitly covered `0007`, and the user requires
approval before existing-database migrations.
