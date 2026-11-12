"""Opt-in, human-reviewed observation workflow. No arbitrary state-setting API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from restaurant_api import workflow_models as m
from restaurant_api.evidence_protocol import Evidence, EvidenceRules
from restaurant_api.routes import Auth, Write
from restaurant_api.security import CONFIGURATORS, Db, location_access
from restaurant_api.settings import get_settings

router = APIRouter(prefix="/v1", tags=["reviewed workflow"])
OPERATORS = CONFIGURATORS | {"staff"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, from_attributes=True)


class PolicyChange(Strict):
    mode: Literal["OFF", "ASSISTED_REVIEW"]
    expected_revision: int = Field(strict=True, ge=0)
    request_key: UUID
    bindings: list[UUID] = Field(max_length=64)
    rules: EvidenceRules = Field(default_factory=EvidenceRules)


class PolicyOut(Strict):
    mode: Literal["OFF", "ASSISTED_REVIEW"]
    revision: int
    enabled_since: datetime | None = None
    rules: EvidenceRules
    rules_sha256: str | None = None
    bindings: list[UUID]


class Decision(Strict):
    action: Literal["confirm", "dismiss"]
    expected_revision: int = Field(strict=True, ge=0)
    expected_suggestion_revision: int = Field(strict=True, ge=1)
    request_key: UUID
    confirmed: bool = Field(default=False, strict=True)
    reason: Literal[
        "", "staff_crossing", "wrong_table", "guests_still_present", "insufficient_view", "other"
    ] = ""


class WorkflowAction(Strict):
    action: Literal["ready", "correct_departure", "correct_arrival", "reconcile_source"]
    expected_revision: int = Field(strict=True, ge=0)
    request_key: UUID
    confirmed: bool = Field(strict=True)
    reason: Literal[
        "",
        "staff_crossing",
        "wrong_table",
        "guests_still_present",
        "insufficient_view",
        "other",
        "source_restarted",
    ] = ""
    session_id: UUID | None = None


class ActionResult(Strict):
    table_id: UUID
    event_id: UUID
    revision: int
    state: str
    cursor: str
    action: str


class PolicyResult(Strict):
    location_id: UUID
    revision: int
    mode: Literal["OFF", "ASSISTED_REVIEW"]


class SuggestionOut(Strict):
    id: UUID
    table_id: UUID
    session_id: UUID | None
    action: Literal["ARRIVAL", "DEPARTURE"]
    status: str
    revision: int
    table_revision: int
    policy_revision: int
    created_at: datetime
    expires_at: datetime
    observed_at: datetime
    actionable: bool
    evidence: Evidence


class TableContext(Strict):
    table_id: UUID
    table_revision: int
    controlled: bool
    verified_ready: bool
    ready_eligible: bool
    session_id: UUID | None
    attempt_id: UUID | None
    pending_since: datetime | None
    evidence_at: datetime | None
    evidence_kind: str | None
    evidence_live: bool
    needs_source_review: bool


class WorkflowView(Strict):
    mode: Literal["OFF", "ASSISTED_REVIEW"]
    policy_revision: int
    server_time: datetime
    cursor: str
    tables: list[TableContext]
    suggestions: list[SuggestionOut]
    tables_truncated: bool
    suggestions_truncated: bool


def call(db, function, **values):
    try:
        return db.scalar(
            text(f"SELECT security.{function}({','.join(':' + k for k in values)})"), values
        )
    except DBAPIError as error:
        status = {"P0403": 403, "P0404": 404, "P0409": 409, "P0422": 422}.get(
            getattr(error.orig, "sqlstate", "")
        )
        if status:
            messages = {
                403: "This role or location cannot perform this workflow action.",
                404: "Resource not found.",
                409: "The table, suggestion or evidence changed. Refresh and check the table.",
                422: "Invalid workflow fields.",
            }
            raise HTTPException(status, messages[status]) from None
        raise


@router.get("/locations/{location_id}/workflow-policy", response_model=PolicyOut)
def policy(location_id: UUID, identity: Auth, db: Db):
    location_access(db, identity, location_id, CONFIGURATORS)
    row = db.get(m.WorkflowPolicy, location_id)
    if row is None:
        return PolicyOut(mode="OFF", revision=0, rules=EvidenceRules(), bindings=[])
    return PolicyOut.model_validate({k: getattr(row, k) for k in PolicyOut.model_fields})


@router.put("/locations/{location_id}/workflow-policy", response_model=PolicyResult)
def change_policy(location_id: UUID, body: PolicyChange, identity: Write, db: Db):
    location_access(db, identity, location_id, CONFIGURATORS)
    return call(
        db,
        "workflow_policy_set",
        loc_=location_id,
        value_=body.model_dump_json(),
        demo_=get_settings().demo_mode,
    )


SUGGESTION_SELECT = """
    SELECT s.id,s.table_id,s.session_id,s.action,s.status,s.revision,s.table_revision,s.policy_revision,
        s.created_at,s.expires_at,e.observed_at,e.summary AS evidence,
        (s.status='PENDING' AND s.expires_at>clock_timestamp() AND security.workflow_live(s.latest_receipt_id)) AS actionable
    FROM public.workflow_suggestions s JOIN public.workflow_evidence e ON e.receipt_id=s.latest_receipt_id
"""


@router.get("/locations/{location_id}/workflow-suggestions", response_model=list[SuggestionOut])
def suggestions(
    location_id: UUID,
    identity: Auth,
    db: Db,
    limit: int = Query(50, ge=1, le=100),
    after: UUID | None = None,
    status: Literal["PENDING", "ACCEPTED", "DISMISSED", "SUPERSEDED"] = "PENDING",
):
    location_access(db, identity, location_id, OPERATORS)
    return (
        db.execute(
            text(
                SUGGESTION_SELECT
                + " WHERE s.location_id=:loc AND s.status=:status AND (CAST(:after AS uuid) IS NULL OR s.id>CAST(:after AS uuid)) ORDER BY s.id LIMIT :limit"
            ),
            {"loc": location_id, "status": status, "after": after, "limit": limit},
        )
        .mappings()
        .all()
    )


@router.get("/locations/{location_id}/workflow", response_model=WorkflowView)
def workflow_view(location_id: UUID, identity: Auth, db: Db):
    location_access(db, identity, location_id, OPERATORS)
    # A single statement snapshots table context, suggestions and their shared cursor.
    result = (
        db.execute(
            text(
                """
        SELECT o.revision,coalesce(p.mode,'OFF') AS mode,coalesce(p.revision,0) AS policy_revision,
        statement_timestamp() AS server_time,
        (SELECT count(*)>500 FROM public.dining_tables WHERE location_id=:loc) AS tables_truncated,
        (SELECT count(*)>100 FROM public.workflow_suggestions WHERE location_id=:loc AND status='PENDING') AS suggestions_truncated,
        coalesce((SELECT jsonb_agg(to_jsonb(q)) FROM (
          SELECT t.id AS table_id,t.operational_revision AS table_revision,t.occupancy_session_id AS session_id,
            coalesce((coalesce(p.bindings,'[]'::jsonb) ? b.id::text OR ws.id IS NOT NULL),false) AS controlled,
            coalesce(t.current_state='AVAILABLE' AND e.kind='VACANT' AND security.workflow_live(e.receipt_id),false) AS verified_ready,
            coalesce(t.current_state IN ('UNKNOWN','CLEANING') AND e.kind='VACANT' AND security.workflow_live(e.receipt_id),false) AS ready_eligible,
            coalesce(ws.status='OPEN' AND (ws.source_generation<>e.source_generation OR ws.binding_id<>e.binding_id),false) AS needs_source_review,
            a.id AS attempt_id,a.pending_since,e.observed_at AS evidence_at,e.kind AS evidence_kind,
            coalesce(security.workflow_live(e.receipt_id),false) AS evidence_live
          FROM public.dining_tables t
          LEFT JOIN public.workflow_sessions ws ON ws.id=t.occupancy_session_id
          LEFT JOIN LATERAL(SELECT id FROM public.edge_bindings WHERE table_id=t.id AND enabled LIMIT 1) b ON true
          LEFT JOIN LATERAL(SELECT x.* FROM public.workflow_evidence x JOIN public.edge_receipts r ON r.event_id=x.receipt_id
            WHERE x.table_id=t.id ORDER BY x.observed_at DESC,r.sequence DESC LIMIT 1) e ON true
          LEFT JOIN LATERAL(SELECT x.* FROM public.workflow_task_attempts x JOIN public.staff_tasks st ON st.id=x.task_id
            WHERE st.table_id=t.id AND x.status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS') ORDER BY x.number DESC LIMIT 1) a ON true
          WHERE t.location_id=:loc ORDER BY t.id LIMIT 500) q),'[]'::jsonb) AS tables,
        coalesce((SELECT jsonb_agg(to_jsonb(q)) FROM ("""
                + SUGGESTION_SELECT
                + """
          WHERE s.location_id=:loc AND s.status='PENDING' ORDER BY s.created_at,s.id LIMIT 100) q),'[]'::jsonb) AS suggestions
        FROM public.location_operations o LEFT JOIN public.workflow_policies p ON p.location_id=o.location_id WHERE o.location_id=:loc
    """
            ),
            {"loc": location_id},
        )
        .mappings()
        .one()
    )
    return WorkflowView(
        mode=result["mode"],
        policy_revision=result["policy_revision"],
        server_time=result["server_time"],
        cursor=f"{location_id}:{result['revision']}",
        tables=result["tables"],
        suggestions=result["suggestions"],
        tables_truncated=result["tables_truncated"],
        suggestions_truncated=result["suggestions_truncated"],
    )


@router.post(
    "/locations/{location_id}/workflow-suggestions/{suggestion_id}/decisions",
    response_model=ActionResult,
)
def decide(location_id: UUID, suggestion_id: UUID, body: Decision, identity: Write, db: Db):
    location_access(db, identity, location_id, OPERATORS)
    row = db.get(m.WorkflowSuggestion, suggestion_id)
    if row is None or row.location_id != location_id:
        raise HTTPException(404, "Resource not found.")
    return call(
        db,
        "workflow_decide",
        table_=row.table_id,
        suggestion_=suggestion_id,
        value_=body.model_dump_json(),
    )


@router.post("/tables/{table_id}/workflow-actions", response_model=ActionResult)
def workflow_action(table_id: UUID, body: WorkflowAction, identity: Write, db: Db):
    from restaurant_api.models import DiningTable

    row = db.get(DiningTable, table_id)
    if row is None:
        raise HTTPException(404, "Resource not found.")
    location_access(db, identity, row.location_id, OPERATORS)
    if body.action.startswith("correct_") or body.action == "reconcile_source":
        location_access(db, identity, row.location_id, CONFIGURATORS)
    return call(
        db, "workflow_decide", table_=table_id, suggestion_=None, value_=body.model_dump_json()
    )
