"""Exercise real HTTP streams, not TestClient's fully buffered streaming implementation."""

import json
import socket
import threading
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from restaurant_api import workflow
from restaurant_api.models import AuthSession, LocationGrant, Membership
from restaurant_api.security import digest
from restaurant_api.settings import get_settings


@pytest.fixture(scope="module")
def server(p3):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0)); listener.listen()
        port = listener.getsockname()[1]
        app = uvicorn.Server(uvicorn.Config(p3.suite.app, log_level="critical", access_log=False,
                                            lifespan="off", timeout_graceful_shutdown=5))
        thread = threading.Thread(target=app.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        address = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                if httpx.get(address + "/health", timeout=1).status_code == 200: break
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        else:
            raise RuntimeError("Isolated HTTP server failed to start")
        yield address
        app.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive()


def messages(response):
    fields = {}
    for line in response.iter_lines():
        if not line:
            if fields:
                yield fields
                fields = {}
        elif ":" in line:
            name, value = line.split(":", 1)
            fields[name] = value.strip()


@pytest.fixture
def network_client(p3, server):
    account = p3.suite.account(member=False)
    with Session(p3.suite.admin) as db, db.begin():
        member_id = uuid4()
        org = UUID(p3.seed["organizations"]["a"]["id"])
        loc = UUID(p3.layout["locations"]["a"]["id"])
        db.add(Membership(id=member_id, user_id=UUID(str(account["user_id"])),
                          organization_id=org, role="owner"))
        db.flush()
        db.add(LocationGrant(membership_id=member_id, organization_id=org, location_id=loc))
    actor = p3.suite.login(account)
    token = actor.client.cookies.get(get_settings().cookie_name)
    with httpx.Client(base_url=server, timeout=8) as client:
        client.cookies.set(get_settings().cookie_name, token)
        yield client, token
    actor.client.close()


def test_real_sse_reconnect_header_replays_only_committed_new_events(p3, table_id, network_client):
    client, _ = network_client
    location = p3.table(table_id).location_id
    before = client.get(f"/v1/locations/{location}/dashboard").json()["cursor"]
    with client.stream("GET", f"/v1/locations/{location}/stream?after={before}") as response:
        assert response.status_code == 200 and "text/event-stream" in response.headers["content-type"]
        frames = messages(response)
        assert next(frames)["event"] == "heartbeat"
        result = p3.perform(table_id, "arrive", demo=True)
        frame = next(frames)
        assert frame["event"] == "change" and frame["id"] == result.json()["cursor"]
        assert json.loads(frame["data"])["table_id"] == str(table_id)
        last = frame["id"]
    result = p3.perform(table_id, "depart", demo=True)
    with client.stream("GET", f"/v1/locations/{location}/stream?after={before}",
                       headers={"Last-Event-ID": last}) as response:
        frame = next(messages(response))
        assert frame["event"] == "change" and frame["id"] == result.json()["cursor"]
        assert json.loads(frame["data"])["event_type"] == "table.depart"


def test_real_stream_closes_when_idle_session_expires_without_refresh(p3, network_client):
    client, token = network_client
    loc = p3.layout["locations"]["a"]["id"]
    with client.stream("GET", f"/v1/locations/{loc}/stream") as response:
        frames = messages(response)
        assert next(frames)["event"] == "heartbeat"
        with Session(p3.suite.admin) as db, db.begin():
            session = db.get(AuthSession, digest(token))
            session.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
        assert next(frames)["event"] == "session_expired"
        assert list(frames) == []
    assert client.get(f"/v1/locations/{loc}/dashboard").status_code == 401


def test_open_stream_does_not_hold_database_transaction(p3, network_client):
    client, _ = network_client
    loc = p3.layout["locations"]["a"]["id"]
    with client.stream("GET", f"/v1/locations/{loc}/stream") as response:
        assert next(messages(response))["event"] == "heartbeat"
        with p3.suite.admin.connect() as db:
            assert db.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE usename=:role "
                                  "AND state='idle in transaction'"),
                             {"role": p3.suite.runtime.url.username}) == 0


def test_stream_limit_is_bounded_and_release_is_idempotent():
    user = UUID("00000000-0000-0000-0000-000000000003")
    leases = [workflow.StreamLease(user) for _ in range(workflow.MAX_STREAMS_PER_USER)]
    try:
        with pytest.raises(HTTPException) as error: workflow.StreamLease(user)
        assert error.value.status_code == 429
    finally:
        for lease in leases:
            lease.close(); lease.close()
    assert user not in workflow._streams
