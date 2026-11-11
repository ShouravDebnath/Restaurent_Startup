"""Real loopback TLS and SQLite transport, synthetic events; never AI accuracy."""

import importlib.util
import json
import os
import socket
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import uvicorn
from restaurant_edge.device_client import (
    DeviceClient,
    DeviceUnavailable,
    ProcessingLease,
    Synchronizer,
)
from restaurant_edge.outbox import Outbox
from sqlalchemy import text

from .test_edge_transport import (
    configure,
    edge_tenants,  # noqa: F401 -- dependency of the shared edge fixture
    observation,
)
from .test_edge_transport import edge as edge_fixture

edge = edge_fixture  # Register the existing pytest fixture in this module.

ROOT = Path(__file__).resolve().parents[3]


class Listener:
    def __init__(self, app, folder):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            self.port = probe.getsockname()[1]
        self.app, self.folder = app, folder
        self.server = self.thread = None

    def start(self):
        self.server = uvicorn.Server(uvicorn.Config(self.app, host='127.0.0.1', port=self.port,
            ssl_certfile=str(self.folder/'server.pem'), ssl_keyfile=str(self.folder/'server-key.pem'),
            proxy_headers=False, access_log=False, log_level='critical', lifespan='off',
            timeout_keep_alive=1, timeout_graceful_shutdown=2))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic()+10
        while not self.server.started and time.monotonic()<deadline and self.thread.is_alive():
            time.sleep(.01)
        assert self.server.started

    def stop(self):
        if self.server:
            self.server.should_exit = True
            self.thread.join(timeout=10)
            assert not self.thread.is_alive(), 'TLS listener leaked'
            self.server = self.thread = None


@pytest.fixture
def tls(edge):
    folder = ROOT/'.secrets/phase6-implementation'/('tls-test-'+uuid4().hex)
    spec = importlib.util.spec_from_file_location('phase6_tls_issuer', ROOT/'scripts/prepare_phase6_tls.py')
    issuer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(issuer)
    issuer.issue(folder)
    listener = Listener(edge.suite.app, folder)
    listener.start()
    try:
        yield listener
    finally:
        listener.stop()


def test_verified_https_and_wrong_certificate_fail_closed(edge, tls):
    configure(edge)
    client = DeviceClient(f'https://127.0.0.1:{tls.port}', tls.folder/'ca.pem', edge.kid, edge.key)
    try:
        reply = client.post('/v1/edge/heartbeat', {'camera': 'ONLINE', 'inference': 'RUNNING', 'queue_pending': 0})
        assert reply['lease_seconds'] == 3600
        assert reply['configuration']['device_id'] == edge.device
        result = client.post('/v1/edge/events', {'events': [observation(edge).model_dump(mode='json')]})
        assert result['receipts'][0]['disposition'] == 'shadow'
    finally:
        client.close()
    # A certificate is not trusted merely because the listener is on loopback.
    import httpx
    with httpx.Client(trust_env=False, timeout=3) as untrusted, pytest.raises(httpx.ConnectError):
        untrusted.get(f'https://127.0.0.1:{tls.port}/health')


def test_real_tls_offline_recovery(edge, tls, tmp_path):
    """Default 2-second smoke; set PHASE6_OUTAGE_SECONDS=900 for required full outage."""
    duration = int(os.environ.get('PHASE6_OUTAGE_SECONDS', '2'))
    assert 2 <= duration <= 900
    configure(edge)
    client = DeviceClient(f'https://127.0.0.1:{tls.port}', tls.folder/'ca.pem', edge.kid, edge.key)
    lease = ProcessingLease()
    reply = client.post('/v1/edge/heartbeat', {'camera': 'ONLINE', 'inference': 'RUNNING', 'queue_pending': 0})
    assert lease.renew(reply, edge.device)
    path = tmp_path/'outbox.sqlite3'
    scope = {'device_id': edge.device, 'organization_id': edge.org, 'location_id': edge.loc}
    box = Outbox(path, **scope)
    edge.stream = UUID(box.stream_id)

    class LostAck:
        def post(self, path, value):
            client.post(path, value)
            raise DeviceUnavailable('Synthetic lost acknowledgement after the server committed')

    try:
        candidate = observation(edge).model_dump(mode='json')
        for field in ('device_id','organization_id','location_id','sequence','stream_id'):
            candidate.pop(field)
        box.commit([candidate], {'phase': 'before-outage'})
        assert not Synchronizer(box, LostAck(), jitter=lambda *_: 1).tick()
        assert box.pending_count == 1
        tls.stop()  # Actual listener unavailable, not a mocked HTTP response.
        start = time.monotonic()
        sync = Synchronizer(box, client, jitter=lambda *_: 1)
        committed = 1
        next_event = start
        failures = 0
        while time.monotonic()-start < duration:
            if time.monotonic() >= next_event:
                candidate = observation(edge).model_dump(mode='json')
                for field in ('device_id','organization_id','location_id','sequence','stream_id'):
                    candidate.pop(field)
                box.commit([candidate], {'phase':'offline','committed':committed+1})
                committed += 1
                next_event = time.monotonic()+60
            assert lease.active(), 'One-hour running-process lease should cover this outage'
            assert not sync.tick()
            failures = max(failures, sync.failures)
            time.sleep(min(1, max(.01, duration-(time.monotonic()-start))))
        elapsed = time.monotonic()-start
        assert elapsed >= duration
        original_ids = [row[0] for row in box.db.execute('SELECT event_id FROM events ORDER BY sequence')]
        box.close()
        # Reopen the exact queue: IDs/sequence are not reassigned, and no cached
        # processing lease is trusted after restart.
        assert not ProcessingLease().active()
        box = Outbox(path, **scope)
        assert box.pending_count == committed
        tls.start()
        renewed = client.post('/v1/edge/heartbeat', {'camera': 'ONLINE', 'inference': 'RUNNING', 'queue_pending': committed})
        restarted_lease = ProcessingLease()
        assert restarted_lease.renew(renewed, edge.device)
        sync = Synchronizer(box, client)
        # The persisted retry schedule remains honored, bounded to <72 seconds.
        deadline = time.monotonic()+80
        while box.pending_count and time.monotonic()<deadline:
            sync.tick()
            time.sleep(.1)
        assert box.pending_count == 0
        with edge.suite.admin.connect() as db:
            rows = db.execute(text('SELECT event_id,sequence FROM edge_receipts WHERE device_id=:id ORDER BY sequence'),
                              {'id':edge.device}).all()
            assert [str(row.event_id) for row in rows] == original_ids
            assert [row.sequence for row in rows] == list(range(1, committed+1))
            assert db.scalar(text('SELECT count(*) FROM staff_tasks WHERE table_id=:id'), {'id':edge.table}) == 0
        report = {'outage_requested_seconds': duration, 'measured_outage_seconds': round(elapsed,3),
                      'durable_events': committed, 'network_failures': failures, 'original_ids_preserved': True,
                      'duplicate_receipts': 0, 'operational_tasks': 0, 'actual_verified_https': True,
                      'real_camera': False, 'real_person_accuracy_evaluated': False}
        target = ROOT/'.secrets/phase6-implementation'/f'tls-outage-{duration}s.json'
        target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        box.close()
        client.close()
