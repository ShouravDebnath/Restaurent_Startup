"""Real RF-DETR + actual generated MP4 + Edge; SIMULATED human authority.

No business database, credentials or person footage. This is an integration
check, not restaurant accuracy or live-cloud authentication verification.
"""

import argparse
import base64
import json
import secrets
import socket
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import uvicorn
from restaurant_edge.companion import create_companion
from restaurant_edge.detectors.onnx_detector import ModelCatalog
from restaurant_edge.source_config import SourceDefinition, SourceRegistry
from restaurant_edge.video_sources import synthetic_mp4
from verify_phase3_browser import open_browser
from verify_phase5_browser import SyntheticAuthority

ROOT = Path(__file__).resolve().parents[1]


class ShadowAuthority(SyntheticAuthority):
    def request(self, method, path, body=None):
        if path.endswith('/dashboard'):
            if method != 'GET' or body is not None:
                raise AssertionError('Only passive simulated dashboard reads')
            self.paths.append((method, path))
            s = self.source
            return {'location': {'id': str(s.location_id), 'organization_id': str(s.organization_id)},
                    'tables_truncated': False, 'tables': [{'id': str(self.table),
                    'organization_id': str(s.organization_id), 'location_id': str(s.location_id),
                    'current_state': 'CLEANING', 'state_source': 'manual', 'operational_revision': 1,
                    'state_since': '2026-11-08T00:00:00+00:00'}]}
        return super().request(method, path, body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True)
    args = parser.parse_args()
    folder = ROOT / '.cache' / ('phase5-rfdetr-browser-' + uuid4().hex)
    folder.mkdir(parents=True)
    video = synthetic_mp4(folder / 'generated-only.mp4', seconds=5)
    source = SourceDefinition(reference='geometric', organization_id=uuid4(), location_id=uuid4(),
                              camera_id=uuid4(), kind='mp4', synthetic=True, authorized=True, file=str(video))
    password = secrets.token_urlsafe(24)
    authority = ShadowAuthority(source, password)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    app = create_companion(SourceRegistry([source], [folder]), port=port,
        cloud_factory=lambda: authority, ai_debug=True, analysis_root=folder / 'profiles',
        model_catalog=ModelCatalog.load(args.catalog))
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
            browser.wait('window.Phase5LabReady === true')
            browser.fill('input[name=email]', 'synthetic@example.invalid')
            browser.fill('input[name=password]', password)
            browser.evaluate("document.querySelector('#login').requestSubmit()")
            browser.wait("!document.querySelector('#workspace').hidden && !!document.querySelector('#camera').value")
            assert browser.evaluate("document.querySelector('#model').value === 'rfdetr_nano' && document.querySelector('#analyze').disabled")
            checks.append('approved RF model selected; initial saved-profile gate enforced')
            browser.evaluate("document.querySelector('#preview').click()")
            browser.wait("picture !== null && document.querySelector('#health').textContent.includes('ONLINE')")
            browser.evaluate("document.querySelector('#visibility').click();document.querySelector('#save').click()")
            browser.wait("revision === 1 && !document.querySelector('#analyze').disabled")
            browser.evaluate("document.querySelector('#analyze').click()")
            browser.wait("document.querySelector('#analysis-status').textContent.includes('RUNNING') && document.querySelector('#metrics').textContent.includes('Measured latest processing')")
            assert browser.evaluate("document.querySelector('#tables').textContent.includes('CLEANING')")
            analysis = app.state.companion.owner.analysis
            assert analysis.latest and analysis.metrics['inference_ms'] > 0
            checks.append('actual MP4 reader and real pretrained ONNX worker update live metrics')
            checks.append('actual model outputs preserve simulated human-confirmed cleaning state')
            browser.send('Page.navigate', {'url': url})
            browser.wait("window.Phase5LabReady === true && !document.querySelector('#workspace').hidden && !!document.querySelector('#camera').value")
            browser.evaluate("document.querySelector('#preview').click()")
            browser.wait("picture !== null && revision === 1 && profile.model === 'rfdetr_nano'")
            browser.evaluate("document.querySelector('#analyze').click()")
            browser.wait("document.querySelector('#metrics').textContent.includes('Measured latest processing')")
            checks.append('refresh restores model/seating revision; explicit restart works')
            browser.send('Emulation.setDeviceMetricsOverride', {
                'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
            assert browser.evaluate('document.documentElement.scrollWidth <= innerWidth')
            (folder / 'real-model-synthetic-mobile.png').write_bytes(base64.b64decode(
                browser.send('Page.captureScreenshot', {'format': 'png'})['data']))
            checks.append('390px live-model lab layout and local screenshot')
            analysis = app.state.companion.owner.analysis
            authority.allowed = False
            app.state.companion.owner.next_check = 0
            browser.wait('picture === null && !active')
            assert app.state.companion.active is None and analysis.process is None
            assert browser.errors == 0
            checks.append('revocation stops actual model/reader and clears preview; zero browser exceptions')
        assert all(method == 'GET' for method, _ in authority.paths)
        record = {'checked_at_utc': datetime.now(UTC).isoformat(), 'checks': checks,
                  'authority': 'SIMULATED', 'video': 'generated geometric MP4; no people',
                  'pretrained_inference': True, 'model': 'rfdetr_nano', 'real_person_footage': False,
                  'business_database_mutations': False, 'folder': str(folder.relative_to(ROOT))}
        (folder / 'verification.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        target = ROOT / '.secrets/phase5-rfdetr-review' / ('browser-verification-' + uuid4().hex + '.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as handle:
            json.dump(record, handle, indent=2)
        print('RF-DETR browser:', len(checks), 'groups passed; genuine model, generated MP4, simulated authority.')
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == '__main__':
    main()
