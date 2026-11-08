"""Real Edge + geometric MP4, SIMULATED authority, no model weights or live DB writes.

Private profiles/video/screenshots remain in .cache. This checks the lab UI and
closed model gate; it does not evaluate person detection or real authentication.
"""

import base64
import json
import secrets
import socket
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import uvicorn
from restaurant_edge.cloud_client import CloudFailure
from restaurant_edge.companion import create_companion
from restaurant_edge.source_config import SourceDefinition, SourceRegistry
from restaurant_edge.video_sources import synthetic_mp4
from verify_phase3_browser import open_browser

ROOT = Path(__file__).resolve().parents[1]


class SyntheticAuthority:
    def __init__(self, source, password):
        self.source, self.password = source, password
        self.user, self.table, self.zone = uuid4(), uuid4(), uuid4()
        self.allowed, self.deadline = True, datetime.now(UTC) + timedelta(minutes=5)
        self.paths = []

    def login(self, email, password):
        if email != 'synthetic@example.invalid' or not secrets.compare_digest(password, self.password):
            raise CloudFailure(401)
        return self.request('GET', '/v1/me')

    def request(self, method, path, body=None):
        self.paths.append((method, path))
        if method != 'GET' or body is not None:
            raise CloudFailure(403)
        s = self.source
        location = {'id': str(s.location_id), 'organization_id': str(s.organization_id), 'name': 'Synthetic lab',
                    'time_zone': 'Asia/Dhaka'}
        camera = {'id': str(s.camera_id), 'organization_id': str(s.organization_id),
                  'source_reference': s.reference, 'label': 'Synthetic geometric replay'}
        if path == '/v1/me':
            return {'id': str(self.user), 'display_name': 'Synthetic manager', 'access': [{
                'role': 'manager', 'organization': {'id': str(s.organization_id), 'name': 'SIMULATED AUTHORITY'},
                'locations': [location]}]}
        if path.endswith('/preview-authorization'):
            if not self.allowed:
                raise CloudFailure(403)
            return {**camera, 'camera_id': str(s.camera_id), 'location_id': str(s.location_id),
                    'expires_at': self.deadline.isoformat(), 'session_deadline': self.deadline.isoformat(),
                    'server_time': datetime.now(UTC).isoformat()}
        if path.endswith('/table-zones'):
            return [{'id': str(self.zone), 'table_id': str(self.table), 'camera_id': str(s.camera_id),
                     'organization_id': str(s.organization_id), 'location_id': str(s.location_id),
                     'revision': 7, 'polygon': [[.1, .1], [.8, .1], [.8, .8], [.1, .8]],
                     'source_width': 640, 'source_height': 360,
                     'view_metadata': {'format_version': 1, 'rotation': 0, 'mirrored': False}}]
        if path.endswith('/cameras'):
            return [camera]
        if path.endswith('/tables'):
            return [{'id': str(self.table), 'label': 'SYNTHETIC T01'}]
        if path.endswith('/' + str(s.camera_id)):
            return camera
        raise CloudFailure(404)

    def close(self):
        pass


def main():
    folder = ROOT / '.cache' / ('phase5-browser-' + uuid4().hex)
    folder.mkdir(parents=True)
    video = synthetic_mp4(folder / 'geometric.mp4', seconds=5)
    source = SourceDefinition(reference='geometric', organization_id=uuid4(), location_id=uuid4(),
                              camera_id=uuid4(), kind='mp4', synthetic=True, authorized=True, file=str(video))
    password = secrets.token_urlsafe(24)
    authority = SyntheticAuthority(source, password)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    app = create_companion(SourceRegistry([source], [folder]), port=port,
        cloud_factory=lambda: authority, ai_debug=True, analysis_root=folder / 'profiles')
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, access_log=False, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    checks = []
    try:
        end = time.monotonic() + 10
        while not server.started and time.monotonic() < end:
            time.sleep(.1)
        assert server.started
        with open_browser(folder / 'edge') as browser:
            url = f'http://127.0.0.1:{port}/analysis'
            browser.send('Page.navigate', {'url': url})
            browser.wait("window.Phase5LabReady === true && !document.querySelector('#login button').disabled")
            browser.fill('input[name=email]', 'synthetic@example.invalid')
            browser.fill('input[name=password]', password)
            browser.evaluate("document.querySelector('#login').requestSubmit()")
            try:
                browser.wait("!document.querySelector('#workspace').hidden && !!document.querySelector('#camera').value")
            except RuntimeError:
                diagnostics = browser.evaluate("({message:document.querySelector('#message').textContent,hidden:document.querySelector('#workspace').hidden,cameras:document.querySelector('#camera').options.length,ready:document.readyState})")
                diagnostics['browser_exceptions'] = browser.errors
                diagnostics['metadata_paths'] = authority.paths
                (folder / 'setup-diagnostics.json').write_text(json.dumps(diagnostics), encoding='utf-8')
                raise
            assert browser.evaluate("document.querySelector('#analyze').disabled")
            checks.append('sign-in UI and unavailable-model gate (simulated authority)')
            browser.evaluate("document.querySelector('#preview').click()")
            browser.wait("picture !== null && document.querySelector('#health').textContent.includes('ONLINE')")
            browser.evaluate("document.querySelector('#pause').click();document.querySelector('#clear').click()")
            for x, y in [[.05, .05], [.9, .05], [.9, .9], [.05, .9]]:
                browser.evaluate(f"document.querySelector('#x').value={x};document.querySelector('#y').value={y};document.querySelector('#add').click()")
            browser.evaluate("document.querySelector('#visibility').click();document.querySelector('#save').click()")
            browser.wait("document.querySelector('#revision').textContent.startsWith('Saved local seating revision 1')")
            checks.append('actual synthetic MP4 preview and separate seating save')
            browser.send('Page.navigate', {'url': url})
            browser.wait("!document.querySelector('#workspace').hidden && !!document.querySelector('#camera').value")
            browser.evaluate("document.querySelector('#preview').click()")
            browser.wait("picture !== null && revision === 1")
            assert browser.evaluate("draft[0][0] === .05 && draft.length === 4")
            checks.append('browser refresh restores private seating revision without changing cloud polygon')
            gated = browser.evaluate("fetch('/local/v1/analysis/start',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:'{}'}).then(r=>r.status)")
            assert gated == 503
            checks.append('backend independently rejects unapproved model startup')
            browser.send('Emulation.setDeviceMetricsOverride', {
                'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert browser.evaluate("formatTime('2026-11-08T00:00:00+00:00').includes('Asia/Dhaka')")
            screenshot = browser.send('Page.captureScreenshot', {'format': 'png'})['data']
            (folder / 'mobile.png').write_bytes(base64.b64decode(screenshot))
            checks.append('390px responsive layout and numeric keyboard-accessible controls')
            browser.send('Network.emulateNetworkConditions', {'offline': True, 'latency': 0,
                'downloadThroughput': -1, 'uploadThroughput': -1})
            browser.evaluate("window.dispatchEvent(new Event('offline'))")
            assert browser.evaluate('picture === null && !active')
            browser.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 0,
                'downloadThroughput': -1, 'uploadThroughput': -1})
            checks.append('offline clears pictures and requires explicit reconnection')
            browser.evaluate("document.querySelector('#preview').click()")
            browser.wait('picture !== null')
            authority.allowed = False
            app.state.companion.owner.next_check = 0
            browser.wait('picture === null && !active')
            assert app.state.companion.active is None and browser.errors == 0
            checks.append('simulated permission revocation stops actual reader; no browser exceptions')
        assert all(method == 'GET' for method, _ in authority.paths)
        result = {'checked_at_utc': datetime.now(UTC).isoformat(), 'checks': checks,
                  'authority': 'SIMULATED', 'video': 'actual geometric synthetic MP4',
                  'pretrained_inference': False, 'real_person_footage': False,
                  'production_data_mutations': False, 'artifact_folder': str(folder.relative_to(ROOT))}
        (ROOT / '.secrets/phase5-browser-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('Phase 5 browser:', len(checks), 'groups passed; authority simulated, weights held, no AI accuracy claim.')
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == '__main__':
    main()
