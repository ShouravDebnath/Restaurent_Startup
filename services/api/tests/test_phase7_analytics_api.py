"""Actual PostgreSQL/authorization/CSV tests on isolated synthetic records."""

import asyncio
import csv
import hashlib
import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from sqlalchemy import text

from restaurant_api.analytics import BoundedExport, admit_export, authorized_csv, release_export
from restaurant_api.settings import get_settings

from .test_phase7_workflow import edge as edge_fixture
from .test_phase7_workflow import edge_tenants as edge_tenants_fixture

edge = edge_fixture
edge_tenants = edge_tenants_fixture


def period():
    day = datetime.now(UTC).date() - timedelta(days=1)
    return day, f"from={day}&to={day + timedelta(days=1)}"


def history(e):
    day, query = period()
    start = datetime.combine(day, datetime.min.time(), UTC)
    table = uuid4()
    with e.suite.admin.begin() as db:
        db.execute(
            text(
                "INSERT INTO dining_tables(id,organization_id,location_id,label,created_at) VALUES(:id,:org,:loc,:label,:created)"
            ),
            {
                "id": table,
                "org": e.org,
                "loc": e.loc,
                "label": "=SUM(1,2)",
                "created": start - timedelta(days=1),
            },
        )
        previous = "UNKNOWN"
        for minutes, state in [
            (0, "AVAILABLE"),
            (60, "OCCUPIED"),
            (120, "RESET_PENDING"),
            (130, "CLEANING"),
            (140, "AVAILABLE"),
        ]:
            seq = db.scalar(
                text(
                    "UPDATE location_operations SET revision=revision+1 WHERE location_id=:id RETURNING revision"
                ),
                {"id": e.loc},
            )
            db.execute(
                text("""INSERT INTO table_events(id,organization_id,location_id,table_id,revision,event_type,source,
                occurred_at,ingested_at,previous_state,new_state,payload) VALUES(:id,:org,:loc,:table,:seq,'fixture.history','demo',
                :moment,:moment,:old,:new,'{}'::jsonb)"""),
                {
                    "id": uuid4(),
                    "org": e.org,
                    "loc": e.loc,
                    "table": table,
                    "seq": seq,
                    "moment": start + timedelta(minutes=minutes),
                    "old": previous,
                    "new": state,
                },
            )
            previous = state
    return table, query


def test_actual_history_report_and_csv_agree_with_closed_ground_truth(edge):
    table, query = history(edge)
    path = f"/v1/locations/{edge.loc}/analytics"
    report = edge.clients["a_manager"].request(
        "GET", path + "?" + query + "&table_id=" + str(table)
    )
    assert report.status_code == 200, report.text
    data = report.json()
    row = data["rows"][0]
    assert data["basis"] == "DEMO" and data["synthetic"] is True
    assert row["occupied_seconds"] == 3600 and row["state_seconds"]["RESET_PENDING"] == 600
    assert row["state_seconds"]["CLEANING"] == 600 and row["state_seconds"]["AVAILABLE"] == 81600
    assert (
        data["summary"]["average_occupied_seconds"] is None
    )  # No fabricated sessions from old-shaped history.
    exported = edge.clients["a_manager"].request(
        "GET", path + ".csv?" + query + "&table_id=" + str(table)
    )
    assert exported.status_code == 200, exported.text
    parsed = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert parsed[1]["table_label"].startswith("Text: ")
    assert float(parsed[1]["occupied_seconds"]) == row["occupied_seconds"]
    assert float(parsed[1]["state_RESET_PENDING"]) == 600
    assert exported.headers["cache-control"] == "private, no-store"
    assert int(exported.headers["content-length"]) == len(exported.content)
    assert int(exported.headers["x-report-bytes"]) == len(exported.content)
    assert "attachment;" in exported.headers["content-disposition"]
    assert not any(
        field in parsed[0]
        for field in ["password", "source_uri", "private_key", "signature", "email", "payload"]
    )


@pytest.mark.parametrize("suffix", ["analytics", "analytics.csv"])
def test_report_roles_tenant_boundaries_and_foreign_table_filter(edge, suffix):
    _table, query = history(edge)
    path = f"/v1/locations/{edge.loc}/{suffix}?{query}"
    anonymous = TestClient(edge.suite.app)
    assert anonymous.get(path).status_code == 401
    for who, status in [("b_owner", 404), ("a_installer", 403), ("a_staff", 403)]:
        assert edge.clients[who].request("GET", path).status_code == status
    other = edge.suite.seed["organizations"]["a"]["resources_1"]["table_id"]
    assert edge.clients["a_owner"].request("GET", path + "&table_id=" + other).status_code == 404
    foreign = edge.suite.seed["organizations"]["b"]["locations"][0]
    assert (
        edge.clients["a_owner"]
        .request("GET", f"/v1/locations/{foreign}/{suffix}?{query}")
        .status_code
        == 404
    )
    anonymous.close()


def test_report_and_csv_are_passive_and_stream_revocation_stops_bytes(edge):
    _, query = history(edge)
    actor = edge.suite.login(edge.suite.seed["accounts"]["a_owner"])
    token = actor.client.cookies.get(get_settings().cookie_name)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with edge.suite.admin.connect() as db:
        before = db.scalar(
            text("SELECT last_seen_at FROM identity.sessions WHERE token_digest=:d"), {"d": digest}
        )
    for suffix in ["analytics", "analytics.csv"]:
        assert actor.request("GET", f"/v1/locations/{edge.loc}/{suffix}?{query}").status_code == 200
    with edge.suite.admin.connect() as db:
        assert (
            db.scalar(
                text("SELECT last_seen_at FROM identity.sessions WHERE token_digest=:d"),
                {"d": digest},
            )
            == before
        )
    stream = authorized_csv(b"x" * 8193, token, edge.loc)
    assert len(next(stream)) == 4096
    with edge.suite.admin.begin() as db:
        db.execute(
            text("UPDATE identity.sessions SET revoked=true WHERE token_digest=:d"), {"d": digest}
        )
    assert list(stream) == []
    assert (
        actor.request("GET", f"/v1/locations/{edge.loc}/analytics.csv?{query}").status_code == 401
    )
    actor.client.close()


@pytest.mark.parametrize(
    "query",
    [
        "from=2026-01-01&to=2026-03-01",
        "from=2026-01-01&to=2026-01-01",
        "from=2026-01-01&to=2026-01-02&group=sql",
        "from=2026-01-01&to=2026-01-02&basis=untrusted",
        "from=invalid&to=2026-01-02",
    ],
)
def test_invalid_report_requests_fail_explicitly(edge, query):
    assert (
        edge.clients["a_owner"]
        .request("GET", f"/v1/locations/{edge.loc}/analytics?{query}")
        .status_code
        == 422
    )


def test_export_admission_limits_and_release():
    users = [uuid4() for _ in range(5)]
    try:
        for user in users[:4]:
            admit_export(user)
        for user in [users[0], users[4]]:
            with pytest.raises(HTTPException) as denied:
                admit_export(user)
            assert denied.value.status_code == 429
        release_export(users[0])
        admit_export(users[4])
    finally:
        for user in users:
            release_export(user)


def test_export_disconnect_releases_admission(monkeypatch):
    user = uuid4()

    async def disconnected(*args):
        raise OSError("simulated disconnected client")

    monkeypatch.setattr(StreamingResponse, "__call__", disconnected)
    admit_export(user)
    response = BoundedExport(iter([b"safe"]), user_id=user)
    with pytest.raises(OSError):
        asyncio.run(response({}, None, None))
    # A lost client cannot permanently exhaust this user's export slot.
    admit_export(user)
    release_export(user)


def test_report_calculation_shares_limit_and_invalid_request_releases_slot(edge):
    _, query = period()
    actor = edge.suite.seed["accounts"]["a_owner"]["user_id"]
    from uuid import UUID

    actor = UUID(actor)
    admit_export(actor)
    try:
        for suffix in ["analytics", "analytics.csv"]:
            response = edge.clients["a_owner"].request(
                "GET", f"/v1/locations/{edge.loc}/{suffix}?{query}"
            )
            assert response.status_code == 429
    finally:
        release_export(actor)
    path = f"/v1/locations/{edge.loc}/analytics"
    assert (
        edge.clients["a_owner"].request("GET", path + "?from=2026-01-01&to=2026-03-01").status_code
        == 422
    )
    assert edge.clients["a_owner"].request("GET", path + "?" + query).status_code == 200
