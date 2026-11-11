from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from restaurant_api.database import set_identity
from restaurant_api.management import migrate, seed_demo

TENANT_TABLES = [
    "organizations",
    "locations",
    "memberships",
    "location_grants",
    "cameras",
    "dining_tables",
    "table_zones",
    "audit_logs",
]


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_rls_restricts_queries_even_without_application_filter(suite, table):
    org_id = suite.seed["organizations"]["a"]["id"]
    actor_id = suite.seed["accounts"]["a_owner"]["user_id"]
    column = "id" if table == "organizations" else "organization_id"
    with Session(suite.runtime) as db, db.begin():
        assert db.scalar(text(f"SELECT count(*) FROM public.{table}")) == 0
        set_identity(db, actor_id)
        rows = db.scalars(text(f"SELECT DISTINCT {column} FROM public.{table}")).all()
        assert set(map(str, rows)) == {org_id}


def test_runtime_has_no_privileged_or_destructive_access(suite):
    with suite.runtime.connect() as connection:
        flags = connection.execute(
            text(
                "SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user"
            )
        ).one()
        assert not any(flags)
        assert not connection.scalar(
            text("SELECT has_schema_privilege(current_user,'public','CREATE')")
        )
        assert not connection.scalar(
            text("SELECT has_table_privilege(current_user,'dining_tables','DELETE')")
        )
        assert not connection.scalar(
            text("SELECT has_table_privilege(current_user,'audit_logs','UPDATE')")
        )
        assert not connection.scalar(
            text("SELECT has_table_privilege(current_user,'dining_tables','TRUNCATE')")
        )
    for table in ("users", "sessions", "login_buckets"):
        with pytest.raises(DBAPIError), suite.runtime.begin() as connection:
            connection.execute(text(f"SELECT * FROM identity.{table}"))


def test_foreign_updates_and_inserts_are_blocked_by_database(suite):
    a, b = suite.seed["organizations"]["a"], suite.seed["organizations"]["b"]
    actor = suite.seed["accounts"]["a_owner"]["user_id"]
    with Session(suite.runtime) as db, db.begin():
        set_identity(db, actor)
        result = db.execute(
            text("UPDATE dining_tables SET label='Rejected' WHERE id=:id"),
            {"id": b["resources_1"]["table_id"]},
        )
        assert result.rowcount == 0
    with pytest.raises(DBAPIError), Session(suite.runtime) as db, db.begin():
        set_identity(db, actor)
        db.execute(
            text(
                "INSERT INTO dining_tables(id,organization_id,location_id,label) "
                "VALUES(:id,:org,:loc,'Rejected')"
            ),
            {"id": uuid4(), "org": b["id"], "loc": b["locations"][0]},
        )
    # Column privileges now reject reparenting before the immutable-ownership trigger.
    with pytest.raises(DBAPIError), Session(suite.runtime) as db, db.begin():
        set_identity(db, actor)
        db.execute(
            text("UPDATE dining_tables SET location_id=:loc WHERE id=:id"),
            {"loc": a["locations"][1], "id": a["resources_1"]["table_id"]},
        )


def test_composite_foreign_keys_prevent_cross_restaurant_zone(suite):
    a, b = suite.seed["organizations"]["a"], suite.seed["organizations"]["b"]
    with pytest.raises(IntegrityError), Session(suite.runtime) as db, db.begin():
        set_identity(db, suite.seed["accounts"]["a_owner"]["user_id"])
        db.execute(
            text(
                "INSERT INTO table_zones(id,organization_id,location_id,table_id,camera_id,"
                "polygon,source_width,source_height) VALUES(:id,:org,:loc,:table,:camera,"
                "'[[0,0],[1,0],[1,1]]'::jsonb,640,480)"
            ),
            {
                "id": uuid4(),
                "org": a["id"],
                "loc": a["locations"][0],
                "table": a["resources_1"]["table_id"],
                "camera": b["resources_1"]["camera_id"],
            },
        )


def test_transaction_context_does_not_survive_connection_reuse(suite):
    engine = create_engine(suite.runtime.url, pool_size=1, max_overflow=0, hide_parameters=True)
    try:
        with Session(engine) as db, db.begin():
            set_identity(db, suite.seed["accounts"]["a_owner"]["user_id"])
            assert db.scalar(text("SELECT count(*) FROM dining_tables")) > 0
        with Session(engine) as db, db.begin():
            assert db.scalar(text("SELECT count(*) FROM dining_tables")) == 0
            assert not db.scalar(text("SELECT current_setting('app.user_id',true)"))
    finally:
        engine.dispose()


def test_migrations_preserve_preexisting_data_and_seed_is_repeatable(suite, tmp_path):
    # This creates a NEW database only on the explicitly configured test server.
    name = "phase2_security_test_migration_" + uuid4().hex[:10]
    with suite.admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(suite.admin.url.set(database=name), hide_parameters=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE preservation_sentinel(id integer PRIMARY KEY,value text)")
            )
            connection.execute(
                text("INSERT INTO preservation_sentinel VALUES(1,'keep this synthetic row')")
            )
            connection.execute(
                text("CREATE TABLE alembic_version(version_num varchar(32) PRIMARY KEY)")
            )
        migrate(engine)
        migrate(engine)
        private = tmp_path / "private-seed.json"
        first = seed_demo(engine, private, "migration-" + uuid4().hex[:8])
        second = seed_demo(engine, private, first["namespace"])
        assert first == second
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT value FROM preservation_sentinel WHERE id=1"))
                == "keep this synthetic row"
            )
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0008"
            assert connection.scalar(text("SELECT count(*) FROM organizations")) == 2
    finally:
        engine.dispose()
