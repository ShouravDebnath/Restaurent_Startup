"""HTTPS-only machine API and CSRF-protected manager administration."""

import asyncio
import base64
import hashlib
from typing import Annotated, Literal
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, HTTPException, Request
from http_message_signatures import HTTPMessageSignaturesException
from pydantic import Field, ValidationError, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from restaurant_api.edge_models import (
    EdgeAssignment,
    EdgeBinding,
    EdgeDevice,
    EdgeHealth,
    EdgeKey,
    EdgeReceipt,
    EdgeShadow,
)
from restaurant_api.edge_protocol import (
    MAX_BODY,
    Digest,
    Health,
    Wire,
    batch_items,
    encode,
    fingerprint,
    parse_json,
)
from restaurant_api.edge_signatures import verify
from restaurant_api.routes import Auth, Write
from restaurant_api.security import CONFIGURATORS, Db, location_access
from restaurant_api.settings import get_settings

router = APIRouter(prefix='/v1', tags=['edge devices'])


def query(db, function, **values):
    """Function names are source constants, never client-controlled identifiers."""
    placeholders = ','.join(f':{name}' for name in values)
    try:
        return db.scalar(text(f'SELECT security.{function}({placeholders})'), values)
    except DBAPIError as error:
        code = getattr(error.orig, 'sqlstate', '')
        if code == '42501':
            raise HTTPException(403, 'Device operation is not authorized.') from None
        if code == '54000':
            raise HTTPException(429, 'Pairing limit reached; try later.') from None
        if code in {'23505', '23514', '22023', '22P02', '22003'}:
            raise HTTPException(409, 'Device request conflicts with its current configuration.') from None
        raise


def enabled():
    if not get_settings().edge_sync_enabled:
        raise HTTPException(503, 'Device synchronization is not enabled.')


async def bounded(request):
    enabled()
    if request.url.scheme != 'https':
        raise HTTPException(403, 'Verified HTTPS is required for devices.')
    if request.headers.get('content-encoding') or request.headers.get('origin') or request.headers.get('cookie'):
        raise HTTPException(403, 'Device requests cannot use browser credentials or compression.')
    if len(request.scope['headers']) > 32 or any(len(k)+len(v)>4096 for k, v in request.scope['headers']):
        raise HTTPException(413, 'Device headers are too large.')
    names = [key.lower() for key, _ in request.scope['headers']]
    if len(names) != len(set(names)):
        raise HTTPException(400, 'Duplicate device headers are not accepted.')
    body = bytearray()
    try:
        async with asyncio.timeout(5):
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    raise HTTPException(413, 'Device message is too large.')
    except TimeoutError:
        raise HTTPException(408, 'Device message timed out.') from None
    if request.headers.get('content-type') != 'application/json':
        raise HTTPException(415, 'JSON is required.')
    return bytes(body)


def payload(model, body):
    try:
        return model.model_validate(parse_json(body))
    except (ValueError, ValidationError, TypeError):
        raise HTTPException(422, 'Device message fields are invalid.') from None


def authenticate(request, db, body, *, pairing=False):
    try:
        key_id = UUID(request.headers.get('x-edge-key-id', ''))
        public = query(db, 'edge_public_key', key_=key_id, pairing_=pairing)
        if public is None:
            raise ValueError('Unknown key')
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public, validate=True))
        nonce = verify(request.method, str(request.url), request.headers, body, key_id, key)
    except (HTTPMessageSignaturesException, ValueError, TypeError, KeyError):
        # Do not expose cryptographic parser exceptions or credential inputs.
        raise HTTPException(401, 'Device authentication failed.') from None
    if pairing:
        query(db, 'edge_pair_accept', key_=key_id, nonce_=nonce)
    else:
        query(db, 'edge_accept', key_=key_id, nonce_=nonce)
    return key_id


class PairStart(Wire):
    request_id: UUID
    key_id: UUID
    public_key: Annotated[str, Field(min_length=44, max_length=44)]


class PairProof(Wire):
    request_id: UUID
    challenge: Annotated[str, Field(pattern=r'^[0-9a-f]{32}$')]


@router.post('/edge/pairings')
async def pair_start(request: Request, db: Db):
    body = await bounded(request)
    value = payload(PairStart, body)
    try:
        public = base64.b64decode(value.public_key, validate=True)
        Ed25519PublicKey.from_public_bytes(public)
    except ValueError:
        raise HTTPException(422, 'A valid Ed25519 public key is required.') from None
    peer = hashlib.sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()
    return query(db, 'edge_pair_start', id_=value.request_id, key_=value.key_id,
                 pub_=value.public_key, fp_=fingerprint(public), peer_=peer)


@router.post('/edge/pairings/proof')
async def pair_proof(request: Request, db: Db):
    body = await bounded(request)
    authenticate(request, db, body, pairing=True)
    value = payload(PairProof, body)
    return query(db, 'edge_pair_prove', id_=value.request_id, challenge_=value.challenge)


@router.post('/edge/events')
@router.post('/edge/batches')
async def batches(request: Request, db: Db):
    body = await bounded(request)
    authenticate(request, db, body)
    try:
        items = batch_items(body)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Device batch envelope or fields are invalid.') from None
    return query(db, 'edge_ingest', items_=encode(items).decode(), demo_=get_settings().demo_mode)


@router.post('/edge/heartbeat')
async def heartbeat(request: Request, db: Db):
    body = await bounded(request)
    authenticate(request, db, body)
    value = payload(Health, body)
    if get_settings().app_env != 'development':
        raise HTTPException(403, 'The initial processing lease is for local development only.')
    return query(db, 'edge_heartbeat', metrics_=encode(value).decode())


class Manage(Wire):
    action: Literal['approve', 'rotate', 'revoke', 'processing', 'assign']
    device_id: UUID | None = None
    expected_revision: Annotated[int | None, Field(strict=True, ge=1)] = None
    request_id: UUID | None = None
    fingerprint: Digest | None = None
    label: Annotated[str | None, Field(min_length=1, max_length=80, pattern=r'^[^\x00-\x1f]+$')] = None
    purpose: Literal['AI_SHADOW', 'SYNTHETIC_WORKFLOW_TEST'] | None = None
    enabled: bool | None = None
    camera_id: UUID | None = None
    table_id: UUID | None = None
    zone_revision: Annotated[int | None, Field(strict=True, ge=1)] = None
    profile_revision: Annotated[int | None, Field(strict=True, ge=1)] = None
    profile_sha256: Digest | None = None
    model_sha256: Digest | None = None

    @model_validator(mode='after')
    def required_fields(self):
        required = {'approve': ['request_id', 'fingerprint', 'label', 'purpose'],
                    'rotate': ['request_id', 'fingerprint'], 'revoke': [], 'processing': ['enabled'],
                    'assign': ['camera_id', 'table_id', 'zone_revision', 'profile_revision',
                               'profile_sha256', 'model_sha256']}[self.action]
        if self.action != 'approve':
            required += ['device_id', 'expected_revision']
        if any(getattr(self, key) is None for key in required):
            raise ValueError('Required command fields are missing')
        return self


@router.post('/locations/{location_id}/devices/commands')
def manage(location_id: UUID, value: Manage, identity: Write, db: Db):
    enabled()
    location_access(db, identity, location_id, CONFIGURATORS)
    return query(db, 'edge_manage', loc_=location_id, action_=value.action,
                 value_=encode(value).decode(), demo_=get_settings().demo_mode)


@router.get('/locations/{location_id}/devices')
def devices(location_id: UUID, identity: Auth, db: Db):
    enabled()
    _, member = location_access(db, identity, location_id)
    device_rows = db.scalars(select(EdgeDevice).where(EdgeDevice.location_id == location_id)).all()
    health_rows = {row.device_id: row for row in db.scalars(select(EdgeHealth).where(EdgeHealth.location_id == location_id))}
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    items = []
    available = {}
    for row in device_rows:
        health = health_rows.get(row.id)
        online = row.status == 'ACTIVE' and row.last_contact_at is not None and (now-row.last_contact_at).total_seconds()<=45
        metrics = health.metrics if health else None
        available[row.id] = (online and row.processing_enabled and health is not None
            and (now-health.measured_at).total_seconds()<=45 and metrics.get('camera')=='ONLINE'
            and metrics.get('inference')=='RUNNING')
        items.append({'id': row.id, 'label': row.label, 'purpose': row.purpose, 'status': row.status,
                          'revision': row.revision, 'processing_enabled': row.processing_enabled,
                          'last_contact_at': row.last_contact_at, 'online': online, 'metrics': metrics})
    shadows = db.execute(select(EdgeShadow, EdgeBinding.epoch, EdgeReceipt.payload)
        .join(EdgeBinding, EdgeBinding.id == EdgeShadow.binding_id)
        .join(EdgeReceipt, (EdgeReceipt.device_id == EdgeShadow.device_id) &
                          (EdgeReceipt.sequence == EdgeShadow.sequence))
        .where(EdgeShadow.location_id == location_id)).all()
    result = {'devices': items, 'server_time': now, 'shadow_only': True,
              'shadows': [{'binding_id': row.binding_id, 'sequence': row.sequence, 'state': row.state,
                               'occurred_at': row.occurred_at, 'reason': row.reason,
                               'stale': ((now-row.occurred_at).total_seconds()>30 or row.needs_context
                                   or not available.get(row.device_id,False)
                                   or payload.get('binding_epoch')!=str(epoch))}
                          for row,epoch,payload in shadows]}
    if member.role in CONFIGURATORS:
        def safe(row):
            return {column.name: getattr(row, column.name) for column in row.__table__.columns}
        result['keys'] = [safe(row) for row in db.scalars(select(EdgeKey).where(EdgeKey.location_id == location_id))]
        result['assignments'] = [safe(row) for row in db.scalars(select(EdgeAssignment).where(EdgeAssignment.location_id == location_id))]
        result['bindings'] = [safe(row) for row in db.scalars(select(EdgeBinding).where(EdgeBinding.location_id == location_id))]
    return result
