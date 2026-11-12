"""Installed Edge + production web + real API on a NEW isolated synthetic database.

Uses signed constructed evidence, not people or video. Never migrates business data,
installs software or removes the retained test database/browser artifacts.
"""

import base64
import csv
import io
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import uvicorn
from restaurant_api.dashboard_seed import seed_dashboard
from restaurant_api.database import get_engine
from restaurant_api.main import create_app
from restaurant_api.management import migrate, provision_runtime, seed_demo
from restaurant_api.settings import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from verify_phase3_browser import click, end_session, open_browser, select, state

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from tests.conftest import Suite
from tests.test_edge_transport import configure, send
from tests.test_edge_transport import edge as edge_fixture
from tests.test_phase7_workflow import evidence, post, view

ORIGIN = "http://localhost:3001"


def ready(url):
    from urllib.request import urlopen

    for _ in range(150):
        try:
            with urlopen(url, timeout=1) as result:
                if result.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError("Isolated browser service did not become ready")


def checked(browser, selector):
    browser.wait(f"!!document.querySelector({json.dumps(selector)})")
    browser.evaluate(
        f"if(!document.querySelector({json.dumps(selector)}).checked)document.querySelector({json.dumps(selector)}).click()"
    )


def pulse(e, kind="VACANT", snapshot=True, **extra):
    assert (
        send(
            e,
            "/v1/edge/heartbeat",
            {"camera": "ONLINE", "inference": "RUNNING", "queue_pending": 0},
        ).status_code
        == 200
    )
    e.sent_at = time.monotonic()
    post(e, evidence(e, kind, snapshot=snapshot, **extra))


def main():
    folder = ROOT / ".secrets/phase7-implementation" / ("browser-" + uuid4().hex)
    folder.mkdir()
    cfg = json.loads((ROOT / ".secrets/phase2-test.json").read_text())
    assert cfg["container"].startswith("restaurant-phase2-test-")
    url = URL.create(
        "postgresql+psycopg",
        username=cfg["username"],
        password=cfg["password"],
        host="127.0.0.1",
        port=cfg["port"],
        database=cfg["database"],
    )
    db_name = "phase2_security_test_phase7_browser_" + uuid4().hex[:10]
    admin = create_engine(url, hide_parameters=True)
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
        db.exec_driver_sql('CREATE DATABASE "' + db_name + '"')
    admin.dispose()
    admin = create_engine(url.set(database=db_name), hide_parameters=True)
    migrate(admin)
    user, password = "restaurant_browser_" + uuid4().hex[:8], secrets.token_urlsafe(36)
    provision_runtime(admin, user, password)
    seed = seed_demo(
        admin, folder / "accounts.json", "phase7-browser-" + uuid4().hex[:8]
    )
    demo_layout = seed_dashboard(admin, seed)
    os.environ["DATABASE_URL"] = url.set(
        database=db_name, username=user, password=password
    ).render_as_string(hide_password=False)
    os.environ["EDGE_SYNC_ENABLED"] = "true"
    os.environ["ALLOWED_ORIGINS"] = ORIGIN + ",http://localhost:3000"
    get_settings.cache_clear()
    get_engine.cache_clear()
    suite = Suite(admin, get_engine(), create_app(), seed, "phase7-browser")
    clients = {key: suite.login(value) for key, value in seed["accounts"].items()}
    patch = pytest.MonkeyPatch()
    generator = edge_fixture.__wrapped__((suite, clients), patch)
    e = next(generator)
    configure(e)
    e.episode, e.generation, e.sequence = uuid4(), uuid4(), 0
    app = create_app()
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=8001, access_log=False, log_level="critical"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    ready("http://127.0.0.1:8001/health")
    env = dict(os.environ, API_INTERNAL_URL="http://127.0.0.1:8001")
    image = os.environ.get("PHASE7_WEB_IMAGE")
    if image and image != "restaurant-phase7-web-reviewed":
        raise ValueError("Only the prepared local Phase 7 test image is allowed")
    container = None
    checks = []
    update_latencies = []
    task_latencies = []
    try:
        with (folder / "web.log").open("w", encoding="utf-8") as log:
            web = (
                None
                if image
                else subprocess.Popen(
                    [
                        "node",
                        str(ROOT / "apps/web/node_modules/next/dist/bin/next"),
                        "start",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        "3001",
                    ],
                    cwd=ROOT / "apps/web",
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            )
            if image:
                container = subprocess.check_output(
                    [
                        "docker",
                        "run",
                        "--detach",
                        "--name",
                        "restaurant-phase7-browser-" + uuid4().hex[:8],
                        "--label",
                        "restaurant.phase7-test=true",
                        "--publish",
                        "127.0.0.1:3001:3000",
                        "--env",
                        "API_INTERNAL_URL=http://host.docker.internal:8001",
                        image,
                    ],
                    text=True,
                ).strip()
            try:
                ready(ORIGIN + "/sign-in")
                with ExitStack() as stack:
                    owner, staff, other = [
                        stack.enter_context(open_browser(folder / key))
                        for key in ["owner", "staff", "other"]
                    ]
                    for browser, key in [
                        (owner, "a_owner"),
                        (staff, "a_staff"),
                        (other, "b_owner"),
                    ]:
                        browser.send("Page.navigate", {"url": ORIGIN + "/dashboard"})
                        browser.login(seed["accounts"][key])
                        stack.callback(end_session, browser)
                    for browser in [owner, staff]:
                        browser.send(
                            "Page.navigate",
                            {"url": f"{ORIGIN}/dashboard?location={e.loc}"},
                        )
                        browser.wait(
                            "document.body.innerText.includes('Updates connected') && !!document.querySelector('.review-panel')"
                        )
                    assert owner.evaluate(
                        "document.querySelector('.review-panel').innerText.includes('Suggestions OFF')"
                    )
                    owner.evaluate(
                        "Array.from(document.querySelectorAll('summary')).find(x=>x.textContent==='Manager review settings').parentElement.open=true"
                    )
                    checked(owner, ".review-panel fieldset input")
                    checked(owner, ".review-panel details:last-child > label input")
                    click(owner, "Enable reviewed DEMO suggestions")
                    owner.wait(
                        "document.querySelector('.review-panel').innerText.includes('Human review enabled')"
                    )
                    e.workflow_revision = (
                        e.clients["a_owner"]
                        .request("GET", f"/v1/locations/{e.loc}/workflow-policy")
                        .json()["revision"]
                    )
                    checks.append(
                        "manager enables only selected synthetic binding; default OFF and explicit threshold review"
                    )
                    pulse(e, "POSITIVE", False)
                    staff.wait("!!document.querySelector('.review-card')")
                    update_latencies.append(time.monotonic() - e.sent_at)
                    assert view(e)["suggestions"][0]["action"] == "ARRIVAL"
                    state(staff, e.table, "UNKNOWN")
                    checked(staff, ".review-card input[type=checkbox]")
                    staff.evaluate("""window.savedFetch=window.fetch;window.fetch=async(...args)=>{
                        const r=await window.savedFetch(...args);if(String(args[0]).endsWith('/decisions')&&r.ok){window.fetch=window.savedFetch;throw new Error('simulated lost response')}return r}""")
                    click(staff, "Confirm arrival")
                    staff.wait(
                        "document.body.innerText.includes('Retry the same request')"
                    )
                    click(staff, "Retry the same request")
                    state(staff, e.table, "OCCUPIED")
                    state(owner, e.table, "OCCUPIED")
                    checks.append(
                        "signed fabricated arrival stays suggestion until physical checkbox; lost response retries same key once; SSE updates second browser"
                    )
                    pulse(e, "VACANT", False)
                    staff.wait(
                        "document.querySelector('.review-card')?.innerText.includes('possible departure')"
                    )
                    update_latencies.append(time.monotonic() - e.sent_at)
                    checked(staff, ".review-card input[type=checkbox]")
                    accepted_at = time.monotonic()
                    click(staff, "Confirm departure")
                    state(owner, e.table, "RESET_PENDING")
                    task_latencies.append(time.monotonic() - accepted_at)
                    select(owner, e.table)
                    owner.evaluate(
                        "document.querySelector('.manager-correction').open=true"
                    )
                    checked(owner, ".manager-correction input")
                    click(owner, "Record correction")
                    state(staff, e.table, "OCCUPIED")
                    pulse(e, "VACANT", False)
                    staff.wait(
                        "document.querySelector('.review-card')?.innerText.includes('possible departure')"
                    )
                    update_latencies.append(time.monotonic() - e.sent_at)
                    checked(staff, ".review-card input[type=checkbox]")
                    click(staff, "Confirm departure")
                    state(staff, e.table, "RESET_PENDING")
                    click(staff, "Acknowledge")
                    select(staff, e.table)
                    click(
                        staff,
                        "Start cleaning",
                        "document.querySelector('.table-details')",
                    )
                    state(staff, e.table, "CLEANING")
                    pulse(
                        e,
                        "VACANT",
                        True,
                        state="CLEANING",
                        reason="CURRENT_HUMAN_STATE",
                    )
                    click(
                        staff,
                        "I checked this table — mark ready",
                        "document.querySelector('.table-details')",
                    )
                    state(owner, e.table, "AVAILABLE")
                    with admin.connect() as db:
                        assert (
                            db.scalar(
                                text(
                                    "SELECT count(*) FROM staff_tasks WHERE table_id=:id"
                                ),
                                {"id": e.table},
                            )
                            == 1
                        )
                        assert (
                            db.scalar(
                                text(
                                    "SELECT count(*) FROM workflow_task_attempts WHERE location_id=:id"
                                ),
                                {"id": e.loc},
                            )
                            == 2
                        )
                    checks.append(
                        "manager correction retains cancelled attempt; later departure reuses task; staff acknowledge/clean/explicit ready completes"
                    )
                    e.episode = uuid4()
                    pulse(e, "POSITIVE", False)
                    staff.wait(
                        "document.querySelector('.review-card')?.innerText.includes('possible arrival')"
                    )
                    click(staff, "Dismiss suggestion")
                    staff.wait("!document.querySelector('.review-card')")
                    state(staff, e.table, "AVAILABLE")
                    checks.append("dismissal creates no task or operational transition")
                    assert not staff.evaluate(
                        "!!document.querySelector('.manager-correction') || Array.from(document.querySelectorAll('button')).some(b=>b.textContent==='Out of service')"
                    )
                    b_loc = seed["organizations"]["b"]["locations"][0]
                    for browser, loc in [(owner, b_loc), (other, e.loc)]:
                        for suffix in [
                            "workflow",
                            "analytics?from=2026-11-01&to=2026-11-02",
                            "analytics.csv?from=2026-11-01&to=2026-11-02",
                        ]:
                            assert (
                                browser.evaluate(
                                    f"fetch('/api/v1/locations/{loc}/{suffix}').then(r=>r.status)"
                                )
                                == 404
                            )
                    checks.append(
                        "both restaurant directions denied for workflow/JSON/CSV; staff lacks manager controls"
                    )
                    staff.send("Network.enable")
                    staff.send(
                        "Network.emulateNetworkConditions",
                        {
                            "offline": True,
                            "latency": 0,
                            "downloadThroughput": 0,
                            "uploadThroughput": 0,
                        },
                    )
                    staff.wait(
                        "document.body.innerText.includes('STALE — updates interrupted')"
                    )
                    assert staff.evaluate(
                        "Array.from(document.querySelectorAll('.table-details button')).every(b=>b.disabled)"
                    )
                    staff.send(
                        "Network.emulateNetworkConditions",
                        {
                            "offline": False,
                            "latency": 0,
                            "downloadThroughput": -1,
                            "uploadThroughput": -1,
                        },
                    )
                    staff.wait("document.body.innerText.includes('Updates connected')")
                    checks.append(
                        "offline browser disables actions, reconnects and reloads authoritative snapshot"
                    )
                    staff.send(
                        "Emulation.setDeviceMetricsOverride",
                        {
                            "width": 390,
                            "height": 844,
                            "deviceScaleFactor": 1,
                            "mobile": True,
                        },
                    )
                    assert staff.evaluate(
                        "document.documentElement.scrollWidth<=innerWidth"
                    )
                    staff.evaluate("document.querySelector('.floor-table').focus()")
                    assert staff.evaluate(
                        "document.activeElement===document.querySelector('.floor-table')"
                    )
                    screenshot = staff.send(
                        "Page.captureScreenshot",
                        {"format": "png", "captureBeyondViewport": False},
                    )
                    (folder / "workflow-mobile.png").write_bytes(
                        base64.b64decode(screenshot["data"])
                    )
                    checks.append(
                        "390px floor and review layout fits; keyboard focus and human-readable labels"
                    )
                    owner.send(
                        "Page.navigate", {"url": f"{ORIGIN}/analytics?location={e.loc}"}
                    )
                    owner.wait("!!document.querySelector('.report-table tbody tr')")
                    assert owner.evaluate(
                        "document.body.innerText.includes('DEMO') && document.body.innerText.includes('UTC')"
                    )
                    download = folder / "downloads"
                    download.mkdir()
                    owner.send(
                        "Browser.setDownloadBehavior",
                        {"behavior": "allow", "downloadPath": str(download)},
                    )
                    # A proxy can finish a chunked response without its original
                    # Content-Length. Never offer a partial or unframed CSV as complete.
                    for mode in ["truncated", "missing_length"]:
                        owner.evaluate(
                            """window.savedFetch=window.fetch;window.fetch=async(...args)=>{
                              const r=await window.savedFetch(...args);
                              if(String(args[0]).includes('/analytics.csv?')&&r.ok){
                                window.fetch=window.savedFetch;
                                const body=await r.arrayBuffer(),headers=new Headers(r.headers);
                                headers.delete('content-length');
                                if("""
                            + json.dumps(mode)
                            + """==='missing_length')headers.delete('x-report-bytes');
                                return new Response("""
                            + json.dumps(mode)
                            + """==='truncated'?body.slice(0,body.byteLength-1):body,{status:200,headers});
                              }return r}
                            """
                        )
                        click(owner, "Download CSV")
                        owner.wait(
                            "document.body.innerText.includes('Export incomplete.')"
                        )
                        assert not list(download.iterdir())
                    click(owner, "Download CSV")
                    for _ in range(60):
                        files = list(download.glob("*.csv"))
                        if files:
                            break
                        time.sleep(0.1)
                    assert files and b"report_metadata" in files[0].read_bytes()
                    owner.send(
                        "Emulation.setDeviceMetricsOverride",
                        {
                            "width": 390,
                            "height": 844,
                            "deviceScaleFactor": 1,
                            "mobile": True,
                        },
                    )
                    assert owner.evaluate(
                        "document.documentElement.scrollWidth<=innerWidth"
                    )
                    assert owner.evaluate(
                        "Array.from(document.querySelectorAll('.inline-form input,.inline-form select,.inline-form button')).every(el=>{const a=el.getBoundingClientRect(),b=el.closest('.config-card').getBoundingClientRect();return a.left>=b.left && a.right<=b.right})"
                    )
                    screenshot = owner.send(
                        "Page.captureScreenshot",
                        {"format": "png", "captureBeyondViewport": False},
                    )
                    (folder / "analytics-mobile.png").write_bytes(
                        base64.b64decode(screenshot["data"])
                    )
                    checks.append(
                        "real report UI rejects truncated/unframed CSV without saving; complete proxy download and mobile layout pass"
                    )
                    other_location = seed["organizations"]["a"]["locations"][0]
                    owner.evaluate(
                        f"(()=>{{const s=document.querySelector('.inline-form select');s.value={json.dumps(other_location)};s.dispatchEvent(new Event('change',{{bubbles:true}}))}})()"
                    )
                    owner.wait(
                        f"new URLSearchParams(location.search).get('location')==={json.dumps(other_location)} && !!document.querySelector('.report-table tbody tr')"
                    )
                    assert not owner.evaluate(
                        "document.querySelector('.report-table').innerText.includes('Transport fixture table')"
                    )
                    checks.append(
                        "report location switch clears previous table data and loads only the newly authorized scope"
                    )
                    # Reproduce the founder's original DEMO A02 flow as actual
                    # clicks, including an unchanged arrival on an occupied table.
                    demo = demo_layout["locations"]["a"]
                    demo_table = demo["table_ids"][1]
                    owner.send("Emulation.clearDeviceMetricsOverride", {})
                    owner.send(
                        "Page.navigate",
                        {"url": f"{ORIGIN}/dashboard?location={demo['id']}"},
                    )
                    owner.wait("document.body.innerText.includes('Updates connected')")
                    select(owner, demo_table)
                    owner.evaluate(
                        "document.querySelector('.simulation-controls').open=true"
                    )
                    click(owner, "Guests arrive")
                    click(owner, "Guests leave")
                    state(owner, demo_table, "RESET_PENDING")
                    task_scope = "Array.from(document.querySelectorAll('.cleaning-task')).find(el=>el.querySelector('h3').textContent.startsWith('A02 '))"
                    click(owner, "Acknowledge", task_scope)
                    click(
                        owner,
                        "Start cleaning",
                        "document.querySelector('.table-details')",
                    )
                    state(owner, demo_table, "CLEANING")
                    click(owner, "I checked this table — mark ready")
                    state(owner, demo_table, "AVAILABLE")
                    owner.send(
                        "Page.navigate",
                        {"url": f"{ORIGIN}/analytics?location={demo['id']}"},
                    )
                    owner.wait(
                        "!!document.querySelector('.report-table tbody tr') && document.querySelectorAll('.inline-form select')[1].options.length>1"
                    )
                    owner.evaluate(
                        f"(()=>{{const s=document.querySelectorAll('.inline-form select')[1];s.value={json.dumps(demo_table)};s.dispatchEvent(new Event('change',{{bubbles:true}}))}})()"
                    )
                    owner.wait(
                        "Array.from(document.querySelectorAll('.report-table tbody th')).length>0 && Array.from(document.querySelectorAll('.report-table tbody th')).every(el=>el.textContent==='A02')"
                    )
                    for label in ["Completed occupied sessions", "Completed resets"]:
                        assert (
                            owner.evaluate(
                                f"Array.from(document.querySelectorAll('.report-summary article')).find(el=>el.querySelector('span').textContent==={json.dumps(label)}).querySelector('strong').textContent"
                            )
                            == "1"
                        )
                    assert owner.evaluate(
                        "Array.from(document.querySelectorAll('.report-summary article')).find(el=>el.querySelector('span').textContent==='Cleaning duration').querySelector('strong').textContent.endsWith(' min')"
                    )
                    scenario_download = folder / "scenario-downloads"
                    scenario_download.mkdir()
                    owner.send(
                        "Browser.setDownloadBehavior",
                        {"behavior": "allow", "downloadPath": str(scenario_download)},
                    )
                    click(owner, "Download CSV")
                    for _ in range(60):
                        files = list(scenario_download.glob("*.csv"))
                        if files:
                            break
                        time.sleep(0.1)
                    assert files
                    rows = list(
                        csv.DictReader(
                            io.StringIO(files[0].read_text(encoding="utf-8-sig"))
                        )
                    )
                    assert (
                        rows[0]["report_completed_resets"]
                        == rows[0]["report_completed_occupied_sessions"]
                        == "1"
                    )
                    assert all(row["table_label"] == "A02" for row in rows[1:])
                    scenario_screenshot = owner.send(
                        "Page.captureScreenshot",
                        {"format": "png", "captureBeyondViewport": False},
                    )
                    (folder / "scenario-analytics.png").write_bytes(
                        base64.b64decode(scenario_screenshot["data"])
                    )
                    checks.append(
                        "actual DEMO A02 arrival/departure/acknowledge/clean/ready clicks produce one visit and reset, numeric cleaning duration and matching CSV"
                    )
                    for browser in [owner, staff, other]:
                        assert browser.errors == 0
                        end_session(browser)
                    checks.append(
                        "no browser JavaScript exceptions; automation sessions revoked"
                    )
            finally:
                if container:
                    info = json.loads(
                        subprocess.check_output(
                            ["docker", "inspect", container], text=True
                        )
                    )[0]
                    assert (
                        info["Name"].startswith("/restaurant-phase7-browser-")
                        and info["Config"]["Labels"]["restaurant.phase7-test"] == "true"
                        and not info["Mounts"]
                    )
                    subprocess.run(
                        ["docker", "stop", container], check=True, capture_output=True
                    )
                elif web:
                    web.terminate()
                    web.wait(timeout=15)
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        generator.close()
        patch.undo()
        for actor in clients.values():
            actor.client.close()
        suite.runtime.dispose()
        admin.dispose()
    assert max(update_latencies) < 5, (
        "Synthetic receipt-to-visible update exceeded the local five-second target"
    )
    report = {
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "checks": checks,
        "isolated_database": db_name,
        "business_database_untouched": True,
        "constructed_evidence_only": True,
        "web_runtime": image or "host production build",
        "receipt_to_visible_seconds": update_latencies,
        "human_click_to_task_seconds": task_latencies,
        "private_artifacts": str(folder.relative_to(ROOT)),
    }
    (ROOT / ".secrets/phase7-implementation/browser-results.json").write_text(
        json.dumps(report, indent=2)
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
