"""Real PostgreSQL workflow/security/concurrency tests; all credentials generated at runtime."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from restaurant_api import workflow
from restaurant_api.dashboard_seed import seed_dashboard
from restaurant_api.database import set_identity
from restaurant_api.management import seed_demo
from restaurant_api.models import (
    ActionReceipt,
    AuthSession,
    LocationGrant,
    LocationOperations,
    Membership,
    StaffTask,
    TableEvent,
    User,
)
from restaurant_api.security import digest
from restaurant_api.settings import get_settings


def protected_routes(p3, letter):
    loc = p3.layout["locations"][letter]
    tid = loc["table_ids"][0]
    return [
        ("GET", f"/v1/locations/{loc['id']}/dashboard", None),
        ("GET", f"/v1/locations/{loc['id']}/tasks", None),
        ("GET", f"/v1/locations/{loc['id']}/activity", None),
        ("GET", f"/v1/locations/{loc['id']}/stream", None),
        ("POST", f"/v1/locations/{loc['id']}/demo/events",
         {"table_id": tid, "action": "vacant", "expected_revision": 0, "request_key": str(uuid4())}),
        ("POST", f"/v1/tables/{tid}/actions",
         {"action": "mark_ready", "expected_revision": 0, "request_key": str(uuid4()), "confirmed": True}),
    ]


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("variant", ["anonymous", "a_to_b", "b_to_a"])
def test_dashboard_routes_reject_foreign_and_anonymous_access(p3, index, variant):
    target = "b" if variant == "a_to_b" else "a"
    method, path, body = protected_routes(p3, target)[index]
    if variant == "anonymous":
        with TestClient(p3.suite.app) as client:
            assert client.request(method, path, json=body).status_code == 401
    else:
        actor = "a" if variant == "a_to_b" else "b"
        assert p3.clients[actor + "_owner"].request(method, path, json=body).status_code == 404


@pytest.mark.parametrize("index", range(6))
def test_same_restaurant_location_grant_is_required(p3, index):
    account = p3.suite.account(member=False)
    with Session(p3.suite.admin) as db, db.begin():
        member = uuid4()
        org = UUID(p3.seed["organizations"]["a"]["id"])
        db.add(Membership(id=member, user_id=UUID(str(account["user_id"])), organization_id=org, role="staff"))
        db.flush()
        db.add(LocationGrant(membership_id=member, organization_id=org,
                             location_id=UUID(p3.seed["organizations"]["a"]["locations"][0])))
    client = p3.suite.login(account)  # Same restaurant, but only a different location is granted.
    method, path, body = protected_routes(p3, "a")[index]
    assert client.request(method, path, json=body).status_code == 404
    client.client.close()


@pytest.mark.parametrize("role", ["owner", "org_admin", "manager", "staff", "installer"])
@pytest.mark.parametrize("action", ["acknowledge", "start_cleaning", "mark_ready", "out_of_service", "reopen"])
def test_operational_role_matrix(p3, table_id, role, action):
    if action in {"acknowledge", "start_cleaning"}:
        p3.prepare(table_id, "RESET_PENDING")
    elif action == "mark_ready":
        p3.prepare(table_id, "CLEANING")
    elif action == "reopen":
        p3.prepare(table_id, "OUT_OF_SERVICE")
    allowed = role != "installer" and (action not in {"out_of_service", "reopen"} or role != "staff")
    response = p3.perform(table_id, action, actor="a_" + role, confirmed=True, reason="maintenance")
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize("role", ["owner", "org_admin", "manager", "staff", "installer"])
@pytest.mark.parametrize("synthetic", [True, False])
def test_demo_requires_synthetic_location_and_manager_role(p3, table_id, role, synthetic):
    if not synthetic:
        table_id = UUID(p3.seed["organizations"]["a"]["resources_1"]["table_id"])
    response = p3.perform(table_id, "vacant", demo=True, actor="a_" + role)
    expected = 404 if not synthetic else 200 if role in {"owner", "org_admin", "manager"} else 403
    assert response.status_code == expected


def test_disabled_demo_mode_rejects_scenario_without_changing_state(p3, table_id, monkeypatch):
    before = p3.table(table_id).operational_revision
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert p3.perform(table_id, "arrive", demo=True).status_code == 404
    assert p3.table(table_id).operational_revision == before
    loc = p3.layout["locations"]["a"]["id"]
    response = p3.clients["a_owner"].request("GET", f"/v1/locations/{loc}/dashboard")
    assert response.json()["demo"] is True and response.json()["simulation_controls"] is False


@pytest.mark.parametrize("state", ["AVAILABLE", "CLEANING", "OUT_OF_SERVICE"])
def test_source_failure_and_resume_preserve_manual_state_and_timer(p3, table_id, state):
    p3.prepare(table_id, state)
    before = p3.table(table_id)
    for action in ("source_offline", "source_resume"):
        assert p3.perform(table_id, action, demo=True).status_code == 200
        after = p3.table(table_id)
        assert after.current_state == state and after.state_since == before.state_since
        assert after.state_source == "manual"
    if state in {"CLEANING", "OUT_OF_SERVICE"}:
        assert p3.perform(table_id, "arrive", demo=True).status_code == 200
        assert p3.table(table_id).current_state == state


@pytest.mark.parametrize("state", ["OCCUPIED", "RESET_PENDING"])
def test_source_failure_makes_unconfirmed_observations_unknown(p3, table_id, state):
    p3.prepare(table_id, state)
    assert p3.perform(table_id, "source_offline", demo=True).status_code == 200
    assert p3.table(table_id).current_state == "UNKNOWN"


def test_full_workflow_duplicate_departure_and_task_completion(p3, table_id):
    p3.prepare(table_id, "RESET_PENDING")
    initial = p3.table(table_id).state_since
    assert p3.perform(table_id, "depart", demo=True).status_code == 200
    assert p3.table(table_id).state_since == initial
    with Session(p3.suite.admin) as db:
        task = db.scalar(select(StaffTask).where(StaffTask.table_id == table_id))
        assert task.status == "OPEN"
        task_id = task.id
    assert p3.perform(table_id, "acknowledge", actor="a_staff", task_id=str(task_id)).status_code == 200
    assert p3.table(table_id).current_state == "RESET_PENDING"
    assert p3.perform(table_id, "mark_ready", actor="a_staff", confirmed=True).status_code == 409
    assert p3.perform(table_id, "start_cleaning", actor="a_staff").status_code == 200
    assert p3.perform(table_id, "mark_ready", actor="a_staff", confirmed=False).status_code == 409
    assert p3.perform(table_id, "mark_ready", actor="a_staff", confirmed=True).status_code == 200
    assert p3.table(table_id).current_state == "AVAILABLE"
    with Session(p3.suite.admin) as db:
        tasks = db.scalars(select(StaffTask).where(StaffTask.table_id == table_id)).all()
        assert len(tasks) == 1 and tasks[0].status == "COMPLETED"
        assert tasks[0].acknowledged_at and tasks[0].started_at and tasks[0].completed_at


def test_occupancy_return_resolves_old_task_and_new_session_has_one_new_task(p3, table_id):
    p3.prepare(table_id, "RESET_PENDING")
    previous = p3.table(table_id).occupancy_session_id
    assert p3.perform(table_id, "arrive", demo=True).status_code == 200
    assert p3.table(table_id).occupancy_session_id != previous
    assert p3.perform(table_id, "depart", demo=True).status_code == 200
    with Session(p3.suite.admin) as db:
        statuses = db.scalars(select(StaffTask.status).where(StaffTask.table_id == table_id)).all()
        assert sorted(statuses) == ["CANCELLED", "OPEN"]


def test_retry_same_request_has_one_atomic_effect_and_changed_payload_conflicts(p3, table_id):
    revision = p3.table(table_id).operational_revision
    key = uuid4()
    first = p3.perform(table_id, "arrive", demo=True, expected=revision, key=key)
    second = p3.perform(table_id, "arrive", demo=True, expected=revision, key=key)
    assert first.status_code == second.status_code == 200 and first.json() == second.json()
    assert p3.perform(table_id, "vacant", demo=True, expected=revision, key=key).status_code == 409
    with Session(p3.suite.admin) as db:
        assert db.query(ActionReceipt).filter_by(table_id=table_id).count() == 1
        assert db.query(TableEvent).filter_by(table_id=table_id, event_type="table.arrive").count() == 1
        event_id = first.json()["event_id"]
        assert db.scalar(text("SELECT count(*) FROM audit_logs WHERE details->>'event_id'=:event"), {"event": event_id}) == 1


@pytest.mark.parametrize("same_request", [False, True])
def test_simultaneous_actions_have_one_effect_or_a_conflict(p3, table_id, same_request):
    revision = p3.table(table_id).operational_revision
    key = uuid4()
    # Each request owns a distinct TestClient and SQL transaction; no client object is shared.
    actors = [p3.suite.login(p3.seed["accounts"]["a_owner"]) for _ in range(2)]
    def write(index):
        return p3.perform(table_id, "arrive", demo=True, expected=revision,
                          key=key if same_request else uuid4(), client=actors[index])
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(write, range(2)))
    assert sorted(r.status_code for r in responses) == ([200, 200] if same_request else [200, 409])
    if same_request:
        assert responses[0].json() == responses[1].json()
    for actor in actors:
        actor.client.close()


@pytest.mark.parametrize("field,value", [("organization_id", str(uuid4())), ("location_id", str(uuid4())),
                                         ("current_state", "AVAILABLE"), ("confirmed", "yes")])
def test_action_body_cannot_change_ownership_state_or_confirmation_type(p3, table_id, field, value):
    assert p3.perform(table_id, "mark_ready", **{field: value}).status_code == 422


def test_forged_task_nested_table_and_unsafe_reason_are_rejected(p3, table_id):
    p3.prepare(table_id, "RESET_PENDING")
    assert p3.perform(table_id, "acknowledge", task_id=str(uuid4())).status_code == 404
    foreign = p3.layout["locations"]["b"]["table_ids"][0]
    loc = p3.layout["locations"]["a"]["id"]
    response = p3.clients["a_owner"].request("POST", f"/v1/locations/{loc}/demo/events", json={
        "table_id": foreign, "action": "arrive", "expected_revision": 0, "request_key": str(uuid4())})
    assert response.status_code == 404
    assert p3.perform(table_id, "out_of_service", reason="unreviewed private text").status_code == 422


@pytest.mark.parametrize("variant", ["csrf", "origin"])
def test_dashboard_mutations_require_csrf_and_origin(p3, table_id, variant):
    headers = {"x-csrf-token": "invalid"} if variant == "csrf" else {"origin": "https://foreign.invalid"}
    response = p3.clients["a_owner"].request("POST", f"/v1/tables/{table_id}/actions", headers=headers,
        json={"action": "out_of_service", "expected_revision": 0, "request_key": str(uuid4()), "reason": "maintenance"})
    assert response.status_code == 403


def test_snapshot_persists_timers_and_has_separate_synthetic_datasets(p3):
    snapshots = []
    for letter in ("a", "b"):
        loc = p3.layout["locations"][letter]["id"]
        path = f"/v1/locations/{loc}/dashboard"
        response = p3.clients[letter + "_staff"].request("GET", path)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        data = response.json()
        again = p3.clients[letter + "_staff"].request("GET", path).json()
        assert data["tables"] == again["tables"] and data["cursor"] == again["cursor"]
        assert data["demo"] and not data["simulation_controls"]
        assert all(row["state_since"].endswith(("Z", "+00:00")) for row in data["tables"])
        snapshots.append({row["id"] for row in data["tables"]})
    assert not snapshots[0].intersection(snapshots[1])


@pytest.mark.parametrize("path_suffix", ["dashboard", "tasks", "activity", "stream"])
def test_passive_http_and_stream_checks_do_not_refresh_idle_time(p3, path_suffix):
    actor = p3.suite.login(p3.seed["accounts"]["a_owner"])
    token = actor.client.cookies.get(get_settings().cookie_name)
    loc = UUID(p3.layout["locations"]["a"]["id"])
    with Session(p3.suite.admin) as db:
        before = db.get(AuthSession, digest(token)).last_seen_at
    if path_suffix == "stream":
        workflow.event_batch(token, loc, 0)
        workflow.event_batch(token, loc, 0)
    else:
        assert actor.request("GET", f"/v1/locations/{loc}/{path_suffix}").status_code == 200
    with Session(p3.suite.admin) as db:
        assert db.get(AuthSession, digest(token)).last_seen_at == before
    actor.client.close()


@pytest.mark.parametrize("variant", ["idle", "absolute", "revoked", "disabled_user", "disabled_membership", "revoked_grant"])
def test_running_stream_rechecks_expiration_identity_and_location_access(p3, variant):
    seed = seed_demo(p3.suite.admin, pytest_private_path(p3), "expiry-" + uuid4().hex[:7])
    layout = seed_dashboard(p3.suite.admin, seed)
    actor = p3.suite.login(seed["accounts"]["a_staff"])
    user = UUID(seed["accounts"]["a_staff"]["user_id"])
    token = actor.client.cookies.get(get_settings().cookie_name)
    loc = UUID(layout["locations"]["a"]["id"])
    with Session(p3.suite.admin) as db:
        revision = db.get(LocationOperations, loc).revision
    frames = workflow.stream_frames(token, loc, revision, user)
    assert "heartbeat" in next(frames)
    with Session(p3.suite.admin) as db, db.begin():
        session = db.get(AuthSession, digest(token))
        if variant == "idle": session.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
        elif variant == "absolute": session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif variant == "revoked": session.revoked = True
        elif variant == "disabled_user": db.get(User, user).enabled = False
        else:
            member = db.scalar(select(Membership).where(Membership.user_id == user))
            if variant == "disabled_membership": member.enabled = False
            else: db.get(LocationGrant, {"membership_id": member.id, "location_id": loc}).enabled = False
    message = next(frames)
    assert "session_expired" in message if variant in {"idle", "absolute", "revoked", "disabled_user"} else "access_lost" in message
    frames.close(); actor.client.close()


def pytest_private_path(p3):
    # Test-only output belongs to the same private pytest temp folder as the seeded accounts.
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp(prefix="restaurant-phase3-test-")) / "accounts.json"


def test_sse_replay_is_ordered_location_scoped_and_does_not_duplicate_effects(p3, table_id):
    loc = p3.table(table_id).location_id
    actor = p3.clients["a_owner"]
    token = actor.client.cookies.get(get_settings().cookie_name)
    with Session(p3.suite.admin) as db:
        before = db.get(LocationOperations, loc).revision
    p3.prepare(table_id, "RESET_PENDING")
    events = workflow.event_batch(token, loc, before)
    assert len(events) == 2
    assert [e["revision"] for e in events] == sorted(e["revision"] for e in events)
    assert all(e["location_id"] == str(loc) for e in events)
    assert workflow.event_batch(token, loc, events[-1]["revision"]) == []
    replay = workflow.event_batch(token, loc, before)
    assert replay == events
    for value in (f"{uuid4()}:0", f"{loc}:999999999", "invalid", f"{loc}:-1"):
        with pytest.raises(HTTPException): workflow.parse_cursor(value, loc, events[-1]["revision"])


@pytest.mark.parametrize("table", ["location_operations", "table_events", "staff_tasks", "action_receipts"])
def test_new_tables_are_rls_scoped_and_runtime_cannot_write_them_directly(p3, table_id, table):
    p3.prepare(table_id, "RESET_PENDING")
    with Session(p3.suite.runtime) as db:
        assert db.scalar(text(f"SELECT count(*) FROM public.{table}")) == 0
        set_identity(db, p3.seed["accounts"]["a_owner"]["user_id"])
        rows = db.scalars(text(f"SELECT DISTINCT organization_id FROM public.{table}")).all()
        assert set(map(str, rows)) == {p3.seed["organizations"]["a"]["id"]}
        assert not db.scalar(text("SELECT has_table_privilege(current_user,:name,'UPDATE')"), {"name": table})
        assert not db.scalar(text("SELECT has_table_privilege(current_user,:name,'DELETE')"), {"name": table})


def test_runtime_cannot_forge_state_or_bypass_privileged_action_checks(p3, table_id):
    with pytest.raises(DBAPIError), Session(p3.suite.runtime) as db, db.begin():
        set_identity(db, p3.seed["accounts"]["a_staff"]["user_id"])
        db.execute(text("UPDATE dining_tables SET current_state='AVAILABLE' WHERE id=:id"), {"id": table_id})
    with Session(p3.suite.runtime) as db, db.begin():
        set_identity(db, p3.seed["accounts"]["a_staff"]["user_id"])
        with pytest.raises(DBAPIError):
            db.execute(text("SELECT security.table_action(:id,'out_of_service',0,:key,:f,NULL,false,'maintenance',false,true)"),
                       {"id": table_id, "key": uuid4(), "f": "0" * 64})


def test_rejected_action_rolls_back_event_task_audit_and_revision(p3, table_id):
    before = p3.table(table_id).operational_revision
    assert p3.perform(table_id, "mark_ready", confirmed=True).status_code == 409
    assert p3.table(table_id).operational_revision == before
    with Session(p3.suite.admin) as db:
        assert db.query(ActionReceipt).filter_by(table_id=table_id).count() == 0
        assert db.query(TableEvent).filter_by(table_id=table_id).count() == 1  # Configuration only.
        assert db.query(StaffTask).filter_by(table_id=table_id).count() == 0


def test_demo_setup_is_repeatable_without_resetting_states_or_passwords(p3, table_id):
    before = p3.table(table_id)
    assert seed_dashboard(p3.suite.admin, p3.seed) == p3.layout
    after = p3.table(table_id)
    assert after.current_state == before.current_state and after.state_since == before.state_since
    assert p3.clients["a_owner"].request("GET", "/v1/me").status_code == 200


def test_history_pagination_and_foreign_table_filter(p3):
    loc = p3.layout["locations"]["a"]["id"]
    actor = p3.clients["a_staff"]
    first = actor.request("GET", f"/v1/locations/{loc}/activity?limit=1").json()
    second = actor.request("GET", f"/v1/locations/{loc}/activity?limit=1&offset=1").json()
    assert len(first) == len(second) == 1 and first[0]["id"] != second[0]["id"]
    assert first[0]["confidence"] is None  # Simulation never invents measured AI confidence.
    foreign = p3.layout["locations"]["b"]["table_ids"][0]
    assert actor.request("GET", f"/v1/locations/{loc}/activity?table_id={foreign}").status_code == 404
    assert actor.request("GET", f"/v1/locations/{loc}/tasks?limit=101").status_code == 422


@pytest.mark.parametrize("scenario", ["source_offline", "source_resume", "arrive"])
def test_ready_is_rejected_when_source_is_offline_unknown_or_occupied(p3, table_id, scenario):
    p3.prepare(table_id, "CLEANING")
    assert p3.perform(table_id, scenario, demo=True).status_code == 200
    assert p3.perform(table_id, "mark_ready", actor="a_staff", confirmed=True).status_code == 409
    assert p3.table(table_id).current_state == "CLEANING"


def test_reopening_requires_new_ready_confirmation(p3, table_id):
    p3.prepare(table_id, "OUT_OF_SERVICE")
    assert p3.perform(table_id, "reopen").json()["state"] == "UNKNOWN"
    assert p3.perform(table_id, "vacant", demo=True).json()["state"] == "UNKNOWN"
    assert p3.perform(table_id, "mark_ready", confirmed=True).json()["state"] == "AVAILABLE"


def test_staff_action_refreshes_idle_time_but_not_absolute_expiry(p3, table_id):
    p3.prepare(table_id, "RESET_PENDING")
    actor = p3.clients["a_staff"]
    token = actor.client.cookies.get(get_settings().cookie_name)
    old = datetime.now(UTC) - timedelta(seconds=60)
    with Session(p3.suite.admin) as db, db.begin():
        session = db.get(AuthSession, digest(token))
        session.last_seen_at = old
        absolute = session.expires_at
    assert p3.perform(table_id, "acknowledge", actor="a_staff").status_code == 200
    with Session(p3.suite.admin) as db:
        session = db.get(AuthSession, digest(token))
        assert session.last_seen_at > old and session.expires_at == absolute


def test_different_tables_publish_committed_events_in_location_order(p3, table_id):
    second = uuid4()
    first = p3.table(table_id)
    with Session(p3.suite.admin) as db, db.begin():
        from restaurant_api.models import DiningTable
        db.add(DiningTable(id=second, organization_id=first.organization_id,
                           location_id=first.location_id, label="Concurrent " + uuid4().hex[:8]))
    actors = [p3.suite.login(p3.seed["accounts"]["a_manager"]) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        replies = list(executor.map(lambda pair: p3.perform(pair[1], "arrive", demo=True, client=actors[pair[0]]),
                                     enumerate([table_id, second])))
    assert all(reply.status_code == 200 for reply in replies)
    revisions = [int(reply.json()["cursor"].split(":")[1]) for reply in replies]
    assert abs(revisions[0] - revisions[1]) == 1
    for actor in actors: actor.client.close()


def test_database_computes_receipt_fingerprint_and_rejects_payload_substitution(p3, table_id):
    key = uuid4()
    args = {"id": table_id, "key": key, "f": "0" * 64, "v": p3.table(table_id).operational_revision}
    statement = text("SELECT security.table_action(:id,:operation,:v,:key,:f,NULL,false,'',true,true)")
    with Session(p3.suite.runtime) as db, db.begin():
        set_identity(db, p3.seed["accounts"]["a_owner"]["user_id"])
        assert db.scalar(statement, dict(args, operation="arrive"))["state"] == "OCCUPIED"
    with pytest.raises(DBAPIError) as error, Session(p3.suite.runtime) as db, db.begin():
        set_identity(db, p3.seed["accounts"]["a_owner"]["user_id"])
        db.scalar(statement, dict(args, operation="vacant"))
    assert error.value.orig.sqlstate == "P0409"


@pytest.mark.parametrize("variant", ["foreign_reference", "duplicate_active"])
def test_task_database_constraints_reject_cross_scope_and_duplicate_active_rows(p3, table_id, variant):
    p3.prepare(table_id, "RESET_PENDING")
    table = p3.table(table_id)
    with pytest.raises(DBAPIError) as error, Session(p3.suite.admin) as db, db.begin():
        db.add(StaffTask(id=uuid4(), table_id=table_id, occupancy_session_id=uuid4(),
                         organization_id=UUID(p3.seed["organizations"]["b"]["id"])
                         if variant == "foreign_reference" else table.organization_id,
                         location_id=table.location_id))
        db.flush()
    assert error.value.orig.sqlstate in {"23503", "23505"}
