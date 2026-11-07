import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from restaurant_api.database import get_db, set_identity
from restaurant_api.models import Location, Membership, Organization
from restaurant_api.settings import get_settings

passwords = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_dummy_hash = passwords.hash(secrets.token_urlsafe(32))
ADMINS = {"owner", "org_admin"}
CONFIGURATORS = ADMINS | {"manager"}
INSTALLERS = CONFIGURATORS | {"installer"}
Db = Annotated[Session, Depends(get_db, scope="function")]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(session_token: str) -> str:
    return hmac.new(session_token.encode(), b"restaurant-phase2-csrf", hashlib.sha256).hexdigest()


def verify_password(encoded: str | None, supplied: str) -> bool:
    try:
        return passwords.verify(encoded or _dummy_hash, supplied)
    except (VerificationError, InvalidHashError):
        return False


def check_origin(request: Request) -> None:
    if request.headers.get("origin") not in get_settings().origins:
        raise HTTPException(403, "Request origin is not allowed.")


@dataclass(frozen=True)
class Identity:
    id: UUID
    session_token: str


def authenticated(request: Request, db: Db) -> Identity:
    token = request.cookies.get(get_settings().cookie_name, "")
    if not 32 <= len(token) <= 128:
        raise HTTPException(401, "Authentication required.")
    user_id = db.scalar(
        text("SELECT security.resolve_session(:digest, :idle)"),
        {"digest": digest(token), "idle": get_settings().session_idle_seconds},
    )
    if user_id is None:
        raise HTTPException(401, "Authentication required.")
    set_identity(db, str(user_id))
    return Identity(user_id, token)


def mutation(request: Request, identity: Annotated[Identity, Depends(authenticated)]) -> Identity:
    check_origin(request)
    if not hmac.compare_digest(
        request.headers.get("x-csrf-token", "").encode(),
        csrf_token(identity.session_token).encode(),
    ):
        raise HTTPException(403, "CSRF verification failed.")
    return identity


def organization_access(db: Session, identity: Identity, org_id: UUID, roles=None):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(404, "Resource not found.")
    member = db.scalar(
        select(Membership).where(
            Membership.user_id == identity.id,
            Membership.organization_id == org_id,
            Membership.enabled.is_(True),
        )
    )
    if member is None:
        raise HTTPException(404, "Resource not found.")
    if roles is not None and member.role not in roles:
        raise HTTPException(403, "This role cannot perform this action.")
    return org, member


def location_access(db: Session, identity: Identity, location_id: UUID, roles=None):
    location = db.get(Location, location_id)
    if location is None:
        raise HTTPException(404, "Resource not found.")
    _, member = organization_access(db, identity, location.organization_id, roles)
    return location, member
