"""Phase 3 HTTP and durable SSE transport. No real video or edge ingestion."""

import hashlib
import json
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from starlette.background import BackgroundTask

from restaurant_api import workflow_schemas as s
from restaurant_api.database import get_db
from restaurant_api.models import DiningTable, LocationOperations, StaffTask, TableEvent
from restaurant_api.routes import Auth, Write
from restaurant_api.security import CONFIGURATORS, Db, location_access, resolve_identity
from restaurant_api.settings import get_settings

router = APIRouter(prefix="/v1", tags=["dashboard"])
HEARTBEAT_SECONDS = 2.0
MAX_STREAMS_PER_USER = 4  # Per process; shared/proxy production quotas remain a deployment gate.
MAX_STREAMS_TOTAL = 32
_streams: dict[UUID, int] = {}
_stream_lock = threading.Lock()


class StreamLease:
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        self.closed = False
        with _stream_lock:
            if (_streams.get(user_id, 0) >= MAX_STREAMS_PER_USER
                    or sum(_streams.values()) >= MAX_STREAMS_TOTAL):
                raise HTTPException(429, "Too many open dashboards. Close another tab.")
            _streams[user_id] = _streams.get(user_id, 0) + 1

    def close(self):
        with _stream_lock:
            if self.closed:
                return
            self.closed = True
            remaining = _streams.get(self.user_id, 1) - 1
            if remaining > 0:
                _streams[self.user_id] = remaining
            else:
                _streams.pop(self.user_id, None)


def cursor(location_id: UUID, revision: int) -> str:
    return f"{location_id}:{revision}"


def parse_cursor(value: str | None, location_id: UUID, revision: int) -> int:
    if value is None:
        return revision
    prefix, separator, number = value.partition(":")
    if (not separator or prefix != str(location_id) or not number.isascii()
            or not number.isdecimal() or len(number) > 10):
        raise HTTPException(409, "Stream position is invalid; reload the dashboard.")
    position = int(number)
    if position > revision:
        raise HTTPException(409, "Stream position is ahead; reload the dashboard.")
    return position


def operation_scope(db, identity, location_id):
    loc, member = location_access(db, identity, location_id)
    ops = db.get(LocationOperations, loc.id)
    if ops is None:
        raise HTTPException(503, "Dashboard migrations are required.")
    return loc, member, ops


@router.get("/locations/{location_id}/dashboard", response_model=s.DashboardOut)
def dashboard(location_id: UUID, identity: Auth, db: Db):
    loc, member, _ = operation_scope(db, identity, location_id)
    # One SQL statement supplies a consistent cursor/state/task snapshot at READ COMMITTED.
    result = db.execute(text("""
        SELECT o.revision,o.is_synthetic,
          coalesce((SELECT jsonb_agg(to_jsonb(t) ORDER BY t.label,t.id) FROM
            (SELECT * FROM public.dining_tables WHERE location_id=:loc ORDER BY label,id LIMIT 500) t),'[]'::jsonb) AS tables,
          coalesce((SELECT jsonb_agg(to_jsonb(t) ORDER BY t.created_at,t.id) FROM
            (SELECT * FROM public.staff_tasks WHERE location_id=:loc AND status IN
             ('OPEN','ACKNOWLEDGED','IN_PROGRESS') ORDER BY created_at,id LIMIT 100) t),'[]'::jsonb) AS tasks,
          (SELECT count(*)>500 FROM public.dining_tables WHERE location_id=:loc) AS tables_truncated,
          (SELECT count(*)>100 FROM public.staff_tasks WHERE location_id=:loc AND status IN
             ('OPEN','ACKNOWLEDGED','IN_PROGRESS')) AS tasks_truncated
        FROM public.location_operations o WHERE o.location_id=:loc
        """), {"loc": location_id}).mappings().first()
    if result is None:
        raise HTTPException(404, "Resource not found.")
    return s.DashboardOut(
        demo=result["is_synthetic"],
        simulation_controls=(result["is_synthetic"] and get_settings().demo_mode
                             and member.role in CONFIGURATORS),
        location=loc, role=member.role, server_time=datetime.now(UTC),
        cursor=cursor(location_id, result["revision"]), tables=result["tables"],
        tasks=result["tasks"], tables_truncated=result["tables_truncated"],
        tasks_truncated=result["tasks_truncated"],
    )


@router.get("/locations/{location_id}/tasks", response_model=list[s.TaskOut])
def tasks(location_id: UUID, identity: Auth, db: Db,
          status: s.TaskStatus | None = None, limit: int = Query(50, ge=1, le=100),
          offset: int = Query(0, ge=0, le=100000)):
    operation_scope(db, identity, location_id)
    query = select(StaffTask).where(StaffTask.location_id == location_id)
    if status:
        query = query.where(StaffTask.status == status)
    return db.scalars(query.order_by(StaffTask.created_at, StaffTask.id).limit(limit).offset(offset)).all()


@router.get("/locations/{location_id}/activity", response_model=list[s.EventOut])
def activity(location_id: UUID, identity: Auth, db: Db, table_id: UUID | None = None,
             limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)):
    operation_scope(db, identity, location_id)
    query = select(TableEvent).where(TableEvent.location_id == location_id)
    if table_id:
        record = db.get(DiningTable, table_id)
        if record is None or record.location_id != location_id:
            raise HTTPException(404, "Resource not found.")
        query = query.where(TableEvent.table_id == table_id)
    return db.scalars(query.order_by(TableEvent.revision.desc()).limit(limit).offset(offset)).all()


def execute_action(db, table_id, body, *, demo=False):
    fields = body.model_dump(mode="json")
    fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    try:
        result = db.scalar(text("""SELECT security.table_action(
            :table,:operation,:expected,:key,:fingerprint,:task,:confirmed,:reason,:demo,:enabled)
            """), {"table": table_id, "operation": body.action,
                    "expected": body.expected_revision, "key": body.request_key,
                    "fingerprint": fingerprint, "task": getattr(body, "task_id", None),
                    "confirmed": getattr(body, "confirmed", False),
                    "reason": getattr(body, "reason", ""), "demo": demo,
                    "enabled": get_settings().demo_mode})
        return s.ActionOut.model_validate(result)
    except DBAPIError as error:
        status = {"P0403": 403, "P0404": 404, "P0409": 409, "P0422": 422}.get(
            getattr(error.orig, "sqlstate", ""))
        if status:
            messages = {403: "This role cannot perform this action.", 404: "Resource not found.",
                        409: "Table or task changed, or the action is unsafe. Refresh and check source status.",
                        422: "Invalid action fields."}
            raise HTTPException(status, messages[status]) from None
        raise


@router.post("/tables/{table_id}/actions", response_model=s.ActionOut)
def staff_action(table_id: UUID, body: s.StaffAction, identity: Write, db: Db):
    record = db.get(DiningTable, table_id)
    if record is None:
        raise HTTPException(404, "Resource not found.")
    return execute_action(db, table_id, body)


@router.post("/locations/{location_id}/demo/events", response_model=s.ActionOut)
def demo_action(location_id: UUID, body: s.DemoAction, identity: Write, db: Db):
    _, _, ops = operation_scope(db, identity, location_id)
    if not get_settings().demo_mode or not ops.is_synthetic:
        raise HTTPException(404, "Resource not found.")
    record = db.get(DiningTable, body.table_id)
    if record is None or record.location_id != location_id:
        raise HTTPException(404, "Resource not found.")
    return execute_action(db, body.table_id, body, demo=True)


def event_batch(token: str, location_id: UUID, position: int):
    """Each invocation owns a short checked transaction; none survives a yield/wait."""
    with contextmanager(get_db)() as db:
        identity = resolve_identity(db, token, touch=False)
        _, _, ops = operation_scope(db, identity, location_id)
        if position > ops.revision:
            raise HTTPException(409, "Reload the dashboard.")
        # Both kinds share the location counter; one ordered query avoids cursor gaps.
        events = db.execute(text('''
            SELECT revision,data FROM (
                SELECT e.revision,to_jsonb(e) AS data FROM public.table_events e
                WHERE e.location_id=:loc AND e.revision>:position
                UNION ALL
                SELECT n.revision,jsonb_build_object('revision',n.revision,'event_type','edge.'||n.kind,
                    'device_id',n.device_id,'location_id',n.location_id) AS data
                FROM public.location_notifications n WHERE n.location_id=:loc AND n.revision>:position
            ) ordered_events ORDER BY revision LIMIT 100
            '''), {'loc': location_id, 'position': position}).mappings().all()
        return [row['data'] if row['data']['event_type'].startswith('edge.') else
                s.EventOut.model_validate(row['data']).model_dump(mode='json') for row in events]


def stream_frames(token: str, location_id: UUID, position: int, user_id: UUID,
                  lease: StreamLease | None = None):
    try:
        while True:
            try:
                events = event_batch(token, location_id, position)
            except HTTPException as error:
                name = "session_expired" if error.status_code == 401 else "access_lost"
                yield f"event: {name}\ndata: {{}}\n\n"
                return
            except SQLAlchemyError:
                yield "event: unavailable\ndata: {}\n\n"
                return
            for event in events:
                position = event["revision"]
                yield (f"id: {cursor(location_id, position)}\nevent: change\n"
                       f"data: {json.dumps(event, separators=(',', ':'))}\n\n")
            yield ("event: heartbeat\ndata: " + json.dumps({
                "server_time": datetime.now(UTC).isoformat(), "cursor": cursor(location_id, position)
            }) + "\n\n")
            time.sleep(HEARTBEAT_SECONDS)
    finally:
        if lease is not None:
            lease.close()


@router.get("/locations/{location_id}/stream", response_class=StreamingResponse)
def stream(location_id: UUID, identity: Auth, db: Db,
           last_event_id: Annotated[str | None, Header(max_length=80)] = None,
           after: str | None = Query(None, max_length=80)):
    _, _, ops = operation_scope(db, identity, location_id)
    position = parse_cursor(last_event_id or after, location_id, ops.revision)
    lease = StreamLease(identity.id)
    return StreamingResponse(
        stream_frames(identity.session_token, location_id, position, identity.id, lease),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        background=BackgroundTask(lease.close),
    )
