import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, text

from restaurant_api import schemas as s
from restaurant_api.models import (
    AuditLog,
    Camera,
    DiningTable,
    Location,
    LocationGrant,
    Membership,
    Organization,
    TableZone,
)
from restaurant_api.security import (
    ADMINS,
    CONFIGURATORS,
    INSTALLERS,
    Db,
    Identity,
    authenticated,
    check_origin,
    csrf_token,
    digest,
    location_access,
    mutation,
    organization_access,
    verify_password,
)
from restaurant_api.settings import get_settings

router = APIRouter(prefix="/v1")
Auth = Annotated[Identity, Depends(authenticated)]
Write = Annotated[Identity, Depends(mutation)]


def audit(db, identity, org_id, action, location_id=None, **details):
    db.flush()
    # Installers may append an audit entry but may not read audit history.
    # Avoid ORM RETURNING of server defaults, which would require SELECT permission.
    db.execute(
        AuditLog.__table__.insert()
        .inline()
        .values(
            organization_id=org_id,
            location_id=location_id,
            actor_id=identity.id,
            action=action,
            details=details,
        )
    )


def resource(db, model, resource_id, location, lock=False):
    query = select(model).where(
        model.id == resource_id,
        model.location_id == location.id,
        model.organization_id == location.organization_id,
    )
    if lock:
        query = query.with_for_update()
    result = db.scalar(query)
    if result is None:
        raise HTTPException(404, "Resource not found.")
    return result


@router.post("/auth/session", response_model=s.SessionOut)
def login(body: s.Login, request: Request, response: Response, db: Db):
    check_origin(request)
    peer = request.client.host if request.client else "unknown"
    allowed = [
        db.scalar(
            text("SELECT security.login_attempt(:key, :limit)"),
            {
                "key": digest(prefix + value),
                "limit": limit,
            },
        )
        for prefix, value, limit in [("email:", body.email, 10), ("peer:", peer, 60)]
    ]
    # Failed login must not roll back its throttle counters.
    db.commit()
    if not all(allowed):
        raise HTTPException(429, "Too many login attempts. Try again later.")
    credentials = (
        db.execute(
            text("SELECT * FROM security.credentials(:email)"),
            {
                "email": body.email,
            },
        )
        .mappings()
        .first()
    )
    valid = verify_password(credentials["password_hash"] if credentials else None, body.password)
    if not valid or not credentials or not credentials["enabled"]:
        raise HTTPException(401, "Invalid email or password.")
    settings = get_settings()
    old = request.cookies.get(settings.cookie_name, "")
    if old:
        db.execute(text("SELECT security.revoke_session(:digest)"), {"digest": digest(old)})
    token = secrets.token_urlsafe(32)
    db.execute(
        text("SELECT security.new_session(:user, :digest, :lifetime)"),
        {
            "user": credentials["user_id"],
            "digest": digest(token),
            "lifetime": settings.session_absolute_seconds,
        },
    )
    response.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_absolute_seconds,
        path="/",
    )
    return s.SessionOut(csrf_token=csrf_token(token))


@router.get("/auth/csrf", response_model=s.SessionOut)
def csrf(identity: Auth):
    return s.SessionOut(csrf_token=csrf_token(identity.session_token))


@router.delete("/auth/session", status_code=204)
def logout(identity: Write, response: Response, db: Db):
    db.execute(
        text("SELECT security.revoke_session(:digest)"),
        {
            "digest": digest(identity.session_token),
        },
    )
    response.delete_cookie(
        get_settings().cookie_name,
        path="/",
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
    )


@router.get("/me", response_model=s.MeOut)
def me(identity: Auth, db: Db):
    profile = dict(db.execute(text("SELECT * FROM security.profile()")).mappings().one())
    access = []
    for member in db.scalars(
        select(Membership).where(
            Membership.user_id == identity.id,
            Membership.enabled.is_(True),
        )
    ):
        org = db.get(Organization, member.organization_id)
        locations = db.scalars(
            select(Location)
            .where(Location.organization_id == org.id)
            .order_by(Location.name, Location.id)
        ).all()
        access.append(
            s.AccessOut(
                organization=s.OrganizationOut.model_validate(org),
                role=member.role,
                locations=locations,
            )
        )
    return s.MeOut(**profile, access=access)


@router.get("/organizations", response_model=list[s.OrganizationOut])
def organizations(identity: Auth, db: Db):
    return db.scalars(select(Organization).order_by(Organization.name, Organization.id)).all()


@router.post("/organizations", response_model=s.OrganizationOut, status_code=201)
def create_organization(body: s.OrganizationIn, identity: Write, db: Db):
    org_id = db.scalar(text("SELECT security.create_organization(:name)"), {"name": body.name})
    return db.get(Organization, org_id)


@router.get("/organizations/{org_id}", response_model=s.OrganizationOut)
def organization(org_id: UUID, identity: Auth, db: Db):
    return organization_access(db, identity, org_id)[0]


@router.patch("/organizations/{org_id}", response_model=s.OrganizationOut)
def update_organization(org_id: UUID, body: s.OrganizationIn, identity: Write, db: Db):
    org, _ = organization_access(db, identity, org_id, ADMINS)
    org.name = body.name
    audit(db, identity, org_id, "organization.updated")
    return org


@router.get("/organizations/{org_id}/locations", response_model=list[s.LocationOut])
def locations(org_id: UUID, identity: Auth, db: Db):
    organization_access(db, identity, org_id)
    return db.scalars(
        select(Location)
        .where(Location.organization_id == org_id)
        .order_by(Location.name, Location.id)
    ).all()


@router.post("/organizations/{org_id}/locations", response_model=s.LocationOut, status_code=201)
def create_location(org_id: UUID, body: s.LocationIn, identity: Write, db: Db):
    organization_access(db, identity, org_id, ADMINS)
    loc_id = db.scalar(
        text("SELECT security.create_location(:org,:name,:zone,:address)"),
        {
            "org": org_id,
            "name": body.name,
            "zone": body.time_zone,
            "address": body.address,
        },
    )
    audit(db, identity, org_id, "location.created", loc_id)
    return db.get(Location, loc_id)


@router.get("/locations/{location_id}", response_model=s.LocationOut)
def location(location_id: UUID, identity: Auth, db: Db):
    return location_access(db, identity, location_id)[0]


@router.patch("/locations/{location_id}", response_model=s.LocationOut)
def update_location(location_id: UUID, body: s.LocationIn, identity: Write, db: Db):
    loc, _ = location_access(db, identity, location_id, ADMINS)
    for key, value in body.model_dump().items():
        setattr(loc, key, value)
    audit(db, identity, loc.organization_id, "location.updated", loc.id)
    return loc


def member_out(db, member):
    profile = (
        db.execute(
            text("SELECT * FROM security.member_profile(:id)"),
            {
                "id": member.id,
            },
        )
        .mappings()
        .one()
    )
    grants = db.scalars(
        select(LocationGrant.location_id).where(
            LocationGrant.membership_id == member.id,
            LocationGrant.enabled.is_(True),
        )
    ).all()
    return s.MembershipOut(
        id=member.id,
        user_id=member.user_id,
        organization_id=member.organization_id,
        role=member.role,
        enabled=member.enabled,
        location_ids=grants,
        **profile,
    )


def manage_grants(db, member, location_ids):
    requested = set(location_ids)
    for loc_id in requested:
        if not db.scalar(
            text("SELECT security.location_belongs(:org,:loc)"),
            {
                "org": member.organization_id,
                "loc": loc_id,
            },
        ):
            raise HTTPException(404, "Resource not found.")
    existing = db.scalars(
        select(LocationGrant).where(
            LocationGrant.membership_id == member.id,
        )
    ).all()
    for grant in existing:
        grant.enabled = grant.location_id in requested
        requested.discard(grant.location_id)
    for loc_id in requested:
        db.add(
            LocationGrant(
                membership_id=member.id, organization_id=member.organization_id, location_id=loc_id
            )
        )


@router.get("/organizations/{org_id}/memberships", response_model=list[s.MembershipOut])
def memberships(org_id: UUID, identity: Auth, db: Db):
    organization_access(db, identity, org_id, ADMINS)
    return [
        member_out(db, m)
        for m in db.scalars(
            select(Membership)
            .where(
                Membership.organization_id == org_id,
            )
            .order_by(Membership.created_at, Membership.id)
        )
    ]


@router.post("/organizations/{org_id}/memberships", response_model=s.MembershipOut, status_code=201)
def create_membership(org_id: UUID, body: s.MembershipIn, identity: Write, db: Db):
    _, actor = organization_access(db, identity, org_id, ADMINS)
    if body.role == "owner" and actor.role != "owner":
        raise HTTPException(403, "Only an owner may assign ownership.")
    user_id = db.scalar(
        text("SELECT security.find_user(:org,:email)"),
        {
            "org": org_id,
            "email": body.email,
        },
    )
    if user_id is None:
        raise HTTPException(404, "Provisioned account not found.")
    member = Membership(user_id=user_id, organization_id=org_id, role=body.role)
    db.add(member)
    db.flush()
    manage_grants(db, member, body.location_ids)
    audit(
        db,
        identity,
        org_id,
        "membership.created",
        member_id=str(member.id),
        role=body.role.value,
        enabled=True,
        location_ids=list(map(str, body.location_ids)),
    )
    return member_out(db, member)


@router.patch("/organizations/{org_id}/memberships/{member_id}", response_model=s.MembershipOut)
def update_membership(
    org_id: UUID, member_id: UUID, body: s.MembershipUpdate, identity: Write, db: Db
):
    _, actor = organization_access(db, identity, org_id, ADMINS)
    db.execute(select(Organization).where(Organization.id == org_id).with_for_update())
    member = db.get(Membership, member_id)
    if member is None or member.organization_id != org_id:
        raise HTTPException(404, "Resource not found.")
    if (member.role == "owner" or body.role == "owner") and actor.role != "owner":
        raise HTTPException(403, "Only an owner may change ownership or owner permissions.")
    if member.user_id == identity.id and (not body.enabled or body.role != member.role):
        raise HTTPException(
            409, "Ask another owner to change your own role or disable your access."
        )
    manage_grants(db, member, body.location_ids)
    member.role, member.enabled = body.role, body.enabled
    audit(
        db,
        identity,
        org_id,
        "membership.updated",
        member_id=str(member.id),
        role=body.role.value,
        enabled=body.enabled,
        location_ids=list(map(str, body.location_ids)),
    )
    return member_out(db, member)


@router.get("/locations/{location_id}/tables", response_model=list[s.TableOut])
def tables(location_id: UUID, identity: Auth, db: Db):
    loc, _ = location_access(db, identity, location_id)
    return db.scalars(
        select(DiningTable)
        .where(DiningTable.location_id == loc.id)
        .order_by(DiningTable.label, DiningTable.id)
    ).all()


@router.get("/locations/{location_id}/tables/{table_id}", response_model=s.TableOut)
def table(location_id: UUID, table_id: UUID, identity: Auth, db: Db):
    loc, _ = location_access(db, identity, location_id)
    return resource(db, DiningTable, table_id, loc)


@router.post("/locations/{location_id}/tables", response_model=s.TableOut, status_code=201)
def create_table(location_id: UUID, body: s.TableIn, identity: Write, db: Db):
    loc, _ = location_access(db, identity, location_id, CONFIGURATORS)
    record = DiningTable(
        organization_id=loc.organization_id, location_id=loc.id, **body.model_dump()
    )
    db.add(record)
    db.flush()
    audit(db, identity, loc.organization_id, "table.created", loc.id, table_id=str(record.id))
    return record


@router.patch("/locations/{location_id}/tables/{table_id}", response_model=s.TableOut)
def update_table(location_id: UUID, table_id: UUID, body: s.TableIn, identity: Write, db: Db):
    loc, _ = location_access(db, identity, location_id, CONFIGURATORS)
    record = resource(db, DiningTable, table_id, loc, lock=True)
    for key, value in body.model_dump().items():
        setattr(record, key, value)
    audit(db, identity, loc.organization_id, "table.updated", loc.id, table_id=str(record.id))
    return record


@router.get("/locations/{location_id}/cameras", response_model=list[s.CameraOut])
def cameras(location_id: UUID, identity: Auth, db: Db):
    loc, _ = location_access(db, identity, location_id)
    return db.scalars(
        select(Camera).where(Camera.location_id == loc.id).order_by(Camera.label, Camera.id)
    ).all()


@router.get("/locations/{location_id}/cameras/{camera_id}", response_model=s.CameraOut)
def camera(location_id: UUID, camera_id: UUID, identity: Auth, db: Db):
    loc, _ = location_access(db, identity, location_id)
    return resource(db, Camera, camera_id, loc)


@router.post("/locations/{location_id}/cameras", response_model=s.CameraOut, status_code=201)
def create_camera(location_id: UUID, body: s.CameraIn, identity: Write, db: Db):
    loc, _ = location_access(db, identity, location_id, INSTALLERS)
    record = Camera(organization_id=loc.organization_id, location_id=loc.id, **body.model_dump())
    db.add(record)
    db.flush()
    audit(db, identity, loc.organization_id, "camera.created", loc.id, camera_id=str(record.id))
    return record


@router.patch("/locations/{location_id}/cameras/{camera_id}", response_model=s.CameraOut)
def update_camera(location_id: UUID, camera_id: UUID, body: s.CameraIn, identity: Write, db: Db):
    loc, _ = location_access(db, identity, location_id, INSTALLERS)
    record = resource(db, Camera, camera_id, loc, lock=True)
    for key, value in body.model_dump().items():
        setattr(record, key, value)
    audit(db, identity, loc.organization_id, "camera.updated", loc.id, camera_id=str(record.id))
    return record


@router.get("/locations/{location_id}/table-zones", response_model=list[s.ZoneOut])
def zones(location_id: UUID, identity: Auth, db: Db):
    loc, _ = location_access(db, identity, location_id)
    return db.scalars(
        select(TableZone)
        .where(TableZone.location_id == loc.id)
        .order_by(TableZone.created_at, TableZone.id)
    ).all()


@router.get("/locations/{location_id}/table-zones/{zone_id}", response_model=s.ZoneOut)
def zone(location_id: UUID, zone_id: UUID, identity: Auth, db: Db):
    loc, _ = location_access(db, identity, location_id)
    return resource(db, TableZone, zone_id, loc)


@router.post("/locations/{location_id}/table-zones", response_model=s.ZoneOut, status_code=201)
def create_zone(location_id: UUID, body: s.ZoneCreate, identity: Write, db: Db):
    loc, _ = location_access(db, identity, location_id, INSTALLERS)
    resource(db, DiningTable, body.table_id, loc)
    resource(db, Camera, body.camera_id, loc)
    from restaurant_api.calibration import zone_request
    previous = zone_request(db, identity, loc, body)
    if previous:
        return previous
    record = TableZone(organization_id=loc.organization_id, location_id=loc.id,
                       **body.model_dump(mode="json", exclude={"request_key"}))
    db.add(record)
    db.flush()
    audit(db, identity, loc.organization_id, "zone.created", loc.id, zone_id=str(record.id))
    return record


@router.put("/locations/{location_id}/table-zones/{zone_id}", response_model=s.ZoneOut)
def update_zone(location_id: UUID, zone_id: UUID, body: s.ZoneUpdate, identity: Write, db: Db):
    loc, _ = location_access(db, identity, location_id, INSTALLERS)
    from restaurant_api.calibration import zone_request
    previous = zone_request(db, identity, loc, body, zone_id)
    if previous:
        return previous
    record = resource(db, TableZone, zone_id, loc, lock=True)
    if record.revision != body.expected_revision:
        raise HTTPException(409, "Zone changed; reload before saving.")
    resource(db, DiningTable, body.table_id, loc)
    resource(db, Camera, body.camera_id, loc)
    for key, value in body.model_dump(mode="json", exclude={"expected_revision", "request_key"}).items():
        setattr(record, key, value)
    record.revision += 1
    audit(
        db,
        identity,
        loc.organization_id,
        "zone.updated",
        loc.id,
        zone_id=str(record.id),
        revision=record.revision,
    )
    return record


@router.get("/organizations/{org_id}/audit-logs", response_model=list[s.AuditOut])
def organization_audits(
    org_id: UUID,
    identity: Auth,
    db: Db,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    organization_access(db, identity, org_id, ADMINS)
    return db.scalars(
        select(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(limit)
        .offset(offset)
    ).all()


@router.get("/locations/{location_id}/audit-logs", response_model=list[s.AuditOut])
def location_audits(
    location_id: UUID,
    identity: Auth,
    db: Db,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    loc, _ = location_access(db, identity, location_id, CONFIGURATORS)
    return db.scalars(
        select(AuditLog)
        .where(AuditLog.location_id == loc.id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(limit)
        .offset(offset)
    ).all()
