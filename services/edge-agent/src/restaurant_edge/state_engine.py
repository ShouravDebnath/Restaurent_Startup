"""Pure time-driven shadow lifecycle. Never writes operational table states."""

import hashlib
import math
from collections import deque
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class TableState:
    state: str = 'UNKNOWN'
    since: float | None = None
    occupied_since: float | None = None
    session_id: str | None = None
    departure_emitted: bool = False
    manual_revision: int = -1
    protected: bool = False
    manual_since: str | None = None
    manual_cutoff: float = -1
    candidate: str | None = None
    candidate_since: float = 0
    samples: int = 0
    covered_seconds: float = 0
    last_sample: float | None = None
    last_positive: float | None = None
    verified: bool = False
    reason: str = 'NOT_OBSERVED'
    observation: str = 'UNCERTAIN'
    count: int | None = None
    score: float | None = None
    quality: str = 'LOW'
    association_quality: float | None = None


class StateEngine:
    def __init__(self, config):
        self.config = config
        self.tables = {str(r.table_id): TableState() for r in config.regions}
        self.run_id = str(uuid4())
        self.events = deque(maxlen=1000)
        self.event_number = 0
        self.generation = None
        self.sequence = -1
        self.last_time = None
        self.model_sha256, self.config_revision, self.media_seconds = None, None, None
        self.config_fingerprint = hashlib.sha256(config.model_dump_json().encode()).hexdigest()

    def change(self, table_id, state, now, utc, reason):
        table = self.tables[table_id]
        table.reason = reason
        if table.state == state:
            return
        previous = table.state
        table.state, table.since = state, now
        self.event_number += 1
        self.events.append({'event_id': str(uuid4()), 'number': self.event_number,
            'analysis_run_id': self.run_id, 'table_id': table_id, 'previous_state': previous,
            'new_state': state, 'processing_utc': utc, 'reason': reason,
            'occupancy_session_id': table.session_id, 'source': 'ai_local_shadow',
            'authoritative': False, 'occupancy_probability': None,
            'organization_id': str(self.config.organization_id), 'location_id': str(self.config.location_id),
            'camera_id': str(self.config.camera_id), 'model': self.config.model,
            'model_sha256': self.model_sha256, 'config_revision': self.config_revision,
            'config_fingerprint': self.config_fingerprint,
            'zone_revision': next(r.zone_revision for r in self.config.regions if str(r.table_id) == table_id),
            'generation': self.generation, 'sequence': self.sequence, 'media_seconds': self.media_seconds})

    def manual(self, rows, now, utc):
        for row in rows:
            key = str(row['id'])
            if key not in self.tables:
                continue
            table = self.tables[key]
            revision = row['operational_revision']
            if revision <= table.manual_revision:
                continue
            table.manual_revision = revision
            if row['state_source'] != 'manual':
                continue
            state = row['current_state']
            if state not in {'AVAILABLE', 'UNKNOWN', 'OCCUPIED', 'RESET_PENDING', 'CLEANING', 'OUT_OF_SERVICE'}:
                raise ValueError('Unsupported manual state')
            table.protected = state in {'AVAILABLE', 'CLEANING', 'OUT_OF_SERVICE'}
            table.manual_since = row['state_since']
            table.manual_cutoff = now
            table.candidate, table.samples = None, 0
            table.covered_seconds = 0
            table.session_id, table.occupied_since = None, None
            table.departure_emitted = False
            self.change(key, state, now, utc, 'CURRENT_HUMAN_STATE')
            table.verified = False

    def invalidate(self, reason, now, utc):
        for key, table in self.tables.items():
            table.candidate, table.samples, table.last_sample = None, 0, None
            table.covered_seconds = 0
            table.verified, table.count, table.score, table.quality = False, None, None, 'LOW'
            table.observation, table.reason = 'UNCERTAIN', reason
            if not table.protected:
                self.change(key, 'UNKNOWN', now, utc, reason)

    def step(self, observations, now, utc, generation, sequence):
        if not math.isfinite(now) or (self.last_time is not None and now < self.last_time):
            raise ValueError('Monotonic analysis time required')
        if generation == self.generation and sequence <= self.sequence:
            return False
        if self.last_time is not None and now - self.last_time > self.config.settings.max_gap_seconds:
            self.invalidate('OBSERVATION_GAP', now, utc)
        if self.generation is not None and generation != self.generation:
            self.invalidate('SOURCE_GENERATION_CHANGED', now, utc)
        self.generation, self.sequence, self.last_time = generation, sequence, now
        settings = self.config.settings
        for key, table in self.tables.items():
            if now < table.manual_cutoff:
                continue
            observation = observations[key]
            gap = table.last_sample is not None and now - table.last_sample > settings.max_gap_seconds
            elapsed = now - table.last_sample if table.last_sample is not None else 0
            if gap:
                table.candidate, table.samples = None, 0
                table.covered_seconds = 0
            table.last_sample = now
            table.observation, table.count = observation.kind, observation.count
            table.score, table.quality, table.reason = observation.score, observation.quality, observation.reason
            table.association_quality = observation.association_quality
            table.verified = observation.kind != 'UNCERTAIN'
            if table.protected and table.state in {'CLEANING', 'OUT_OF_SERVICE'}:
                if observation.kind == 'POSITIVE':
                    table.reason = 'PERSON_DURING_PROTECTED_MANUAL_STATE'
                continue
            if observation.kind == 'UNCERTAIN':
                table.candidate, table.samples = None, 0
                table.covered_seconds = 0
                if not table.protected and (table.last_positive is None or now - table.last_positive > settings.max_gap_seconds):
                    self.change(key, 'UNKNOWN', now, utc, observation.reason)
                continue
            if observation.kind == 'POSITIVE':
                table.last_positive = now
            if table.candidate != observation.kind:
                table.candidate, table.candidate_since, table.samples = observation.kind, now, 1
                table.covered_seconds = 0
            else:
                table.samples += 1
                table.covered_seconds += min(elapsed, settings.coverage_step_seconds)
            duration = now - table.candidate_since
            if (table.samples < settings.min_samples or duration <= 0
                or table.covered_seconds / duration < settings.minimum_coverage):
                continue
            if observation.kind == 'POSITIVE' and table.covered_seconds >= settings.arrival_seconds:
                if table.session_id is None or table.departure_emitted:
                    table.session_id, table.occupied_since = str(uuid4()), now
                    table.departure_emitted = False
                table.protected, table.manual_since = False, None
                self.change(key, 'OCCUPIED', now, utc, 'STABLE_PERSON_EVIDENCE')
            elif observation.kind == 'VACANT' and table.covered_seconds >= settings.departure_seconds and table.session_id:
                if not table.departure_emitted:
                    self.change(key, 'RESET_PENDING', now, utc, 'POSSIBLE_DEPARTURE')
                    table.departure_emitted = True
                elif table.state == 'UNKNOWN':
                    self.change(key, 'RESET_PENDING', now, utc, 'PREVIOUS_RESET_STILL_UNCONFIRMED')
        return True

    def snapshot(self, now):
        return [{'table_id': key, 'state': t.state, 'state_elapsed_seconds': 0 if t.since is None else max(0, now - t.since),
                 'occupied_elapsed_seconds': None if t.occupied_since is None else max(0, now - t.occupied_since),
                 'human_state_since': t.manual_since, 'manual_revision': t.manual_revision,
                 'verified': t.verified, 'observation': t.observation, 'visible_person_estimate': t.count,
                 'detector_score': t.score, 'evidence_quality': t.quality, 'reason': t.reason,
                 'association_quality': t.association_quality, 'covered_evidence_seconds': t.covered_seconds,
                 'occupancy_probability': None, 'authoritative': False}
                for key, t in self.tables.items()]
