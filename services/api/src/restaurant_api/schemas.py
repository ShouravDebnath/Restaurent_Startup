from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

Label = Annotated[str, Field(min_length=1, max_length=80)]
Name = Annotated[str, Field(min_length=1, max_length=120)]
Point = tuple[Annotated[float, Field(ge=0, le=1)], Annotated[float, Field(ge=0, le=1)]]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)


class Role(StrEnum):
    owner = "owner"
    org_admin = "org_admin"
    manager = "manager"
    staff = "staff"
    installer = "installer"


def normalized_email(value: str) -> str:
    value = value.strip().casefold()
    if len(value) > 254 or value.count("@") != 1 or any(c.isspace() for c in value):
        raise ValueError("Use a valid email address")
    local, domain = value.split("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Use a valid email address")
    return value


class Login(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128, repr=False)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        return normalized_email(value)


class SessionOut(Strict):
    authenticated: bool = True
    csrf_token: str


class OrganizationIn(Strict):
    name: Name


class OrganizationOut(OrganizationIn):
    id: UUID
    plan: str
    created_at: datetime


class LocationIn(Strict):
    name: Name
    time_zone: str = Field(max_length=100)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("time_zone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Use a valid IANA time zone") from error
        return value


class LocationOut(LocationIn):
    id: UUID
    organization_id: UUID
    created_at: datetime


class MembershipIn(Strict):
    email: str = Field(max_length=254)
    role: Role
    location_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        return normalized_email(value)


class MembershipUpdate(Strict):
    role: Role
    enabled: bool
    location_ids: list[UUID] = Field(max_length=100)


class MembershipOut(Strict):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: Role
    enabled: bool
    email: str
    display_name: str
    location_ids: list[UUID]


class AccessOut(Strict):
    organization: OrganizationOut
    role: Role
    locations: list[LocationOut]


class MeOut(Strict):
    id: UUID
    email: str
    display_name: str
    access: list[AccessOut]


class TableIn(Strict):
    label: Label
    seats: int | None = Field(default=None, ge=1, le=100)


class TableOut(TableIn):
    id: UUID
    organization_id: UUID
    location_id: UUID
    current_state: Literal[
        "UNKNOWN", "AVAILABLE", "OCCUPIED", "RESET_PENDING", "CLEANING", "OUT_OF_SERVICE"
    ]
    state_since: datetime
    created_at: datetime


class CameraIn(Strict):
    label: Label
    source_reference: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,80}$")


class CameraOut(CameraIn):
    id: UUID
    organization_id: UUID
    location_id: UUID
    status: Literal["NOT_CONFIGURED"]
    created_at: datetime


class CalibrationView(Strict):
    format_version: Literal[1] = 1
    rotation: Literal[0, 90, 180, 270] = 0
    mirrored: bool = Field(default=False, strict=True)


class ZoneIn(Strict):
    table_id: UUID
    camera_id: UUID
    polygon: list[Point] = Field(min_length=3, max_length=64)
    source_width: int = Field(ge=1, le=32768)
    source_height: int = Field(ge=1, le=32768)
    view_metadata: CalibrationView | None = None

    @field_validator("polygon")
    @classmethod
    def valid_polygon(cls, points):
        n = len(points)
        if len(set(points)) != n:
            raise ValueError("Polygon vertices must be distinct")
        area = sum(
            points[i][0] * points[(i + 1) % n][1] - points[i][1] * points[(i + 1) % n][0]
            for i in range(n)
        )
        if abs(area) < 0.00000001:
            raise ValueError("Polygon must have an area")

        def turn(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        for i in range(n):
            a, b = points[i], points[(i + 1) % n]
            for j in range(i + 1, n):
                if j == (i + 1) % n or (j + 1) % n == i:
                    continue
                c, d = points[j], points[(j + 1) % n]
                if (
                    turn(a, b, c) * turn(a, b, d) <= 0
                    and turn(c, d, a) * turn(c, d, b) <= 0
                    and max(min(a[0], b[0]), min(c[0], d[0]))
                    <= min(max(a[0], b[0]), max(c[0], d[0]))
                    and max(min(a[1], b[1]), min(c[1], d[1]))
                    <= min(max(a[1], b[1]), max(c[1], d[1]))
                ):
                    raise ValueError("Polygon edges must not intersect")
        return points


class ZoneCreate(ZoneIn):
    request_key: UUID | None = None


class ZoneUpdate(ZoneCreate):
    expected_revision: int = Field(ge=1)


class ZoneOut(ZoneIn):
    id: UUID
    organization_id: UUID
    location_id: UUID
    revision: int
    created_at: datetime


class AuditOut(Strict):
    id: UUID
    organization_id: UUID
    location_id: UUID | None
    actor_id: UUID
    action: str
    created_at: datetime
    details: dict
