"""Installed Edge verification of three isolated synthetic dashboard sessions; no installs."""

import base64
import json
import socket
import subprocess
import time
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from verify_phase2_browser import EDGE, Browser
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def open_browser(folder):
    folder = folder.resolve()
    folder.mkdir(parents=True)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen([
        str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
        "--disable-background-networking", f"--remote-debugging-port={port}",
        "--user-data-dir=" + str(folder / "profile"), "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        for _ in range(100):
            try:
                with urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as response:
                    page = next((p for p in json.load(response) if p.get("type") == "page"), None)
                if page:
                    break
            except (URLError, OSError):
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Isolated Edge browser did not start")
        with connect(page["webSocketDebuggerUrl"], proxy=None, max_size=10_000_000) as socket_:
            browser = Browser(socket_)
            browser.send("Runtime.enable"); browser.send("Page.enable")
            browser.send("Page.bringToFront")
            browser.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
            browser.send("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            yield browser
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)


def click(browser, label, scope="document"):
    expression = f"Array.from({scope}.querySelectorAll('button')).find(b=>b.textContent.trim()==={json.dumps(label)})"
    browser.wait(f"!!({expression}) && !({expression}).disabled")
    browser.evaluate(f"({expression}).click()")


def select(browser, identifier):
    selector = f"[data-table-id='{identifier}']"
    browser.wait(f"!!document.querySelector({json.dumps(selector)})")
    browser.evaluate(f"document.querySelector({json.dumps(selector)}).click()")


def state(browser, identifier, expected):
    browser.wait(f"document.querySelector(\"[data-table-id='{identifier}']\")?.dataset.state === {json.dumps(expected)}")


def snapshot(browser, location):
    return browser.evaluate(f"fetch('/api/v1/locations/{location}/dashboard',{{cache:'no-store'}}).then(r=>r.json())")


def controls(browser):
    browser.evaluate("document.querySelector('.simulation-controls').open=true")


def end_session(browser):
    """Revoke automation sessions even if a browser assertion fails."""
    try:
        browser.send("Network.emulateNetworkConditions", {
            "offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        browser.evaluate("""(async()=>{ const r=await fetch('/api/v1/auth/csrf');
            if(r.ok){const s=await r.json();await fetch('/api/v1/auth/session',{
                method:'DELETE',headers:{'X-CSRF-Token':s.csrf_token}})}})()""")
    except (OSError, RuntimeError, TimeoutError, WebSocketException):
        print("Browser-session cleanup could not be verified; private details omitted.")


def main():
    if not EDGE.is_file():
        raise RuntimeError("Installed Edge not available; no software installed")
    seed = json.loads((ROOT / ".secrets/phase2-demo-credentials.json").read_text())
    layout = json.loads((ROOT / ".secrets/phase3-demo-layout.json").read_text())
    assert seed["namespace"] == layout["namespace"] == "local-phase2"
    folder = ROOT / ".cache" / ("phase3-browser-" + uuid4().hex[:10])
    checks = []
    with ExitStack() as stack:
        owner = stack.enter_context(open_browser(folder / "a-owner"))
        other = stack.enter_context(open_browser(folder / "b-owner"))
        staff = stack.enter_context(open_browser(folder / "a-staff"))
        browsers = [(owner, "a_owner", "a"), (other, "b_owner", "b"), (staff, "a_staff", "a")]
        for browser, account, letter in browsers:
            browser.send("Page.navigate", {"url": "http://localhost:3000/dashboard"})
            browser.login(seed["accounts"][account])
            stack.callback(end_session, browser)
            loc = layout["locations"][letter]["id"]
            browser.send("Page.navigate", {"url": f"http://localhost:3000/dashboard?location={loc}"})
            seeded_ids = json.dumps(layout["locations"][letter]["table_ids"])
            browser.wait(f"{seeded_ids}.every(id=>!!document.querySelector('[data-table-id=\"'+id+'\"]')) && document.body.innerText.includes('Updates connected')")
            assert browser.evaluate("document.body.innerText.includes('DEMO — simulated information')")
            assert browser.evaluate("!document.cookie.includes('restaurant_session')")
        checks.append("three isolated logins, protected redirect, six seeded tables plus configured extras, DEMO labels and HttpOnly cookies")
        a, b = layout["locations"]["a"], layout["locations"]["b"]
        assert owner.evaluate(f"fetch('/api/v1/locations/{b['id']}/dashboard').then(r=>r.status)") == 404
        assert other.evaluate(f"fetch('/api/v1/locations/{a['id']}/dashboard').then(r=>r.status)") == 404
        assert not staff.evaluate("!!document.querySelector('.simulation-controls')")
        assert not staff.evaluate("Array.from(document.querySelectorAll('button')).some(b=>b.textContent==='Out of service')")
        checks.append("cross-restaurant requests denied; staff has no scenario or manager controls")
        before_b = snapshot(other, b["id"])["tables"]
        # Complete a new occupancy session on a previously available demo table.
        identifier = a["table_ids"][0]
        select(owner, identifier); controls(owner)
        current = snapshot(owner, a["id"])
        original = next(t for t in current["tables"] if t["id"] == identifier)
        if original["current_state"] != "AVAILABLE":
            raise RuntimeError("Expected the documented initial demo state; seed never resets existing data")
        click(owner, "Source offline", "document.querySelector('.simulation-controls')")
        owner.wait("document.querySelector('.table-details').innerText.includes('Source information is unavailable')")
        failed = next(t for t in snapshot(owner, a["id"])["tables"] if t["id"] == identifier)
        assert failed["current_state"] == "AVAILABLE" and failed["state_since"] == original["state_since"]
        click(owner, "Show vacant", "document.querySelector('.simulation-controls')")
        owner.wait("document.querySelector('.table-details').innerText.includes('Demo observation: vacant')")
        click(owner, "Guests arrive", "document.querySelector('.simulation-controls')")
        state(owner, identifier, "OCCUPIED"); state(staff, identifier, "OCCUPIED")
        occupied_since = next(t for t in snapshot(owner, a["id"])["tables"] if t["id"] == identifier)["state_since"]
        owner.send("Page.addScriptToEvaluateOnNewDocument", {"source":
            "(()=>{const real=Date.now.bind(Date);Date.now=()=>real()+600000})()"})
        owner.send("Page.reload")
        owner.wait("document.body.innerText.includes('Updates connected')")
        state(owner, identifier, "OCCUPIED"); select(owner, identifier); controls(owner)
        assert next(t for t in snapshot(owner, a["id"])["tables"] if t["id"] == identifier)["state_since"] == occupied_since
        time.sleep(3)
        timer = owner.evaluate("document.querySelector('.table-details').innerText.match(/Occupancy timer: ([0-9:]+)/)?.[1]")
        assert timer and int(timer.split(":")[-2]) < 2  # Ten-minute browser skew must not appear.
        checks.append("manual-ready state survives source failure; saved timer survives reload and ten-minute client clock skew")
        click(owner, "Guests leave", "document.querySelector('.simulation-controls')")
        state(staff, identifier, "RESET_PENDING"); select(staff, identifier)
        task_scope = "Array.from(document.querySelectorAll('.cleaning-task')).find(t=>t.querySelector('h3').textContent.startsWith('A01 '))"
        click(staff, "Acknowledge", task_scope)
        staff.wait(f"({task_scope})?.innerText.includes('ACKNOWLEDGED')")
        click(staff, "Start cleaning", "document.querySelector('.table-details')")
        state(owner, identifier, "CLEANING"); state(staff, identifier, "CLEANING")
        click(staff, "I checked this table — mark ready", "document.querySelector('.table-details')")
        state(owner, identifier, "AVAILABLE")
        assert snapshot(other, b["id"])["tables"] == before_b
        checks.append("staff acknowledge/clean/ready persists and updates another A browser; B remains unchanged")
        # A sustained connection must survive the old proxy's ten-second lifetime.
        time.sleep(12)
        assert owner.evaluate("document.body.innerText.includes('Updates connected')")
        checks.append("authorized stream through Next.js remains connected beyond ten seconds")
        for index, expected in [(3, "CLEANING"), (5, "OUT_OF_SERVICE")]:
            identifier = a["table_ids"][index]
            select(owner, identifier); controls(owner)
            before = next(t for t in snapshot(owner, a["id"])["tables"] if t["id"] == identifier)
            click(owner, "Source offline", "document.querySelector('.simulation-controls')")
            owner.wait("document.querySelector('.table-details').innerText.includes('Source information is unavailable')")
            after = next(t for t in snapshot(owner, a["id"])["tables"] if t["id"] == identifier)
            assert after["current_state"] == expected and after["state_since"] == before["state_since"]
        checks.append("cleaning and manager-blocked states retain their timestamps during source failure")
        owner.send("Network.enable")
        owner.send("Network.emulateNetworkConditions", {"offline": True, "latency": 0, "downloadThroughput": 0, "uploadThroughput": 0})
        owner.wait("document.body.innerText.includes('STALE — updates interrupted')")
        assert owner.evaluate("Array.from(document.querySelectorAll('.table-details button')).every(b=>b.disabled)")
        owner.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        owner.wait("document.body.innerText.includes('Updates connected')")
        checks.append("network loss pauses actions, labels stale information, then reconnects with a fresh snapshot")
        owner.send("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        assert owner.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        owner.evaluate("document.querySelector('.floor-table').focus()")
        assert owner.evaluate("document.activeElement === document.querySelector('.floor-table')")
        owner.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13, "text": "\r", "unmodifiedText": "\r"})
        owner.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
        owner.wait("document.querySelector('.floor-table').getAttribute('aria-pressed') === 'true'")
        assert owner.evaluate("Array.from(document.querySelectorAll('.floor-table')).every(b=>b.textContent.trim().length>5)")
        screenshot = owner.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (folder / "mobile.png").write_bytes(base64.b64decode(screenshot["data"]))
        owner.send("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        screenshot = owner.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (folder / "desktop.png").write_bytes(base64.b64decode(screenshot["data"]))
        checks.append("390px mobile layout has no horizontal overflow; table controls work with keyboard and text labels")
        assert owner.evaluate("document.body.innerText.includes('America/New_York')")
        assert other.evaluate("document.body.innerText.includes('Asia/Dhaka')")
        for browser, expected in [(owner, ("1:30:00", "1:30:00")), (other, ("11:30:00", "12:30:00"))]:
            # Client-only history fixtures exercise actual UI formatting across the NY DST fold.
            # Nothing is inserted into the database or presented as recorded server history.
            browser.evaluate("""window.phase3OriginalFetch=window.fetch;
                window.fetch=async(...args)=>{const r=await window.phase3OriginalFetch(...args);
                  if(String(args[0]).includes('/activity?')&&r.ok){const rows=await r.json();
                    rows[0]={...rows[0],occurred_at:'2026-11-01T05:30:00Z'};
                    rows[1]={...rows[1],occurred_at:'2026-11-01T06:30:00Z'};
                    return new Response(JSON.stringify(rows),{status:200,headers:{'Content-Type':'application/json'}})}
                  return r} """)
            click(browser, "Refresh")
            browser.wait("document.querySelector('.activity-panel time')?.dateTime === '2026-11-01T05:30:00Z'")
            times = browser.evaluate("Array.from(document.querySelectorAll('.activity-panel time')).slice(0,2).map(t=>t.textContent)")
            assert all(value in actual for value, actual in zip(expected, times, strict=True))
            browser.evaluate("window.fetch=window.phase3OriginalFetch;delete window.phase3OriginalFetch")
            click(browser, "Refresh")
        checks.append("location time zones and actual history rendering across New York DST fold pass with client-only date fixtures")
        for browser, _, _ in browsers:
            click(browser, "Sign out")
            browser.wait("location.pathname === '/sign-in'")
            assert browser.errors == 0
        checks.append("all three sessions log out; no browser JavaScript exceptions")
    report = {"verified_at_utc": datetime.now(UTC).isoformat(), "checks": checks,
              "screenshots": str(folder.relative_to(ROOT)), "synthetic_records_changed": True}
    (ROOT / ".secrets/phase3-browser-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
