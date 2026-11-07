from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

POLYGON = [[0.1, 0.1], [0.8, 0.1], [0.8, 0.8], [0.1, 0.8]]


def routes(seed, letter):
    org = seed["organizations"][letter]
    oid, loc = org["id"], org["locations"][0]
    r = org["resources_1"]
    zone = {
        "table_id": r["table_id"],
        "camera_id": r["camera_id"],
        "polygon": POLYGON,
        "source_width": 1920,
        "source_height": 1080,
    }
    return [
        ("GET", f"/v1/organizations/{oid}", None),
        ("PATCH", f"/v1/organizations/{oid}", {"name": "Synthetic renamed"}),
        ("GET", f"/v1/organizations/{oid}/locations", None),
        ("POST", f"/v1/organizations/{oid}/locations", {"name": "Synthetic", "time_zone": "UTC"}),
        ("GET", f"/v1/locations/{loc}", None),
        ("PATCH", f"/v1/locations/{loc}", {"name": "Synthetic", "time_zone": "UTC"}),
        ("GET", f"/v1/organizations/{oid}/memberships", None),
        (
            "POST",
            f"/v1/organizations/{oid}/memberships",
            {"email": "synthetic@example.invalid", "role": "staff", "location_ids": []},
        ),
        (
            "PATCH",
            f"/v1/organizations/{oid}/memberships/{uuid4()}",
            {"role": "staff", "enabled": True, "location_ids": []},
        ),
        ("GET", f"/v1/organizations/{oid}/audit-logs", None),
        ("GET", f"/v1/locations/{loc}/audit-logs", None),
        ("GET", f"/v1/locations/{loc}/tables", None),
        ("POST", f"/v1/locations/{loc}/tables", {"label": "Synthetic", "seats": 4}),
        ("GET", f"/v1/locations/{loc}/tables/{r['table_id']}", None),
        (
            "PATCH",
            f"/v1/locations/{loc}/tables/{r['table_id']}",
            {"label": "Synthetic", "seats": 4},
        ),
        ("GET", f"/v1/locations/{loc}/cameras", None),
        (
            "POST",
            f"/v1/locations/{loc}/cameras",
            {"label": "Synthetic", "source_reference": "local_camera"},
        ),
        ("GET", f"/v1/locations/{loc}/cameras/{r['camera_id']}", None),
        ("PATCH", f"/v1/locations/{loc}/cameras/{r['camera_id']}", {"label": "Synthetic"}),
        ("GET", f"/v1/locations/{loc}/table-zones", None),
        ("POST", f"/v1/locations/{loc}/table-zones", zone),
        ("GET", f"/v1/locations/{loc}/table-zones/{r['zone_id']}", None),
        (
            "PUT",
            f"/v1/locations/{loc}/table-zones/{r['zone_id']}",
            {**zone, "expected_revision": 1},
        ),
    ]


@pytest.mark.parametrize("index", range(23))
@pytest.mark.parametrize("direction", [("a", "b"), ("b", "a")])
def test_every_scoped_route_blocks_other_restaurant(suite, clients, index, direction):
    actor, target = direction
    method, path, body = routes(suite.seed, target)[index]
    response = clients[f"{actor}_owner"].request(method, path, json=body)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("index", range(23))
def test_every_scoped_route_requires_login(suite, index):
    method, path, body = routes(suite.seed, "a")[index]
    with TestClient(suite.app) as client:
        assert client.request(method, path, json=body).status_code == 401


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/v1/me", None),
        ("GET", "/v1/auth/csrf", None),
        ("GET", "/v1/organizations", None),
        ("POST", "/v1/organizations", {"name": "Synthetic"}),
        ("DELETE", "/v1/auth/session", None),
    ],
)
def test_identity_routes_require_login(suite, method, path, body):
    with TestClient(suite.app) as client:
        assert client.request(method, path, json=body).status_code == 401


def test_discovery_exposes_only_explicit_access(suite, clients):
    for letter in ("a", "b"):
        response = clients[f"{letter}_manager"].request("GET", "/v1/me")
        assert response.status_code == 200
        access = response.json()["access"]
        assert len(access) == 1
        assert access[0]["organization"]["id"] == suite.seed["organizations"][letter]["id"]
        assert [item["id"] for item in access[0]["locations"]] == [
            suite.seed["organizations"][letter]["locations"][0]
        ]
        assert "password_hash" not in response.text
        organizations = clients[f"{letter}_manager"].request("GET", "/v1/organizations").json()
        assert [item["id"] for item in organizations] == [suite.seed["organizations"][letter]["id"]]


@pytest.mark.parametrize("role", ["org_admin", "manager", "staff", "installer"])
def test_same_restaurant_requires_location_grant(suite, clients, role):
    location = suite.seed["organizations"]["a"]["locations"][1]
    response = clients[f"a_{role}"].request("GET", f"/v1/locations/{location}/tables")
    assert response.status_code == 404
    assert clients["a_owner"].request("GET", f"/v1/locations/{location}/tables").status_code == 200


@pytest.mark.parametrize(
    "resource,id_key",
    [("tables", "table_id"), ("cameras", "camera_id"), ("table-zones", "zone_id")],
)
def test_foreign_id_under_authorized_location_is_hidden(suite, clients, resource, id_key):
    loc = suite.seed["organizations"]["a"]["locations"][0]
    foreign = suite.seed["organizations"]["b"]["resources_1"][id_key]
    found = clients["a_owner"].request("GET", f"/v1/locations/{loc}/{resource}/{foreign}")
    missing = clients["a_owner"].request("GET", f"/v1/locations/{loc}/{resource}/{uuid4()}")
    assert found.status_code == missing.status_code == 404
    assert found.json()["error"]["message"] == missing.json()["error"]["message"]


@pytest.mark.parametrize("field", ["organization_id", "location_id", "current_state"])
def test_ownership_and_state_body_tampering_rejected(suite, clients, field):
    loc = suite.seed["organizations"]["a"]["locations"][0]
    body = {"label": "Tampered", field: "AVAILABLE" if field == "current_state" else str(uuid4())}
    assert (
        clients["a_owner"].request("POST", f"/v1/locations/{loc}/tables", json=body).status_code
        == 422
    )


@pytest.mark.parametrize("target", ["foreign_org", "other_location"])
def test_zone_cannot_link_foreign_camera_or_table(suite, clients, target):
    org = suite.seed["organizations"]["a"]
    foreign = (
        suite.seed["organizations"]["b"]["resources_1"]
        if target == "foreign_org"
        else org["resources_2"]
    )
    for field in ("camera_id", "table_id"):
        body = {**org["resources_1"], "polygon": POLYGON, "source_width": 640, "source_height": 480}
        body.pop("zone_id")
        body[field] = foreign[field]
        response = clients["a_owner"].request(
            "POST", f"/v1/locations/{org['locations'][0]}/table-zones", json=body
        )
        assert response.status_code == 404


@pytest.mark.parametrize("role", ["owner", "org_admin", "manager", "staff", "installer"])
def test_role_matrix_for_tables_and_cameras(suite, clients, role):
    loc = suite.seed["organizations"]["a"]["locations"][0]
    table = clients[f"a_{role}"].request(
        "POST", f"/v1/locations/{loc}/tables", json={"label": uuid4().hex}
    )
    assert table.status_code == (201 if role in {"owner", "org_admin", "manager"} else 403)
    if table.status_code == 201:
        assert table.json()["current_state"] == "UNKNOWN"
        assert datetime.fromisoformat(table.json()["state_since"]).utcoffset() == timedelta(0)
    camera = clients[f"a_{role}"].request(
        "POST", f"/v1/locations/{loc}/cameras", json={"label": uuid4().hex}
    )
    assert camera.status_code == (403 if role == "staff" else 201)
    if camera.status_code == 201:
        assert camera.json()["status"] == "NOT_CONFIGURED"


@pytest.mark.parametrize("role", ["owner", "org_admin", "manager", "staff", "installer"])
def test_role_matrix_for_memberships_and_audits(suite, clients, role):
    org = suite.seed["organizations"]["a"]
    response = clients[f"a_{role}"].request("GET", f"/v1/organizations/{org['id']}/memberships")
    assert response.status_code == (200 if role in {"owner", "org_admin"} else 403)
    response = clients[f"a_{role}"].request(
        "GET", f"/v1/locations/{org['locations'][0]}/audit-logs"
    )
    assert response.status_code == (200 if role in {"owner", "org_admin", "manager"} else 403)


def test_membership_management_and_revocation(suite, clients):
    account = suite.account(member=False)
    org = suite.seed["organizations"]["a"]
    path = f"/v1/organizations/{org['id']}/memberships"
    response = clients["a_owner"].request(
        "POST",
        path,
        json={
            "email": account["email"],
            "role": "staff",
            "location_ids": [org["locations"][0]],
        },
    )
    assert response.status_code == 201
    member_id = response.json()["id"]
    actor = suite.login(account)
    assert actor.request("GET", f"/v1/locations/{org['locations'][0]}/tables").status_code == 200
    update = {"role": "staff", "enabled": False, "location_ids": [org["locations"][0]]}
    assert (
        clients["a_owner"].request("PATCH", path + "/" + member_id, json=update).status_code == 200
    )
    assert actor.request("GET", f"/v1/locations/{org['locations'][0]}/tables").status_code == 404


def test_explicit_self_grant_is_required_for_admin(suite, clients):
    account = suite.account(role="org_admin")
    actor = suite.login(account)
    org = suite.seed["organizations"]["a"]
    path = f"/v1/locations/{org['locations'][1]}/tables"
    assert actor.request("GET", path).status_code == 404
    response = actor.request(
        "PATCH",
        f"/v1/organizations/{org['id']}/memberships/{account['member_id']}",
        json={"role": "org_admin", "enabled": True, "location_ids": org["locations"]},
    )
    assert response.status_code == 200
    assert actor.request("GET", path).status_code == 200


def test_no_privilege_escalation_or_foreign_grants(suite, clients):
    org = suite.seed["organizations"]["a"]
    members = clients["a_owner"].request("GET", f"/v1/organizations/{org['id']}/memberships").json()
    staff = next(m for m in members if m["user_id"] == suite.seed["accounts"]["a_staff"]["user_id"])
    path = f"/v1/organizations/{org['id']}/memberships/{staff['id']}"
    assert (
        clients["a_staff"]
        .request(
            "PATCH",
            path,
            json={
                "role": "owner",
                "enabled": True,
                "location_ids": org["locations"],
            },
        )
        .status_code
        == 403
    )
    assert (
        clients["a_org_admin"]
        .request(
            "PATCH",
            path,
            json={
                "role": "owner",
                "enabled": True,
                "location_ids": org["locations"],
            },
        )
        .status_code
        == 403
    )
    assert (
        clients["a_owner"]
        .request(
            "PATCH",
            path,
            json={
                "role": "staff",
                "enabled": True,
                "location_ids": suite.seed["organizations"]["b"]["locations"],
            },
        )
        .status_code
        == 404
    )
