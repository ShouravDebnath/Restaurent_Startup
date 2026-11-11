"""Actual approved RF-DETR/MP4/TLS background runner; SYNTHETIC pixels only."""

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from restaurant_edge.analysis_config import AnalysisConfig, ConfigStore
from restaurant_edge.detectors.onnx_detector import ModelCatalog
from restaurant_edge.device_runner import DeviceRunner
from restaurant_edge.video_sources import synthetic_mp4
from sqlalchemy import text

from .test_edge_https import tls as tls_fixture
from .test_edge_transport import (
    command,
    configure,
    edge_tenants,  # noqa: F401 -- dependency of the shared edge fixture
)
from .test_edge_transport import edge as edge_fixture

edge = edge_fixture
tls = tls_fixture
ROOT = Path(__file__).resolve().parents[3]


def test_native_synthetic_background_runner(edge, tls, monkeypatch):
    catalog_path = os.environ.get('RFDETR_TEST_CATALOG')
    if not catalog_path:
        pytest.skip('Native-model opt-in needs the already-approved private catalog; no download')
    artifact = ModelCatalog.load(catalog_path).get('rfdetr_nano')
    configure(edge)
    folder = ROOT/'.secrets/phase6-implementation'/('native-run-'+uuid4().hex)
    folder.mkdir()
    config = AnalysisConfig.model_validate({'organization_id':str(edge.org),'location_id':str(edge.loc),
        'camera_id':str(edge.camera),'model':'rfdetr_nano','source_width':640,'source_height':360,
        'regions':[{'table_id':str(edge.table),'zone_id':str(uuid4()),'zone_revision':1,
            'seating':[[.1,.1],[.8,.1],[.8,.8],[.1,.8]],'visibility_reviewed':True}]})
    record = ConfigStore(folder/'profiles').save(config,0,uuid4(),edge.suite.seed['accounts']['a_owner']['user_id'])
    digest = hashlib.sha256(json.dumps(config.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
    assert digest == record['fingerprint']
    response = command(edge, action='assign',camera_id=str(edge.camera),table_id=str(edge.table),zone_revision=1,
        profile_revision=record['revision'],profile_sha256=digest,model_sha256=artifact.sha256)
    assert response.status_code == 200
    video = folder/'synthetic.mp4'
    synthetic_mp4(video, 20)
    sources = folder/'sources.json'
    sources.write_text(json.dumps({'version':1,'roots':[str(folder)],'sources':[
        {'reference':'phase6-synthetic','organization_id':str(edge.org),'location_id':str(edge.loc),
         'camera_id':str(edge.camera),'kind':'mp4','synthetic':True,'authorized':True,'file':str(video)}]}))
    # API/queue tests use generated keys. Native Windows vault persistence has a
    # separate explicit local check; this fixture must not populate OS credentials.
    monkeypatch.setattr('restaurant_edge.device_runner.load_identity',lambda _:({'key_id':edge.kid},edge.key))
    settings = {'identity':'unused-fixture','api':f'https://127.0.0.1:{tls.port}','ca':tls.folder/'ca.pem',
        'profiles':folder/'profiles','models':catalog_path,'sources':sources,'camera_id':str(edge.camera),
        'source_reference':'phase6-synthetic','outbox':folder/'outbox.sqlite3'}
    with edge.suite.admin.connect() as db:
        before = db.scalar(text('SELECT to_jsonb(t) FROM dining_tables t WHERE id=:id'),{'id':edge.table})
    result = DeviceRunner(settings).run(seconds=12)
    assert result['analysis_status'] == 'RUNNING', result
    assert result['inference_ms'] is not None and result['inference_ms']>0
    assert set(result['shadow_states'].values()) == {'UNKNOWN'}
    assert result['pending'] == 0
    with edge.suite.admin.connect() as db:
        assert db.scalar(text('SELECT to_jsonb(t) FROM dining_tables t WHERE id=:id'),{'id':edge.table}) == before
        assert db.scalar(text('SELECT count(*) FROM edge_health WHERE device_id=:id'),{'id':edge.device}) == 1
    report = dict(result,actual_pretrained_model=True,synthetic_video=True,real_person_accuracy=False,
                  canonical_table_preserved=True,model_sha256=artifact.sha256)
    (ROOT/'.secrets/phase6-implementation/native-run-result.json').write_text(json.dumps(report,indent=2))
