"""Signed fabricated evidence tests operational safeguards, not person recognition."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from restaurant_api.database import set_identity
from restaurant_api.evidence_protocol import EvidenceRules, rules_digest
from restaurant_api.workflow import event_batch

from .test_edge_transport import configure, observation, send
from .test_edge_transport import edge as edge_fixture
from .test_edge_transport import edge_tenants as edge_tenants_fixture

edge = edge_fixture
edge_tenants = edge_tenants_fixture


def revision(e):
    with e.suite.admin.connect() as db:
        return db.scalar(
            text("SELECT operational_revision FROM dining_tables WHERE id=:id"), {"id": e.table}
        )


def view(e, who="a_staff"):
    response = e.clients[who].request("GET", f"/v1/locations/{e.loc}/workflow")
    assert response.status_code == 200, response.text
    return response.json()


def enable(e):
    configure(e)
    e.episode = uuid4()
    e.generation = uuid4()
    e.sequence = 0
    response = e.clients["a_owner"].request(
        "PUT",
        f"/v1/locations/{e.loc}/workflow-policy",
        json={
            "mode": "ASSISTED_REVIEW",
            "expected_revision": 0,
            "request_key": str(uuid4()),
            "bindings": [e.binding["id"]],
            "rules": {},
        },
    )
    assert response.status_code == 200, response.text
    e.workflow_revision = response.json()["revision"]
    policy = e.clients["a_owner"].request("GET", f"/v1/locations/{e.loc}/workflow-policy").json()
    assert policy["rules_sha256"] == rules_digest(EvidenceRules().model_dump())
    return e


def evidence(e, kind="POSITIVE", *, snapshot=False, **changes):
    e.sequence += 1
    raw = observation(e, e.sequence).model_dump(mode="json")
    raw.update(
        version=2,
        state="OCCUPIED" if kind == "POSITIVE" else "RESET_PENDING",
        reason="STABLE_PERSON" if kind == "POSITIVE" else "STABLE_VACANCY",
        occupancy_session_id=str(e.episode),
        source_generation=str(e.generation),
        manual_revision=revision(e),
        evidence_type="snapshot" if snapshot else "transition",
        workflow_revision=e.workflow_revision,
        rules_sha256=rules_digest({}),
        evidence={
            "kind": kind,
            "quality": "HIGH",
            "detector_score": 0.8 if kind == "POSITIVE" else None,
            "association_score": 0.95 if kind == "POSITIVE" else None,
            "sample_count": 55,
            "window_seconds": 27,
            "covered_seconds": 27,
            "max_gap_seconds": 0.5,
            "frame_age_seconds": 0.4,
            "visibility_reviewed": True,
        },
    )
    raw.update(changes)
    return raw


def post(e, raw):
    response = send(e, "/v1/edge/events", {"events": [raw]})
    assert response.status_code == 200, response.text
    return response.json()


def decision(e, suggestion=None, action="confirm", who="a_staff", **extra):
    suggestion = suggestion or view(e)["suggestions"][0]
    body = {
        "action": action,
        "expected_revision": revision(e),
        "expected_suggestion_revision": suggestion["revision"],
        "request_key": str(uuid4()),
        "confirmed": True,
    }
    body.update(extra)
    return e.clients[who].request(
        "POST",
        f"/v1/locations/{e.loc}/workflow-suggestions/{suggestion['id']}/decisions",
        json=body,
    )


def action(e, operation, who="a_staff", **extra):
    body = {
        "action": operation,
        "expected_revision": revision(e),
        "request_key": str(uuid4()),
        "confirmed": True,
    }
    body.update(extra)
    return e.clients[who].request("POST", f"/v1/tables/{e.table}/workflow-actions", json=body)


def task_action(e, operation, **extra):
    body = {
        "action": operation,
        "expected_revision": revision(e),
        "request_key": str(uuid4()),
    } | extra
    return e.clients["a_staff"].request("POST", f"/v1/tables/{e.table}/actions", json=body)


def arrive_depart(e):
    post(e, evidence(e))
    assert decision(e).status_code == 200
    post(e, evidence(e, "VACANT"))
    assert decision(e).status_code == 200


def test_phase7_default_off_and_old_v1_shadow_only(edge):
    configure(edge)
    assert view(edge)["mode"] == "OFF"
    assert view(edge)["suggestions"] == []
    post(edge, observation(edge).model_dump(mode="json"))
    assert view(edge)["suggestions"] == []
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM staff_tasks WHERE table_id=:id"), {"id": edge.table}
            )
            == 0
        )


def test_full_review_task_clean_ready_audit_and_sse(edge):
    enable(edge)
    initial = revision(edge)
    post(edge, evidence(edge))
    assert revision(edge) == initial
    assert decision(edge, confirmed=False).status_code == 409
    assert decision(edge).json()["state"] == "OCCUPIED"
    post(edge, evidence(edge, "VACANT"))
    assert decision(edge).json()["state"] == "RESET_PENDING"
    task = edge.clients["a_staff"].request("GET", f"/v1/locations/{edge.loc}/tasks").json()[0]
    assert task_action(edge, "acknowledge", task_id=task["id"]).json()["state"] == "RESET_PENDING"
    assert task_action(edge, "start_cleaning", task_id=task["id"]).json()["state"] == "CLEANING"
    assert task_action(edge, "mark_ready", confirmed=True).status_code == 409
    assert action(edge, "ready").status_code == 409  # No stale pre-cleaning evidence.
    post(
        edge,
        evidence(edge, "VACANT", snapshot=True, state="CLEANING", reason="CURRENT_HUMAN_STATE"),
    )
    assert view(edge)["tables"][0]["ready_eligible"] is True
    assert action(edge, "ready").json()["state"] == "AVAILABLE"
    with edge.suite.admin.connect() as db:
        attempts = db.execute(
            text(
                "SELECT status,acknowledged_at,started_at,completed_at FROM workflow_task_attempts WHERE task_id=:id"
            ),
            {"id": task["id"]},
        ).one()
        assert attempts.status == "COMPLETED" and all(attempts[1:])
        assert (
            db.scalar(
                text("SELECT count(*) FROM workflow_decisions WHERE table_id=:id"),
                {"id": edge.table},
            )
            == 3
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_logs WHERE location_id=:id AND action LIKE :prefix"
                ),
                {"id": edge.loc, "prefix": "workflow.%"},
            )
            == 4
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM workflow_journal WHERE table_id=:id AND session_id IS NOT NULL"
                ),
                {"id": edge.table},
            )
            >= 5
        )
    token = edge.clients["a_staff"].client.cookies.get("restaurant_session")
    from restaurant_api.settings import get_settings

    token = edge.clients["a_staff"].client.cookies.get(get_settings().cookie_name)
    events = event_batch(token, edge.loc, 0)
    assert any(row["event_type"] == "workflow.confirm" for row in events)


def test_dismissal_is_sticky_without_a_task(edge):
    enable(edge)
    raw = evidence(edge)
    post(edge, raw)
    assert decision(edge, action="dismiss", reason="staff_crossing").status_code == 200
    post(edge, evidence(edge))
    assert view(edge)["suggestions"] == []
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM staff_tasks WHERE table_id=:id"), {"id": edge.table}
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT current_state FROM dining_tables WHERE id=:id"), {"id": edge.table}
            )
            == "UNKNOWN"
        )


@pytest.mark.parametrize(
    "problem",
    [
        "stale",
        "future",
        "weak_score",
        "unknown",
        "visibility",
        "gap",
        "coverage",
        "wrong_policy",
        "wrong_manual",
    ],
)
def test_unsafe_observations_cannot_suggest_or_mutate(edge, problem):
    enable(edge)
    raw = evidence(edge)
    if problem == "stale":
        raw["occurred_at"] = (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
    elif problem == "future":
        raw["occurred_at"] = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
    elif problem == "weak_score":
        raw["evidence"]["detector_score"] = 0.1
    elif problem == "unknown":
        raw["evidence"]["kind"] = "UNCERTAIN"
    elif problem == "visibility":
        raw["evidence"]["visibility_reviewed"] = False
    elif problem == "gap":
        raw["evidence"]["max_gap_seconds"] = 3
    elif problem == "coverage":
        raw["evidence"]["covered_seconds"] = 5
    elif problem == "wrong_policy":
        raw["workflow_revision"] += 1
    else:
        raw["manual_revision"] += 1
    before = revision(edge)
    post(edge, raw)
    assert view(edge)["suggestions"] == []
    assert revision(edge) == before


def test_snapshot_never_creates_arrival_and_manual_echo_never_ready(edge):
    enable(edge)
    post(edge, evidence(edge, snapshot=True))
    post(edge, evidence(edge, reason="CURRENT_HUMAN_STATE"))
    assert view(edge)["suggestions"] == []
    assert action(edge, "ready").status_code == 409


def test_medium_vacancy_keeps_human_gate_and_low_quality_is_refused(edge):
    enable(edge)
    post(edge, evidence(edge))
    assert decision(edge).status_code == 200
    raw = evidence(edge, "VACANT")
    raw["evidence"]["quality"] = "MEDIUM"
    post(edge, raw)
    assert len(view(edge)["suggestions"]) == 1
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT current_state FROM dining_tables WHERE id=:id"), {"id": edge.table}
            )
            == "OCCUPIED"
        )
    raw = evidence(edge, "VACANT")
    raw["evidence"]["quality"] = "LOW"
    post(edge, raw)
    assert view(edge)["suggestions"] == []


@pytest.mark.parametrize("boundary", ["receipt_derivation", "human_decision"])
def test_transaction_failure_cannot_ack_or_leave_partial_workflow(edge, boundary):
    enable(edge)
    raw = evidence(edge)
    if boundary == "human_decision":
        post(edge, raw)
    table = "workflow_suggestions" if boundary == "receipt_derivation" else "workflow_decisions"
    marker = "phase7_fault_" + uuid4().hex
    before = revision(edge)
    with edge.suite.admin.begin() as db:
        assert db.scalar(text("SELECT current_database()")).startswith("phase2_security_test")
        # Only this newly created isolated synthetic table can hit the fault.
        db.exec_driver_sql(
            f"CREATE FUNCTION security.{marker}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.table_id='{edge.table}'::uuid THEN RAISE EXCEPTION 'Synthetic transaction fault' USING ERRCODE='P0409'; END IF; RETURN NEW; END $$"
        )
        db.exec_driver_sql(
            f"CREATE TRIGGER {marker} AFTER INSERT ON public.{table} FOR EACH ROW EXECUTE FUNCTION security.{marker}()"
        )
    try:
        if boundary == "receipt_derivation":
            response = send(edge, "/v1/edge/events", {"events": [raw]})
            assert response.status_code >= 400
            with edge.suite.admin.connect() as db:
                assert (
                    db.scalar(
                        text("SELECT count(*) FROM edge_receipts WHERE event_id=:id"),
                        {"id": raw["event_id"]},
                    )
                    == 0
                )
        else:
            assert decision(edge).status_code == 409
            assert view(edge)["suggestions"][0]["status"] == "PENDING"
        assert revision(edge) == before
        with edge.suite.admin.connect() as db:
            assert (
                db.scalar(
                    text("SELECT count(*) FROM workflow_sessions WHERE table_id=:id"),
                    {"id": edge.table},
                )
                == 0
            )
            assert (
                db.scalar(
                    text("SELECT count(*) FROM staff_tasks WHERE table_id=:id"), {"id": edge.table}
                )
                == 0
            )
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM audit_logs WHERE location_id=:id AND action=:action"
                    ),
                    {"id": edge.loc, "action": "workflow.confirm"},
                )
                == 0
            )
    finally:
        with edge.suite.admin.begin() as db:
            # Remove only fault-injection objects created by this test, never data.
            db.exec_driver_sql(f"DROP TRIGGER {marker} ON public.{table}")
            db.exec_driver_sql(f"DROP FUNCTION security.{marker}()")
    if boundary == "receipt_derivation":
        post(edge, raw)
    assert decision(edge).status_code == 200


def test_manager_correction_reuses_task_and_preserves_cancelled_attempt(edge):
    enable(edge)
    arrive_depart(edge)
    context = view(edge)["tables"][0]
    session = context["session_id"]
    assert (
        action(
            edge, "correct_departure", session_id=session, reason="guests_still_present"
        ).status_code
        == 403
    )
    assert (
        action(
            edge,
            "correct_departure",
            who="a_manager",
            session_id=session,
            reason="guests_still_present",
        ).json()["state"]
        == "OCCUPIED"
    )
    post(edge, evidence(edge, "VACANT"))
    assert decision(edge).json()["state"] == "RESET_PENDING"
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM staff_tasks WHERE table_id=:id"), {"id": edge.table}
            )
            == 1
        )
        attempts = db.execute(
            text(
                "SELECT a.status,a.cancelled_at FROM workflow_task_attempts a JOIN staff_tasks t ON t.id=a.task_id WHERE t.table_id=:id ORDER BY number"
            ),
            {"id": edge.table},
        ).all()
        assert [a.status for a in attempts] == ["CANCELLED", "OPEN"]
        assert attempts[0].cancelled_at is not None


def test_stale_suggestion_and_identical_request_retry(edge):
    enable(edge)
    post(edge, evidence(edge))
    old = view(edge)["suggestions"][0]
    post(edge, evidence(edge, snapshot=True))
    assert decision(edge, old).status_code == 409
    current = view(edge)["suggestions"][0]
    key = str(uuid4())
    first = decision(edge, current, request_key=key)
    assert first.status_code == 200
    second = decision(
        edge, current, request_key=key, expected_revision=first.json()["revision"] - 1
    )
    assert second.status_code == 200 and second.json() == first.json()
    assert decision(edge, current, request_key=key, reason="other").status_code == 409


def test_concurrent_accepts_and_repeated_delivery_have_one_effect(edge):
    enable(edge)
    raw = evidence(edge)
    post(edge, raw)
    post(edge, raw)
    current = view(edge)["suggestions"][0]
    body = {
        "action": "confirm",
        "expected_revision": revision(edge),
        "expected_suggestion_revision": current["revision"],
        "request_key": str(uuid4()),
        "confirmed": True,
    }
    client = edge.clients["a_staff"]

    def submit(_):
        return client.request(
            "POST",
            f"/v1/locations/{edge.loc}/workflow-suggestions/{current['id']}/decisions",
            json=body,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(submit, range(2)))
    assert all(r.status_code == 200 for r in replies)
    assert replies[0].json() == replies[1].json()
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM workflow_sessions WHERE table_id=:id"),
                {"id": edge.table},
            )
            == 1
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM workflow_decisions WHERE table_id=:id"),
                {"id": edge.table},
            )
            == 1
        )


def test_manager_blocks_and_cleaning_win_over_ai(edge):
    enable(edge)
    arrive_depart(edge)
    assert task_action(edge, "start_cleaning").status_code == 200
    before = revision(edge)
    post(edge, evidence(edge))
    assert revision(edge) == before and view(edge)["suggestions"] == []
    response = edge.clients["a_manager"].request(
        "POST",
        f"/v1/tables/{edge.table}/actions",
        json={
            "action": "out_of_service",
            "expected_revision": before,
            "request_key": str(uuid4()),
            "reason": "maintenance",
        },
    )
    assert response.json()["state"] == "OUT_OF_SERVICE"
    post(edge, evidence(edge, "VACANT", snapshot=True))
    assert action(edge, "ready").status_code == 409


def test_restaurant_location_anonymous_and_installer_boundaries(edge):
    enable(edge)
    post(edge, evidence(edge))
    suggestion = view(edge)["suggestions"][0]
    paths = [
        ("GET", f"/v1/locations/{edge.loc}/workflow", None),
        ("GET", f"/v1/locations/{edge.loc}/workflow-suggestions", None),
        ("GET", f"/v1/locations/{edge.loc}/workflow-policy", None),
        (
            "PUT",
            f"/v1/locations/{edge.loc}/workflow-policy",
            {
                "mode": "OFF",
                "expected_revision": 1,
                "request_key": str(uuid4()),
                "bindings": [],
                "rules": {},
            },
        ),
        (
            "POST",
            f"/v1/locations/{edge.loc}/workflow-suggestions/{suggestion['id']}/decisions",
            {
                "action": "confirm",
                "expected_revision": revision(edge),
                "expected_suggestion_revision": suggestion["revision"],
                "request_key": str(uuid4()),
                "confirmed": True,
            },
        ),
        (
            "POST",
            f"/v1/tables/{edge.table}/workflow-actions",
            {
                "action": "ready",
                "expected_revision": revision(edge),
                "request_key": str(uuid4()),
                "confirmed": True,
            },
        ),
    ]
    anonymous = TestClient(edge.suite.app)
    for method, path, body in paths:
        assert anonymous.request(method, path, json=body).status_code == 401
        assert edge.clients["b_owner"].request(method, path, json=body).status_code == 404
        assert edge.clients["a_installer"].request(method, path, json=body).status_code == 403
    # A new location is not automatically granted even to the organization owner.
    other = uuid4()
    with edge.suite.admin.begin() as db:
        db.execute(
            text(
                "INSERT INTO locations(id,organization_id,name,time_zone) VALUES(:id,:org,:name,:tz)"
            ),
            {"id": other, "org": edge.org, "name": "Ungrantable synthetic test", "tz": "UTC"},
        )
    assert (
        edge.clients["a_owner"].request("GET", f"/v1/locations/{other}/workflow").status_code == 404
    )
    foreign = edge.suite.seed["organizations"]["b"]["locations"][0]
    assert (
        edge.clients["a_owner"].request("GET", f"/v1/locations/{foreign}/workflow").status_code
        == 404
    )
    anonymous.close()


def test_direct_database_runtime_has_read_scope_and_no_mutation_or_legacy_bypass(edge):
    enable(edge)
    with edge.suite.runtime.connect() as db:
        set_identity(db, edge.suite.seed["accounts"]["b_owner"]["user_id"])
        assert (
            db.scalar(
                text("SELECT count(*) FROM workflow_policies WHERE location_id=:id"),
                {"id": edge.loc},
            )
            == 0
        )
    for sql in [
        "UPDATE workflow_policies SET mode='OFF'",
        "DELETE FROM workflow_decisions",
        "SELECT security.workflow_legacy_action(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)",
    ]:
        with edge.suite.runtime.connect() as db:
            set_identity(db, edge.suite.seed["accounts"]["a_owner"]["user_id"])
            with pytest.raises(DBAPIError):
                db.execute(text(sql))


def test_manager_reconciles_restarted_source_without_inventing_a_visit(edge):
    enable(edge)
    post(edge, evidence(edge))
    assert decision(edge).status_code == 200
    original = view(edge)["tables"][0]["session_id"]
    with edge.suite.admin.connect() as db:
        before = db.execute(
            text("SELECT arrived_at FROM workflow_sessions WHERE id=:id"), {"id": original}
        ).one()
        timer = db.scalar(
            text("SELECT state_since FROM dining_tables WHERE id=:id"), {"id": edge.table}
        )
    edge.generation = uuid4()
    edge.episode = uuid4()
    post(edge, evidence(edge, "VACANT", snapshot=True))
    assert view(edge)["tables"][0]["needs_source_review"] is True
    assert (
        action(edge, "reconcile_source", session_id=original, reason="source_restarted").status_code
        == 403
    )
    accepted = action(
        edge, "reconcile_source", who="a_manager", session_id=original, reason="source_restarted"
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "OCCUPIED"
    with edge.suite.admin.connect() as db:
        session = db.execute(
            text("SELECT id,arrived_at,source_episode FROM workflow_sessions WHERE table_id=:id"),
            {"id": edge.table},
        ).one()
        assert str(session.id) == original and session.arrived_at == before.arrived_at
        assert (
            db.scalar(
                text("SELECT state_since FROM dining_tables WHERE id=:id"), {"id": edge.table}
            )
            == timer
        )
        edge.episode = session.source_episode
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM table_events WHERE table_id=:id AND event_type='workflow.reconcile_source'"
                ),
                {"id": edge.table},
            )
            == 1
        )
    post(edge, evidence(edge, "VACANT"))
    assert decision(edge).json()["state"] == "RESET_PENDING"
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM workflow_sessions WHERE table_id=:id"),
                {"id": edge.table},
            )
            == 1
        )


def test_revoked_device_and_changed_policy_invalidate_human_acceptance(edge):
    from .test_edge_transport import command

    enable(edge)
    post(edge, evidence(edge))
    pending = view(edge)["suggestions"][0]
    assert command(edge, action="revoke").status_code == 200
    assert decision(edge, pending).status_code == 409
    assert revision(edge) == pending["table_revision"]
    response = edge.clients["a_manager"].request(
        "PUT",
        f"/v1/locations/{edge.loc}/workflow-policy",
        json={
            "mode": "OFF",
            "expected_revision": 1,
            "request_key": str(uuid4()),
            "bindings": [],
            "rules": {},
        },
    )
    assert response.status_code == 200
    assert view(edge)["suggestions"] == []


@pytest.mark.parametrize(
    "state", ["UNKNOWN", "AVAILABLE", "OCCUPIED", "RESET_PENDING", "CLEANING", "OUT_OF_SERVICE"]
)
def test_no_device_state_can_independently_mark_ready(edge, state):
    enable(edge)
    before = revision(edge)
    post(edge, evidence(edge, "VACANT", snapshot=True, state=state))
    assert revision(edge) == before
    assert view(edge)["suggestions"] == []


def test_protected_cleaning_recovers_only_after_new_valid_source_context(edge):
    enable(edge)
    arrive_depart(edge)
    task = edge.clients["a_staff"].request("GET", f"/v1/locations/{edge.loc}/tasks").json()[0]
    assert task_action(edge, "start_cleaning", task_id=task["id"]).status_code == 200
    invalid = evidence(edge, "VACANT", state="UNSUPPORTED")
    assert post(edge, invalid)["receipts"][0]["disposition"] == "rejected"
    before = revision(edge)
    post(
        edge,
        evidence(edge, "VACANT", snapshot=True, state="CLEANING", reason="CURRENT_HUMAN_STATE"),
    )
    assert view(edge)["tables"][0]["ready_eligible"] is False
    edge.generation = uuid4()
    post(
        edge,
        evidence(edge, "VACANT", snapshot=True, state="CLEANING", reason="CURRENT_HUMAN_STATE"),
    )
    assert view(edge)["tables"][0]["ready_eligible"] is True
    assert revision(edge) == before
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT current_state FROM dining_tables WHERE id=:id"), {"id": edge.table}
            )
            == "CLEANING"
        )


def test_reordered_delayed_and_uncertain_receipts_do_not_rewind_workflow(edge):
    enable(edge)
    one = evidence(edge)
    two = evidence(edge, snapshot=True)
    post(edge, two)
    assert view(edge)["suggestions"] == []
    post(edge, one)
    pending = view(edge)["suggestions"][0]
    assert decision(edge, pending).status_code == 200
    before = revision(edge)
    raw = evidence(
        edge, "VACANT", occurred_at=(datetime.now(UTC) - timedelta(minutes=15)).isoformat()
    )
    post(edge, raw)
    post(edge, raw)
    assert revision(edge) == before and view(edge)["suggestions"] == []
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM staff_tasks WHERE table_id=:id"), {"id": edge.table}
            )
            == 0
        )


def test_new_routes_deny_reverse_tenant_direction_and_missing_csrf(edge):
    enable(edge)
    foreign = edge.suite.seed["organizations"]["b"]
    loc = foreign["locations"][0]
    table = foreign["resources_1"]["table_id"]
    proposal = uuid4()
    paths = [
        ("GET", f"/v1/locations/{loc}/workflow", None),
        ("GET", f"/v1/locations/{loc}/workflow-policy", None),
        ("GET", f"/v1/locations/{loc}/workflow-suggestions", None),
        (
            "PUT",
            f"/v1/locations/{loc}/workflow-policy",
            {
                "mode": "OFF",
                "expected_revision": 0,
                "request_key": str(uuid4()),
                "bindings": [],
                "rules": {},
            },
        ),
        (
            "POST",
            f"/v1/locations/{loc}/workflow-suggestions/{proposal}/decisions",
            {
                "action": "confirm",
                "expected_revision": 0,
                "expected_suggestion_revision": 1,
                "request_key": str(uuid4()),
                "confirmed": True,
            },
        ),
        (
            "POST",
            f"/v1/tables/{table}/workflow-actions",
            {
                "action": "ready",
                "expected_revision": 0,
                "request_key": str(uuid4()),
                "confirmed": True,
            },
        ),
    ]
    for method, path, body in paths:
        assert edge.clients["a_owner"].request(method, path, json=body).status_code == 404
    assert (
        edge.clients["a_owner"]
        .client.put(
            f"/v1/locations/{edge.loc}/workflow-policy",
            json={
                "mode": "OFF",
                "expected_revision": 1,
                "request_key": str(uuid4()),
                "bindings": [],
                "rules": {},
            },
            headers={"origin": "http://localhost:3000"},
        )
        .status_code
        == 403
    )


def test_suggestion_keyset_pagination_and_expiry_are_passive(edge):
    import hashlib

    from restaurant_api.settings import get_settings

    enable(edge)
    post(edge, evidence(edge))
    account = edge.suite.login(edge.suite.seed["accounts"]["a_staff"])
    digest = hashlib.sha256(
        account.client.cookies.get(get_settings().cookie_name).encode()
    ).hexdigest()
    path = f"/v1/locations/{edge.loc}/workflow-suggestions"
    with edge.suite.admin.connect() as db:
        before = db.scalar(
            text("SELECT last_seen_at FROM identity.sessions WHERE token_digest=:d"), {"d": digest}
        )
    response = account.request("GET", path + "?limit=1")
    assert response.status_code == 200 and len(response.json()) == 1
    assert account.request("GET", path + "?after=" + response.json()[0]["id"]).json() == []
    with edge.suite.admin.begin() as db:
        assert (
            db.scalar(
                text("SELECT last_seen_at FROM identity.sessions WHERE token_digest=:d"),
                {"d": digest},
            )
            == before
        )
        db.execute(
            text(
                "UPDATE identity.sessions SET expires_at=now()-interval '1 second' WHERE token_digest=:d"
            ),
            {"d": digest},
        )
    assert account.request("GET", path).status_code == 401
    account.client.close()
