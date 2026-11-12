"""Scoped, bounded snapshot reports and reauthorized CSV delivery."""

from contextlib import contextmanager
from datetime import date, datetime
from threading import Lock
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from restaurant_api.analytics_domain import calculate, csv_bytes, report_range
from restaurant_api.database import get_db
from restaurant_api.models import DiningTable
from restaurant_api.routes import Auth
from restaurant_api.security import CONFIGURATORS, Db, location_access, resolve_identity

router = APIRouter(prefix="/v1", tags=["analytics"])
INPUT_LIMIT = 100000
_export_lock = Lock()
_export_users: set[UUID] = set()


class BoundedExport(StreamingResponse):
    """Release admission even when a client disconnects or streaming fails."""

    def __init__(self, *args, user_id, **kwargs):
        self.user_id = user_id
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            release_export(self.user_id)


def admit_export(user_id):
    # Local single-process deployment: one calculation/export per user, four total.
    with _export_lock:
        if user_id in _export_users or len(_export_users) >= 4:
            raise HTTPException(429, "A report or export is already running. Try again shortly.")
        _export_users.add(user_id)


def release_export(user_id):
    with _export_lock:
        _export_users.discard(user_id)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BucketRow(Strict):
    table_id: UUID
    table_label: str
    bucket_start: datetime
    bucket_end: datetime
    local_label: str
    configured_seconds: float
    usable_seconds: float
    state_seconds: dict[str, float] | None
    occupied_seconds: float | None
    recorded_occupied_fraction: float | None
    workflow_coverage: float | None
    known_evidence_seconds: float
    unknown_evidence_seconds: float
    evidence_coverage: float | None
    estimated_occupied_seconds: float
    estimated_occupied_fraction: float | None


class Summary(Strict):
    average_occupied_seconds: float | None
    completed_occupied_sessions: int
    completed_resets: int
    average_wait_to_clean_seconds: float | None
    average_cleaning_seconds: float | None
    average_time_to_ready_seconds: float | None
    cancelled_attempts: int
    open_reset_attempts: int
    oldest_open_reset_seconds: float | None
    open_occupied_sessions: int
    cross_boundary_sessions: int
    excluded_sessions: int
    excluded_attempts: int
    corrections_applied: int


class Report(Strict):
    from_date: date
    to_date_exclusive: date
    time_zone: str
    group: Literal["day", "hour"]
    basis: Literal["CONFIRMED_WORKFLOW", "DEMO", "LEGACY", "ESTIMATED_EVIDENCE"]
    estimate_basis: Literal["ESTIMATED_EVIDENCE"]
    synthetic: bool
    as_of: datetime
    calculation_version: int
    cursor: str
    rows: list[BucketRow]
    summary: Summary
    limitations: list[str]


SNAPSHOT_SQL = """
WITH tables_ AS (SELECT id,label,created_at FROM public.dining_tables
    WHERE location_id=:loc AND (CAST(:table_id AS uuid) IS NULL OR id=CAST(:table_id AS uuid)) ORDER BY id LIMIT 101),
events_ AS (
    (SELECT e.*,coalesce(j.basis,'LEGACY') AS basis FROM public.table_events e
      LEFT JOIN public.workflow_journal j ON j.event_id=e.id
      WHERE e.table_id IN (SELECT id FROM tables_) AND e.occurred_at>=:start AND e.occurred_at<:end ORDER BY e.occurred_at,e.revision LIMIT 100001)
    UNION ALL
    (SELECT DISTINCT ON(e.table_id) e.*,coalesce(j.basis,'LEGACY') AS basis FROM public.table_events e
      LEFT JOIN public.workflow_journal j ON j.event_id=e.id
      WHERE e.table_id IN (SELECT id FROM tables_) AND e.occurred_at<:start ORDER BY e.table_id,e.occurred_at DESC,e.revision DESC)
),
scenario_tasks_ AS (
    SELECT t.* FROM public.staff_tasks t WHERE t.table_id IN(SELECT id FROM tables_)
      AND t.created_at<:end AND coalesce(t.completed_at,CAST(:end AS timestamptz))>=:start
      AND EXISTS(SELECT 1 FROM public.location_operations o WHERE o.location_id=t.location_id AND o.is_synthetic)
      AND NOT EXISTS(SELECT 1 FROM public.workflow_sessions s WHERE s.id=t.occupancy_session_id
          AND s.table_id=t.table_id) ORDER BY t.created_at,t.id LIMIT 100001
)
SELECT statement_timestamp() AS as_of,o.is_synthetic AS synthetic,o.revision,
    coalesce((SELECT jsonb_agg(to_jsonb(t)) FROM tables_ t),'[]'::jsonb) AS tables,
    coalesce((SELECT jsonb_agg(to_jsonb(e)) FROM events_ e),'[]'::jsonb) AS events,
    coalesce((SELECT jsonb_agg(to_jsonb(s)) FROM (SELECT * FROM public.workflow_sessions
        WHERE table_id IN(SELECT id FROM tables_) AND arrived_at<:end
        AND coalesce(ready_at,departed_at,CAST(:end AS timestamptz))>=:start LIMIT 100001) s),'[]'::jsonb) AS sessions,
    coalesce((SELECT jsonb_agg(to_jsonb(a)) FROM (SELECT a.* FROM public.workflow_task_attempts a
        JOIN public.staff_tasks t ON t.id=a.task_id WHERE t.table_id IN(SELECT id FROM tables_) AND a.pending_since<:end
        AND coalesce(a.completed_at,a.cancelled_at,CAST(:end AS timestamptz))>=:start LIMIT 100001) a),'[]'::jsonb) AS attempts,
    coalesce((SELECT jsonb_agg(to_jsonb(t)||jsonb_build_object(
        'arrived_at',(SELECT e.occurred_at FROM public.table_events e
            WHERE e.table_id=t.table_id AND e.location_id=t.location_id AND e.organization_id=t.organization_id
              AND e.occurred_at<=t.created_at AND e.source='demo' AND e.event_type='table.arrive'
              AND e.new_state='OCCUPIED' AND e.previous_state NOT IN('OCCUPIED','CLEANING','OUT_OF_SERVICE')
            ORDER BY e.occurred_at DESC,e.revision DESC LIMIT 1),
        'departure_verified',(SELECT count(*)=1 FROM public.table_events e JOIN public.workflow_journal j ON j.event_id=e.id
            WHERE e.table_id=t.table_id AND e.location_id=t.location_id AND e.organization_id=t.organization_id
              AND e.occurred_at=t.created_at AND e.source='demo' AND e.event_type IN('table.depart','table.vacant')
              AND e.new_state='RESET_PENDING' AND e.previous_state IN('OCCUPIED','UNKNOWN') AND j.basis='DEMO'),
        'start_verified',(SELECT count(*)=1 FROM public.table_events e JOIN public.workflow_journal j ON j.event_id=e.id
            WHERE e.table_id=t.table_id AND e.location_id=t.location_id AND e.organization_id=t.organization_id
              AND e.occurred_at=t.started_at AND e.source='manual' AND e.event_type='table.start_cleaning'
              AND e.previous_state='RESET_PENDING' AND e.new_state='CLEANING' AND j.basis='DEMO'),
        'ready_verified',(SELECT count(*)=1 FROM public.table_events e JOIN public.workflow_journal j ON j.event_id=e.id
            WHERE e.table_id=t.table_id AND e.location_id=t.location_id AND e.organization_id=t.organization_id
              AND e.occurred_at=t.completed_at AND e.source='manual' AND e.event_type='table.mark_ready'
              AND e.previous_state IN('CLEANING','UNKNOWN') AND e.new_state='AVAILABLE' AND j.basis='DEMO')
        )) FROM scenario_tasks_ t),'[]'::jsonb) AS scenario_tasks,
    coalesce((SELECT jsonb_agg(to_jsonb(e)) FROM (SELECT e.*,r.sequence FROM public.workflow_evidence e
        JOIN public.edge_receipts r ON r.event_id=e.receipt_id WHERE e.table_id IN(SELECT id FROM tables_)
        AND e.observed_at>=CAST(:start AS timestamptz)-interval '15 seconds' AND e.observed_at<:end LIMIT 100001) e),'[]'::jsonb) AS evidence,
    coalesce((SELECT jsonb_agg(to_jsonb(c)) FROM (SELECT table_id,event_type,occurred_at,payload FROM public.table_events
        WHERE table_id IN(SELECT id FROM tables_) AND event_type IN('workflow.correct_arrival','workflow.correct_departure')
        AND occurred_at<=statement_timestamp() LIMIT 100001) c),'[]'::jsonb) AS corrections,
    coalesce((SELECT jsonb_agg(to_jsonb(c)) FROM (SELECT device_id,occurred_at FROM public.workflow_quality_boundaries
        WHERE location_id=:loc AND occurred_at>=CAST(:start AS timestamptz)-interval '15 seconds'
        AND occurred_at<:end LIMIT 100001) c),'[]'::jsonb) AS boundaries
FROM public.location_operations o WHERE o.location_id=:loc
"""


def build(db, identity, location_id, from_date, to_date, group, basis, table_id):
    loc, _ = location_access(db, identity, location_id, CONFIGURATORS)
    if table_id:
        table = db.get(DiningTable, table_id)
        if table is None or table.location_id != location_id:
            raise HTTPException(404, "Resource not found.")
    try:
        start, end, _ = report_range(from_date, to_date, loc.time_zone)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    db.execute(text("SET LOCAL statement_timeout='8s'"))
    snapshot = dict(
        db.execute(
            text(SNAPSHOT_SQL),
            {"loc": location_id, "table_id": table_id, "start": start, "end": end},
        )
        .mappings()
        .one()
    )
    if any(
        len(snapshot[k]) > INPUT_LIMIT
        for k in [
            "events",
            "sessions",
            "attempts",
            "scenario_tasks",
            "evidence",
            "corrections",
            "boundaries",
        ]
    ):
        raise HTTPException(
            422, "Report history is too large. Select a shorter range or one table."
        )
    snapshot["cursor"] = f"{location_id}:{snapshot.pop('revision')}"
    basis = basis or ("DEMO" if snapshot["synthetic"] else "CONFIRMED_WORKFLOW")
    try:
        return calculate(snapshot, from_date, to_date, loc.time_zone, group, basis)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.get("/locations/{location_id}/analytics", response_model=Report)
def analytics(
    location_id: UUID,
    identity: Auth,
    db: Db,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    group: Literal["day", "hour"] = "day",
    basis: Literal["CONFIRMED_WORKFLOW", "DEMO", "LEGACY", "ESTIMATED_EVIDENCE"] | None = None,
    table_id: UUID | None = None,
):
    location_access(db, identity, location_id, CONFIGURATORS)
    admit_export(identity.id)
    try:
        return build(db, identity, location_id, from_date, to_date, group, basis, table_id)
    finally:
        release_export(identity.id)


def authorized_csv(data, token, location_id):
    # API framing and the browser's expected-byte check detect interruption.
    # Already delivered bytes cannot be recalled.
    for start in range(0, len(data), 4096):
        try:
            with contextmanager(get_db)() as db:
                identity = resolve_identity(db, token, touch=False)
                location_access(db, identity, location_id, CONFIGURATORS)
        except HTTPException:
            return
        yield data[start : start + 4096]


@router.get("/locations/{location_id}/analytics.csv", response_class=StreamingResponse)
def export(
    location_id: UUID,
    identity: Auth,
    db: Db,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    group: Literal["day", "hour"] = "day",
    basis: Literal["CONFIRMED_WORKFLOW", "DEMO", "LEGACY", "ESTIMATED_EVIDENCE"] | None = None,
    table_id: UUID | None = None,
):
    location_access(db, identity, location_id, CONFIGURATORS)
    admit_export(identity.id)
    try:
        report = build(db, identity, location_id, from_date, to_date, group, basis, table_id)
        data = csv_bytes(report)
        if len(data) > 16777216:
            raise HTTPException(422, "Export is too large; select a shorter range.")
    except BaseException:
        release_export(identity.id)
        raise
    return BoundedExport(
        authorized_csv(data, identity.session_token, location_id),
        user_id=identity.id,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="restaurant-report-{from_date.isoformat()}.csv"',
            "Content-Length": str(len(data)),
            "X-Report-Bytes": str(len(data)),
            "Cache-Control": "private, no-store",
        },
    )
