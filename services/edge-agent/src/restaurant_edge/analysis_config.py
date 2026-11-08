"""Private, scoped immutable seating revisions. No PostgreSQL writes."""

import hashlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from restaurant_edge.association import valid_polygon


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, allow_inf_nan=False)


class Settings(Strict):
    entry_score: float = Field(default=.6, ge=.05, le=1)
    retention_score: float = Field(default=.4, ge=.05, le=1)
    arrival_seconds: float = Field(default=10, ge=2, le=120)
    departure_seconds: float = Field(default=25, ge=5, le=300)
    max_gap_seconds: float = Field(default=2, ge=.5, le=3)
    result_max_age: float = Field(default=2, ge=.5, le=5)
    border_margin: float = Field(default=.015, ge=0, le=.1)
    min_samples: int = Field(default=3, ge=3, le=30)
    coverage_step_seconds: float = Field(default=1, ge=.2, le=2)
    minimum_coverage: float = Field(default=.8, ge=.5, le=1)

    @model_validator(mode='after')
    def thresholds(self):
        if self.retention_score > self.entry_score:
            raise ValueError('Retention must not exceed entry score')
        return self


class Region(Strict):
    table_id: UUID
    zone_id: UUID
    zone_revision: int = Field(ge=1)
    seating: list[tuple[float, float]] = Field(min_length=3, max_length=64)
    exclusions: list[list[tuple[float, float]]] = Field(default_factory=list, max_length=8)
    anchor: Literal['feet', 'torso'] = 'torso'
    visibility_reviewed: bool = Field(default=False, strict=True)

    @model_validator(mode='after')
    def polygons(self):
        if not all(valid_polygon(p) for p in [self.seating, *self.exclusions]):
            raise ValueError('Invalid normalized seating/exclusion polygon')
        return self


class AnalysisConfig(Strict):
    organization_id: UUID
    location_id: UUID
    camera_id: UUID
    source_width: int = Field(ge=1, le=4096)
    source_height: int = Field(ge=1, le=2160)
    model: Literal['yolox_tiny', 'rfdetr_nano'] = 'yolox_tiny'
    settings: Settings = Field(default_factory=Settings)
    regions: list[Region] = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def unique_tables(self):
        if len({r.table_id for r in self.regions}) != len(self.regions):
            raise ValueError('One primary zone per table is required')
        return self


class Conflict(Exception):
    pass


class ConfigStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()

    def directory(self, scope):
        return self.root.joinpath(*(str(UUID(str(v))) for v in scope))

    def load(self, scope):
        directory = self.directory(scope)
        with self.lock:
            try:
                revision = int((directory / 'current').read_text())
            except FileNotFoundError:
                return None
            record = json.loads((directory / f'{revision:06d}.json').read_text(encoding='utf-8'))
            config = AnalysisConfig.model_validate(record['config'])
            if tuple(map(str, scope)) != tuple(str(getattr(config, k)) for k in ('organization_id', 'location_id', 'camera_id')):
                raise ValueError('Configuration scope mismatch')
            return record

    def save(self, config, expected, request_key, actor):
        scope = (config.organization_id, config.location_id, config.camera_id)
        directory = self.directory(scope)
        payload = config.model_dump(mode='json')
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        request_key = str(UUID(str(request_key)))
        with self.lock:
            directory.mkdir(parents=True, exist_ok=True)
            for path in directory.glob('*.json'):
                old = json.loads(path.read_text(encoding='utf-8'))
                if old['request_key'] == request_key:
                    if old['fingerprint'] != fingerprint or old['expected_revision'] != expected or old['actor'] != actor:
                        raise Conflict('Request identity conflict')
                    return old
            current = self.load(scope)
            revision = current['revision'] if current else 0
            if expected != revision or revision >= 500:
                raise Conflict('Revision conflict or history quota reached')
            record = {'revision': revision + 1, 'config': payload, 'request_key': request_key,
                      'expected_revision': expected, 'fingerprint': fingerprint, 'actor': actor,
                      'created_at': datetime.now(UTC).isoformat()}
            try:
                with (directory / f'{revision + 1:06d}.json').open('x', encoding='utf-8') as handle:
                    json.dump(record, handle, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
            except FileExistsError:
                raise Conflict('Concurrent or interrupted revision requires review') from None
            pointer = directory / (uuid4().hex + '.tmp')
            pointer.write_text(str(revision + 1), encoding='ascii')
            os.replace(pointer, directory / 'current')
            return record
