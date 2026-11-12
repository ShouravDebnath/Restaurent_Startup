"""One-camera, separately leased background shadow runner; no human preview server.

The interactive lab retains its original short consent/manual-metadata deadlines.
This runner uses its last scoped manual snapshot only while an in-memory machine
lease is active. Offline results are observations, never current staff authority.
"""

import contextlib
import copy
import hashlib
import json
import time
from pathlib import Path

from restaurant_edge.analysis import Analysis
from restaurant_edge.analysis_config import AnalysisConfig, ConfigStore
from restaurant_edge.capture import Capture
from restaurant_edge.detectors.onnx_detector import ModelCatalog
from restaurant_edge.device_client import (
    DeviceClient,
    DeviceRevoked,
    DeviceUnavailable,
    LeaseGuard,
    ProcessingLease,
    Synchronizer,
)
from restaurant_edge.device_identity import load_identity
from restaurant_edge.durable_engine import DurableEngine
from restaurant_edge.outbox import Outbox
from restaurant_edge.source_config import SourceRegistry


def validate_binding(config, record, cloud, artifact):
    if (str(config.organization_id) != cloud['organization_id'] or str(config.location_id) != cloud['location_id']
            or cloud['purpose'] != 'AI_SHADOW' or not cloud['processing_enabled']):
        raise ValueError('Device processing scope is not approved')
    assignments = [row for row in cloud['assignments'] if row['camera_id']==str(config.camera_id) and row['enabled']]
    if len(assignments) != 1:
        raise ValueError('Exactly one approved camera assignment is required')
    assignment = assignments[0]
    digest = hashlib.sha256(json.dumps(config.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
    if (record['fingerprint'] != digest or assignment['profile_sha256'] != digest
            or assignment['profile_revision'] != record['revision'] or assignment['model_sha256'] != artifact.sha256):
        raise ValueError('Approved model or seating profile has changed')
    bindings = [row for row in cloud['bindings'] if row['assignment_id']==assignment['id'] and row['enabled']]
    if {row['table_id'] for row in bindings} != {str(row.table_id) for row in config.regions}:
        raise ValueError('Every seating region must have an explicit table binding')
    for region in config.regions:
        binding = next(row for row in bindings if row['table_id']==str(region.table_id))
        if binding['zone_revision'] != region.zone_revision:
            raise ValueError('Calibration revision changed')
    return dict(cloud, assignments=[assignment], bindings=bindings)


class DeviceRunner:
    def __init__(self, settings):
        self.settings = settings
        self.identity, key = load_identity(settings['identity'])
        self.client = DeviceClient(settings['api'], settings['ca'], self.identity['key_id'], key)
        self.lease = ProcessingLease()
        self.capture = self.analysis = self.box = None
        self.cloud = None
        self.online = False
        self.guard = None

    def stop_native_on_expiry(self):
        # No SQLite/engine writes from this thread. Stop inference before joining
        # the reader; the owning thread reconciles its durable context afterward.
        if self.analysis:
            with self.analysis.lock:
                if self.analysis.cancel:
                    self.analysis.cancel.set()
                if self.analysis.process and self.analysis.process.is_alive():
                    self.analysis.process.terminate()
        if self.capture:
            self.capture.stop()

    def manual_snapshot(self):
        if not self.lease.active():
            raise DeviceRevoked('Processing lease expired')
        cloud = self.lease.configuration
        return {'location': {'id': cloud['location_id'], 'organization_id': cloud['organization_id']},
                'tables': [dict(row, organization_id=cloud['organization_id'], location_id=cloud['location_id'])
                           for row in copy.deepcopy(cloud['manual'])],
                'tables_truncated': False}

    def health(self):
        source = self.capture.health() if self.capture else {'status': 'UNKNOWN'}
        metrics = self.analysis.metrics if self.analysis else {}
        camera = {'ONLINE': 'ONLINE', 'FILE_ENDED': 'COMPLETE'}.get(source['status'], 'OFFLINE')
        age = (time.monotonic()-self.analysis.latest['received_monotonic']
               if self.analysis and self.analysis.latest else None)
        inference = 'STOPPED'
        if self.analysis and self.analysis.status == 'RUNNING':
            inference = ('RUNNING' if age is not None and 0<=age<=self.analysis.config.settings.result_max_age
                         else 'DEGRADED')
        return {'camera': camera, 'inference': inference, 'queue_pending': self.box.pending_count if self.box else 0,
                    'frame_age_ms': min(3600000,max(0,int(age*1000))) if age is not None else None,
                    'inference_ms': metrics.get('total_ms'), 'memory_bytes': metrics.get('working_set_bytes')}

    def run(self, *, seconds=None):
        """Restart always obtains fresh online authority BEFORE opening capture."""
        result = {}
        try:
            first = self.client.post('/v1/edge/heartbeat', {'camera': 'UNKNOWN', 'inference': 'STOPPED', 'queue_pending': 0})
            device_id = first['configuration']['device_id']
            if not self.lease.renew(first, device_id):
                raise DeviceRevoked('Manager-approved processing is not enabled')
            self.cloud = self.lease.configuration
            scope = (self.cloud['organization_id'], self.cloud['location_id'], self.settings['camera_id'])
            record = ConfigStore(self.settings['profiles']).load(scope)
            if record is None:
                raise ValueError('Save and approve a local seating profile first')
            config = AnalysisConfig.model_validate(record['config'])
            artifact = ModelCatalog.load(self.settings['models']).get(config.model)
            self.cloud = validate_binding(config, record, self.cloud, artifact)
            source = SourceRegistry.load(self.settings['sources']).get(*scope, self.settings['source_reference'])
            if source is None or not source.synthetic or source.kind != 'mp4':
                raise ValueError('Phase 6 machine processing currently permits synthetic MP4 only')
            self.box = Outbox(self.settings['outbox'], device_id=device_id,
                              organization_id=self.cloud['organization_id'], location_id=self.cloud['location_id'])
            sync = Synchronizer(self.box, self.client)
            self.capture = Capture(source, fps=2, loop=False)
            self.analysis = Analysis(self.capture, config, artifact, self.manual_snapshot)
            self.analysis.engine = DurableEngine(self.analysis.engine, self.box, self.cloud)
            self.analysis.engine.config_revision = record['revision']
            self.capture.start()
            self.analysis.start()
            self.guard = LeaseGuard(self.lease, self.stop_native_on_expiry)
            self.guard.start()
            started, next_heartbeat = time.monotonic(), time.monotonic()
            last_heartbeat, last_health = float('-inf'), None
            while seconds is None or time.monotonic()-started < seconds:
                if not self.lease.active():
                    raise DeviceRevoked('Processing lease expired; fresh online authorization required')
                health = self.health()
                health_state = (health['camera'], health['inference'])
                now = time.monotonic()
                # A ready/stale source must not wait a whole 15-second cadence
                # to become visible. Bound transition attempts to one per second.
                if now >= next_heartbeat or (health_state != last_health and now-last_heartbeat >= 1):
                    try:
                        reply = self.client.post('/v1/edge/heartbeat', health)
                        updated = validate_binding(config, record, reply['configuration'], artifact)
                        old_bindings = {(row['id'], row['epoch']) for row in self.cloud['bindings']}
                        if {(row['id'], row['epoch']) for row in updated['bindings']} != old_bindings:
                            raise DeviceRevoked('Binding changed; restart after reviewing the local profile')
                        if not self.lease.renew(reply, device_id):
                            raise DeviceRevoked('Processing permission withdrawn')
                        self.cloud = updated
                        self.analysis.engine.configuration = updated
                        self.online = True
                    except DeviceRevoked:
                        self.lease.revoke()
                        raise
                    except DeviceUnavailable:
                        self.online = False
                    last_heartbeat, last_health = time.monotonic(), health_state
                    next_heartbeat = last_heartbeat+15
                self.analysis.tick()
                sync.tick()
                if self.analysis.status in {'COMPLETED', 'ERROR', 'STOPPED'}:
                    print('Device source stopped; committed metadata remains in the local queue.')
                    if self.analysis.status == 'ERROR':
                        raise RuntimeError('Device analysis failed; native processing stopped and queue preserved')
                    break
                time.sleep(.1)
            result.update(pending=self.box.pending_count, analysis_status=self.analysis.status,
                          shadow_only=True, online=self.online,
                          inference_ms=self.analysis.metrics.get('total_ms'),
                          shadow_states={key: row.state for key,row in self.analysis.engine.tables.items()})
            return result
        finally:
            if self.guard:
                self.guard.close()
            self.lease.revoke()
            if self.analysis:
                with contextlib.suppress(Exception):
                    self.analysis.stop()
            if self.capture:
                self.capture.stop()
            if self.box:
                # stop() may commit a final UNKNOWN. Delivery permission is separate
                # from processing and still authenticates this same device.
                with contextlib.suppress(DeviceUnavailable):
                    Synchronizer(self.box, self.client).tick()
                result['pending'] = self.box.pending_count
                with contextlib.suppress(DeviceUnavailable):
                    self.client.post('/v1/edge/heartbeat', self.health())
                self.box.close()
            self.client.close()


def sync_saved(settings):
    """Deliver an existing queue without opening video or restoring a processing lease."""
    identity, key = load_identity(settings['identity'])
    client = DeviceClient(settings['api'], settings['ca'], identity['key_id'], key)
    try:
        reply = client.post('/v1/edge/heartbeat', {'camera':'UNKNOWN','inference':'STOPPED','queue_pending':0})
        cloud = reply['configuration']
        if not Path(settings['outbox']).is_file():
            raise ValueError('No existing queue; sync does not create a new stream')
        with Outbox(settings['outbox'], device_id=cloud['device_id'], organization_id=cloud['organization_id'],
                    location_id=cloud['location_id']) as box:
            sync = Synchronizer(box, client)
            while box.pending_count and sync.tick():
                pass
            return {'pending':box.pending_count,'video_opened':False}
    finally:
        client.close()


def load_settings(path):
    path = Path(path).resolve(strict=True)
    value = json.loads(path.read_text(encoding='utf-8'))
    required = {'api', 'ca', 'identity', 'profiles', 'models', 'sources', 'camera_id', 'source_reference', 'outbox'}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError('Invalid device runner configuration')
    for name in ('ca', 'identity', 'profiles', 'models', 'sources', 'outbox'):
        value[name] = str((path.parent/value[name]).resolve())
    return value
