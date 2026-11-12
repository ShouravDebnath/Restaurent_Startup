"""Commit barrier around the existing Phase 5 pure engine.

A candidate engine is visible only after its events and checkpoint are committed.
After restart evidence is rebuilt from UNKNOWN under a fresh online lease; old
queued events retain their original IDs, stream sequence and timestamps.
"""

import copy
from dataclasses import asdict
from uuid import uuid4

from restaurant_edge.evidence_protocol import rules_digest
from restaurant_edge.evidence_window import EvidenceWindows


class DurableEngine:
    def __init__(self, engine, outbox, configuration):
        self.engine, self.outbox, self.configuration = engine, outbox, configuration
        self.source_generation = str(uuid4())
        self.windows = EvidenceWindows()
        self.sent = {}
        self.frame_age_seconds = None
        self.workflow_revision = None

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
        windows, sent = copy.deepcopy(self.windows), copy.deepcopy(self.sent)
        generation = self.source_generation
        workflow = self.configuration.get('workflow', {})
        negotiated = (2 in self.configuration.get('protocol_versions', []) and workflow.get('mode') == 'ASSISTED_REVIEW')
        workflow_revision = workflow.get('revision') if negotiated else None
        if operation == 'step' and args[3] == candidate.generation and args[4] <= candidate.sequence:
            return False
        if workflow_revision != self.workflow_revision:
            windows.reset(); sent.clear()
        if operation == 'step':
            if candidate.generation is not None and args[3] != candidate.generation:
                windows.reset(); sent.clear(); generation = str(uuid4())
            windows.add(args[0], args[1], candidate.config.settings)
        elif operation == 'invalidate':
            windows.reset()
        elif operation == 'manual':
            for row in args[0]:
                key = str(row['id'])
                if key in candidate.tables and row['operational_revision'] > candidate.tables[key].manual_revision:
                    windows.reset(key)
        previous_number = candidate.event_number
        result = getattr(candidate, operation)(*args)
        # Restore only an explicitly mapped episode from this same uninterrupted run.
        # A restart/new source generation needs new review, never a fabricated visit.
        if operation == 'manual' and negotiated:
            for row in args[0]:
                key = str(row['id'])
                matching = next((s for s in workflow.get('sessions', []) if s['table_id'] == key
                    and s['source_generation'] == generation), None)
                if matching and key in candidate.tables and row['current_state'] == 'OCCUPIED':
                    candidate.tables[key].session_id = matching['source_episode']
                    candidate.tables[key].departure_emitted = False
        events = [event for event in candidate.events if event['number']>previous_number]
        if candidate.event_number-previous_number != len(events):
            raise RuntimeError('Transition group exceeds durable event capacity')
        bindings = {str(row['table_id']): row for row in self.configuration['bindings']}
        assignments = {str(row['id']): row for row in self.configuration['assignments']}
        regions = {str(r.table_id): r for r in candidate.config.regions}
        def summary(key):
            return windows.summary(key, regions[key], candidate.config.settings,
                                   self.frame_age_seconds if operation == 'step' else None)
        def v2(key):
            return negotiated and str(bindings[key]['id']) in workflow.get('bindings', [])
        def enrich(message, key, evidence_type):
            if v2(key):
                message.update(version=2,evidence_type=evidence_type,workflow_revision=workflow_revision,
                    rules_sha256=rules_digest(candidate.config.settings.model_dump()),evidence=summary(key))
            return message
        messages = []
        for event in events:
            binding = bindings[event['table_id']]
            assignment = assignments[str(binding['assignment_id'])]
            reason = event['reason']
            reason = {'STABLE_PERSON_EVIDENCE': 'STABLE_PERSON', 'POSSIBLE_DEPARTURE': 'STABLE_VACANCY',
                      'PREVIOUS_RESET_STILL_UNCONFIRMED': 'STABLE_VACANCY'}.get(reason, reason)
            allowed = {'STABLE_PERSON', 'STABLE_VACANCY', 'NOT_OBSERVED', 'OBSERVATION_GAP',
                       'SOURCE_CHANGED', 'CAMERA_OFFLINE', 'CURRENT_HUMAN_STATE', 'LEASE_EXPIRED'}
            message = {'event_id': event['event_id'], 'binding_id': str(binding['id']),
                'binding_epoch': str(binding['epoch']), 'camera_id': event['camera_id'], 'table_id': event['table_id'],
                'occurred_at': event['processing_utc'], 'state': event['new_state'], 'reason': reason if reason in allowed else 'UNCERTAIN',
                'occupancy_session_id': event['occupancy_session_id'],
                'manual_revision': max(0, candidate.tables[event['table_id']].manual_revision),
                'zone_revision': binding['zone_revision'], 'profile_revision': assignment['profile_revision'],
                'profile_sha256': assignment['profile_sha256'], 'model_sha256': assignment['model_sha256'],
                'policy_revision': assignment['policy_revision'], 'frame_sequence': max(0,candidate.sequence),
                'source_generation': generation}
            messages.append(enrich(message, event['table_id'],
                'transition' if reason in {'STABLE_PERSON','STABLE_VACANCY'} else 'snapshot'))
        # No transition is required for current table evidence, including while cleaning.
        for key, table in candidate.tables.items():
            if not v2(key):
                continue
            # Re-reading unchanged human metadata is not a new observation or
            # a source failure. A changed manual revision still clears evidence.
            if operation == 'manual' and table.manual_revision == self.engine.tables[key].manual_revision:
                continue
            q=summary(key)
            last=sent.get(key)
            now=args[1]
            if last is not None and last[1] == q['kind'] and 0<=now-last[0]<10:
                continue
            binding=bindings[key]; assignment=assignments[str(binding['assignment_id'])]
            message={'event_id':str(uuid4()),'binding_id':str(binding['id']),'binding_epoch':str(binding['epoch']),
                'camera_id':str(candidate.config.camera_id),'table_id':key,'occurred_at':args[2],
                'state':table.state,'reason':'UNCERTAIN' if q['kind']=='UNCERTAIN' else 'CURRENT_HUMAN_STATE',
                'occupancy_session_id':table.session_id,'manual_revision':max(0,table.manual_revision),
                'zone_revision':binding['zone_revision'],'profile_revision':assignment['profile_revision'],
                'profile_sha256':assignment['profile_sha256'],'model_sha256':assignment['model_sha256'],
                'policy_revision':assignment['policy_revision'],'frame_sequence':max(0,candidate.sequence),
                'source_generation':generation}
            messages.append(enrich(message,key,'snapshot'))
            sent[key]=(now,q['kind'])
        # Stored for inspection/reconciliation, never blindly restored as fresh evidence.
        checkpoint = {'version': 1, 'run_id': candidate.run_id, 'event_number': candidate.event_number,
                          'source_generation': generation,
                          'tables': {key: asdict(value) for key,value in candidate.tables.items()}}
        self.outbox.commit(messages, checkpoint)
        self.engine = candidate
        self.windows, self.sent = windows, sent
        self.source_generation, self.workflow_revision = generation, workflow_revision
        return result

    def manual(self, *args):
        return self._apply('manual', *args)

    def invalidate(self, *args):
        return self._apply('invalidate', *args)

    def step(self, *args):
        return self._apply('step', *args)
