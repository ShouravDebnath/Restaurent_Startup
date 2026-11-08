"""Actual Windows reader/process cleanup with SIMULATED detector outputs."""

import multiprocessing
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from test_analysis_domain import configuration

from restaurant_edge.analysis import Analysis, inference_worker
from restaurant_edge.analysis_metrics import process_metrics
from restaurant_edge.capture import Capture
from restaurant_edge.detectors.base import Person
from restaurant_edge.detectors.onnx_detector import ApprovedArtifact
from restaurant_edge.source_config import SourceDefinition
from restaurant_edge.video_sources import synthetic_mp4


class FixtureDetector:
    """No model weights. This fixture does not examine people in pixels."""
    def __init__(self, artifact):
        self.last_metrics = {'simulated_detector': True}
    def detect(self, image):
        assert image.shape == (360, 640, 3)
        return (Person((.2, .2, .4, .6), .9),)
    def close(self):
        pass


class HungDetector(FixtureDetector):
    def detect(self, image):
        time.sleep(30)
        return ()


def fixture_worker(artifact, incoming, outgoing, cancel):
    inference_worker(artifact, incoming, outgoing, cancel, factory=FixtureDetector)


def hung_worker(artifact, incoming, outgoing, cancel):
    inference_worker(artifact, incoming, outgoing, cancel, factory=HungDetector)


def manual_provider(config, state='UNKNOWN'):
    return {'location': {'id': str(config.location_id), 'organization_id': str(config.organization_id)},
            'tables_truncated': False, 'tables': [{
                'id': str(r.table_id), 'organization_id': str(config.organization_id),
                'location_id': str(config.location_id), 'operational_revision': 1,
                'state_source': 'manual' if state != 'UNKNOWN' else 'unverified',
                'current_state': state, 'state_since': '2026-11-08T00:00:00+00:00'} for r in config.regions]}


def pair(tmp_path, worker=fixture_worker, loop=True):
    config = configuration(settings={'arrival_seconds': 2, 'departure_seconds': 5})
    path = synthetic_mp4(tmp_path / 'geometric-fixture.mp4', seconds=5)
    source = SourceDefinition(reference='synthetic', organization_id=config.organization_id,
        location_id=config.location_id, camera_id=config.camera_id, kind='mp4', synthetic=True,
        authorized=True, file=str(path))
    capture = Capture(source, fps=5, loop=loop)
    artifact = ApprovedArtifact(Path('not-a-real-model.onnx'), 'f' * 64)
    analysis = Analysis(capture, config, artifact, lambda: manual_provider(config), worker=worker)
    return capture, analysis


def wait_for(analysis, predicate, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        analysis.tick()
        if predicate():
            return
        time.sleep(.05)
    raise AssertionError('Synthetic worker condition timed out')


def test_actual_bgr_mailbox_is_opt_in_original_size_and_not_a_browser_jpeg(tmp_path):
    capture, analysis = pair(tmp_path)
    capture.start()
    try:
        assert capture.raw_frame() is None
        capture.enable_analysis(True)
        wait_for(analysis, lambda: capture.health()['status'] == 'ONLINE')
        frame = None
        end = time.monotonic() + 5
        while frame is None and time.monotonic() < end:
            frame = capture.raw_frame()
            time.sleep(.05)
        assert frame['pixels'].shape == (360, 640, 3) and frame['pixels'].dtype == np.uint8
        assert frame['width'] == 640 and frame['height'] == 360
        assert capture.frame().startswith(b'\xff\xd8')
    finally:
        capture.stop()


def test_sibling_worker_pipeline_results_are_scoped_fresh_and_stop_preserves_preview(tmp_path):
    before = {p.pid for p in multiprocessing.active_children()}
    capture, analysis = pair(tmp_path)
    capture.start()
    try:
        analysis.start()
        wait_for(analysis, lambda: bool(analysis.snapshot()['detections']))
        result = analysis.snapshot()
        assert result['authoritative'] is False and result['metrics']['simulated_detector'] is True
        assert result['frame']['width'] == 640 and 'pixels' not in result['frame']
        assert capture.process.pid != analysis.process.pid
        analysis.stop()
        assert capture.process.is_alive() and analysis.process is None
        assert analysis.snapshot()['detections'] == []
    finally:
        analysis.stop()
        capture.stop()
    assert {p.pid for p in multiprocessing.active_children()} == before


def test_hung_inference_is_killed_but_reader_survives(tmp_path):
    capture, analysis = pair(tmp_path, hung_worker)
    capture.start()
    try:
        analysis.start()
        wait_for(analysis, lambda: analysis.status == 'ERROR', timeout=15)
        assert analysis.reason == 'INFERENCE_TIMEOUT' and analysis.process is None
        assert capture.process.is_alive()
    finally:
        analysis.stop()
        capture.stop()


def test_normal_mp4_completion_releases_model_worker(tmp_path):
    capture, analysis = pair(tmp_path, loop=False)
    capture.start()
    try:
        analysis.start()
        wait_for(analysis, lambda: analysis.status == 'COMPLETED')
        assert analysis.process is None and analysis.snapshot()['detections'] == []
    finally:
        analysis.stop()
        capture.stop()


def test_stale_results_hide_boxes_and_preserve_manual_cleaning(tmp_path):
    capture, analysis = pair(tmp_path)
    capture.start()
    try:
        analysis.manual_provider = lambda: manual_provider(analysis.config, 'CLEANING')
        analysis.start()
        wait_for(analysis, lambda: bool(analysis.snapshot()['detections']))
        analysis.latest['received_monotonic'] = time.monotonic() - 10
        snapshot = analysis.snapshot()
        assert snapshot['detections'] == [] and snapshot['tables'][0]['state'] == 'CLEANING'
        assert not snapshot['tables'][0]['verified']
    finally:
        analysis.stop()
        capture.stop()


def test_bad_manual_snapshot_is_rejected_before_any_native_worker(tmp_path):
    _capture, analysis = pair(tmp_path)
    analysis.manual_provider = lambda: {'location': {'id': 'foreign'}}
    with pytest.raises((ValueError, KeyError)):
        analysis.start()
    assert analysis.process is None


def test_cpu_and_own_process_memory_instrumentation():
    metrics = process_metrics()
    assert metrics['process_id'] > 0 and metrics['process_cpu_seconds'] >= 0
    if metrics['working_set_bytes'] is not None:
        assert metrics['peak_working_set_bytes'] >= metrics['working_set_bytes'] > 0


def test_slow_metadata_refresh_does_not_block_the_permission_watchdog_tick(tmp_path):
    capture, analysis = pair(tmp_path)
    release = threading.Event()
    capture.start()
    try:
        analysis.start()
        wait_for(analysis, lambda: bool(analysis.snapshot()['detections']))
        def slow_snapshot():
            release.wait(timeout=5)
            return manual_provider(analysis.config)
        analysis.manual_provider, analysis.next_manual = slow_snapshot, 0
        started = time.monotonic()
        analysis.tick()
        assert time.monotonic() - started < .5
        analysis.manual_at = time.monotonic() - 3.5
        assert analysis.snapshot()['detections'] == []
    finally:
        release.set()
        analysis.stop()
        capture.stop()


def test_simulated_detector_on_actual_frames_produces_only_local_shadow_events(tmp_path):
    capture, analysis = pair(tmp_path)
    capture.start()
    try:
        analysis.start()
        wait_for(analysis, lambda: next(iter(analysis.engine.tables.values())).state == 'OCCUPIED')
        assert any(row['new_state'] == 'OCCUPIED' and not row['authoritative']
                   for row in analysis.engine.events)
        assert analysis.snapshot()['metrics']['simulated_detector']
    finally:
        analysis.stop()
        capture.stop()
