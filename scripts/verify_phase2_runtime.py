"""Exercise only synthetic Phase 2 data through the running Next.js proxy and API."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "http://localhost:3000"


def main():
    seed = json.loads(
        (ROOT / ".secrets/phase2-demo-credentials.json").read_text(encoding="utf-8")
    )
    assert seed["namespace"] == "local-phase2", (
        "Only the explicit synthetic seed is supported"
    )
    checks = []
    for path in ("/health", "/ready", "/v1/demo/tenant"):
        assert httpx.get("http://localhost:8000" + path).status_code == 200
    checks.append("existing health/demo and database readiness")
    with httpx.Client(base_url=ORIGIN, timeout=10) as anonymous:
        assert anonymous.get("/").status_code == 200
        assert anonymous.get("/api/v1/me").status_code == 401
    checks.append("unauthenticated proxy request rejected")
    clients = {}
    try:
        for key in ("a_owner", "b_owner", "a_staff"):
            client = httpx.Client(base_url=ORIGIN, timeout=10)
            account = seed["accounts"][key]
            response = client.post(
                "/api/v1/auth/session",
                headers={"origin": ORIGIN},
                json={
                    "email": account["email"],
                    "password": account["password"],
                },
            )
            assert response.status_code == 200
            assert "httponly" in response.headers["set-cookie"].lower()
            clients[key] = (
                client,
                {"origin": ORIGIN, "x-csrf-token": response.json()["csrf_token"]},
            )
            me = client.get("/api/v1/me")
            assert me.status_code == 200 and len(me.json()["access"]) == 1
            assert (
                me.json()["access"][0]["organization"]["id"]
                == seed["organizations"][key[0]]["id"]
            )
        checks.append("three real logins and scoped identity discovery")
        for actor, target in (("a", "b"), ("b", "a")):
            client, headers = clients[actor + "_owner"]
            foreign = seed["organizations"][target]["locations"][0]
            path = f"/api/v1/locations/{foreign}/tables"
            assert client.get(path).status_code == 404
            assert (
                client.post(
                    path, headers=headers, json={"label": "Rejected cross tenant"}
                ).status_code
                == 404
            )
        checks.append("cross-restaurant reads and writes blocked in both directions")
        a = seed["organizations"]["a"]
        prefix = f"/api/v1/locations/{a['locations'][0]}"
        client, headers = clients["a_owner"]
        assert (
            client.post(
                prefix + "/tables",
                headers={"origin": ORIGIN},
                json={"label": "Rejected CSRF"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                prefix + "/tables",
                headers=headers,
                json={
                    "label": "Rejected ownership",
                    "organization_id": seed["organizations"]["b"]["id"],
                },
            ).status_code
            == 422
        )
        label = "Runtime check " + uuid4().hex[:8]
        created = client.post(
            prefix + "/tables", headers=headers, json={"label": label, "seats": 4}
        )
        assert created.status_code == 201
        table_id = created.json()["id"]
        assert created.json()["current_state"] == "UNKNOWN"
        assert (
            client.patch(
                prefix + "/tables/" + table_id,
                headers=headers,
                json={"label": label, "seats": 6},
            ).status_code
            == 200
        )
        assert client.get(prefix + "/tables/" + table_id).json()["seats"] == 6
        assert client.get(prefix + "/cameras").status_code == 200
        assert client.get(prefix + "/table-zones").status_code == 200
        assert client.get(prefix + "/audit-logs").status_code == 200
        checks.append("authorized persistent table changes, metadata reads, and audits")
        staff, staff_headers = clients["a_staff"]
        assert (
            staff.post(
                prefix + "/tables",
                headers=staff_headers,
                json={"label": "Rejected staff"},
            ).status_code
            == 403
        )
        assert (
            staff.get(f"/api/v1/locations/{a['locations'][1]}/tables").status_code
            == 404
        )
        checks.append("role and same-restaurant location restrictions")
        assert (
            staff.delete("/api/v1/auth/session", headers=staff_headers).status_code
            == 204
        )
        assert staff.get("/api/v1/me").status_code == 401
        checks.append("logout revocation through proxy")
        report = {
            "verified_at_utc": datetime.now(UTC).isoformat(),
            "checks": checks,
            "created_synthetic_table_id": table_id,
            "existing_records_deleted": False,
        }
        (ROOT / ".secrets/phase2-runtime-verification.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(
            f"Running frontend/API/database verification passed: {len(checks)} groups. No credentials printed."
        )
    finally:
        for client, headers in clients.values():
            try:
                client.delete("/api/v1/auth/session", headers=headers)
            finally:
                client.close()


if __name__ == "__main__":
    main()
