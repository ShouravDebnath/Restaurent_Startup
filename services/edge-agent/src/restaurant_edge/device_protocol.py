"""Phase 6 wire contract. Mirrored byte-for-byte in both deployed Python packages.

Only allowlisted metadata crosses the device boundary. No image, source URI,
bounding box, traceback, arbitrary attributes, or human credential field exists.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_BODY = 131072
MAX_EVENTS = 100
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Positive = Annotated[int, Field(strict=True, ge=1, le=2147483647)]
State = Literal['UNKNOWN', 'AVAILABLE', 'OCCUPIED', 'RESET_PENDING', 'CLEANING', 'OUT_OF_SERVICE']


class Wire(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, allow_inf_nan=False)


class Observation(Wire):
    version: Literal[1] = 1
    event_id: UUID
    device_id: UUID
    stream_id: UUID
    sequence: Positive
    organization_id: UUID
    location_id: UUID
    binding_id: UUID
    binding_epoch: UUID
    camera_id: UUID
    table_id: UUID
    occurred_at: datetime
    kind: Literal['shadow', 'fixture_arrive', 'fixture_depart'] = 'shadow'
    state: State
    reason: Literal['STABLE_PERSON', 'STABLE_VACANCY', 'NOT_OBSERVED', 'OBSERVATION_GAP',
                    'SOURCE_CHANGED', 'CAMERA_OFFLINE', 'CURRENT_HUMAN_STATE',
                    'UNCERTAIN', 'FIXTURE', 'LEASE_EXPIRED']
    occupancy_session_id: UUID | None = None
    manual_revision: Annotated[int, Field(strict=True, ge=0)]
    zone_revision: Positive
    profile_revision: Positive
    profile_sha256: Digest
    model_sha256: Digest
    policy_revision: Positive
    frame_sequence: Annotated[int, Field(strict=True, ge=0)]
    source_generation: UUID

    @field_validator('version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('Integer protocol version required')
        return value

    @field_validator('occurred_at')
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None or value.utcoffset().total_seconds() != 0:
            raise ValueError('UTC timestamp required')
        return value.astimezone(UTC)


class Batch(Wire):
    events: Annotated[list[Observation], Field(min_length=1, max_length=MAX_EVENTS)]


class OwnedEnvelope(Wire):
    """Safe identity only for a terminal rejection. Never stores invalid raw fields."""
    event_id: UUID
    device_id: UUID
    stream_id: UUID
    sequence: Positive
    organization_id: UUID
    location_id: UUID
    binding_id: UUID
    camera_id: UUID
    table_id: UUID
    source_generation: UUID


def batch_items(body: bytes):
    value = parse_json(body)
    if not isinstance(value, dict) or set(value) != {'events'} or not isinstance(value['events'], list):
        raise ValueError('Invalid batch envelope')
    if not 1 <= len(value['events']) <= MAX_EVENTS:
        raise ValueError('Invalid event count')
    items, ids = [], set()
    for raw in value['events']:
        if not isinstance(raw, dict) or set(raw)-set(Observation.model_fields):
            raise ValueError('Unknown fields are not accepted')
        try:
            event = Observation.model_validate(raw)
            identity = str(event.event_id)
            items.append({'event': event.model_dump(mode='json'), 'sha256': fingerprint(encode(event))})
        except ValueError:
            safe = OwnedEnvelope.model_validate({key: raw[key] for key in OwnedEnvelope.model_fields if key in raw})
            identity = str(safe.event_id)
            items.append({'event': dict(safe.model_dump(mode='json'), _rejected=True),
                          'sha256': fingerprint(encode(raw))})
        if identity in ids:
            raise ValueError('Duplicate event IDs')
        ids.add(identity)
    return items


class Health(Wire):
    camera: Literal['ONLINE', 'OFFLINE', 'COMPLETE', 'UNKNOWN']
    inference: Literal['RUNNING', 'STOPPED', 'DEGRADED', 'UNKNOWN']
    queue_pending: Annotated[int, Field(strict=True, ge=0, le=100000)]
    frame_age_ms: Annotated[int | None, Field(strict=True, ge=0, le=3600000)] = None
    inference_ms: Annotated[float | None, Field(ge=0, le=3600000)] = None
    memory_bytes: Annotated[int | None, Field(strict=True, ge=0, le=1099511627776)] = None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def parse_json(body: bytes):
    if len(body) > MAX_BODY:
        raise ValueError('Message too large')
    return json.loads(body, object_pairs_hook=_unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite number')))


def encode(value) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode='json')
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def fingerprint(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()
