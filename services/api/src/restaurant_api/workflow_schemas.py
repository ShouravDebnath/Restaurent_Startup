"""Explicit dashboard contracts; no camera credentials or invented AI confidence."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from restaurant_api.schemas import LocationOut, Strict

State = Literal["UNKNOWN", "AVAILABLE", "OCCUPIED", "RESET_PENDING", "CLEANING", "OUT_OF_SERVICE"]
TaskStatus = Literal["OPEN", "ACKNOWLEDGED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]


class DashboardTable(Strict):
    id: UUID
    organization_id: UUID
    location_id: UUID
    label: str
    seats: int | None
    current_state: State
    state_since: datetime
    created_at: datetime
    operational_revision: int
    state_source: str
    occupancy_session_id: UUID | None
    occupied_since: datetime | None
    source_status: str
    observation: str
    observed_at: datetime | None


class TaskOut(Strict):
    id: UUID
    organization_id: UUID
    location_id: UUID
    table_id: UUID
    occupancy_session_id: UUID
    status: TaskStatus
    type: Literal["RESET"]
    created_at: datetime
    acknowledged_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    resolution: str | None


class EventOut(Strict):
    id: UUID
    organization_id: UUID
    location_id: UUID
    table_id: UUID
    revision: int
    event_type: str
    source: str
    actor_id: UUID | None
    occurred_at: datetime
    ingested_at: datetime
    schema_version: int
    previous_state: State
    new_state: State
    payload: dict
    confidence: float | None


class DashboardOut(Strict):
    demo: bool
    simulation_controls: bool
    location: LocationOut
    role: str
    server_time: datetime
    cursor: str
    tables: list[DashboardTable]
    tasks: list[TaskOut]
    tables_truncated: bool
    tasks_truncated: bool


class StaffAction(Strict):
    action: Literal["acknowledge", "start_cleaning", "mark_ready", "out_of_service", "reopen"]
    expected_revision: int = Field(ge=0, le=2147483647, strict=True)
    request_key: UUID
    task_id: UUID | None = None
    confirmed: bool = Field(default=False, strict=True)
    reason: Literal["", "maintenance", "reserved", "safety", "other"] = ""


class DemoAction(Strict):
    table_id: UUID
    action: Literal["arrive", "depart", "vacant", "source_offline", "source_resume"]
    expected_revision: int = Field(ge=0, le=2147483647, strict=True)
    request_key: UUID


class ActionOut(Strict):
    table_id: UUID
    event_id: UUID
    revision: int
    cursor: str
    state: State
