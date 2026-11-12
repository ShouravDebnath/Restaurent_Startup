"""Real saved DEMO actions must reach reports without rewriting any history."""

import csv
import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from restaurant_api.analytics_domain import calculate


def table_records(p3, table_id):
    with p3.suite.admin.connect() as db:
        return {
            name: db.scalars(
                text(f"SELECT to_jsonb(t) FROM public.{name} t WHERE table_id=:id"),
                {"id": table_id},
            ).all()
            for name in ["table_events", "staff_tasks", "workflow_sessions"]
        }


def saved_workflow(p3, table_id, *, repeat=False):
    assert p3.perform(table_id, "arrive", demo=True).status_code == 200
    if repeat:
        assert p3.perform(table_id, "arrive", demo=True).status_code == 200
    assert p3.perform(table_id, "depart", demo=True).status_code == 200
    for action in ["acknowledge", "start_cleaning", "mark_ready"]:
        assert p3.perform(table_id, action, confirmed=action == "mark_ready").status_code == 200


def report_path(p3, table_id):
    table = p3.table(table_id)
    day = datetime.now(UTC).astimezone(ZoneInfo("America/New_York")).date()
    return (
        f"/v1/locations/{table.location_id}/analytics",
        f"from={day}&to={day + timedelta(days=1)}&table_id={table_id}",
    )


@pytest.mark.parametrize("repeat", [False, True])
def test_actual_demo_actions_report_completed_visit_and_cleaning_without_backfill(
    p3, table_id, repeat
):
    saved_workflow(p3, table_id, repeat=repeat)
    before = table_records(p3, table_id)
    assert before["workflow_sessions"] == []
    task = before["staff_tasks"][0]
    arrival = next(e for e in before["table_events"] if e["event_type"] == "table.arrive")
    path, query = report_path(p3, table_id)
    response = p3.clients["a_owner"].request("GET", path + "?" + query)
    assert response.status_code == 200, response.text
    data = response.json()
    summary = data["summary"]
    assert data["basis"] == "DEMO" and data["calculation_version"] == 2
    assert summary["completed_occupied_sessions"] == summary["completed_resets"] == 1

    def duration(end, start):
        return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()

    assert summary["average_occupied_seconds"] == duration(
        task["created_at"], arrival["occurred_at"]
    )
    assert summary["average_cleaning_seconds"] == duration(task["completed_at"], task["started_at"])
    assert summary["average_time_to_ready_seconds"] == duration(
        task["completed_at"], task["created_at"]
    )
    assert summary["average_wait_to_clean_seconds"] == duration(
        task["started_at"], task["created_at"]
    )
    assert data["rows"][0]["state_seconds"]["CLEANING"] == summary["average_cleaning_seconds"]
    export = p3.clients["a_owner"].request("GET", path + ".csv?" + query)
    assert export.status_code == 200
    rows = list(csv.DictReader(io.StringIO(export.content.decode("utf-8-sig"))))
    assert rows[0]["report_completed_resets"] == "1"
    assert float(rows[0]["report_average_cleaning_seconds"]) == summary["average_cleaning_seconds"]
    assert int(export.headers["x-report-bytes"]) == len(export.content)
    for basis in ["LEGACY", "CONFIRMED_WORKFLOW", "ESTIMATED_EVIDENCE"]:
        other = p3.clients["a_owner"].request("GET", path + "?" + query + "&basis=" + basis)
        assert other.status_code == 200
        assert other.json()["summary"]["completed_resets"] == 0
    assert p3.clients["b_owner"].request("GET", path + "?" + query).status_code == 404
    assert p3.clients["a_staff"].request("GET", path + "?" + query).status_code == 403
    assert table_records(p3, table_id) == before


def test_departure_after_an_older_demo_arrival_keeps_original_visit_start(p3, table_id):
    saved_workflow(p3, table_id, repeat=True)
    with p3.suite.admin.begin() as db:
        arrival = db.execute(
            text(
                "SELECT id,occurred_at FROM table_events WHERE table_id=:id AND event_type='table.arrive' ORDER BY revision LIMIT 1"
            ),
            {"id": table_id},
        ).one()
        earlier = arrival.occurred_at - timedelta(days=5)
        # Only this test's new synthetic rows are adjusted to reproduce A02's
        # already-open pre-journal visit. Business records are never touched.
        db.execute(
            text("UPDATE dining_tables SET created_at=:at WHERE id=:id"),
            {"id": table_id, "at": earlier - timedelta(days=1)},
        )
        db.execute(
            text("UPDATE table_events SET occurred_at=:at WHERE id=:id"),
            {"id": arrival.id, "at": earlier},
        )
        db.execute(
            text("UPDATE workflow_journal SET basis='LEGACY',occurred_at=:at WHERE event_id=:id"),
            {"id": arrival.id, "at": earlier},
        )
    before = table_records(p3, table_id)
    path, query = report_path(p3, table_id)
    data = p3.clients["a_owner"].request("GET", path + "?" + query).json()
    assert data["summary"]["completed_occupied_sessions"] == 1
    assert data["summary"]["cross_boundary_sessions"] == 1
    assert data["summary"]["average_occupied_seconds"] > 5 * 86400
    assert data["summary"]["completed_resets"] == 1
    assert table_records(p3, table_id) == before


def test_cancelled_demo_reset_is_not_counted_as_staff_completed(p3, table_id):
    assert p3.perform(table_id, "arrive", demo=True).status_code == 200
    assert p3.perform(table_id, "depart", demo=True).status_code == 200
    assert p3.perform(table_id, "out_of_service", reason="maintenance").status_code == 200
    path, query = report_path(p3, table_id)
    data = p3.clients["a_owner"].request("GET", path + "?" + query).json()
    assert data["summary"]["completed_resets"] == 0
    assert data["summary"]["average_cleaning_seconds"] is None
    assert data["summary"]["cancelled_attempts"] == 1


def test_duplicate_demo_departure_retry_has_one_reported_task(p3, table_id):
    assert p3.perform(table_id, "arrive", demo=True).status_code == 200
    key, expected = uuid4(), p3.table(table_id).operational_revision
    first = p3.perform(table_id, "depart", demo=True, key=key, expected=expected)
    again = p3.perform(table_id, "depart", demo=True, key=key, expected=expected)
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    for action in ["start_cleaning", "mark_ready"]:
        assert p3.perform(table_id, action, confirmed=action == "mark_ready").status_code == 200
    path, query = report_path(p3, table_id)
    data = p3.clients["a_owner"].request("GET", path + "?" + query).json()
    assert data["summary"]["completed_resets"] == 1
    assert len(table_records(p3, table_id)["staff_tasks"]) == 1


def scenario_snapshot():
    from .test_phase7_analytics_domain import snapshot

    data = snapshot()
    session, attempt = data["sessions"][0], data["attempts"][0]
    data["scenario_tasks"] = [
        {
            "table_id": "one",
            "occupancy_session_id": session["id"],
            "arrived_at": session["arrived_at"],
            "created_at": attempt["pending_since"],
            "started_at": attempt["started_at"],
            "completed_at": attempt["completed_at"],
            "status": "COMPLETED",
            "resolution": "staff_confirmed_ready",
            "departure_verified": True,
            "start_verified": True,
            "ready_verified": True,
        }
    ]
    data["sessions"], data["attempts"] = [], []
    return data


@pytest.mark.parametrize(
    "change",
    [
        "production",
        "foreign_table",
        "missing_departure",
        "missing_start",
        "missing_ready",
        "wrong_resolution",
    ],
)
def test_unproven_or_foreign_scenario_does_not_supply_completed_reset(change):
    from .test_phase7_analytics_domain import DAY

    data = scenario_snapshot()
    task = data["scenario_tasks"][0]
    if change == "production":
        data["synthetic"] = False
    elif change == "foreign_table":
        task["table_id"] = "foreign"
    elif change == "wrong_resolution":
        task["resolution"] = "manager_blocked"
    else:
        task[change.replace("missing_", "") + "_verified"] = False
    result = calculate(data, DAY, DAY + timedelta(days=1), "UTC", basis="DEMO")
    assert result["summary"]["completed_resets"] == 0
    assert result["summary"]["average_cleaning_seconds"] is None


def test_missing_demo_arrival_keeps_known_cleaning_but_never_invents_occupied_duration():
    from .test_phase7_analytics_domain import DAY

    data = scenario_snapshot()
    data["scenario_tasks"][0]["arrived_at"] = None
    result = calculate(data, DAY, DAY + timedelta(days=1), "UTC", basis="DEMO")
    assert result["summary"]["completed_occupied_sessions"] == 0
    assert result["summary"]["average_occupied_seconds"] is None
    assert result["summary"]["completed_resets"] == 1
    assert result["summary"]["average_cleaning_seconds"] == 600


def test_canonical_and_duplicate_scenario_records_are_not_counted_twice():
    from .test_phase7_analytics_domain import DAY, snapshot

    data = scenario_snapshot()
    data["scenario_tasks"] *= 2
    for canonical in [False, True]:
        if canonical:
            data.update(sessions=snapshot()["sessions"], attempts=snapshot()["attempts"])
        result = calculate(data, DAY, DAY + timedelta(days=1), "UTC", basis="DEMO")
        assert result["summary"]["completed_occupied_sessions"] == 1
        assert result["summary"]["completed_resets"] == 1


def test_demo_summary_uses_new_york_completion_day_instead_of_utc_day():
    from .test_phase7_analytics_domain import DAY

    data = scenario_snapshot()
    new_york = calculate(data, DAY - timedelta(days=1), DAY, "America/New_York", basis="DEMO")
    following = calculate(data, DAY, DAY + timedelta(days=1), "America/New_York", basis="DEMO")
    utc = calculate(data, DAY, DAY + timedelta(days=1), "UTC", basis="DEMO")
    assert new_york["summary"]["completed_resets"] == 1
    assert following["summary"]["completed_resets"] == 0
    assert utc["summary"]["completed_resets"] == 1
