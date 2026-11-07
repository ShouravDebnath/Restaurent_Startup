"""Headless checks with installed Microsoft Edge; uses synthetic local accounts only."""

import base64
import json
import socket
import subprocess
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


class Browser:
    def __init__(self, socket_):
        self.socket = socket_
        self.sequence = 0
        self.errors = 0

    def send(self, method, params=None):
        self.sequence += 1
        self.socket.send(
            json.dumps({"id": self.sequence, "method": method, "params": params or {}})
        )
        while True:
            result = json.loads(self.socket.recv(timeout=15))
            if result.get("method") == "Runtime.exceptionThrown":
                self.errors += 1
            if result.get("id") == self.sequence:
                if "error" in result:
                    raise RuntimeError(
                        "Browser protocol command failed; private details omitted"
                    )
                return result.get("result", {})

    def evaluate(self, expression):
        result = self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in result:
            raise RuntimeError("Browser evaluation failed; private details omitted")
        return result.get("result", {}).get("value")

    def wait(self, expression):
        for _ in range(60):
            if self.evaluate(expression):
                return
            time.sleep(0.2)
        raise RuntimeError("Browser condition timed out; no credentials printed")

    def fill(self, selector, value):
        # Trusted keyboard input drives React's state, without logging the supplied text.
        self.evaluate(f"document.querySelector({json.dumps(selector)}).focus()")
        self.send("Input.insertText", {"text": value})

    def login(self, account):
        self.wait(
            "location.pathname === '/sign-in' && !!document.querySelector('input[name=email]')"
        )
        self.fill("input[name=email]", account["email"])
        self.fill("input[name=password]", account["password"])
        self.evaluate("document.querySelector('form').requestSubmit()")
        self.wait(
            "location.pathname === '/settings' && !!document.querySelector('.switcher select')"
        )


def main():
    if not EDGE.is_file():
        raise RuntimeError(
            "Installed Microsoft Edge was not found; no browser installed"
        )
    seed = json.loads(
        (ROOT / ".secrets/phase2-demo-credentials.json").read_text(encoding="utf-8")
    )
    assert seed["namespace"] == "local-phase2"
    folder = ROOT / ".cache" / ("phase2-browser-" + uuid4().hex[:10])
    folder.mkdir(parents=True)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [
            str(EDGE),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            f"--remote-debugging-port={port}",
            "--user-data-dir=" + str(folder / "profile"),
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    connection = None
    contexts = ExitStack()
    try:
        for _ in range(50):
            try:
                with urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as response:
                    pages = json.load(response)
                page = next((p for p in pages if p.get("type") == "page"), None)
                if page:
                    break
            except (URLError, OSError):
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("Headless browser did not become ready")
        connection = contexts.enter_context(
            connect(page["webSocketDebuggerUrl"], proxy=None, max_size=10_000_000)
        )
        browser = Browser(connection)
        browser.send("Runtime.enable")
        browser.send("Page.enable")
        browser.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False},
        )
        browser.send("Page.navigate", {"url": "http://localhost:3000/settings"})
        browser.login(seed["accounts"]["a_owner"])
        browser.wait("!document.body.innerText.includes('Loading settings')")
        assert (
            browser.evaluate(
                "document.querySelector('.switcher select').options.length"
            )
            == 1
        )
        assert (
            browser.evaluate(
                "document.querySelector('.switcher select').selectedOptions[0].textContent"
            )
            == "Synthetic Restaurant A"
        )
        permitted_locations = browser.evaluate(
            "Array.from(document.querySelectorAll('.switcher select')[1].options).map(o=>o.value)"
        )
        assert set(seed["organizations"]["a"]["locations"]).issubset(permitted_locations)
        marker = "Browser check " + uuid4().hex[:8]
        browser.evaluate(
            "Array.from(document.querySelectorAll('summary')).find(e=>e.textContent==='Add a table').parentElement.open=true"
        )
        browser.fill('input[aria-label="New table label"]', marker)
        browser.evaluate(
            "document.querySelector('input[aria-label=\"New table label\"]').closest('form').requestSubmit()"
        )
        browser.wait(
            "!!document.querySelector('.notice') && document.querySelector('input[aria-label=\"New table label\"]').value === ''"
        )
        browser.wait(
            f"Array.from(document.querySelectorAll('input')).some(e=>e.value==={json.dumps(marker)})"
        )
        screenshot = browser.send("Page.captureScreenshot", {"format": "png"})
        (folder / "settings-desktop.png").write_bytes(
            base64.b64decode(screenshot["data"])
        )
        browser.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
        )
        assert browser.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        screenshot = browser.send("Page.captureScreenshot", {"format": "png"})
        (folder / "settings-mobile.png").write_bytes(
            base64.b64decode(screenshot["data"])
        )
        browser.evaluate(
            "Array.from(document.querySelectorAll('button')).find(e=>e.textContent==='Sign out').click()"
        )
        browser.login(seed["accounts"]["b_owner"])
        browser.wait("!document.body.innerText.includes('Loading settings')")
        assert (
            browser.evaluate(
                "document.querySelector('.switcher select').selectedOptions[0].textContent"
            )
            == "Synthetic Restaurant B"
        )
        assert not browser.evaluate(
            f"Array.from(document.querySelectorAll('input')).some(e=>e.value==={json.dumps(marker)})"
        )
        foreign = seed["organizations"]["a"]["locations"][0]
        assert (
            browser.evaluate(
                f"fetch('/api/v1/locations/{foreign}/tables').then(r=>r.status)"
            )
            == 404
        )
        browser.evaluate(
            "Array.from(document.querySelectorAll('button')).find(e=>e.textContent==='Sign out').click()"
        )
        browser.wait("location.pathname === '/sign-in'")
        assert browser.errors == 0
        report = {
            "verified_at_utc": datetime.now(UTC).isoformat(),
            "browser": "installed Microsoft Edge",
            "checks": [
                "unauthenticated redirect",
                "A login and permitted selectors",
                "table creation form",
                "desktop and mobile layout",
                "logout and B login",
                "A table hidden from B",
                "cross-restaurant fetch rejected",
                "B logout",
            ],
            "javascript_exceptions": browser.errors,
            "screenshots": str(folder.relative_to(ROOT)),
        }
        (ROOT / ".secrets/phase2-browser-verification.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(
            "Browser verification passed: 8 groups; no JavaScript exceptions. Screenshots: "
            + str(folder.relative_to(ROOT))
        )
    finally:
        if connection is not None:
            try:
                connection.send(json.dumps({"id": 100000, "method": "Browser.close"}))
            finally:
                contexts.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
