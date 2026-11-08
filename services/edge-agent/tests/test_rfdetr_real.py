"""Opt-in REAL pretrained inference on generated arrays. No person accuracy claim.

Set RFDETR_TEST_CATALOG to a private reviewed manifest. No downloads, no footage.
"""

import os
import socket
import time
from uuid import uuid4

import numpy as np
import pytest
from test_analysis_domain import configuration
from test_analysis_workers import manual_provider

from restaurant_edge.analysis import Analysis
from restaurant_edge.association import associate
from restaurant_edge.capture import Capture
from restaurant_edge.detectors.factory import detector_for
from restaurant_edge.detectors.onnx_detector import ModelCatalog
from restaurant_edge.source_config import SourceDefinition
from restaurant_edge.state_engine import StateEngine
from restaurant_edge.video_sources import synthetic_mp4


@pytest.fixture(scope='module')
def detector():
    path = os.environ.get('RFDETR_TEST_CATALOG')
    if not path:
        pytest.skip('Real-model opt-in: no approved private RFDETR_TEST_CATALOG; no download attempted')
    catalog = ModelCatalog.load(path)
    model = detector_for(catalog.get('rfdetr_nano'))
    yield model
    model.close()


def test_real_model_runs_offline_on_generated_pixels(detector, monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError('Inference must not use network')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)
    for pixels in [np.zeros((360, 640, 3), dtype=np.uint8),
                   np.full((360, 640, 3), 127, dtype=np.uint8)]:
        result = detector.detect(pixels)
        assert isinstance(result, tuple) and len(result) <= 128
        assert detector.last_metrics['inference_ms'] > 0
        assert detector.session.get_providers() == ['CPUExecutionProvider']


@pytest.mark.parametrize('protected', ['CLEANING', 'OUT_OF_SERVICE'])
def test_real_outputs_enter_association_and_cannot_replace_human_states(detector, protected):
    config = configuration(model='rfdetr_nano')
    engine = StateEngine(config)
    region = config.regions[0]
    utc = '2026-11-08T00:00:00+00:00'
    engine.manual([{'id': str(region.table_id), 'operational_revision': 1,
        'state_source': 'manual', 'current_state': protected, 'state_since': utc}], 0, utc)
    people = detector.detect(np.zeros((360, 640, 3), dtype=np.uint8))
    observations = associate(people, config)
    for index in range(30):
        engine.step(observations, index * .5, utc, 'generated', index)
    assert engine.tables[str(region.table_id)].state == protected
    assert all(not e['authoritative'] for e in engine.events)


def test_real_reader_model_worker_and_shadow_state_cleanup(tmp_path):
    path = os.environ.get('RFDETR_TEST_CATALOG')
    if not path:
        pytest.skip('Real-model opt-in: no approved private catalog')
    config = configuration(model='rfdetr_nano')
    artifact = ModelCatalog.load(path).get('rfdetr_nano')
    video = synthetic_mp4(tmp_path / 'generated-only.mp4', seconds=3)
    source = SourceDefinition(reference='generated-' + uuid4().hex, organization_id=config.organization_id,
        location_id=config.location_id, camera_id=config.camera_id, kind='mp4', synthetic=True,
        authorized=True, file=str(video))
    capture = Capture(source, fps=2, loop=True)
    analysis = Analysis(capture, config, artifact, lambda: manual_provider(config, 'CLEANING'))
    capture.start()
    try:
        analysis.start()
        deadline = time.monotonic() + 22
        while time.monotonic() < deadline:
            analysis.tick()
            if analysis.latest:
                break
            if analysis.status == 'ERROR':
                pytest.fail('Actual reader/model integration failed: ' + str(analysis.reason))
            time.sleep(.05)
        assert analysis.latest and analysis.status == 'RUNNING'
        result = analysis.snapshot()
        assert result['metrics']['inference_ms'] > 0 and result['metrics']['frame_age_ms'] < 2000
        assert all(t['state'] == 'CLEANING' for t in result['tables'])
        assert not result['authoritative']
    finally:
        analysis.stop()
        capture.stop()
    assert analysis.process is None and capture.health()['status'] != 'ONLINE'
