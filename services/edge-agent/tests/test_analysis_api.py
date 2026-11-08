"""Simulated authority/worker: permission contracts, not real detector validation."""

import secrets
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_analysis_domain import SQUARE
from test_companion import ORIGIN, FakeAuthority, FakeCapture, login, start

from restaurant_edge.companion import create_companion
from restaurant_edge.source_config import SourceDefinition, SourceRegistry
from restaurant_edge.video_sources import synthetic_mp4


class LabAuthority(FakeAuthority):
    def __init__(self, source):
        super().__init__(source)
        self.user_id, self.table_id, self.zone_id = uuid4(), uuid4(), uuid4()
        self.role = 'manager'
        self.zone_revision = 7

    def request(self, method, path, body=None):
        s = self.source
        if path == '/v1/me':
            self.paths.append((method, path))
            return {'id': str(self.user_id), 'display_name': 'Synthetic manager', 'access': [{
                'role': self.role, 'organization': {'id': str(s.organization_id), 'name': 'Synthetic A'},
                'locations': [{'id': str(s.location_id), 'name': 'Synthetic lab'}]}]}
        if path.endswith('/table-zones'):
            self.paths.append((method, path))
            return [{'id': str(self.zone_id), 'organization_id': str(s.organization_id),
                     'location_id': str(s.location_id), 'camera_id': str(s.camera_id),
                     'table_id': str(self.table_id), 'revision': self.zone_revision,
                     'polygon': SQUARE, 'source_width': 20, 'source_height': 20,
                     'view_metadata': {'format_version': 1, 'rotation': 0, 'mirrored': False}}]
        return super().request(method, path, body)


@pytest.fixture
def lab(tmp_path):
    path = synthetic_mp4(tmp_path / 'synthetic.mp4', seconds=.2)
    source = SourceDefinition(reference='synthetic', organization_id=uuid4(), location_id=uuid4(),
                              camera_id=uuid4(), kind='mp4', authorized=True, synthetic=True, file=str(path))
    clients = []
    def factory():
        authority = LabAuthority(source)
        clients.append(authority)
        return authority
    app = create_companion(SourceRegistry([source], [tmp_path]), cloud_factory=factory,
                           capture_factory=FakeCapture, ai_debug=True, analysis_root=tmp_path / 'profiles')
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        assert start(client, source, headers).status_code == 200
        authority = clients[0]
        body = {'config': {'organization_id': str(source.organization_id), 'location_id': str(source.location_id),
                'camera_id': str(source.camera_id), 'source_width': 20, 'source_height': 20,
                'regions': [{'table_id': str(authority.table_id), 'zone_id': str(authority.zone_id),
                             'zone_revision': 7, 'seating': SQUARE, 'visibility_reviewed': True}]},
                'expected_revision': 0, 'request_key': str(uuid4())}
        yield client, app.state.companion, source, authority, headers, body, tmp_path


def save(client, headers, body):
    return client.put('/local/v1/analysis/config', headers=headers, json=body)


def test_profile_revision_reload_idempotency_and_no_cloud_writes(lab):
    client, state, _, authority, headers, body, folder = lab
    first = save(client, headers, body)
    assert first.status_code == 200 and first.json()['revision'] == 1
    assert save(client, headers, body).json() == first.json()
    assert client.get('/local/v1/analysis/config').json() == first.json()
    assert state.active is not None and authority.zone_revision == 7
    assert all(method == 'GET' for method, _ in authority.paths)
    assert len(list(folder.rglob('000001.json'))) == 1


@pytest.mark.parametrize('field', ['organization_id', 'location_id', 'camera_id'])
def test_cross_restaurant_or_location_configuration_is_denied(lab, field):
    client, _, _, _, headers, body, _ = lab
    body['config'][field] = str(uuid4())
    assert save(client, headers, body).status_code == 404


@pytest.mark.parametrize('field', ['table_id', 'zone_id'])
def test_foreign_table_zone_is_not_silently_accepted(lab, field):
    client, _, _, _, headers, body, _ = lab
    body['config']['regions'][0][field] = str(uuid4())
    assert save(client, headers, body).status_code == 409


def test_stale_calibration_and_concurrent_revision_fail_closed(lab):
    client, _, _, authority, headers, body, _ = lab
    assert save(client, headers, body).status_code == 200
    body['request_key'] = str(uuid4())
    assert save(client, headers, body).status_code == 409
    body['expected_revision'] = 1
    authority.zone_revision = 8
    assert save(client, headers, body).status_code == 409


def test_model_gate_never_opens_camera_again_or_downloads_weights(lab):
    client, state, _, _, headers, body, _ = lab
    assert save(client, headers, body).status_code == 200
    capture = state.active
    response = client.post('/local/v1/analysis/start', headers=headers, json={})
    assert response.status_code == 503 and 'No download' in response.json()['error']['message']
    assert state.active is capture and not capture.stopped and state.owner.analysis is None
    assert client.get('/local/v1/analysis/status').json()['detections'] == []


def test_installer_geometry_is_allowed_but_initial_and_threshold_approval_is_not(lab):
    client, _, _, authority, headers, body, _ = lab
    authority.role = 'installer'
    assert save(client, headers, body).status_code == 403
    authority.role = 'manager'
    assert save(client, headers, body).status_code == 200
    authority.role = 'installer'
    body['expected_revision'], body['request_key'] = 1, str(uuid4())
    body['config']['regions'][0]['anchor'] = 'feet'
    assert save(client, headers, body).status_code == 200
    body['expected_revision'], body['request_key'] = 2, str(uuid4())
    body['config']['settings'] = {'arrival_seconds': 12}
    assert save(client, headers, body).status_code == 403


@pytest.mark.parametrize('role', ['staff', 'unrecognized'])
def test_role_loss_denies_every_analysis_read(lab, role):
    client, _, _, authority, _, _, _ = lab
    authority.role = role
    for route in ['config', 'status', 'events']:
        assert client.get('/local/v1/analysis/' + route).status_code == 403


def test_revoke_deadline_and_passive_reads_do_not_renew_access(lab):
    client, state, _, authority, headers, body, _ = lab
    assert save(client, headers, body).status_code == 200
    session = state.owner
    deadline = session.authorized_until
    for _ in range(3):
        assert client.get('/local/v1/analysis/status').status_code == 200
    assert session.authorized_until == deadline
    session.authorized_until = time.monotonic() - 1
    assert client.get('/local/v1/analysis/config').status_code == 403
    assert state.active is None
    authority.allowed = False
    assert client.get('/local/v1/analysis/events').status_code == 403


def test_other_browser_cannot_read_the_current_users_shadow_state(lab):
    client, _, _, _, _, _, _ = lab
    with TestClient(client.app, base_url=ORIGIN) as other:
        login(other)
        assert other.get('/local/v1/analysis/status').status_code == 409


def test_origin_csrf_strict_body_no_secret_echo_and_event_limits(lab):
    client, _, _, _, headers, body, _ = lab
    assert client.put('/local/v1/analysis/config', json=body, headers={'Origin': ORIGIN}).status_code == 403
    assert client.get('/local/v1/analysis/status', headers={'Host': 'evil.invalid'}).status_code == 403
    canary = secrets.token_urlsafe(24)
    response = client.post('/local/v1/analysis/start', json={'model_path': canary}, headers=headers)
    assert response.status_code == 422 and canary not in response.text
    assert client.get('/local/v1/analysis/events?limit=101').status_code == 422
    assert client.get('/local/v1/analysis/events?after=-1').status_code == 422


def test_real_footage_source_cannot_be_enabled_under_synthetic_only_approval(lab):
    client, _, source, _, headers, body, _ = lab
    source.synthetic = False
    assert save(client, headers, body).status_code == 403


def test_permission_revocation_stops_analysis_with_the_reader(lab):
    client, state, _, authority, _, _, _ = lab
    class SimulatedAnalysis:
        stopped = False
        def stop(self, reason):
            self.stopped = True
    analysis = SimulatedAnalysis()
    capture = state.active
    state.owner.analysis = analysis
    authority.allowed = False
    state.owner.next_check = 0
    assert client.get('/local/v1/analysis/status').status_code == 403
    assert analysis.stopped and capture.stopped and state.active is None


def test_local_absolute_session_expiry_prevents_ai_reads(lab):
    client, state, _, _, _, _, _ = lab
    state.owner.created = time.monotonic() - 3601
    assert client.get('/local/v1/analysis/status').status_code == 401
    assert state.active is None


def test_reused_request_identity_for_different_body_is_a_conflict(lab):
    client, _, _, _, headers, body, _ = lab
    assert save(client, headers, body).status_code == 200
    body['config']['regions'][0]['anchor'] = 'feet'
    assert save(client, headers, body).status_code == 409


def test_native_login_fallback_uses_post_and_never_echoes_private_form_input(lab):
    client, _, _, _, _, _, _ = lab
    for path in ['/', '/analysis']:
        html = client.get(path).text
        assert 'method="post" action="/local/v1/login"' in html
        assert '<button disabled>Sign in</button>' in html
    canary = secrets.token_urlsafe(24)
    response = client.post('/local/v1/login', content='password=' + canary,
        headers={'Origin': ORIGIN, 'Content-Type': 'application/x-www-form-urlencoded'})
    assert response.status_code == 415 and canary not in response.text
