"""Explicit local administration; never imported or run by the API request path."""

import argparse
import getpass
import json
import secrets
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from psycopg import Error as PsycopgError
from psycopg import sql
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_api.models import (
    AuditLog,
    Camera,
    DiningTable,
    Location,
    LocationGrant,
    Membership,
    Organization,
    TableZone,
    User,
)
from restaurant_api.schemas import normalized_email
from restaurant_api.security import passwords

API_ROOT = Path(__file__).resolve().parents[2]
if not (API_ROOT / "alembic.ini").is_file():
    API_ROOT = Path.cwd()  # Installed container package; migrations are copied to /app.


def migrate(engine) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def provision_runtime(engine, username: str, password: str) -> None:
    if username in {"postgres", "public"} or not username.startswith("restaurant_"):
        raise ValueError("Choose a dedicated restaurant_ runtime role")
    with engine.begin() as connection:
        flags = connection.execute(
            text(
                "SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=:u"
            ),
            {"u": username},
        ).first()
        if flags is not None and any(flags):
            raise ValueError("Existing runtime role has privileged flags; refusing to use it")
        cursor = connection.connection.driver_connection.cursor()
        if flags is None:
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOBYPASSRLS"
                ).format(sql.Identifier(username), sql.Literal(password))
            )
        database = connection.scalar(text("SELECT current_database()"))
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(username)
            )
        )
        statements = [
            "GRANT USAGE ON SCHEMA public,security TO {}",
            "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA security TO {}",
            "GRANT SELECT,UPDATE ON public.organizations,public.locations TO {}",
            (
                "GRANT SELECT,INSERT,UPDATE ON public.memberships,public.location_grants,"
                "public.cameras,public.table_zones TO {}"
            ),
            "GRANT SELECT,INSERT ON public.audit_logs TO {}",
            "REVOKE ALL ON public.dining_tables FROM {}",
            "GRANT SELECT ON public.dining_tables TO {}",
            "GRANT INSERT(id,organization_id,location_id,label,seats) ON public.dining_tables TO {}",
            "GRANT UPDATE(label,seats) ON public.dining_tables TO {}",
            (
                "GRANT SELECT ON public.location_operations,public.table_events,"
                "public.staff_tasks,public.action_receipts TO {}"
            ),
            "GRANT SELECT ON public.table_zone_revisions,public.camera_preview_grants TO {}",
            (
                "GRANT SELECT ON public.edge_devices,public.edge_keys,public.edge_assignments,"
                "public.edge_bindings,public.edge_receipts,public.edge_shadows,public.edge_health,"
                "public.edge_audits,public.location_notifications TO {}"
            ),
            # Internal helpers are invoked only by other SECURITY DEFINER functions.
            "REVOKE EXECUTE ON FUNCTION security.edge_publish(uuid,text) FROM {}",
            "REVOKE EXECUTE ON FUNCTION security.edge_fixture(uuid,jsonb,boolean) FROM {}",
            (
                "GRANT SELECT ON public.workflow_policies,public.workflow_sessions,public.workflow_evidence,"
                "public.workflow_suggestions,public.workflow_task_attempts,public.workflow_decisions,"
                "public.workflow_policy_history,public.workflow_journal,public.workflow_quality_boundaries TO {}"
            ),
            "REVOKE EXECUTE ON FUNCTION security.workflow_legacy_action(uuid,text,integer,uuid,text,uuid,boolean,text,boolean,boolean) FROM {}",
            "REVOKE EXECUTE ON FUNCTION security.workflow_event(uuid,text,text,jsonb) FROM {}",
            "REVOKE EXECUTE ON FUNCTION security.workflow_receive() FROM {}",
            "REVOKE EXECUTE ON FUNCTION security.workflow_task_projection() FROM {}",
            "REVOKE EXECUTE ON FUNCTION security.workflow_journal_capture() FROM {}",
            "REVOKE EXECUTE ON FUNCTION security.workflow_quality(jsonb,jsonb) FROM {}",
            "REVOKE EXECUTE ON FUNCTION security.workflow_rules_digest(jsonb) FROM {}",
            "REVOKE EXECUTE ON FUNCTION security.workflow_quality_boundary() FROM {}",
        ]
        for statement in statements:
            cursor.execute(sql.SQL(statement).format(sql.Identifier(username)))
        # Database ownership or inherited privileged roles would undermine isolation.
        unsafe = connection.scalar(
            text(
                "SELECT EXISTS(SELECT 1 FROM pg_auth_members WHERE member="
                "(SELECT oid FROM pg_roles WHERE rolname=:u)) OR EXISTS(SELECT 1 FROM pg_database "
                "WHERE datname=current_database() AND datdba=(SELECT oid FROM pg_roles WHERE rolname=:u))"
            ),
            {"u": username},
        )
        if unsafe:
            raise ValueError("Runtime role must not own the database or inherit another role")


def seed_demo(engine, private_path: Path, namespace: str = "local-phase2") -> dict:
    """Idempotent synthetic seed; never overwrites existing rows or passwords."""
    private_path.parent.mkdir(parents=True, exist_ok=True)
    saved = json.loads(private_path.read_text(encoding="utf-8")) if private_path.exists() else {}
    if saved and saved.get("namespace") != namespace:
        raise ValueError("Seed credentials file belongs to a different namespace")
    accounts = saved.get("accounts", {})
    result = {"namespace": namespace, "accounts": accounts, "organizations": {}}

    def identifier(name):
        return uuid5(NAMESPACE_URL, f"restaurant-ai/{namespace}/{name}")

    with Session(engine) as db, db.begin():
        for letter in ("a", "b"):
            org_id = identifier(f"org-{letter}")
            if db.get(Organization, org_id) is None:
                db.add(Organization(id=org_id, name=f"Synthetic Restaurant {letter.upper()}"))
                db.flush()
            location_ids = [identifier(f"{letter}-location-{i}") for i in (1, 2)]
            for index, loc_id in enumerate(location_ids, start=1):
                if db.get(Location, loc_id) is None:
                    db.add(
                        Location(
                            id=loc_id,
                            organization_id=org_id,
                            name=f"Demo Location {index}",
                            time_zone="America/New_York" if letter == "a" else "Asia/Dhaka",
                        )
                    )
            db.flush()
            result["organizations"][letter] = {
                "id": str(org_id),
                "locations": list(map(str, location_ids)),
            }
            for role in ("owner", "org_admin", "manager", "staff", "installer"):
                key = f"{letter}_{role}"
                user_id = identifier(f"user-{key}")
                member_id = identifier(f"member-{key}")
                email = f"{namespace}.{key}@example.invalid"
                if db.get(User, user_id) is None:
                    if key in accounts:
                        raise ValueError(
                            "Credentials exist without their seeded user; review manually"
                        )
                    password = secrets.token_urlsafe(24)
                    accounts[key] = {"email": email, "password": password, "user_id": str(user_id)}
                    db.add(
                        User(
                            id=user_id,
                            email=email,
                            display_name=f"Demo {letter.upper()} {role}",
                            password_hash=passwords.hash(password),
                        )
                    )
                    db.flush()
                elif key not in accounts:
                    raise ValueError(
                        "Existing seed credentials are missing; use explicit account recovery"
                    )
                if db.get(Membership, member_id) is None:
                    db.add(
                        Membership(
                            id=member_id,
                            user_id=user_id,
                            organization_id=org_id,
                            role=role,
                        )
                    )
                    db.flush()
                    for loc_id in location_ids if role == "owner" else location_ids[:1]:
                        db.add(
                            LocationGrant(
                                membership_id=member_id,
                                location_id=loc_id,
                                organization_id=org_id,
                            )
                        )
            db.flush()
            for index, loc_id in enumerate(location_ids, start=1):
                camera_id = identifier(f"{letter}-camera-{index}")
                table_id = identifier(f"{letter}-table-{index}")
                zone_id = identifier(f"{letter}-zone-{index}")
                if db.get(Camera, camera_id) is None:
                    db.add(
                        Camera(
                            id=camera_id,
                            organization_id=org_id,
                            location_id=loc_id,
                            label="Demo camera",
                            source_reference=f"local_demo_{letter}_{index}",
                        )
                    )
                if db.get(DiningTable, table_id) is None:
                    db.add(
                        DiningTable(
                            id=table_id,
                            organization_id=org_id,
                            location_id=loc_id,
                            label="T01",
                            seats=4,
                        )
                    )
                db.flush()
                if db.get(TableZone, zone_id) is None:
                    db.add(
                        TableZone(
                            id=zone_id,
                            organization_id=org_id,
                            location_id=loc_id,
                            camera_id=camera_id,
                            table_id=table_id,
                            polygon=[[0.1, 0.1], [0.8, 0.1], [0.8, 0.8], [0.1, 0.8]],
                            source_width=1920,
                            source_height=1080,
                        )
                    )
                result["organizations"][letter][f"resources_{index}"] = {
                    "camera_id": str(camera_id),
                    "table_id": str(table_id),
                    "zone_id": str(zone_id),
                }
            audit_id = identifier(f"{letter}-seed-audit")
            if db.get(AuditLog, audit_id) is None:
                db.add(
                    AuditLog(
                        id=audit_id,
                        organization_id=org_id,
                        actor_id=identifier(f"user-{letter}_owner"),
                        action="demo.seeded",
                        details={"synthetic": True},
                    )
                )
        # Persist private credentials before the database transaction commits, so a failed
        # file write rolls back newly created accounts rather than losing their passwords.
        private_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicit Phase 2 local administration")
    parser.add_argument(
        "command", choices=["prepare", "migrate", "provision", "seed", "seed-dashboard", "create-user"]
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument(
        "--credentials-file", type=Path, default=Path(".secrets/phase2-demo-credentials.json")
    )
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    if args.command == "prepare":
        if not args.env_file.is_file():
            parser.error(
                "Copy .env.example to a private .env and set its database credentials first"
            )
        updates = {}
        if not values.get("APP_DB_USER"):
            updates["APP_DB_USER"] = "restaurant_app"
        if not values.get("APP_DB_PASSWORD"):
            updates["APP_DB_PASSWORD"] = secrets.token_urlsafe(36)
        with args.env_file.open("a", encoding="utf-8") as output:
            for key, value in updates.items():
                output.write(f"\n{key}={value}\n")
        print("prepare: private runtime settings ready; no database connection made.")
        return 0
    engine = create_engine(
        URL.create(
            "postgresql+psycopg",
            host=args.host,
            port=args.port,
            database=values.get("POSTGRES_DB"),
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
        ),
        hide_parameters=True,
    )
    try:
        if args.command == "migrate":
            migrate(engine)
        elif args.command == "provision":
            username = values.get("APP_DB_USER") or "restaurant_app"
            password = values.get("APP_DB_PASSWORD") or secrets.token_urlsafe(36)
            provision_runtime(engine, username, password)
            if not values.get("APP_DB_PASSWORD"):
                with args.env_file.open("a", encoding="utf-8") as output:
                    output.write(f"\nAPP_DB_USER={username}\nAPP_DB_PASSWORD={password}\n")
        elif args.command == "seed":
            seed_demo(engine, args.credentials_file)
        elif args.command == "seed-dashboard":
            from restaurant_api.dashboard_seed import seed_dashboard

            seed = json.loads(args.credentials_file.read_text(encoding="utf-8"))
            result = seed_dashboard(engine, seed)
            args.credentials_file.with_name("phase3-demo-layout.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
        elif args.command == "create-user":
            email = normalized_email(input("Email: "))
            name = input("Display name: ").strip()
            password = getpass.getpass("Passphrase (15-128 characters): ")
            if not 15 <= len(password) <= 128 or not 1 <= len(name) <= 120:
                raise ValueError("Invalid account details")
            with Session(engine) as db, db.begin():
                if db.scalar(select(User).where(User.email == email)) is not None:
                    raise ValueError("Account already exists; no account changed")
                db.add(User(email=email, display_name=name, password_hash=passwords.hash(password)))
        print(f"{args.command}: completed; private values were not printed.")
        return 0
    except (SQLAlchemyError, PsycopgError, OSError, ValueError, EOFError) as error:
        print(
            f"{args.command}: failed ({type(error).__name__}); no secret details printed.",
            file=sys.stderr,
        )
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
