"""Explicit local API-restart/replay check on marked synthetic data; no DB/volume reset."""

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "http://localhost:3000"


def replay(client, location, position, event_id):
    with client.stream("GET", f"/api/v1/locations/{location}/stream",
                       headers={"Last-Event-ID": position}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                if event.get("id") == event_id:
                    return event
    raise RuntimeError("Expected durable event was not replayed")


def main():
    seed = json.loads((ROOT / ".secrets/phase2-demo-credentials.json").read_text())
    layout = json.loads((ROOT / ".secrets/phase3-demo-layout.json").read_text())
    assert seed["namespace"] == layout["namespace"] == "local-phase2"
    location = layout["locations"]["a"]["id"]
    table = layout["locations"]["a"]["table_ids"][4]
    checks = []
    with httpx.Client(base_url=ORIGIN, timeout=10) as client:
        account = seed["accounts"]["a_org_admin"]
        login = client.post("/api/v1/auth/session", headers={"Origin": ORIGIN},
                            json={"email": account["email"], "password": account["password"]})
        assert login.status_code == 200
        headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        try:
            snapshot = client.get(f"/api/v1/locations/{location}/dashboard").json()
            assert snapshot["demo"] and snapshot["simulation_controls"]
            record = next(t for t in snapshot["tables"] if t["id"] == table)
            body = {"table_id": table, "action": "source_offline", "expected_revision": record["operational_revision"],
                    "request_key": str(uuid4())}
            result = client.post(f"/api/v1/locations/{location}/demo/events", headers=headers, json=body)
            assert result.status_code == 200
            saved = result.json()
            first = replay(client, location, snapshot["cursor"], saved["event_id"])
            checks.append("committed synthetic event replays through the Next.js proxy")
            restarted = subprocess.run(["docker", "compose", "restart", "api"], cwd=ROOT,
                                       capture_output=True, text=True, check=False)
            if restarted.returncode:
                raise RuntimeError("API restart failed; private output omitted")
            for _ in range(60):
                try:
                    if httpx.get("http://localhost:8000/ready", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
            else:
                raise RuntimeError("API did not become ready after restart")
            assert client.get("/api/v1/me").status_code == 200
            checks.append("database-backed human session remains valid after API restart")
            second = replay(client, location, snapshot["cursor"], saved["event_id"])
            assert first == second
            checks.append("same durable event and cursor replay after process restart")
            duplicate = client.post(f"/api/v1/locations/{location}/demo/events", headers=headers, json=body)
            assert duplicate.status_code == 200 and duplicate.json() == saved
            final = client.get(f"/api/v1/locations/{location}/dashboard").json()
            after = next(t for t in final["tables"] if t["id"] == table)
            assert after["operational_revision"] == saved["revision"]
            assert after["current_state"] == record["current_state"]
            checks.append("retry after restart has one effect and preserves the prior table state")
        finally:
            assert client.delete("/api/v1/auth/session", headers=headers).status_code == 204
    report = {"verified_at_utc": datetime.now(UTC).isoformat(), "checks": checks,
              "api_restarted": True, "database_volume_untouched": True}
    (ROOT / ".secrets/phase3-restart-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
