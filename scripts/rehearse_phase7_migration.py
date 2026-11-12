"""Restore a private backup to a NEW marked test database; never migrate business data."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from restaurant_api import edge_models, workflow_models  # noqa: F401
from restaurant_api.management import migrate, provision_runtime
from restaurant_api.models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    backup = args.backup.resolve(strict=True)
    if (
        not backup.is_relative_to((ROOT / ".secrets/backups").resolve())
        or backup.suffix != ".dump"
    ):
        raise RuntimeError("Choose a private backup archive")
    config = json.loads(
        (ROOT / ".secrets/phase2-test.json").read_text(encoding="utf-8")
    )
    container = config["container"]
    info = json.loads(
        subprocess.check_output(["docker", "inspect", container], text=True)
    )[0]
    if (
        not container.startswith("restaurant-phase2-test-")
        or info["Config"].get("Labels", {}).get("restaurant.phase2-test") != "true"
        or info["Mounts"]
        or "/var/lib/postgresql/data" not in info["HostConfig"].get("Tmpfs", {})
    ):
        raise RuntimeError("Marked isolated test server required")
    name = "phase2_security_test_phase7_restore_" + uuid4().hex[:10]
    url = URL.create(
        "postgresql+psycopg",
        username=config["username"],
        password=config["password"],
        host="127.0.0.1",
        port=config["port"],
        database=config["database"],
    )
    admin = create_engine(url, hide_parameters=True)
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
        db.exec_driver_sql('CREATE DATABASE "' + name + '"')
    with backup.open("rb") as archive:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "pg_restore",
                "--no-owner",
                "--no-privileges",
                "--username",
                config["username"],
                "--dbname",
                name,
            ],
            stdin=archive,
            capture_output=True,
            check=False,
        )
    if result.returncode:
        raise RuntimeError("Private restore failed; no business data changed")
    engine = create_engine(url.set(database=name), hide_parameters=True)
    records = {}
    with engine.connect() as db:
        for schema in ("public", "identity"):
            for table in db.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname=:s"),
                {"s": schema},
            ):
                if table != "alembic_version":
                    records[schema + "." + table] = db.scalars(
                        text("SELECT to_jsonb(t) FROM " + schema + "." + table + " t")
                    ).all()
    private = ROOT / ".secrets/phase7-implementation"
    private.mkdir(exist_ok=True)
    (private / ("restored-records-" + name + ".json")).write_text(
        json.dumps(records), encoding="utf-8"
    )
    migrate(engine)
    migrate(engine)
    import secrets

    provision_runtime(
        engine,
        "restaurant_phase7_rehearsal_" + uuid4().hex[:8],
        secrets.token_urlsafe(36),
    )
    with engine.connect() as db:
        for table, rows in records.items():
            actual = db.scalars(text("SELECT to_jsonb(t) FROM " + table + " t")).all()
            assert all(
                any(all(x.get(k) == v for k, v in row.items()) for x in actual)
                for row in rows
            ), "Original restored row changed"
        differences = compare_metadata(
            MigrationContext.configure(db, opts={"include_schemas": True}),
            Base.metadata,
        )
        assert not differences, "Model/schema mismatch"
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0009"
        assert db.scalar(text("SELECT count(*) FROM workflow_policies")) == 0
    report = {
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "isolated_database": name,
        "backup": str(backup.relative_to(ROOT)),
        "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        "preserved_records": sum(map(len, records.values())),
        "model_differences": len(differences),
        "migration_head": "0009",
        "default_workflow": "OFF",
        "runtime_grants_checked": True,
        "business_database_untouched": True,
    }
    (private / "migration-rehearsal.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    engine.dispose()
    admin.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- keep database/credential diagnostics private at the CLI boundary
        private = ROOT / ".secrets/phase7-implementation"
        private.mkdir(exist_ok=True)
        (private / ("rehearsal-failure-" + uuid4().hex + ".txt")).write_text(
            str(error), encoding="utf-8"
        )
        print(
            "Isolated rehearsal stopped:",
            type(error).__name__,
            "; diagnostics retained privately.",
        )
        raise SystemExit(1) from None
