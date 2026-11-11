"""Simulated observations, actual durable queue and deterministic lease boundaries."""

import hashlib
import json
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_analysis_domain import configuration, feed, table

from restaurant_edge.device_client import (
    DeviceRevoked,
    DeviceUnavailable,
    LeaseGuard,
    ProcessingLease,
    Synchronizer,
)
from restaurant_edge.device_runner import DeviceRunner
from restaurant_edge.durable_engine import DurableEngine
from restaurant_edge.outbox import Outbox, OutboxError
from restaurant_edge.state_engine import StateEngine


def test_processing_lease_deadline_clock_and_restart():
    now = [10.0]
    lease = ProcessingLease(lambda: now[0])
    device = str(uuid4())
    assert not lease.active()
    assert lease.renew({'lease_seconds': 3600, 'configuration': {'device_id': device, 'processing_enabled': True}}, device)
    now[0] = 3609.999
    assert lease.active()
    now[0] = 3610
    assert not lease.active()
    now[0] = 100
    assert not lease.active()
    assert not ProcessingLease().active()


@pytest.mark.parametrize('seconds', [3601, -1, True, '3600'])
def test_invalid_lease_cannot_extend_processing(seconds):
    lease = ProcessingLease()
    device = str(uuid4())
    assert not lease.renew({'lease_seconds': seconds, 'configuration': {'device_id': device, 'processing_enabled': True}}, device)
    assert not lease.active()


def durable(tmp_path, max_pending=100):
    config = configuration()
    device = str(uuid4())
    assignment = str(uuid4())
    cloud = {'bindings': [{'id':str(uuid4()), 'table_id':str(config.regions[0].table_id),
        'assignment_id':assignment,'epoch':str(uuid4()),'zone_revision':7}],
        'assignments': [{'id':assignment,'profile_revision':1,'profile_sha256':'a'*64,
                        'model_sha256':'b'*64,'policy_revision':1}]}
    box = Outbox(tmp_path/'outbox.sqlite3', device_id=device, organization_id=config.organization_id,
                 location_id=config.location_id, max_pending=max_pending)
    engine = DurableEngine(StateEngine(config), box, cloud)
    return engine, box


def test_expiry_stops_processing_while_sender_is_blocked():
    now = [0.0]
    lease = ProcessingLease(lambda: now[0])
    device = str(uuid4())
    assert lease.renew({'lease_seconds':1,'configuration':{'device_id':device,'processing_enabled':True}},device)
    stopped = threading.Event()
    guard = LeaseGuard(lease, stopped.set)
    guard.start()
    try:
        now[0] = 1.01
        assert stopped.wait(timeout=1)
        assert not lease.active()
    finally:
        guard.close()


def test_health_recomputes_age_instead_of_reusing_old_fast_inference_metric(monkeypatch):
    runner = DeviceRunner.__new__(DeviceRunner)
    runner.capture = SimpleNamespace(health=lambda:{'status':'ONLINE'})
    runner.box = SimpleNamespace(pending_count=0)
    runner.analysis = SimpleNamespace(status='RUNNING',metrics={'frame_age_ms':10},
        latest={'received_monotonic':100},config=SimpleNamespace(settings=SimpleNamespace(result_max_age=2)))
    monkeypatch.setattr('restaurant_edge.device_runner.time.monotonic',lambda:105)
    assert runner.health()['inference']=='DEGRADED'
    assert runner.health()['frame_age_ms']==5000


def test_transition_saved_at_creation_and_before_publication(tmp_path):
    engine, box = durable(tmp_path)
    try:
        feed(engine, 'POSITIVE', 0, 10)
        assert table(engine).state == 'OCCUPIED'
        pending = box.pending()
        assert len(pending) == 1 and pending[0][0]['state'] == 'OCCUPIED'
        assert pending[0][0]['reason'] == 'STABLE_PERSON'
        assert box.checkpoint()['tables'][next(iter(engine.tables))]['state'] == 'OCCUPIED'
    finally:
        box.close()


def test_failed_commit_keeps_previous_engine_visible(tmp_path):
    engine, box = durable(tmp_path, max_pending=0)
    try:
        feed(engine, 'POSITIVE', 0, 9.5)
        with pytest.raises(OutboxError):
            feed(engine, 'POSITIVE', 10, 10)
        assert table(engine).state == 'UNKNOWN'
        assert box.pending_count == 0
        assert box.checkpoint()['tables'][next(iter(engine.tables))]['state'] == 'UNKNOWN'
    finally:
        box.close()


def test_retry_fresh_signature_same_events_and_revocation_retention(tmp_path):
    engine, box = durable(tmp_path)
    now = [100.0]

    class Offline:
        def post(self, path, value):
            raise DeviceUnavailable('Simulated outage')

    class Revoked:
        def post(self, path, value):
            raise DeviceRevoked('Simulated credential revocation')

    try:
        feed(engine, 'POSITIVE', 0, 10)
        original = box.pending()[0][0]
        sync = Synchronizer(box, Offline(), clock=lambda: now[0], jitter=lambda *_:1)
        assert not sync.tick()
        assert box.pending(101) == []
        now[0] = 103
        with pytest.raises(DeviceRevoked):
            Synchronizer(box, Revoked(), clock=lambda: now[0]).tick()
        assert box.pending(now[0])[0][0] == original
        assert box.pending_count == 1
    finally:
        box.close()


def test_ready_at_heartbeat_boundary_publishes_running_before_short_run_ends(tmp_path, monkeypatch):
    """Simulated delayed readiness, real runner/lease/outbox; no model accuracy claim."""
    from restaurant_edge import device_runner as module

    config = configuration()
    digest = hashlib.sha256(json.dumps(config.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
    assignment = str(uuid4())
    cloud = {'device_id':str(uuid4()), 'organization_id':str(config.organization_id),
        'location_id':str(config.location_id), 'purpose':'AI_SHADOW', 'processing_enabled':True,
        'assignments':[{'id':assignment, 'camera_id':str(config.camera_id), 'enabled':True,
            'profile_sha256':digest, 'profile_revision':1, 'model_sha256':'b'*64}],
        'bindings':[{'id':str(uuid4()), 'assignment_id':assignment, 'enabled':True,
            'table_id':str(config.regions[0].table_id), 'epoch':str(uuid4()), 'zone_revision':7}],
        'manual':[]}
    ticks, sent = [0], []
    def clock():
        return ticks[0]/10  # Exact deterministic heartbeat boundary.

    class Client:
        def post(self, path, value):
            assert path == '/v1/edge/heartbeat'
            sent.append((clock(),value['inference']))
            return {'lease_seconds':3600,'configuration':cloud}

        def close(self):
            pass

    class Capture:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def health(self):
            return {'status':'ONLINE'}

    class Analysis:
        def __init__(self, *args):
            self.engine, self.config = StateEngine(config), config
            self.status, self.metrics, self.latest = 'LOADING', {}, None

        def start(self):
            pass

        def tick(self):
            if clock() >= 15:
                self.status, self.metrics = 'RUNNING', {'total_ms':1}
                self.latest = {'received_monotonic':clock()}

        def stop(self):
            self.status = 'STOPPED'

    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=clock,sleep=lambda _:ticks.__setitem__(0,ticks[0]+1)))
    record = {'config':config.model_dump(mode='json'),'revision':1,'fingerprint':digest}
    monkeypatch.setattr(module,'ConfigStore',lambda _:SimpleNamespace(load=lambda _:record))
    monkeypatch.setattr(module,'ModelCatalog',SimpleNamespace(load=lambda _:SimpleNamespace(get=lambda _:SimpleNamespace(sha256='b'*64))))
    source = SimpleNamespace(synthetic=True,kind='mp4')
    monkeypatch.setattr(module,'SourceRegistry',SimpleNamespace(load=lambda _:SimpleNamespace(get=lambda *_:source)))
    monkeypatch.setattr(module,'Capture',Capture)
    monkeypatch.setattr(module,'Analysis',Analysis)
    runner = DeviceRunner.__new__(DeviceRunner)
    runner.settings = {'profiles':'unused','models':'unused','sources':'unused',
        'camera_id':str(config.camera_id),'source_reference':'simulated','outbox':tmp_path/'queue.sqlite3'}
    runner.client, runner.lease = Client(), ProcessingLease(clock)
    runner.capture = runner.analysis = runner.box = runner.cloud = runner.guard = None
    runner.online = False
    result = runner.run(seconds=22)
    assert result['analysis_status'] == 'RUNNING'
    assert any(state=='RUNNING' and when<=16 for when,state in sent), sent
    assert sent[-1][1] == 'STOPPED'
    # State-change publication must not become an unbounded heartbeat loop.
    assert len(sent) <= 5
