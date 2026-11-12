# Phase 7 additive migration and local activation review

**Later A02 Analytics correction — 2026-11-12:** The reporting fix uses the
existing `0009` schema and unchanged hashed migrations below. Only API/web code
was refreshed; no further migration, backfill or business-record change.
[Current verification](phase_explanations/PHASE_07.md#a02-demo-analytics-correction--2026-11-12).

**Prepared/applied:** 2026-11-12, Asia/Dhaka. **Approval:** separately granted by
the founder for exact `0009`, restricted runtime grants and matching local
API/web activation. Application is complete; existing locations remain OFF.
Public/pilot deployment is not authorized.

The implemented workflow and report routes need revision `0009` after existing
`0008`. [The explanation](phase_explanations/PHASE_07.md) describes behavior and
tests. No new dependencies, credential rotation, public deployment, Phase 8,
commit or push are part of this change.

## Exact changes and risks

- Nine additive workflow/provenance/quality tables; scoped foreign keys, RLS,
  indexes and read-only runtime grants.
- Scoped unique constraints on existing receipt/task/event identifiers. Existing
  primary IDs already satisfy uniqueness; rehearsal checks actual records.
- Controlled functions/triggers derive suggestions atomically with receipts,
  protect staff decisions and capture attempts/audits. The old table-action entry
  delegates unchanged for unenrolled tables and rejects bypasses for enrolled ones.
- Existing locations have no policy row and remain OFF. No legacy session or
  camera-coverage history is invented or backfilled.
- PostgreSQL transactional DDL may briefly lock affected tables. Apply locally
  with device writers paused, then provision the existing restricted login using
  its existing private credentials. A failure rolls back its transaction; do not
  drop volumes, reset migration history or use a destructive downgrade.
- Activate matching API/web code only after migration/grants succeed. The prepared
  `restaurant-phase7-api-reviewed` and `restaurant-phase7-web-reviewed` images
  copy verified code/assets onto the existing installed runtimes. No package
  installation or dependency upgrade was needed or is requested. Retain the DB
  container, volume and all private configuration. A brief application interruption
  is expected. Restart the existing local TLS listener with matching code if used.

## Backup and rehearsal

A fresh private backup and isolated restored-backup rehearsal are complete
for this exact revision. The final rehearsal preserved 580 records,
upgraded twice to head `0009`, provisioned restricted grants, found zero
SQLAlchemy/schema differences and left all locations OFF. The live business DB
was separately checked read-only at `0008` with all baseline rows/files intact.

The fresh archive `.secrets/backups/phase2-before-20261111T184341Z-00d8a62f.dump`
was inspected and restored only to new isolated database
`phase2_security_test_phase7_restore_812b349c23` for the final recovery fix. Its SHA256 is
`c5ef6874f4e6f2b7e180a1df82900986306891866f43d849011f3f8f77cc1e3d`.
That rehearsal preserved all **580** records, ran upgrade twice, checked restricted
grants, left policies OFF and found **zero** model/schema differences.

Exact migration SHA256 values:

| File | SHA256 |
| --- | --- |
| `0009_workflow_schema.sql` | `d78f4b771867b9ef6b8c56dc1ff8a14c04bf1b8e813ca727b820fc1f81520ff2` |
| `0009_workflow_security.sql` | `8aa548c9781ed14b466fe68b60c1f68048dde48afa555040f1dda29a1c1ab578` |
| `0009_reviewed_workflow.py` | `116edfaff319a96b8110264f97726eeed10b3efddf3538d2321800a339f2648b` |

The first complete rerun recorded **633 passes and one native freshness failure**
while a frontend build overlapped. The sequential rerun passed **634 tests** in
234.37 seconds, retaining all original cases, thresholds and timeouts. The final
report-admission and protected-context recovery fixes passed **74 affected checks**.
The recovery fix clears only a rejection-context flag after valid fresh evidence
from a new source generation; it never changes the protected operational state.
The updated actual Edge walkthrough passed **ten groups**, including human
workflow, correction, lost-response retry, isolation, offline reconnect, location
switch and a real proxy CSV download. Pre-approval regression passed **636 tests**, zero skips, one existing warning, in
233.61 seconds. All ten browser groups also pass using the prepared Linux web
image against a new isolated PostgreSQL database.

A successful rehearsal is not permission to migrate the existing database.

## Approved local activation and actual outcome

Apply exact reviewed `0009` and runtime grants to the existing local database,
then activate matching API/web/local TLS code. Preserve all then-current rows,
ten existing user/password records, credentials, Revision 7, seating Revision 1,
four seating files and original database volume. Any new demonstration resources
must be explicitly synthetic additions; existing locations stay OFF unless
separately selected by a permitted manager.

After approval, capture a final private pre-apply inventory/backup, apply forward,
verify all protected row values and schema/grants, then demonstrate only synthetic
workflow. Stop and report any unexpected difference instead of resetting data.

The reviewed request above was subsequently approved. Immediately before applying,
a new private archive was created and rehearsed on another isolated restored
database: `.secrets/backups/pre-approved-phase7-20261111T191740-eeff9d.dump`,
SHA256 `842a5b3f8bf52c8052c12d14dc4fa08105e2b2771098b612f1c0b951d01d6a9c`.
Only then were the exact three hashed artifacts applied to the existing local
database. Head is `0009`, zero model/schema differences; all 580 pre-apply records,
PostgreSQL role password verifiers, ten users/password records, four seating
files, calibration Revision 7, seating Revision 1 and private credentials remain
preserved. The original database container and volume are unchanged.

Matching API/web images were activated with existing environment values and
installed dependencies preserved. The local TLS listener uses its existing
certificate/key. A related post-activation CSV framing defect was fixed without
changing the approved migration: Next.js strips Content-Length, so the API also
sends `X-Report-Bytes` and the UI verifies decoded bytes before saving. Ten
isolated Linux-web browser groups reject incomplete/unframed downloads and
verify the normal human workflow. No additional migration or install was used.

Live checks on the activated stack pass A/B own-scope dashboard/workflow/report/
CSV/SSE, opposite-tenant 404, anonymous 401, OFF defaults and CA-verified local
TLS readiness/routes. Five newly added verification sessions were all revoked;
no original row was changed. Existing locations were not enrolled and no
operational demonstration was written to the business database.

No commit, push, public deployment or Phase 8 was performed.

Post-activation final regression passed **636 tests**, zero skips, one existing
warning, in **235.33 seconds**, after the CSV completion fix. The preceding full
run had 635 passes and one native freshness failure (238.64 seconds); the exact
native test passed separately in 69.09 seconds and then in the full rerun.
Tests, thresholds and native deadlines were not weakened or skipped. Intermittent
CPU/end-to-end freshness remains a documented deployment/capacity limitation.
