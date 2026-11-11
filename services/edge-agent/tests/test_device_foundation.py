"""Synthetic transport contracts; no camera, person footage, or business DB required."""

import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from http_message_signatures import HTTPMessageSignaturesException

from restaurant_edge.device_identity import create_identity, load_identity
from restaurant_edge.device_protocol import Observation, encode, parse_json
from restaurant_edge.device_signatures import sign, verify
from restaurant_edge.outbox import Outbox, OutboxError

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def event():
    return {'event_id': str(uuid4()), 'binding_id': str(uuid4()), 'binding_epoch': str(uuid4()),
                'camera_id': str(uuid4()), 'table_id': str(uuid4()), 'occurred_at': datetime.now(UTC).isoformat(),
                'state': 'UNKNOWN', 'reason': 'NOT_OBSERVED', 'manual_revision': 0, 'zone_revision': 1,
                'profile_revision': 1, 'profile_sha256': 'a'*64, 'model_sha256': 'b'*64,
                'policy_revision': 1, 'frame_sequence': 0, 'source_generation': str(uuid4())}


@pytest.fixture
def scope():
    return {'device_id': uuid4(), 'organization_id': uuid4(), 'location_id': uuid4()}


@pytest.mark.parametrize('stem,api,edge', [
    ('device_protocol', 'edge_protocol', 'device_protocol'),
    ('device_signatures', 'edge_signatures', 'device_signatures')])
def test_deployed_contracts_are_identical(stem, api, edge):
    canonical = (ROOT/'packages/contracts'/f'{stem}.py').read_bytes()
    assert canonical == (ROOT/'services/api/src/restaurant_api'/f'{api}.py').read_bytes()
    assert canonical == (ROOT/'services/edge-agent/src/restaurant_edge'/f'{edge}.py').read_bytes()


def test_durable_atomic_queue_restart(tmp_path, event, scope):
    path = tmp_path/'queue.sqlite3'
    with Outbox(path, **scope) as box:
        assert box.db.execute('PRAGMA synchronous').fetchone()[0] == 3
        assert box.db.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
        result = box.commit([event], {'state': 'UNKNOWN', 'cursor': 1})
        stream = box.stream_id
        assert result[0].sequence == 1
    with Outbox(path, **scope) as box:
        assert box.stream_id == stream
        assert box.pending_count == 1
        assert box.checkpoint() == {'state': 'UNKNOWN', 'cursor': 1}
        assert box.pending()[0][0]['event_id'] == event['event_id']
        result = box.commit([dict(event, event_id=str(uuid4()))], {'cursor': 2})
        assert result[0].sequence == 2


def test_failed_commit_does_not_publish_event_or_checkpoint(tmp_path, event, scope):
    with Outbox(tmp_path/'queue.sqlite3', **scope) as box:
        box.commit([event], {'cursor': 1})
        with pytest.raises(OutboxError):
            box.commit([dict(event, event_id=str(uuid4())), event], {'cursor': 3})
        assert box.pending_count == 1
        assert box.checkpoint() == {'cursor': 1}
        assert box.commit([dict(event, event_id=str(uuid4()))], {'cursor': 2})[0].sequence == 2


def test_same_device_only_and_single_owner(tmp_path, scope):
    path = tmp_path/'queue.sqlite3'
    with Outbox(path, **scope), pytest.raises(OutboxError):
        Outbox(path, **scope)
    with pytest.raises(OutboxError):
        Outbox(path, **dict(scope, device_id=uuid4()))
    assert path.exists()
    with Outbox(path, **scope):
        pass


def test_corrupt_queue_preserved(tmp_path, scope):
    path = tmp_path/'queue.sqlite3'
    original = b'not a sqlite database'
    path.write_bytes(original)
    with pytest.raises(OutboxError):
        Outbox(path, **scope)
    assert path.read_bytes() == original


def test_capacity_stops_without_eviction(tmp_path, scope, event):
    with Outbox(tmp_path/'queue.sqlite3', **scope, max_pending=1) as box:
        box.commit([event], {})
        with pytest.raises(OutboxError):
            box.commit([dict(event, event_id=str(uuid4()))], {'lost': True})
        assert box.pending()[0][0]['event_id'] == event['event_id']
        assert box.checkpoint() == {}


@pytest.mark.parametrize('mutation', ['sha256', 'sequence', 'event_id', 'disposition', 'missing'])
def test_bad_ack_keeps_original_events(tmp_path, scope, event, mutation):
    with Outbox(tmp_path/'queue.sqlite3', **scope) as box:
        box.commit([event], {})
        submitted = box.pending()
        row, sha = submitted[0]
        receipt = {'event_id': row['event_id'], 'sequence': row['sequence'], 'sha256': sha,
                       'disposition': 'shadow', 'reason': 'ACCEPTED'}
        if mutation != 'missing':
            receipt[mutation] = 'invalid'
        with pytest.raises(OutboxError):
            box.acknowledge(submitted, [] if mutation == 'missing' else [receipt])
        assert box.pending_count == 1


def test_ack_retry_and_quarantine(tmp_path, scope, event):
    with Outbox(tmp_path/'queue.sqlite3', **scope) as box:
        box.commit([event], {})
        submitted = box.pending()
        box.retry([submitted[0][0]], 100, 10)
        assert box.pending(109) == []
        assert box.pending(110) == submitted
        row, sha = submitted[0]
        receipt = {'event_id': row['event_id'], 'sequence': row['sequence'], 'sha256': sha,
                       'disposition': 'rejected', 'reason': 'INVALID'}
        box.acknowledge(submitted, [receipt])
        assert box.pending_count == 0
        assert box.db.execute('SELECT payload,status FROM events').fetchone() == (encode(row), 'quarantined')


def test_payload_immutable_even_via_sql(tmp_path, scope, event):
    with Outbox(tmp_path/'queue.sqlite3', **scope) as box:
        box.commit([event], {})
        with pytest.raises(sqlite3.DatabaseError):
            box.db.execute("UPDATE events SET payload='changed'")


def test_candidate_cannot_be_relabelled_for_another_queue(tmp_path, scope, event):
    with Outbox(tmp_path/'queue.sqlite3', **scope) as box:
        with pytest.raises(OutboxError):
            box.commit([dict(event, organization_id=str(uuid4()))], {})
        assert box.pending_count == 0
        assert box.checkpoint() is None


@pytest.mark.parametrize('during_transaction', [False,True])
def test_forced_process_exit_recovers_committed_queue(tmp_path, scope, event, during_transaction):
    worker = '''
import json,os,sys
from restaurant_edge.outbox import Outbox
data=json.load(sys.stdin)
box=Outbox(sys.argv[1],**data['scope'])
box.commit([data['event']],{'committed':True})
if data['during_transaction']:
    box.db.execute('BEGIN IMMEDIATE')
    box.db.execute("UPDATE checkpoint SET value=?",(b'{"not_committed":true}',))
    box.db.execute('UPDATE identity SET next_sequence=500')
os._exit(23)
'''
    path = tmp_path/'queue.sqlite3'
    value = {'scope':{key:str(value) for key,value in scope.items()},'event':event,
             'during_transaction':during_transaction}
    child = subprocess.run([sys.executable,'-c',worker,str(path)],input=json.dumps(value),
                           text=True,capture_output=True,check=False)
    assert child.returncode == 23
    with Outbox(path,**scope) as box:
        assert box.pending_count == 1
        assert box.checkpoint() == {'committed':True}
        assert box.pending()[0][0]['event_id'] == event['event_id']
        assert box.commit([dict(event,event_id=str(uuid4()))],{})[0].sequence == 2


@pytest.mark.parametrize('body', [b'{"x":1,"x":2}', b'{"value":NaN}', b'{"value":Infinity}', b'x'*131073],
                         ids=['duplicate', 'nan', 'infinity', 'oversize'])
def test_ambiguous_or_large_json_denied(body):
    with pytest.raises(ValueError):
        parse_json(body)


@pytest.mark.parametrize('extra', ['image', 'video', 'password', 'source_url', 'boxes', 'metadata'])
def test_no_private_payload_fields(event, scope, extra):
    row = dict(event, **{k: str(v) for k, v in scope.items()}, stream_id=str(uuid4()), sequence=1)
    row[extra] = 'private-input'
    with pytest.raises(ValueError) as error:
        Observation.model_validate(row)
    assert 'private-input' not in str(error.value)


def test_native_signature_and_digest():
    key, kid = Ed25519PrivateKey.generate(), uuid4()
    body, url = b'{"events":[]}', 'https://localhost:8443/v1/edge/batches'
    request = sign('POST', url, body, kid, key)
    assert verify('POST', url, request.headers, body, kid, key.public_key())
    for method, target, content in [('GET', url, body), ('POST', url+'/other', body),
                                    ('POST', url, b'{"changed":true}')]:
        with pytest.raises(HTTPMessageSignaturesException):
            verify(method, target, request.headers, content, kid, key.public_key())
    with pytest.raises(HTTPMessageSignaturesException):
        verify('POST', url, request.headers, body, kid, Ed25519PrivateKey.generate().public_key())


def test_stale_signature_rejected():
    key, kid = Ed25519PrivateKey.generate(), uuid4()
    url = 'https://localhost/v1/edge/heartbeat'
    request = sign('POST', url, b'{}', kid, key, now=datetime.now(UTC)-timedelta(minutes=15))
    with pytest.raises(HTTPMessageSignaturesException):
        verify('POST', url, request.headers, b'{}', kid, key.public_key())


def test_only_public_identity_in_file(tmp_path):
    class MemoryVault:
        def __init__(self):
            self.values = {}

        def get_password(self, service, user):
            return self.values.get((service, user))

        def set_password(self, service, user, value):
            self.values[service, user] = value

    vault = MemoryVault()
    path = tmp_path/'identity.json'
    identity = create_identity(path, backend=vault)
    assert load_identity(path, backend=vault)[0] == identity
    assert all(secret not in path.read_text() for secret in vault.values.values())
    with pytest.raises(RuntimeError):
        create_identity(path, backend=vault)
    value = json.loads(path.read_text())
    value['fingerprint'] = 'a'*64
    path.write_text(json.dumps(value))
    with pytest.raises(RuntimeError):
        load_identity(path, backend=vault)
