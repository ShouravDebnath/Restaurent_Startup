"""Human-only calibration metadata and permission APIs; never accept/return video or URLs."""

import hashlib
import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from restaurant_api import schemas as s
from restaurant_api.models import Camera, PreviewGrant, TableZone, ZoneRevision
from restaurant_api.security import (
    CONFIGURATORS,
    INSTALLERS,
    Db,
    Identity,
    authenticated,
    digest,
    location_access,
    mutation,
)
from restaurant_api.settings import get_settings

router = APIRouter(prefix="/v1")
Auth = Annotated[Identity, Depends(authenticated)]
Write = Annotated[Identity, Depends(mutation)]


class GrantIn(s.Strict):
    viewer_id: UUID
    duration_seconds: int = Field(default=900, ge=60, le=3600, strict=True)
    request_key: UUID
    consent: bool = Field(strict=True)


class GrantOut(s.Strict):
    id: UUID
    organization_id: UUID
    location_id: UUID
    camera_id: UUID
    viewer_id: UUID
    granted_by: UUID
    duration_seconds: int
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class PreviewAuthorization(s.Strict):
    camera_id: UUID
    organization_id: UUID
    location_id: UUID
    viewer_id: UUID
    grant_id: UUID
    expires_at: datetime
    server_time: datetime
    session_deadline: datetime
    source_reference: str | None


class RevisionOut(s.Strict):
    id: UUID
    zone_id: UUID
    organization_id: UUID
    location_id: UUID
    camera_id: UUID
    table_id: UUID
    revision: int
    actor_id: UUID | None
    created_at: datetime
    reason: str
    snapshot: s.ZoneOut


def camera_scope(db, identity, location_id, camera_id, roles):
    from restaurant_api.routes import resource
    loc, _ = location_access(db, identity, location_id, roles)
    return loc, resource(db, Camera, camera_id, loc)


def database_action(db, params):
    try:
        return db.scalar(text("SELECT security.preview_action(:camera,:key,:viewer,:seconds,:revoke)"), params)
    except DBAPIError as error:
        status = {"P0403": 403, "P0404": 404, "P0409": 409, "P0422": 422}.get(
            getattr(error.orig, "sqlstate", ""), 503)
        raise HTTPException(status, "Preview permission request was rejected.") from None


@router.post("/locations/{location_id}/cameras/{camera_id}/preview-grants", response_model=GrantOut,
             status_code=201)
def issue_grant(location_id: UUID, camera_id: UUID, body: GrantIn, identity: Write, db: Db):
    camera_scope(db, identity, location_id, camera_id, CONFIGURATORS)
    if not body.consent:
        raise HTTPException(422, "Explicit camera-preview consent is required.")
    grant_id = database_action(db, {"camera": camera_id, "key": body.request_key,
        "viewer": body.viewer_id, "seconds": body.duration_seconds, "revoke": False})
    return db.get(PreviewGrant, grant_id)


@router.get("/locations/{location_id}/cameras/{camera_id}/preview-grants", response_model=list[GrantOut])
def grants(location_id: UUID, camera_id: UUID, identity: Auth, db: Db,
           limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)):
    camera_scope(db, identity, location_id, camera_id, CONFIGURATORS)
    return db.scalars(select(PreviewGrant).where(PreviewGrant.camera_id == camera_id)
        .order_by(PreviewGrant.created_at.desc(), PreviewGrant.id).limit(limit).offset(offset)).all()


@router.post("/locations/{location_id}/cameras/{camera_id}/preview-grants/{grant_id}/revoke",
             response_model=GrantOut)
def revoke_grant(location_id: UUID, camera_id: UUID, grant_id: UUID, identity: Write, db: Db):
    camera_scope(db, identity, location_id, camera_id, CONFIGURATORS)
    result = database_action(db, {"camera": camera_id, "key": grant_id, "viewer": identity.id,
                                  "seconds": 0, "revoke": True})
    return db.get(PreviewGrant, result)


@router.get("/locations/{location_id}/cameras/{camera_id}/preview-authorization",
            response_model=PreviewAuthorization)
def preview_authorization(location_id: UUID, camera_id: UUID, identity: Auth, db: Db):
    loc, camera = camera_scope(db, identity, location_id, camera_id, INSTALLERS)
    grant = db.scalar(select(PreviewGrant).where(PreviewGrant.camera_id == camera_id,
        PreviewGrant.viewer_id == identity.id, PreviewGrant.revoked_at.is_(None),
        PreviewGrant.expires_at > func.clock_timestamp()).order_by(PreviewGrant.expires_at.desc()).limit(1))
    if grant is None:
        raise HTTPException(403, "An active explicit camera-preview grant is required.")
    return PreviewAuthorization(camera_id=camera_id, organization_id=loc.organization_id,
        location_id=loc.id, viewer_id=identity.id, grant_id=grant.id, expires_at=grant.expires_at,
        server_time=db.scalar(select(func.clock_timestamp())), source_reference=camera.source_reference,
        session_deadline=db.scalar(text("SELECT security.session_deadline(:digest,:idle)"),
            {"digest": digest(identity.session_token), "idle": get_settings().session_idle_seconds}))


@router.get("/locations/{location_id}/table-zones/{zone_id}/revisions", response_model=list[RevisionOut])
def revisions(location_id: UUID, zone_id: UUID, identity: Auth, db: Db,
              limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)):
    from restaurant_api.routes import resource
    loc, _ = location_access(db, identity, location_id, INSTALLERS)
    resource(db, TableZone, zone_id, loc)
    return db.scalars(select(ZoneRevision).where(ZoneRevision.zone_id == zone_id)
        .order_by(ZoneRevision.revision.desc()).limit(limit).offset(offset)).all()


def zone_request(db, identity, loc, body, zone_id=None):
    """Serialize a scoped retry key before locking a zone; return its original snapshot."""
    if body.request_key is None:
        return None
    payload = {"zone_id": str(zone_id) if zone_id else None,
               "body": body.model_dump(mode="json", exclude={"request_key"})}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    lock = f"calibration/{identity.id}/{loc.id}/{body.request_key}"
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,725))"), {"key": lock})
    # Permissions must still hold after waiting for the other transaction.
    location_access(db, identity, loc.id, INSTALLERS)
    previous = db.scalar(select(ZoneRevision).where(ZoneRevision.actor_id == identity.id,
        ZoneRevision.location_id == loc.id, ZoneRevision.request_key == body.request_key))
    if previous:
        if previous.fingerprint != fingerprint:
            raise HTTPException(409, "Request key was already used for a different calibration.")
        return previous.snapshot
    db.execute(text("SELECT set_config('app.calibration_key',:key,true), "
        "set_config('app.calibration_fingerprint',:fingerprint,true)"),
        {"key": str(body.request_key), "fingerprint": fingerprint})
    return None
