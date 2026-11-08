"""Scoped loopback AI lab. All remote requests are passive metadata GETs."""

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import Field

from restaurant_edge.analysis import Analysis
from restaurant_edge.analysis_config import AnalysisConfig, ConfigStore, Conflict, Strict
from restaurant_edge.detectors.onnx_detector import ModelCatalog, ModelUnavailable

MANAGERS = {'owner', 'org_admin', 'manager'}


class SaveAnalysis(Strict):
    config: AnalysisConfig
    expected_revision: int = Field(ge=0, le=500)
    request_key: UUID


class Empty(Strict):
    pass


def install_routes(app, state, current, *, enabled, root, catalog=None, factory=Analysis):
    store = ConfigStore(root)
    catalog = catalog or ModelCatalog()
    app.state.analysis_store = store

    def context(request, force=False):
        session = current(request)
        if not enabled:
            raise HTTPException(409, 'Local AI debugging is not enabled.')
        state.permission(session, force=force)
        if state.owner is not session or state.active is None:
            raise HTTPException(404, 'Start your authorized preview first.')
        source = session.source
        if not source.synthetic:
            raise HTTPException(403, 'Only explicitly synthetic footage is approved for Phase 5 testing.')
        me = session.cloud.request('GET', '/v1/me')
        role = next((r['role'] for r in me['access']
                     if str(r['organization']['id']) == str(source.organization_id)
                     and any(str(loc['id']) == str(source.location_id) for loc in r['locations'])), None)
        if role not in MANAGERS | {'installer'}:
            raise HTTPException(403, 'Setup role and location permission required.')
        return session, role, str(me['id']), (source.organization_id, source.location_id, source.camera_id)

    def validate(config, session, passive=False):
        scope = (config.organization_id, config.location_id, config.camera_id)
        expected = (session.source.organization_id, session.source.location_id, session.source.camera_id)
        if scope != expected:
            raise HTTPException(404, 'Configuration is outside the selected camera scope.')
        path = f'/v1/locations/{config.location_id}/table-zones'
        zones = session.cloud.passive(path) if passive and hasattr(session.cloud, 'passive') else session.cloud.request('GET', path)
        for region in config.regions:
            match = next((z for z in zones if str(z['id']) == str(region.zone_id)), None)
            if (match is None or str(match['organization_id']) != str(config.organization_id)
                or str(match['location_id']) != str(config.location_id)
                or str(match['camera_id']) != str(config.camera_id)
                or str(match['table_id']) != str(region.table_id)
                or match['revision'] != region.zone_revision or not match.get('view_metadata')
                or match['source_width'] != config.source_width
                or match['source_height'] != config.source_height):
                raise HTTPException(409, 'Calibration changed or is not reviewed for this original view.')

    def audit(scope, actor, action):
        directory = store.directory(scope) / 'audit'
        directory.mkdir(parents=True, exist_ok=True)
        if len(list(directory.glob('*.json'))) >= 1000:
            raise HTTPException(409, 'Local audit quota reached; review retained records.')
        import json
        from datetime import UTC, datetime
        with (directory / (uuid4().hex + '.json')).open('x', encoding='utf-8') as handle:
            json.dump({'actor': actor, 'action': action, 'scope': list(map(str, scope)),
                       'created_at': datetime.now(UTC).isoformat()}, handle)

    @app.get('/analysis')
    def page():
        return FileResponse(Path(__file__).parent / 'static' / 'analysis.html')

    @app.get('/local/v1/analysis/availability')
    def availability(request: Request):
        current(request)
        return {'enabled': enabled, 'models': list(catalog.entries),
                'message': 'Local shadow estimates only. No cloud state writes. Model weights require separate approval.'}

    @app.get('/local/v1/analysis/config')
    def configuration(request: Request):
        _, _, _, scope = context(request)
        return store.load(scope) or {'revision': 0, 'config': None}

    @app.put('/local/v1/analysis/config')
    def save(body: SaveAnalysis, request: Request):
        session, role, actor, scope = context(request, True)
        validate(body.config, session)
        with state.lock:
            if state.owner is not session:
                raise HTTPException(409, 'Preview changed.')
            previous = store.load(scope)
            if role not in MANAGERS and (previous is None or
                    previous['config']['settings'] != body.config.settings.model_dump()
                    or previous['config']['model'] != body.config.model):
                raise HTTPException(403, 'A manager must approve the initial profile, detector and operational thresholds.')
            try:
                record = store.save(body.config, body.expected_revision, body.request_key, actor)
            except Conflict:
                raise HTTPException(409, 'Local configuration revision or request identity conflict.') from None
            if session.analysis:
                session.analysis.stop('CONFIGURATION_CHANGED')
                session.analysis = None
            return record

    @app.post('/local/v1/analysis/start')
    def start(body: Empty, request: Request):
        session, _, actor, scope = context(request, True)
        record = store.load(scope)
        if record is None:
            raise HTTPException(409, 'Save a reviewed seating profile first.')
        config = AnalysisConfig.model_validate(record['config'])
        validate(config, session)
        try:
            artifact = catalog.get(config.model)
        except ModelUnavailable:
            raise HTTPException(503, 'Model weights are unavailable or lack the required approval. No download was attempted.') from None
        with state.lock:
            if state.owner is not session or state.active is None:
                raise HTTPException(409, 'Preview changed.')
            if session.analysis:
                raise HTTPException(409, 'Stop the current analysis before starting another.')
            def manual_snapshot():
                validate(config, session, passive=True)
                path = f'/v1/locations/{config.location_id}/dashboard'
                return session.cloud.passive(path) if hasattr(session.cloud, 'passive') else session.cloud.request('GET', path)
            audit(scope, actor, 'analysis_start_requested')
            analysis = factory(state.active, config, artifact, manual_snapshot)
            analysis.engine.config_revision = record['revision']
            session.analysis = analysis
            try:
                analysis.start()
            except Exception:  # noqa: BLE001 - native startup details must not reach a browser
                analysis.stop('ANALYSIS_START_FAILED', 'ERROR')
                raise HTTPException(503, 'Local analysis could not start safely.') from None
        return {'started': True, 'authoritative': False, 'config_revision': record['revision']}

    @app.post('/local/v1/analysis/stop')
    def stop(body: Empty, request: Request):
        session, _, actor, scope = context(request, True)
        with state.lock:
            if session.analysis:
                session.analysis.stop()
                session.analysis = None
                audit(scope, actor, 'analysis_stop')
        return {'stopped': True, 'preview_preserved': True}

    @app.get('/local/v1/analysis/status')
    def status(request: Request):
        session, _, _, _ = context(request)
        with state.lock:
            if not session.analysis:
                return {'status': 'STOPPED', 'tables': [], 'detections': [], 'frame': None,
                        'authoritative': False, 'reason': 'EXPLICIT_START_REQUIRED'}
            return session.analysis.snapshot()

    @app.get('/local/v1/analysis/events')
    def events(request: Request, after: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100)):
        session, _, _, _ = context(request)
        with state.lock:
            if not session.analysis:
                return {'events': [], 'history_truncated': False}
            engine = session.analysis.engine
            rows = list(engine.events)
            return {'events': [e for e in rows if e['number'] > after][:limit],
                    'history_truncated': bool(rows and after < rows[0]['number'] - 1)}
