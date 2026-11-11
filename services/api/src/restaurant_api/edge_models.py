"""Phase 6 metadata only. No raw images, private keys or camera credentials."""

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_api.models import Base, Created, Identified, Scoped


class EdgePairing(Identified, Created, Base):
    __tablename__ = 'pairings'
    __table_args__: ClassVar[dict] = {'schema': 'edge_private'}
    key_id: Mapped[UUID] = mapped_column(unique=True)
    public_key: Mapped[str] = mapped_column(String(44))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    challenge: Mapped[str] = mapped_column(String(32))
    peer_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    proved: Mapped[bool] = mapped_column(Boolean, server_default='false')
    device_id: Mapped[UUID | None]


class EdgeNonce(Base):
    __tablename__ = 'nonces'
    __table_args__: ClassVar[dict] = {'schema': 'edge_private'}
    key_id: Mapped[UUID] = mapped_column(primary_key=True)
    nonce: Mapped[str] = mapped_column(String(32), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EdgeDevice(Identified, Created, Scoped, Base):
    __tablename__ = 'edge_devices'
    __table_args__ = (
        UniqueConstraint('id', 'organization_id', 'location_id'),
        ForeignKeyConstraint(['location_id', 'organization_id'], ['locations.id', 'locations.organization_id']),
        CheckConstraint("purpose IN ('AI_SHADOW','SYNTHETIC_WORKFLOW_TEST')", name='edge_purpose'),
        CheckConstraint("status IN ('ACTIVE','REVOKED')", name='edge_status'),
    )
    label: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(32), server_default='AI_SHADOW')
    status: Mapped[str] = mapped_column(String(12), server_default='ACTIVE')
    processing_enabled: Mapped[bool] = mapped_column(Boolean, server_default='false')
    revision: Mapped[int] = mapped_column(Integer, server_default='1')
    stream_id: Mapped[UUID | None]
    stream_cursor: Mapped[int] = mapped_column(Integer, server_default='0')
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offline_published: Mapped[bool] = mapped_column(Boolean, server_default='false')


class EdgeKey(Identified, Created, Scoped, Base):
    __tablename__ = 'edge_keys'
    __table_args__ = (
        ForeignKeyConstraint(['device_id', 'organization_id', 'location_id'],
                             ['edge_devices.id', 'edge_devices.organization_id', 'edge_devices.location_id']),
        UniqueConstraint('fingerprint'),
    )
    device_id: Mapped[UUID] = mapped_column(index=True)
    public_key: Mapped[str] = mapped_column(String(44))
    fingerprint: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, server_default='false')


class EdgeAssignment(Identified, Created, Scoped, Base):
    __tablename__ = 'edge_assignments'
    __table_args__ = (
        UniqueConstraint('id', 'device_id', 'organization_id', 'location_id', 'camera_id'),
        Index('one_active_edge_camera', 'camera_id', unique=True, postgresql_where=text('enabled')),
        ForeignKeyConstraint(['device_id', 'organization_id', 'location_id'],
                             ['edge_devices.id', 'edge_devices.organization_id', 'edge_devices.location_id']),
        ForeignKeyConstraint(['camera_id', 'organization_id', 'location_id'],
                             ['cameras.id', 'cameras.organization_id', 'cameras.location_id']),
    )
    device_id: Mapped[UUID] = mapped_column(index=True)
    camera_id: Mapped[UUID]
    epoch: Mapped[UUID]
    enabled: Mapped[bool] = mapped_column(Boolean, server_default='false')
    model_sha256: Mapped[str] = mapped_column(String(64))
    profile_sha256: Mapped[str] = mapped_column(String(64))
    profile_revision: Mapped[int] = mapped_column(Integer)
    policy_revision: Mapped[int] = mapped_column(Integer, server_default='1')


class EdgeBinding(Identified, Created, Scoped, Base):
    __tablename__ = 'edge_bindings'
    __table_args__ = (
        Index('one_active_edge_table', 'table_id', unique=True, postgresql_where=text('enabled')),
        UniqueConstraint('id', 'device_id', 'organization_id', 'location_id'),
        ForeignKeyConstraint(['assignment_id', 'device_id', 'organization_id', 'location_id', 'camera_id'],
                             ['edge_assignments.id', 'edge_assignments.device_id', 'edge_assignments.organization_id',
                              'edge_assignments.location_id', 'edge_assignments.camera_id']),
        ForeignKeyConstraint(['table_id', 'organization_id', 'location_id'],
                             ['dining_tables.id', 'dining_tables.organization_id', 'dining_tables.location_id']),
    )
    assignment_id: Mapped[UUID]
    device_id: Mapped[UUID] = mapped_column(index=True)
    camera_id: Mapped[UUID]
    table_id: Mapped[UUID]
    zone_revision: Mapped[int] = mapped_column(Integer)
    epoch: Mapped[UUID]
    enabled: Mapped[bool] = mapped_column(Boolean, server_default='true')


class EdgeReceipt(Created, Scoped, Base):
    __tablename__ = 'edge_receipts'
    __table_args__ = (
        ForeignKeyConstraint(['device_id', 'organization_id', 'location_id'],
                             ['edge_devices.id', 'edge_devices.organization_id', 'edge_devices.location_id']),
        UniqueConstraint('device_id', 'stream_id', 'sequence'),
        CheckConstraint("disposition IN ('pending','shadow','fixture','history','rejected')", name='edge_disposition'),
    )
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    device_id: Mapped[UUID] = mapped_column(index=True)
    stream_id: Mapped[UUID]
    sequence: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    disposition: Mapped[str] = mapped_column(String(12), server_default='pending')
    reason: Mapped[str] = mapped_column(String(24), server_default='PENDING_GAP')


class EdgeShadow(Scoped, Base):
    __tablename__ = 'edge_shadows'
    __table_args__ = (
        ForeignKeyConstraint(['binding_id', 'device_id', 'organization_id', 'location_id'],
                             ['edge_bindings.id', 'edge_bindings.device_id', 'edge_bindings.organization_id',
                              'edge_bindings.location_id']),
    )
    binding_id: Mapped[UUID] = mapped_column(primary_key=True)
    device_id: Mapped[UUID]
    sequence: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(32))
    source_generation: Mapped[UUID | None]
    needs_context: Mapped[bool] = mapped_column(Boolean, server_default='false')


class EdgeHealth(Scoped, Base):
    __tablename__ = 'edge_health'
    __table_args__ = (
        ForeignKeyConstraint(['device_id', 'organization_id', 'location_id'],
                             ['edge_devices.id', 'edge_devices.organization_id', 'edge_devices.location_id']),
    )
    device_id: Mapped[UUID] = mapped_column(primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[dict] = mapped_column(JSONB)


class EdgeAudit(Identified, Created, Scoped, Base):
    __tablename__ = 'edge_audits'
    __table_args__ = (
        ForeignKeyConstraint(['device_id', 'organization_id', 'location_id'],
                             ['edge_devices.id', 'edge_devices.organization_id', 'edge_devices.location_id']),
    )
    device_id: Mapped[UUID]
    action: Mapped[str] = mapped_column(String(40))
    event_id: Mapped[UUID | None]


class LocationNotification(Scoped, Created, Base):
    __tablename__ = 'location_notifications'
    __table_args__ = (
        ForeignKeyConstraint(['location_id', 'organization_id'], ['locations.id', 'locations.organization_id']),
    )
    location_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(String(24))
