"""Phase 2 persistence. Device/event/task models belong to later milestones."""

from datetime import datetime
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLES = ("owner", "org_admin", "manager", "staff", "installer")
STATES = ("UNKNOWN", "AVAILABLE", "OCCUPIED", "RESET_PENDING", "CLEANING", "OUT_OF_SERVICE")


class Base(DeclarativeBase):
    pass


class Identified:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Created:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Identified, Created, Base):
    __tablename__ = "users"
    __table_args__: ClassVar[dict] = {"schema": "identity"}
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(512))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    provider_subject: Mapped[str | None] = mapped_column(String(255), unique=True)


class AuthSession(Created, Base):
    __tablename__ = "sessions"
    __table_args__: ClassVar[dict] = {"schema": "identity"}
    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, server_default="false")


class LoginBucket(Base):
    __tablename__ = "login_buckets"
    __table_args__: ClassVar[dict] = {"schema": "identity"}
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Organization(Identified, Created, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(120))
    plan: Mapped[str] = mapped_column(String(40), server_default="development")


class Location(Identified, Created, Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("id", "organization_id"),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    time_zone: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(500))


class Membership(Identified, Created, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id"),
        UniqueConstraint("id", "organization_id"),
        CheckConstraint("role IN ('owner','org_admin','manager','staff','installer')", name="role"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")


class LocationGrant(Created, Base):
    __tablename__ = "location_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"], ["memberships.id", "memberships.organization_id"]
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"], ["locations.id", "locations.organization_id"]
        ),
    )
    membership_id: Mapped[UUID] = mapped_column(primary_key=True)
    location_id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Scoped:
    organization_id: Mapped[UUID] = mapped_column(index=True)
    location_id: Mapped[UUID] = mapped_column(index=True)


class Camera(Identified, Created, Scoped, Base):
    __tablename__ = "cameras"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "organization_id"], ["locations.id", "locations.organization_id"]
        ),
        UniqueConstraint("id", "organization_id", "location_id"),
        UniqueConstraint("location_id", "label"),
        CheckConstraint("status = 'NOT_CONFIGURED'", name="camera_unconfigured"),
    )
    label: Mapped[str] = mapped_column(String(80))
    source_reference: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), server_default="NOT_CONFIGURED")


class DiningTable(Identified, Created, Scoped, Base):
    __tablename__ = "dining_tables"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "organization_id"], ["locations.id", "locations.organization_id"]
        ),
        UniqueConstraint("id", "organization_id", "location_id"),
        UniqueConstraint("location_id", "label"),
        CheckConstraint("seats IS NULL OR seats BETWEEN 1 AND 100", name="seats"),
        CheckConstraint(
            "current_state IN ('UNKNOWN','AVAILABLE','OCCUPIED','RESET_PENDING',"
            "'CLEANING','OUT_OF_SERVICE')",
            name="table_state",
        ),
    )
    label: Mapped[str] = mapped_column(String(80))
    seats: Mapped[int | None] = mapped_column(Integer)
    current_state: Mapped[str] = mapped_column(String(30), server_default="UNKNOWN")
    state_since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TableZone(Identified, Created, Scoped, Base):
    __tablename__ = "table_zones"
    __table_args__ = (
        ForeignKeyConstraint(
            ["table_id", "organization_id", "location_id"],
            ["dining_tables.id", "dining_tables.organization_id", "dining_tables.location_id"],
        ),
        ForeignKeyConstraint(
            ["camera_id", "organization_id", "location_id"],
            ["cameras.id", "cameras.organization_id", "cameras.location_id"],
        ),
        UniqueConstraint("table_id", "camera_id"),
        CheckConstraint("revision >= 1", name="zone_revision"),
        CheckConstraint("source_width > 0 AND source_height > 0", name="source_resolution"),
        CheckConstraint("security.valid_polygon(polygon)", name="normalized_polygon"),
    )
    table_id: Mapped[UUID] = mapped_column()
    camera_id: Mapped[UUID] = mapped_column()
    polygon: Mapped[list] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, server_default="1")
    source_width: Mapped[int] = mapped_column(Integer)
    source_height: Mapped[int] = mapped_column(Integer)


class AuditLog(Identified, Created, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "organization_id"], ["locations.id", "locations.organization_id"]
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    location_id: Mapped[UUID | None] = mapped_column()
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"))
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
