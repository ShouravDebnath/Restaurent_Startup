from collections.abc import Generator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from restaurant_api.settings import get_settings


@lru_cache
def get_engine():
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"},
    )


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine(), expire_on_commit=False) as db:
        flags = db.execute(
            text(
                "SELECT r.rolsuper OR r.rolbypassrls OR r.rolcreatedb OR r.rolcreaterole "
                "OR has_schema_privilege(current_user,'public','CREATE') "
                "OR has_schema_privilege(current_user,'security','CREATE') "
                "OR has_schema_privilege(current_user,'identity','USAGE') "
                "OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid) "
                "OR EXISTS(SELECT 1 FROM pg_database WHERE datname=current_database() AND datdba=r.oid) "
                "OR EXISTS(SELECT 1 FROM pg_class WHERE relnamespace='public'::regnamespace "
                "AND relowner=r.oid) FROM pg_roles r WHERE rolname=current_user"
            )
        ).scalar_one()
        if flags:
            raise HTTPException(503, "Restricted database runtime configuration is required.")
        yield db
        db.commit()


def set_identity(db: Session, user_id: str) -> None:
    db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": user_id})
