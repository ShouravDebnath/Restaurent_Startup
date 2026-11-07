"""Actual PostgreSQL tests for explicit preview consent, history and calibration races."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from restaurant_api.database import set_identity

from .test_security import POLYGON


def scope(suite, letter="a"):
    org = suite.seed["organizations"][letter]
    return org["locations"][0], org["resources_1"]


def endpoints(suite, letter="a"):
    loc, r = scope(suite, letter)
    camera = f"/v1/locations/{loc}/cameras/{r['camera_id']}"
    body = {"viewer_id": suite.seed["accounts"][f"{letter}_installer"]["user_id"],
            "request_key": str(uuid4()), "consent": True}
    return [("POST", camera + "/preview-grants", body),
            ("GET", camera + "/preview-grants", None),
            ("POST", camera + f"/preview-grants/{uuid4()}/revoke", None),
            ("GET", camera + "/preview-authorization", None),
            ("GET", f"/v1/locations/{loc}/table-zones/{r['zone_id']}/revisions", None)]


@pytest.mark.parametrize("index", range(5))
@pytest.mark.parametrize("letter", ["a", "b"])
def test_new_routes_block_other_tenant_and_anonymous(suite, clients, index, letter):
    method, path, body = endpoints(suite, letter)[index]
    other = "b" if letter == "a" else "a"
    assert clients[other + "_owner"].request(method, path, json=body).status_code == 404
    with TestClient(suite.app) as anon:
        assert anon.request(method, path, json=body).status_code == 401


def test_preview_requires_explicit_consent_and_role(suite, clients):
    loc, r = scope(suite)
    path = f"/v1/locations/{loc}/cameras/{r['camera_id']}"
    viewer = suite.seed["accounts"]["a_installer"]["user_id"]
    body = {"viewer_id": viewer, "request_key": str(uuid4()), "consent": False}
    assert clients["a_owner"].request("POST", path + "/preview-grants", json=body).status_code == 422
    for role in ["staff", "installer"]:
        assert clients["a_" + role].request("POST", path + "/preview-grants",
            json={**body, "consent": True}).status_code == 403
    body["viewer_id"] = suite.seed["accounts"]["a_staff"]["user_id"]
    body["consent"] = True
    assert clients["a_owner"].request("POST", path + "/preview-grants", json=body).status_code == 422
    body["viewer_id"] = suite.seed["accounts"]["b_installer"]["user_id"]
    assert clients["a_owner"].request("POST", path + "/preview-grants", json=body).status_code == 422


def test_grant_retry_revoke_and_expiration(suite, clients):
    loc, r = scope(suite)
    path = f"/v1/locations/{loc}/cameras/{r['camera_id']}"
    # A fresh eligible account avoids another test's active preview grant.
    account = suite.account("installer")
    actor = suite.login(account)
    assert actor.request("GET", path + "/preview-authorization").status_code == 403
    body = {"viewer_id": str(account["user_id"]), "request_key": str(uuid4()), "consent": True,
            "duration_seconds": 60}
    first = clients["a_manager"].request("POST", path + "/preview-grants", json=body)
    assert first.status_code == 201
    assert clients["a_manager"].request("POST", path + "/preview-grants", json=body).json() == first.json()
    assert clients["a_manager"].request("POST", path + "/preview-grants",
        json={**body, "duration_seconds": 120}).status_code == 409
    assert actor.request("GET", path + "/preview-authorization").status_code == 200
    revoked = clients["a_manager"].request("POST", path + "/preview-grants/" + first.json()["id"] + "/revoke")
    assert revoked.status_code == 200 and revoked.json()["revoked_at"]
    assert actor.request("GET", path + "/preview-authorization").status_code == 403
    body["request_key"] = str(uuid4())
    second = clients["a_owner"].request("POST", path + "/preview-grants", json=body).json()
    with suite.admin.begin() as db:
        db.execute(text("UPDATE camera_preview_grants SET created_at=created_at-interval '2 hour',"
            "expires_at=expires_at-interval '2 hour' WHERE id=:id"), {"id": second["id"]})
    assert actor.request("GET", path + "/preview-authorization").status_code == 403
    actor.client.close()


def test_preview_reads_do_not_refresh_idle_session(suite, clients):
    loc, r = scope(suite)
    account = suite.account("installer")
    actor = suite.login(account)
    path = f"/v1/locations/{loc}/cameras/{r['camera_id']}"
    clients["a_owner"].request("POST", path + "/preview-grants", json={
        "viewer_id": str(account["user_id"]), "request_key": str(uuid4()), "consent": True})
    def last_seen():
        with suite.admin.connect() as db:
            return db.scalar(text("SELECT last_seen_at FROM identity.sessions WHERE user_id=:u"),
                             {"u": account["user_id"]})
    before = last_seen()
    for _ in range(3):
        assert actor.request("GET", path + "/preview-authorization").status_code == 200
    assert last_seen() == before
    with suite.admin.begin() as db:
        db.execute(text("UPDATE identity.sessions SET last_seen_at=last_seen_at-interval '2 hour' WHERE user_id=:u"),
                   {"u": account["user_id"]})
    assert actor.request("GET", path + "/preview-authorization").status_code == 401
    actor.client.close()


def test_history_persistence_retry_and_concurrent_revision(suite, clients):
    loc, _ = scope(suite)
    base = f"/v1/locations/{loc}"
    table = clients["a_owner"].request("POST", base + "/tables", json={"label": uuid4().hex}).json()
    camera = clients["a_owner"].request("POST", base + "/cameras", json={"label": uuid4().hex}).json()
    body = {"table_id": table["id"], "camera_id": camera["id"], "polygon": POLYGON,
            "source_width": 640, "source_height": 360, "request_key": str(uuid4()),
            "view_metadata": {"rotation": 0, "mirrored": False, "format_version": 1}}
    first = clients["a_installer"].request("POST", base + "/table-zones", json=body)
    assert first.status_code == 201
    assert clients["a_installer"].request("POST", base + "/table-zones", json=body).json() == first.json()
    path = base + "/table-zones/" + first.json()["id"]
    change = {**body, "expected_revision": 1, "request_key": str(uuid4()), "source_width": 800}
    def update(_):
        # Separate requests/transactions; no shared TestClient/thread state.
        with suite.login(suite.seed["accounts"]["a_manager"]).client as c:
            csrf = c.get('/v1/auth/csrf').json()['csrf_token']
            return c.put(path, json={**change, "request_key": str(uuid4())},
                         headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf}).status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(update, range(2))) == [200, 409]
    rows = clients["a_installer"].request("GET", path + "/revisions").json()
    assert [row["revision"] for row in rows] == [2, 1]
    assert rows[0]["snapshot"]["source_width"] == 800
    assert rows[1]["snapshot"]["polygon"] == POLYGON
    assert clients["a_staff"].request("GET", path + "/revisions").status_code == 403
    with Session(suite.runtime) as db, db.begin():
        set_identity(db, str(suite.seed["accounts"]["b_owner"]["user_id"]))
        assert db.scalar(text("SELECT count(*) FROM table_zone_revisions WHERE zone_id=:z"),
                         {"z": UUID(first.json()["id"])}) == 0


@pytest.mark.parametrize("index", range(5))
def test_new_routes_require_same_organization_location_grant(suite, index):
    account = suite.account('org_admin')
    actor = suite.login(account)
    method, path, body = endpoints(suite)[index]
    with suite.admin.begin() as db:
        db.execute(text("UPDATE location_grants SET enabled=false WHERE membership_id=:m"),
                   {'m':account['member_id']})
    assert actor.request(method, path, json=body).status_code == 404
    actor.client.close()


@pytest.mark.parametrize('restriction', ['user','membership','location','absolute_session'])
def test_preview_rechecks_disabled_identity_and_absolute_session(suite, clients, restriction):
    account = suite.account('installer')
    actor = suite.login(account)
    loc, r = scope(suite)
    path = f"/v1/locations/{loc}/cameras/{r['camera_id']}"
    assert clients['a_owner'].request('POST',path+'/preview-grants',json={
        'viewer_id':str(account['user_id']),'request_key':str(uuid4()),'consent':True}).status_code==201
    assert actor.request('GET',path+'/preview-authorization').status_code==200
    query, key = {
        'user':('UPDATE identity.users SET enabled=false WHERE id=:key',account['user_id']),
        'membership':('UPDATE memberships SET enabled=false WHERE id=:key',account['member_id']),
        'location':('UPDATE location_grants SET enabled=false WHERE membership_id=:key',account['member_id']),
        'absolute_session':("UPDATE identity.sessions SET expires_at=clock_timestamp()-interval '1 second' WHERE user_id=:key",account['user_id']),
    }[restriction]
    with suite.admin.begin() as db:
        db.execute(text(query),{'key':key})
    assert actor.request('GET',path+'/preview-authorization').status_code == (401 if restriction in {'user','absolute_session'} else 404)
    actor.client.close()


@pytest.mark.parametrize('table', ['table_zone_revisions','camera_preview_grants'])
def test_new_security_records_cannot_be_updated_directly(suite, table):
    with suite.runtime.connect() as db:
        with pytest.raises(DBAPIError) as rejected:
            db.execute(text(f"DELETE FROM {table} WHERE false"))
        assert rejected.value.orig.sqlstate=='42501'
        db.rollback()


def test_calibration_history_and_audit_roll_back_together(suite, clients, monkeypatch):
    from restaurant_api import routes
    loc, _ = scope(suite)
    base=f'/v1/locations/{loc}'
    table=clients['a_owner'].request('POST',base+'/tables',json={'label':uuid4().hex}).json()
    camera=clients['a_owner'].request('POST',base+'/cameras',json={'label':uuid4().hex}).json()
    key=str(uuid4())
    original=routes.audit
    interrupted_zones=[]
    def interrupted(db, identity, org, action, location, **details):
        original(db, identity, org, action, location, **details)
        if action=='zone.created':
            interrupted_zones.append(details['zone_id'])
            raise RuntimeError('synthetic interruption after audit')
    monkeypatch.setattr(routes,'audit',interrupted)
    with pytest.raises(RuntimeError,match='synthetic interruption'):
        clients['a_owner'].request('POST',base+'/table-zones',json={
            'camera_id':camera['id'],'table_id':table['id'],'polygon':POLYGON,
            'source_width':640,'source_height':360,'request_key':key})
    with suite.admin.connect() as db:
        assert db.scalar(text('SELECT count(*) FROM table_zones WHERE table_id=:t'),{'t':table['id']})==0
        assert db.scalar(text('SELECT count(*) FROM table_zone_revisions WHERE request_key=:k'),{'k':key})==0
        assert len(interrupted_zones)==1
        assert db.scalar(text("SELECT count(*) FROM audit_logs WHERE details->>'zone_id'=:z"),
                         {'z':interrupted_zones[0]})==0
