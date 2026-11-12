"""Reviewed workflow provenance. Only narrow database functions may mutate it."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
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


def scope_ref(column, table, target="id"):
    return ForeignKeyConstraint(
        [column, "organization_id", "location_id"],
        [f"{table}.{target}", f"{table}.organization_id", f"{table}.location_id"],
    )


class WorkflowPolicy(Scoped, Base):
    __tablename__ = "workflow_policies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "organization_id"], ["locations.id", "locations.organization_id"]
        ),
        CheckConstraint("mode IN ('OFF','ASSISTED_REVIEW')", name="workflow_mode"),
        CheckConstraint("revision > 0", name="workflow_policy_revision"),
    )
    location_id: Mapped[UUID] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(24), server_default="OFF")
    revision: Mapped[int] = mapped_column(Integer)
    enabled_since: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rules: Mapped[dict] = mapped_column(JSONB)
    rules_sha256: Mapped[str] = mapped_column(String(64))
    bindings: Mapped[list] = mapped_column(JSONB)


class WorkflowSession(Identified, Created, Scoped, Base):
    __tablename__ = "workflow_sessions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "location_id"),
        UniqueConstraint("binding_id", "source_generation", "source_episode"),
        scope_ref("table_id", "dining_tables"),
        ForeignKeyConstraint(
            ["binding_id", "device_id", "organization_id", "location_id"],
            [
                "edge_bindings.id",
                "edge_bindings.device_id",
                "edge_bindings.organization_id",
                "edge_bindings.location_id",
            ],
        ),
        scope_ref("arrival_receipt_id", "edge_receipts", "event_id"),
        CheckConstraint(
            "status IN ('OPEN','VACATED','COMPLETE','INVALIDATED')", name="workflow_session_status"
        ),
        Index("workflow_session_table_time", "table_id", "arrived_at"),
    )
    table_id: Mapped[UUID]
    device_id: Mapped[UUID]
    binding_id: Mapped[UUID]
    source_generation: Mapped[UUID]
    source_episode: Mapped[UUID]
    arrival_receipt_id: Mapped[UUID]
    arrived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), server_default="OPEN")


class WorkflowEvidence(Scoped, Base):
    __tablename__ = "workflow_evidence"
    __table_args__ = (
        UniqueConstraint("receipt_id", "organization_id", "location_id"),
        scope_ref("receipt_id", "edge_receipts", "event_id"),
        scope_ref("table_id", "dining_tables"),
        ForeignKeyConstraint(
            ["binding_id", "device_id", "organization_id", "location_id"],
            [
                "edge_bindings.id",
                "edge_bindings.device_id",
                "edge_bindings.organization_id",
                "edge_bindings.location_id",
            ],
        ),
        CheckConstraint("kind IN ('POSITIVE','VACANT','UNCERTAIN')", name="workflow_evidence_kind"),
        CheckConstraint("valid_until >= observed_at", name="workflow_evidence_interval"),
        Index("workflow_evidence_table_time", "table_id", "observed_at"),
    )
    receipt_id: Mapped[UUID] = mapped_column(primary_key=True)
    table_id: Mapped[UUID]
    device_id: Mapped[UUID]
    binding_id: Mapped[UUID]
    source_generation: Mapped[UUID]
    policy_revision: Mapped[int] = mapped_column(Integer)
    manual_revision: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(12))
    qualified: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(32))
    summary: Mapped[dict] = mapped_column(JSONB)


class WorkflowSuggestion(Identified, Created, Scoped, Base):
    __tablename__ = "workflow_suggestions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "location_id"),
        scope_ref("table_id", "dining_tables"),
        scope_ref("receipt_id", "edge_receipts", "event_id"),
        scope_ref("latest_receipt_id", "workflow_evidence", "receipt_id"),
        scope_ref("session_id", "workflow_sessions"),
        ForeignKeyConstraint(
            ["binding_id", "device_id", "organization_id", "location_id"],
            [
                "edge_bindings.id",
                "edge_bindings.device_id",
                "edge_bindings.organization_id",
                "edge_bindings.location_id",
            ],
        ),
        UniqueConstraint("receipt_id"),
        CheckConstraint("action IN ('ARRIVAL','DEPARTURE')", name="workflow_suggestion_action"),
        CheckConstraint(
            "status IN ('PENDING','ACCEPTED','DISMISSED','SUPERSEDED')",
            name="workflow_suggestion_status",
        ),
        Index(
            "workflow_pending_suggestion",
            "table_id",
            "action",
            unique=True,
            postgresql_where=text("status='PENDING'"),
        ),
    )
    table_id: Mapped[UUID]
    device_id: Mapped[UUID]
    binding_id: Mapped[UUID]
    source_generation: Mapped[UUID]
    source_episode: Mapped[UUID]
    receipt_id: Mapped[UUID]
    latest_receipt_id: Mapped[UUID]
    session_id: Mapped[UUID | None]
    action: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16), server_default="PENDING")
    revision: Mapped[int] = mapped_column(Integer, server_default="1")
    table_revision: Mapped[int] = mapped_column(Integer)
    policy_revision: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowAttempt(Identified, Scoped, Base):
    __tablename__ = "workflow_task_attempts"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "location_id"),
        UniqueConstraint("task_id", "number"),
        scope_ref("task_id", "staff_tasks"),
        scope_ref("session_id", "workflow_sessions"),
        CheckConstraint(
            "status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','COMPLETED','CANCELLED')",
            name="workflow_attempt_status",
        ),
        Index(
            "workflow_current_attempt",
            "task_id",
            unique=True,
            postgresql_where=text("status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS')"),
        ),
    )
    task_id: Mapped[UUID]
    session_id: Mapped[UUID]
    number: Mapped[int] = mapped_column(Integer)
    pending_since: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    resolution: Mapped[str | None] = mapped_column(String(80))


class WorkflowDecision(Identified, Created, Scoped, Base):
    __tablename__ = "workflow_decisions"
    __table_args__ = (
        UniqueConstraint("actor_id", "location_id", "request_key"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"], ["locations.id", "locations.organization_id"]
        ),
        scope_ref("table_id", "dining_tables"),
        scope_ref("suggestion_id", "workflow_suggestions"),
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"))
    table_id: Mapped[UUID | None]
    suggestion_id: Mapped[UUID | None]
    action: Mapped[str] = mapped_column(String(32))
    request_key: Mapped[UUID]
    fingerprint: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(32))
    result: Mapped[dict] = mapped_column(JSONB)


class WorkflowPolicyHistory(Identified, Created, Scoped, Base):
    __tablename__ = "workflow_policy_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "organization_id"], ["locations.id", "locations.organization_id"]
        ),
        UniqueConstraint("location_id", "revision"),
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"))
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB)


class WorkflowJournal(Scoped, Base):
    __tablename__ = "workflow_journal"
    __table_args__ = (
        scope_ref("event_id", "table_events"),
        scope_ref("table_id", "dining_tables"),
        scope_ref("session_id", "workflow_sessions"),
        scope_ref("attempt_id", "workflow_task_attempts"),
        CheckConstraint(
            "basis IN ('CONFIRMED_WORKFLOW','DEMO','LEGACY')", name="workflow_journal_basis"
        ),
        Index("workflow_journal_location_time", "location_id", "occurred_at"),
    )
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    table_id: Mapped[UUID]
    session_id: Mapped[UUID | None]
    attempt_id: Mapped[UUID | None]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    basis: Mapped[str] = mapped_column(String(24))


class WorkflowQualityBoundary(Scoped, Base):
    __tablename__ = "workflow_quality_boundaries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "revision"],
            ["location_notifications.location_id", "location_notifications.revision"],
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id", "location_id"],
            ["edge_devices.id", "edge_devices.organization_id", "edge_devices.location_id"],
        ),
        CheckConstraint(
            "reason IN ('OFFLINE','DEGRADED','CONFIG_CHANGED','POLICY_CHANGED')",
            name="workflow_boundary_reason",
        ),
        Index("workflow_boundary_device_time", "device_id", "occurred_at"),
    )
    location_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[UUID]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(24))
