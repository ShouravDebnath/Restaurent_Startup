"""Synthetic device security and durable PostgreSQL effects, never AI accuracy."""

import base64
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from restaurant_api.database import set_identity
from restaurant_api.edge_models import EdgeShadow
from restaurant_api.edge_protocol import Observation, encode
from restaurant_api.edge_signatures import sign
from restaurant_api.management import seed_demo
from restaurant_api.models import (
    Camera,
    DiningTable,
    Location,
    LocationGrant,
    LocationOperations,
    Membership,
    TableZone,
)
from restaurant_api.settings import get_settings


@pytest.fixture(scope='session')
def edge_tenants(suite, tmp_path_factory):
    # Keep the original Phase 2 discovery assertions meaningful: new device tests
    # must not append locations/grants to their shared restaurant fixture.
    isolated = copy.copy(suite)
    isolated.namespace = 'edge-tests-'+uuid4().hex[:10]
    isolated.seed = seed_demo(suite.admin, tmp_path_factory.mktemp('edge-private')/'accounts.json', isolated.namespace)
    clients = {key: isolated.login(account) for key,account in isolated.seed['accounts'].items()}
    yield isolated, clients
    for client in clients.values():
        client.client.close()


@pytest.fixture
def edge(edge_tenants, monkeypatch):
    suite, clients = edge_tenants
    monkeypatch.setenv('EDGE_SYNC_ENABLED', 'true')
    get_settings.cache_clear()
    org = UUID(suite.seed['organizations']['a']['id'])
    loc, camera, table = uuid4(), uuid4(), uuid4()
    with Session(suite.admin) as db, db.begin():
        db.add(Location(id=loc, organization_id=org, name='Phase 6 Transport Fixture', time_zone='UTC'))
        db.flush()
        db.get(LocationOperations, loc).is_synthetic = True
        for member in db.scalars(select(Membership).where(Membership.organization_id == org)):
            db.add(LocationGrant(membership_id=member.id, location_id=loc, organization_id=org))
        db.add(Camera(id=camera, organization_id=org, location_id=loc, label='Synthetic camera'))
        db.add(DiningTable(id=table, organization_id=org, location_id=loc, label='Transport fixture table'))
        db.flush()
        db.add(TableZone(organization_id=org, location_id=loc, table_id=table, camera_id=camera,
                         polygon=[[0.1,0.1],[0.8,0.1],[0.8,0.8],[0.1,0.8]], source_width=640, source_height=480))
    client = TestClient(suite.app, base_url='https://testserver', client=('edge-'+uuid4().hex, 51000))
    result = SimpleNamespace(suite=suite, clients=clients, client=client, org=org, loc=loc, camera=camera, table=table,
                             key=Ed25519PrivateKey.generate(), kid=uuid4(), request_id=uuid4(), stream=uuid4())
    yield result
    client.close()
    get_settings.cache_clear()


def send(edge, path, value, *, signed=True, key=None, kid=None, **kwargs):
    body = encode(value)
    if signed:
        request = sign('POST', 'https://testserver'+path, body, kid or edge.kid, key or edge.key, **kwargs)
        headers = dict(request.headers)
    else:
        headers = {'content-type': 'application/json'}
    return edge.client.post(path, content=body, headers=headers)


def pair(edge, purpose='AI_SHADOW'):
    public = base64.b64encode(edge.key.public_key().public_bytes_raw()).decode()
    start = send(edge, '/v1/edge/pairings', {'request_id': str(edge.request_id), 'key_id': str(edge.kid), 'public_key': public}, signed=False)
    assert start.status_code == 200, start.text
    challenge = start.json()
    proved = send(edge, '/v1/edge/pairings/proof', {'request_id': str(edge.request_id), 'challenge': challenge['challenge']})
    assert proved.status_code == 200, proved.text
    approved = edge.clients['a_owner'].request('POST', f'/v1/locations/{edge.loc}/devices/commands', json={
        'action': 'approve', 'request_id': str(edge.request_id), 'fingerprint': challenge['fingerprint'], 'label': 'Synthetic edge', 'purpose': purpose})
    assert approved.status_code == 200, approved.text
    edge.device = approved.json()['device_id']
    edge.revision = approved.json()['revision']
    return challenge


def command(edge, **body):
    result = edge.clients['a_owner'].request('POST', f'/v1/locations/{edge.loc}/devices/commands',
        json=dict(device_id=edge.device, expected_revision=edge.revision, **body))
    if result.status_code == 200:
        edge.revision = result.json()['revision']
    return result


def configure(edge, purpose='AI_SHADOW'):
    pair(edge, purpose)
    assert command(edge, action='assign', camera_id=str(edge.camera), table_id=str(edge.table), zone_revision=1,
        profile_revision=1, profile_sha256='a'*64, model_sha256='b'*64).status_code == 200
    assert command(edge, action='processing', enabled=True).status_code == 200
    response = send(edge, '/v1/edge/heartbeat', {'camera': 'ONLINE', 'inference': 'RUNNING', 'queue_pending': 0})
    assert response.status_code == 200, response.text
    edge.config = response.json()['configuration']
    edge.binding = edge.config['bindings'][0]
    edge.assignment = edge.config['assignments'][0]
    return edge.config


def observation(edge, seq=1, **changes):
    return Observation.model_validate(dict(event_id=str(uuid4()), device_id=edge.device, stream_id=str(edge.stream),
        sequence=seq, organization_id=str(edge.org), location_id=str(edge.loc), binding_id=edge.binding['id'],
        binding_epoch=edge.binding['epoch'], camera_id=str(edge.camera), table_id=str(edge.table),
        occurred_at=datetime.now(UTC).isoformat(), state='UNKNOWN', reason='NOT_OBSERVED', manual_revision=0,
        zone_revision=1, profile_revision=1, profile_sha256='a'*64, model_sha256='b'*64,
        policy_revision=edge.assignment['policy_revision'], frame_sequence=seq, source_generation=str(uuid4()), **changes))


def batch(edge, *events, **kwargs):
    return send(edge, '/v1/edge/batches', {'events': [item.model_dump(mode='json') for item in events]}, **kwargs)


def test_pairing_fingerprint_proof_and_separate_processing(edge):
    pair(edge)
    response = send(edge, '/v1/edge/heartbeat', {'camera': 'UNKNOWN', 'inference': 'STOPPED', 'queue_pending': 0})
    assert response.status_code == 200
    assert response.json()['lease_seconds'] == 0
    assert response.json()['configuration']['bindings'] == []
    # Pairing grants neither a human login nor video preview consent.
    assert edge.client.get('/v1/me').status_code == 401
    wrong = command(edge, action='rotate', request_id=str(uuid4()), fingerprint='a'*64)
    assert wrong.status_code == 409


def test_delivery_duplicate_and_shadow_preserve_table(edge):
    configure(edge)
    with Session(edge.suite.admin) as db:
        before = db.scalar(text('SELECT to_jsonb(t) FROM dining_tables t WHERE id=:id'), {'id': edge.table})
    event = observation(edge)
    first = batch(edge, event)
    assert first.status_code == 200, first.text
    assert first.json()['receipts'][0]['disposition'] == 'shadow'
    assert batch(edge, event).json() == first.json()
    with Session(edge.suite.admin) as db:
        assert db.scalar(text('SELECT to_jsonb(t) FROM dining_tables t WHERE id=:id'), {'id': edge.table}) == before
        assert db.scalar(select(EdgeShadow.sequence).where(EdgeShadow.device_id == UUID(edge.device))) == 1
        assert db.scalar(text('SELECT count(*) FROM staff_tasks WHERE table_id=:id'), {'id': edge.table}) == 0


@pytest.mark.parametrize('field', ['organization_id', 'location_id', 'camera_id', 'table_id', 'binding_id', 'device_id'])
def test_forged_scope_denied(edge, field):
    configure(edge)
    event = observation(edge).model_copy(update={field: uuid4()})
    assert batch(edge, event).status_code == 403


def test_out_of_order_and_changed_payload_conflict(edge):
    configure(edge)
    one, two = observation(edge, 1), observation(edge, 2)
    response = batch(edge, two)
    assert response.status_code == 200, response.text
    assert response.json()['receipts'][0]['disposition'] == 'pending'
    assert batch(edge, one).json()['cursor'] == 2
    assert batch(edge, two).json()['receipts'][0]['disposition'] == 'shadow'
    assert batch(edge, one.model_copy(update={'reason': 'UNCERTAIN'})).status_code == 409
    assert batch(edge, observation(edge, 1)).status_code == 409
    assert batch(edge, observation(edge, 2000)).status_code == 409


def test_revocation_invalid_key_and_replay(edge):
    configure(edge)
    event = observation(edge)
    nonce = uuid4().hex
    assert batch(edge, event, nonce=nonce).status_code == 200
    assert batch(edge, event, nonce=nonce).status_code == 409
    assert batch(edge, event, key=Ed25519PrivateKey.generate()).status_code == 401
    assert command(edge, action='revoke').status_code == 200
    assert batch(edge, event).status_code == 401


def test_stale_history_and_config_change(edge):
    configure(edge)
    event = observation(edge).model_copy(update={'occurred_at': datetime.now(UTC)-timedelta(minutes=15)})
    assert batch(edge, event).json()['receipts'][0]['reason'] == 'STALE'
    changed = observation(edge, 2).model_copy(update={'profile_sha256': 'c'*64})
    assert batch(edge, changed).json()['receipts'][0]['reason'] == 'CONFIG_CHANGED'
    with Session(edge.suite.admin) as db:
        assert db.scalar(select(EdgeShadow).where(EdgeShadow.device_id == UUID(edge.device))) is None


def test_real_reset_task_exactly_once_under_concurrent_retries(edge):
    configure(edge, 'SYNTHETIC_WORKFLOW_TEST')
    episode = uuid4()
    one = observation(edge, 1).model_copy(update={'kind': 'fixture_arrive', 'reason': 'FIXTURE',
                                                 'state': 'OCCUPIED', 'occupancy_session_id': episode})
    two = observation(edge, 2).model_copy(update={'kind': 'fixture_depart', 'reason': 'FIXTURE',
                                                 'state': 'RESET_PENDING', 'occupancy_session_id': episode})
    assert batch(edge, one).json()['receipts'][0]['disposition'] == 'fixture'
    assert batch(edge, two).json()['receipts'][0]['disposition'] == 'fixture'
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: batch(edge, one, two), range(8)))
    assert all(response.status_code == 200 for response in responses)
    with Session(edge.suite.admin) as db:
        assert db.scalar(text('SELECT count(*) FROM staff_tasks WHERE table_id=:id'), {'id': edge.table}) == 1
        assert db.scalar(text('SELECT count(*) FROM table_events WHERE table_id=:id AND source=\'edge_fixture\''), {'id': edge.table}) == 2
        assert db.get(DiningTable, edge.table).current_state == 'RESET_PENDING'


@pytest.mark.parametrize('letter', ['a', 'b'])
@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_manager_routes_both_tenants_and_anonymous(edge, letter, method):
    org = edge.suite.seed['organizations'][letter]
    loc = org['locations'][0]
    path = f'/v1/locations/{loc}/devices' + ('/commands' if method == 'POST' else '')
    other = 'b' if letter == 'a' else 'a'
    body = {'action': 'revoke', 'device_id': str(uuid4()), 'expected_revision': 1} if method == 'POST' else None
    assert edge.clients[other+'_owner'].request(method, path, json=body).status_code == 404
    assert edge.client.request(method, path, json=body).status_code == 401


def test_runtime_has_no_direct_device_writes_or_private_schema(edge):
    configure(edge)
    with Session(edge.suite.runtime) as db, db.begin():
        set_identity(db, edge.suite.seed['accounts']['b_owner']['user_id'])
        assert db.scalar(text('SELECT count(*) FROM edge_devices WHERE id=:id'), {'id': edge.device}) == 0
    for statement in ['SELECT * FROM edge_private.pairings', "UPDATE edge_devices SET status='ACTIVE'",
                      'SELECT security.edge_publish(gen_random_uuid(),\'health\')']:
        with pytest.raises(DBAPIError), Session(edge.suite.runtime) as db, db.begin():
            db.execute(text(statement))


@pytest.mark.parametrize('path', ['/v1/edge/pairings', '/v1/edge/pairings/proof', '/v1/edge/batches',
                                  '/v1/edge/events', '/v1/edge/heartbeat'])
def test_machine_routes_require_tls_and_no_unauthenticated_data(edge, path):
    assert send(edge, path, {}, signed=False).status_code in {401, 422}
    with TestClient(edge.suite.app) as plain:
        assert plain.post(path, json={}).status_code == 403


def test_blueprint_event_route_shares_receipts_and_rejects_path_replay(edge):
    configure(edge)
    event = observation(edge)
    body = {'events': [event.model_dump(mode='json')]}
    first = send(edge, '/v1/edge/events', body)
    assert first.status_code == 200
    assert first.json()['receipts'][0]['disposition'] == 'shadow'
    assert batch(edge, event).json() == first.json()
    nonce = uuid4().hex
    assert send(edge, '/v1/edge/events', body, nonce=nonce).json() == first.json()
    assert send(edge, '/v1/edge/events', body, nonce=nonce).status_code == 409
    # An alias is not permission to reuse a signature for a different target.
    encoded = encode(body)
    request = sign('POST', 'https://testserver/v1/edge/batches', encoded, edge.kid, edge.key)
    assert edge.client.post('/v1/edge/events', content=encoded, headers=dict(request.headers)).status_code == 401
    foreign = observation(edge, 2).model_copy(update={'location_id': uuid4()})
    assert send(edge, '/v1/edge/events', {'events': [foreign.model_dump(mode='json')]}).status_code == 403
    with edge.suite.admin.connect() as db:
        assert db.scalar(text('SELECT count(*) FROM edge_receipts WHERE device_id=:id'), {'id': edge.device}) == 1
        assert db.scalar(text('SELECT count(*) FROM staff_tasks WHERE table_id=:id'), {'id': edge.table}) == 0
    assert command(edge, action='revoke').status_code == 200
    assert send(edge, '/v1/edge/events', body).status_code == 401


@pytest.mark.parametrize('role', ['staff', 'installer'])
def test_non_managers_cannot_approve_or_change_devices(edge, role):
    response = edge.clients['a_'+role].request('POST', f'/v1/locations/{edge.loc}/devices/commands',
        json={'action':'revoke','device_id':str(uuid4()),'expected_revision':1})
    assert response.status_code == 403


def test_same_restaurant_ungranted_location_is_hidden(edge):
    account = edge.suite.account('manager')  # Only the original first location is granted.
    client = edge.suite.login(account)
    try:
        assert client.request('GET', f'/v1/locations/{edge.loc}/devices').status_code == 404
        assert client.request('POST', f'/v1/locations/{edge.loc}/devices/commands',
            json={'action':'revoke','device_id':str(uuid4()),'expected_revision':1}).status_code == 404
    finally:
        client.client.close()


def test_key_rotation_keeps_event_identity_and_retires_old_key(edge):
    configure(edge)
    event = observation(edge)
    first = batch(edge, event)
    assert first.status_code == 200
    old_key, old_kid = edge.key, edge.kid
    edge.key, edge.kid, edge.request_id = Ed25519PrivateKey.generate(), uuid4(), uuid4()
    public = base64.b64encode(edge.key.public_key().public_bytes_raw()).decode()
    start = send(edge, '/v1/edge/pairings', {'request_id':str(edge.request_id), 'key_id':str(edge.kid),
        'public_key':public}, signed=False)
    assert start.status_code == 200
    assert send(edge, '/v1/edge/pairings/proof', {'request_id':str(edge.request_id),
        'challenge':start.json()['challenge']}).status_code == 200
    rotated = command(edge, action='rotate', request_id=str(edge.request_id), fingerprint=start.json()['fingerprint'])
    assert rotated.status_code == 200, rotated.text
    assert batch(edge, event).json() == first.json()
    # The short overlap is explicit; old queued event bytes also work with the new key.
    assert batch(edge, event, key=old_key, kid=old_kid).status_code == 200
    with edge.suite.admin.begin() as db:
        db.execute(text("UPDATE edge_keys SET expires_at=clock_timestamp()-interval '1 second' WHERE id=:id"), {'id':old_kid})
    assert batch(edge, event, key=old_key, kid=old_kid).status_code == 401
    assert batch(edge, event).status_code == 200


def test_manually_confirmed_state_and_new_zone_are_protected(edge):
    configure(edge)
    with edge.suite.admin.begin() as db:
        db.execute(text("UPDATE dining_tables SET current_state='CLEANING',state_source='manual',"
            "operational_revision=operational_revision+1 WHERE id=:id"), {'id':edge.table})
    response = batch(edge, observation(edge))
    assert response.json()['receipts'][0]['reason'] == 'MANUAL_CHANGED'
    with edge.suite.admin.begin() as db:
        assert db.scalar(text('SELECT current_state FROM dining_tables WHERE id=:id'), {'id':edge.table}) == 'CLEANING'
        db.execute(text('UPDATE table_zones SET revision=revision+1 WHERE table_id=:id'), {'id':edge.table})
    assert batch(edge, observation(edge, 2)).json()['receipts'][0]['reason'] == 'CONFIG_CHANGED'


def test_offline_notification_is_scoped_ordered_and_does_not_touch_human_idle(edge):
    from restaurant_api.edge_monitor import mark_offline
    from restaurant_api.workflow import event_batch
    configure(edge)
    with edge.suite.admin.begin() as db:
        before = db.scalar(text('SELECT revision FROM location_operations WHERE location_id=:id'), {'id':edge.loc})
        session_before = db.execute(text('SELECT token_digest,last_seen_at FROM identity.sessions ORDER BY token_digest')).all()
        db.execute(text("UPDATE edge_devices SET last_contact_at=clock_timestamp()-interval '46 seconds' WHERE id=:id"), {'id':edge.device})
    assert mark_offline() >= 1
    events = event_batch(edge.clients['a_owner'].client.cookies.get('restaurant_session'), edge.loc, before)
    assert any(row['event_type']=='edge.offline' for row in events)
    assert all(row['location_id']==str(edge.loc) for row in events)
    assert mark_offline() == 0
    with edge.suite.admin.connect() as db:
        assert db.execute(text('SELECT token_digest,last_seen_at FROM identity.sessions ORDER BY token_digest')).all() == session_before


def test_exact_body_malformed_headers_and_no_raw_video(edge):
    configure(edge)
    path = '/v1/edge/heartbeat'
    body = encode({'camera':'ONLINE','inference':'RUNNING','queue_pending':0})
    request = sign('POST', 'https://testserver'+path, body, edge.kid, edge.key)
    assert edge.client.post(path, content=body+b' ', headers=dict(request.headers)).status_code == 401
    duplicated = list(request.headers.items())+[('x-edge-key-id', str(edge.kid))]
    assert edge.client.post(path, content=body, headers=duplicated).status_code == 400
    private = send(edge, path, {'camera':'ONLINE','inference':'RUNNING','queue_pending':0,'video':'private-fixture-marker'})
    assert private.status_code == 422 and 'private-fixture-marker' not in private.text
    event = observation(edge)
    wire = event.model_dump(mode='json')
    wire['camera_password'] = 'private-fixture-marker'
    result = send(edge, '/v1/edge/batches', {'events':[wire]})
    assert result.status_code == 422 and 'private-fixture-marker' not in result.text


def test_revoke_and_ingest_serialized_by_device_lock(edge):
    configure(edge)
    event = observation(edge)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ingestion = pool.submit(batch, edge, event)
        revocation = pool.submit(command, edge, action='revoke')
        results = ingestion.result(), revocation.result()
    assert results[1].status_code == 200
    assert results[0].status_code in {200,401,403}
    assert batch(edge, event).status_code == 401
    with edge.suite.admin.connect() as db:
        assert db.scalar(text('SELECT count(*) FROM edge_receipts WHERE device_id=:id'), {'id':edge.device}) in {0,1}


@pytest.mark.parametrize('invalid', [{'version':2},{'version':True},{'kind':'unsupported'},{'state':'UNSUPPORTED'}])
def test_owned_invalid_event_terminal_receipt_and_new_context_required(edge, invalid):
    configure(edge)
    generation = uuid4()
    first = observation(edge,1).model_copy(update={'source_generation':generation})
    assert batch(edge,first).status_code == 200
    bad = observation(edge,2).model_dump(mode='json')
    bad.update(invalid,source_generation=str(generation))
    result = send(edge,'/v1/edge/batches',{'events':[bad]})
    assert result.status_code == 200, result.text
    assert result.json()['receipts'][0]['disposition'] == 'rejected'
    assert result.json()['receipts'][0]['reason'] == 'INVALID'
    with edge.suite.admin.connect() as db:
        payload = db.scalar(text('SELECT payload FROM edge_receipts WHERE event_id=:id'),{'id':bad['event_id']})
        assert set(payload)=={'event_id','device_id','stream_id','sequence','organization_id','location_id',
                              'binding_id','camera_id','table_id','source_generation','_rejected'}
        row = db.execute(text('SELECT state,needs_context FROM edge_shadows WHERE binding_id=:id'),{'id':edge.binding['id']}).one()
        assert row.state=='UNKNOWN' and row.needs_context
    blocked = observation(edge,3).model_copy(update={'source_generation':generation})
    assert batch(edge,blocked).json()['receipts'][0]['reason']=='CONTEXT_REQUIRED'
    fresh = observation(edge,4)
    assert batch(edge,fresh).json()['receipts'][0]['disposition']=='shadow'
    assert send(edge,'/v1/edge/batches',{'events':[bad]}).json()['receipts'][0]['disposition']=='rejected'


def test_unhealthy_source_and_retired_binding_never_display_current_shadow(edge):
    configure(edge)
    assert batch(edge,observation(edge)).status_code == 200
    def view():
        return edge.clients['a_owner'].request('GET',f'/v1/locations/{edge.loc}/devices').json()['shadows'][0]
    assert not view()['stale']
    assert send(edge,'/v1/edge/heartbeat',{'camera':'OFFLINE','inference':'DEGRADED','queue_pending':0}).status_code==200
    assert view()['stale']
    assert send(edge,'/v1/edge/heartbeat',{'camera':'ONLINE','inference':'RUNNING','queue_pending':0}).status_code==200
    assert not view()['stale']
    assert command(edge,action='assign',camera_id=str(edge.camera),table_id=str(edge.table),zone_revision=1,
        profile_revision=1,profile_sha256='a'*64,model_sha256='b'*64).status_code==200
    assert view()['stale']
