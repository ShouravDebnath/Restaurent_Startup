import secrets
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from restaurant_api.database import set_identity

POLYGON = [[0.1, 0.1], [0.8, 0.1], [0.8, 0.8], [0.1, 0.8]]


def test_permission_changes_record_explicit_grants_in_audit(suite, clients):
    account = suite.account(member=False)
    org = suite.seed["organizations"]["a"]
    response = clients["a_owner"].request(
        "POST",
        f"/v1/organizations/{org['id']}/memberships",
        json={"email": account["email"], "role": "staff", "location_ids": [org["locations"][0]]},
    )
    assert response.status_code == 201
    records = (
        clients["a_owner"]
        .request("GET", f"/v1/organizations/{org['id']}/audit-logs?limit=100")
        .json()
    )
    record = next(
        row for row in records if row["details"].get("member_id") == response.json()["id"]
    )
    assert record["details"]["location_ids"] == [org["locations"][0]]
    assert record["details"]["role"] == "staff" and record["details"]["enabled"]


def test_full_configuration_round_trip_and_audit(suite):
    account = suite.account(member=False)
    actor = suite.login(account)
    response = actor.request("POST", "/v1/organizations", json={"name": "Synthetic new restaurant"})
    assert response.status_code == 201
    org_id = response.json()["id"]
    assert (
        actor.request(
            "PATCH", f"/v1/organizations/{org_id}", json={"name": "Synthetic renamed"}
        ).status_code
        == 200
    )
    response = actor.request(
        "POST",
        f"/v1/organizations/{org_id}/locations",
        json={
            "name": "First location",
            "time_zone": "America/New_York",
            "address": "Synthetic address",
        },
    )
    assert response.status_code == 201
    loc = response.json()["id"]
    prefix = f"/v1/locations/{loc}"
    assert actor.request("GET", prefix).status_code == 200
    assert actor.request("GET", f"/v1/organizations/{org_id}/locations").json()[0]["id"] == loc
    assert (
        actor.request(
            "PATCH", prefix, json={"name": "Renamed location", "time_zone": "Asia/Dhaka"}
        ).status_code
        == 200
    )
    table = actor.request("POST", prefix + "/tables", json={"label": "T02", "seats": 6})
    assert table.status_code == 201
    table_id = table.json()["id"]
    assert (
        actor.request(
            "PATCH", prefix + "/tables/" + table_id, json={"label": "T03", "seats": 8}
        ).status_code
        == 200
    )
    assert actor.request("GET", prefix + "/tables/" + table_id).json()["seats"] == 8
    camera = actor.request(
        "POST", prefix + "/cameras", json={"label": "North", "source_reference": "north_local"}
    )
    assert camera.status_code == 201
    camera_id = camera.json()["id"]
    assert (
        actor.request(
            "PATCH",
            prefix + "/cameras/" + camera_id,
            json={"label": "North revised", "source_reference": "north_local"},
        ).status_code
        == 200
    )
    assert (
        actor.request("GET", prefix + "/cameras/" + camera_id).json()["status"] == "NOT_CONFIGURED"
    )
    body = {
        "table_id": table_id,
        "camera_id": camera_id,
        "polygon": POLYGON,
        "source_width": 1920,
        "source_height": 1080,
    }
    response = actor.request("POST", prefix + "/table-zones", json=body)
    assert response.status_code == 201
    zone_id = response.json()["id"]
    response = actor.request(
        "PUT", prefix + "/table-zones/" + zone_id, json={**body, "expected_revision": 1}
    )
    assert response.status_code == 200 and response.json()["revision"] == 2
    assert (
        actor.request(
            "PUT", prefix + "/table-zones/" + zone_id, json={**body, "expected_revision": 1}
        ).status_code
        == 409
    )
    assert actor.request("GET", prefix + "/table-zones/" + zone_id).json()["revision"] == 2
    assert len(actor.request("GET", prefix + "/table-zones").json()) == 1
    audit = actor.request("GET", f"/v1/organizations/{org_id}/audit-logs?limit=100")
    assert audit.status_code == 200
    actions = {row["action"] for row in audit.json()}
    assert {
        "organization.created",
        "organization.updated",
        "location.created",
        "location.updated",
        "table.created",
        "table.updated",
        "camera.created",
        "camera.updated",
        "zone.created",
        "zone.updated",
    } <= actions
    for row in audit.json():
        assert row["organization_id"] == org_id
        assert datetime.fromisoformat(row["created_at"]).utcoffset() == timedelta(0)
    assert account["password"] not in audit.text
    assert "password_hash" not in audit.text
    assert actor.request("GET", prefix + "/audit-logs?limit=1&offset=0").status_code == 200
    assert len(actor.request("GET", prefix + "/audit-logs?limit=1&offset=0").json()) == 1
    assert actor.request("GET", prefix + "/audit-logs?limit=101").status_code == 422


@pytest.mark.parametrize("role", ["owner", "org_admin", "manager", "staff", "installer"])
def test_zone_role_matrix(suite, clients, role):
    loc = suite.seed["organizations"]["a"]["locations"][0]
    prefix = f"/v1/locations/{loc}"
    table = (
        clients["a_owner"].request("POST", prefix + "/tables", json={"label": uuid4().hex}).json()
    )
    camera = (
        clients["a_owner"].request("POST", prefix + "/cameras", json={"label": uuid4().hex}).json()
    )
    body = {
        "table_id": table["id"],
        "camera_id": camera["id"],
        "polygon": POLYGON,
        "source_width": 640,
        "source_height": 480,
    }
    response = clients[f"a_{role}"].request("POST", prefix + "/table-zones", json=body)
    assert response.status_code == (403 if role == "staff" else 201)
    if response.status_code == 201:
        update = clients[f"a_{role}"].request(
            "PUT",
            prefix + "/table-zones/" + response.json()["id"],
            json={**body, "expected_revision": 1},
        )
        assert update.status_code == 200 and update.json()["revision"] == 2


@pytest.mark.parametrize(
    "points",
    [
        [[-0.1, 0], [1, 0], [0, 1]],
        [[0, 0], [1, 1], [0, 1], [1, 0]],
        [[0, 0], [0.5, 0.5], [1, 1]],
        [[0, 0], [1, 0], [1, 0]],
    ],
)
def test_invalid_polygon_rejected_by_api_and_database(suite, clients, points):
    org = suite.seed["organizations"]["a"]
    body = {
        "table_id": org["resources_1"]["table_id"],
        "camera_id": org["resources_1"]["camera_id"],
        "polygon": points,
        "source_width": 640,
        "source_height": 480,
    }
    assert (
        clients["a_owner"]
        .request("POST", f"/v1/locations/{org['locations'][0]}/table-zones", json=body)
        .status_code
        == 422
    )
    import json

    with suite.runtime.connect() as connection:
        assert not connection.scalar(
            text("SELECT security.valid_polygon(CAST(:points AS jsonb))"),
            {"points": json.dumps(points)},
        )


def test_camera_secret_url_rejected_without_echo(suite, clients):
    org = suite.seed["organizations"]["a"]
    private = secrets.token_urlsafe(24)
    response = clients["a_owner"].request(
        "POST",
        f"/v1/locations/{org['locations'][0]}/cameras",
        json={
            "label": "Rejected camera",
            "source_reference": f"rtsp://synthetic:{private}@local/stream",
        },
    )
    assert response.status_code == 422
    assert private not in response.text and "rtsp://" not in response.text


def test_failed_update_does_not_write_audit_or_change_data(suite, clients):
    org = suite.seed["organizations"]["a"]
    prefix = f"/v1/locations/{org['locations'][0]}"
    label1, label2 = uuid4().hex, uuid4().hex
    first = clients["a_owner"].request("POST", prefix + "/tables", json={"label": label1}).json()
    clients["a_owner"].request("POST", prefix + "/tables", json={"label": label2})
    with suite.admin.connect() as connection:
        before = connection.scalar(text("SELECT count(*) FROM audit_logs"))
    response = clients["a_owner"].request(
        "PATCH", prefix + "/tables/" + first["id"], json={"label": label2}
    )
    assert response.status_code == 409
    assert (
        clients["a_owner"].request("GET", prefix + "/tables/" + first["id"]).json()["label"]
        == label1
    )
    with suite.admin.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM audit_logs")) == before


def test_foreign_membership_id_and_owner_protection(suite, clients):
    a = suite.seed["organizations"]["a"]
    foreign_member = uuid5(NAMESPACE_URL, f"restaurant-ai/{suite.namespace}/member-b_staff")
    response = clients["a_owner"].request(
        "PATCH",
        f"/v1/organizations/{a['id']}/memberships/{foreign_member}",
        json={"role": "staff", "enabled": True, "location_ids": []},
    )
    assert response.status_code == 404
    owner_member = uuid5(NAMESPACE_URL, f"restaurant-ai/{suite.namespace}/member-a_owner")
    assert (
        clients["a_org_admin"]
        .request(
            "PATCH",
            f"/v1/organizations/{a['id']}/memberships/{owner_member}",
            json={"role": "owner", "enabled": True, "location_ids": []},
        )
        .status_code
        == 403
    )
    assert (
        clients["a_owner"]
        .request(
            "PATCH",
            f"/v1/organizations/{a['id']}/memberships/{owner_member}",
            json={"role": "owner", "enabled": False, "location_ids": []},
        )
        .status_code
        == 409
    )


def test_last_owner_cannot_be_demoted_in_database(suite):
    account = suite.account(member=False)
    actor = suite.login(account)
    org = actor.request(
        "POST", "/v1/organizations", json={"name": "Owner safeguard example"}
    ).json()
    with pytest.raises(IntegrityError), Session(suite.runtime) as db, db.begin():
        set_identity(db, str(account["user_id"]))
        db.execute(
            text("UPDATE memberships SET role='manager' WHERE organization_id=:org"),
            {"org": org["id"]},
        )


def test_one_user_can_have_explicit_access_to_two_restaurants(suite, clients):
    account = suite.account()
    org = suite.seed["organizations"]["b"]
    response = clients["b_owner"].request(
        "POST",
        f"/v1/organizations/{org['id']}/memberships",
        json={
            "email": account["email"],
            "role": "staff",
            "location_ids": [org["locations"][0]],
        },
    )
    assert response.status_code == 201
    actor = suite.login(account)
    assert len(actor.request("GET", "/v1/me").json()["access"]) == 2
    assert actor.request("GET", f"/v1/locations/{org['locations'][0]}/tables").status_code == 200
    assert actor.request("GET", f"/v1/locations/{org['locations'][1]}/tables").status_code == 404
