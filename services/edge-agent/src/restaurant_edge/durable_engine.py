"""Commit barrier around the existing Phase 5 pure engine.

A candidate engine is visible only after its events and checkpoint are committed.
After restart evidence is rebuilt from UNKNOWN under a fresh online lease; old
queued events retain their original IDs, stream sequence and timestamps.
"""

import copy
from dataclasses import asdict
from uuid import uuid4


class DurableEngine:
    def __init__(self, engine, outbox, configuration):
        self.engine, self.outbox, self.configuration = engine, outbox, configuration
        self.source_generation = str(uuid4())

    def __getattr__(self, key):
        return getattr(self.engine, key)

    @property
    def model_sha256(self):
        return self.engine.model_sha256

    @model_sha256.setter
    def model_sha256(self, value):
        self.engine.model_sha256 = value

    @property
    def config_revision(self):
        return self.engine.config_revision

    @config_revision.setter
    def config_revision(self, value):
        self.engine.config_revision = value

    @property
    def media_seconds(self):
        return self.engine.media_seconds

    @media_seconds.setter
    def media_seconds(self, value):
        self.engine.media_seconds = value

    def _apply(self, operation, *args):
        candidate = copy.deepcopy(self.engine)
        previous_number = candidate.event_number
        result = getattr(candidate, operation)(*args)
        events = [event for event in candidate.events if event['number']>previous_number]
        if candidate.event_number-previous_number != len(events):
            raise RuntimeError('Transition group exceeds durable event capacity')
        bindings = {str(row['table_id']): row for row in self.configuration['bindings']}
        assignments = {str(row['id']): row for row in self.configuration['assignments']}
        messages = []
        for event in events:
            binding = bindings[event['table_id']]
            assignment = assignments[str(binding['assignment_id'])]
            reason = event['reason']
            reason = {'STABLE_PERSON_EVIDENCE': 'STABLE_PERSON', 'POSSIBLE_DEPARTURE': 'STABLE_VACANCY',
                      'PREVIOUS_RESET_STILL_UNCONFIRMED': 'STABLE_VACANCY'}.get(reason, reason)
            allowed = {'STABLE_PERSON', 'STABLE_VACANCY', 'NOT_OBSERVED', 'OBSERVATION_GAP',
                       'SOURCE_CHANGED', 'CAMERA_OFFLINE', 'CURRENT_HUMAN_STATE', 'LEASE_EXPIRED'}
            messages.append({'event_id': event['event_id'], 'binding_id': str(binding['id']),
                'binding_epoch': str(binding['epoch']), 'camera_id': event['camera_id'], 'table_id': event['table_id'],
                'occurred_at': event['processing_utc'], 'state': event['new_state'], 'reason': reason if reason in allowed else 'UNCERTAIN',
                'occupancy_session_id': event['occupancy_session_id'],
                'manual_revision': max(0, candidate.tables[event['table_id']].manual_revision),
                'zone_revision': binding['zone_revision'], 'profile_revision': assignment['profile_revision'],
                'profile_sha256': assignment['profile_sha256'], 'model_sha256': assignment['model_sha256'],
                'policy_revision': assignment['policy_revision'], 'frame_sequence': max(0,candidate.sequence),
                'source_generation': self.source_generation})
        # Stored for inspection/reconciliation, never blindly restored as fresh evidence.
        checkpoint = {'version': 1, 'run_id': candidate.run_id, 'event_number': candidate.event_number,
                          'source_generation': self.source_generation,
                          'tables': {key: asdict(value) for key,value in candidate.tables.items()}}
        self.outbox.commit(messages, checkpoint)
        self.engine = candidate
        return result

    def manual(self, *args):
        return self._apply('manual', *args)

    def invalidate(self, *args):
        return self._apply('invalidate', *args)

    def step(self, *args):
        return self._apply('step', *args)
