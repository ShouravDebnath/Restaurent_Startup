"""One-owner SQLite rollback-journal outbox; immutable events and atomic checkpoints.

Pending entries are never evicted. Network activity must happen outside transactions.
Corrupt, mismatched, busy or full stores fail closed, without resetting the database.
"""

import json
import os
import shutil
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4

from restaurant_edge.device_protocol import Observation, encode, fingerprint


class OutboxError(RuntimeError):
    pass


class Outbox:
    def __init__(self, path, *, device_id, organization_id, location_id,
                 max_pending=100000, max_bytes=268435456, reserve_bytes=16777216):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.owner = threading.get_ident()
        self.max_pending, self.max_bytes, self.reserve_bytes = max_pending, max_bytes, reserve_bytes
        self.lock = None
        self.db = None
        try:
            self.lock = self.path.with_suffix('.owner').open('a+b')
            if os.name == 'nt':
                import msvcrt
                self.lock.seek(0)
                if not self.lock.read(1):
                    self.lock.write(b'0')
                    self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.db = sqlite3.connect(self.path, isolation_level=None, timeout=5)
            self.db.execute('PRAGMA journal_mode=DELETE')
            self.db.execute('PRAGMA synchronous=EXTRA')
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA busy_timeout=5000')
            if self.db.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
                raise OutboxError('Rollback journal unavailable')
            if self.db.execute('PRAGMA synchronous').fetchone()[0] != 3:
                raise OutboxError('Required durability unavailable')
            if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise OutboxError('Queue integrity check failed; preserve the file for review')
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS identity (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), device_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL, location_id TEXT NOT NULL,
                    stream_id TEXT NOT NULL, next_sequence INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, sequence INTEGER UNIQUE NOT NULL,
                    payload BLOB NOT NULL, sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','delivered','quarantined')),
                    attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
                    disposition TEXT, reason TEXT);
                CREATE TABLE IF NOT EXISTS checkpoint (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), value BLOB NOT NULL);
                CREATE TRIGGER IF NOT EXISTS immutable_event BEFORE UPDATE OF
                    event_id,sequence,payload,sha256 ON events BEGIN
                    SELECT RAISE(ABORT,'immutable event'); END;
            ''')
            identity = self.db.execute('SELECT * FROM identity').fetchone()
            scope = tuple(str(x) for x in (device_id, organization_id, location_id))
            if identity is None:
                self.db.execute('INSERT INTO identity VALUES (1,?,?,?,?,1)', (*scope, str(uuid4())))
            elif identity[1:4] != scope:
                raise OutboxError('Queue belongs to another device or location')
            self.device_id, self.organization_id, self.location_id = scope
            self.stream_id = self.db.execute('SELECT stream_id FROM identity').fetchone()[0]
        except Exception as error:
            self.close()
            if isinstance(error, OutboxError):
                raise
            raise OutboxError('Queue unavailable; existing files were preserved') from None

    def _owned(self):
        if threading.get_ident() != self.owner or self.db is None:
            raise OutboxError('Queue must be used by its owning thread')

    @property
    def pending_count(self):
        self._owned()
        return self.db.execute("SELECT count(*) FROM events WHERE status='pending'").fetchone()[0]

    def commit(self, candidates, checkpoint):
        """Allocate sequence and save transitions + engine context in ONE durable commit."""
        self._owned()
        if self.pending_count + len(candidates) > self.max_pending:
            raise OutboxError('Queue capacity reached; processing must pause')
        if shutil.disk_usage(self.path.parent).free < self.reserve_bytes:
            raise OutboxError('Disk reserve reached; processing must pause')
        checkpoint_bytes = encode(checkpoint)
        if len(checkpoint_bytes) > 1048576:
            raise OutboxError('Checkpoint too large')
        committed = []
        try:
            self.db.execute('BEGIN IMMEDIATE')
            sequence = self.db.execute('SELECT next_sequence FROM identity').fetchone()[0]
            for candidate in candidates:
                for field in ('device_id', 'organization_id', 'location_id', 'stream_id'):
                    if field in candidate and str(candidate[field]) != str(getattr(self, field)):
                        raise OutboxError('Candidate scope differs from its immutable queue identity')
                value = dict(candidate, device_id=self.device_id, organization_id=self.organization_id,
                             location_id=self.location_id, stream_id=self.stream_id, sequence=sequence)
                event = Observation.model_validate(value)
                payload = encode(event)
                if len(payload) > 8192:
                    raise OutboxError('Event too large')
                self.db.execute("INSERT INTO events(event_id,sequence,payload,sha256,status) "
                                "VALUES (?,?,?,?,'pending')",
                                (str(event.event_id), sequence, payload, fingerprint(payload)))
                committed.append(event)
                sequence += 1
            self.db.execute('UPDATE identity SET next_sequence=?', (sequence,))
            self.db.execute('INSERT INTO checkpoint VALUES(1,?) ON CONFLICT(singleton) '
                            'DO UPDATE SET value=excluded.value', (checkpoint_bytes,))
            size = self.db.execute('PRAGMA page_count').fetchone()[0] * self.db.execute(
                'PRAGMA page_size').fetchone()[0]
            if size > self.max_bytes:
                raise OutboxError('Queue disk quota reached; processing must pause')
            self.db.execute('COMMIT')
            return committed
        except Exception as error:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            if isinstance(error, OutboxError):
                raise
            raise OutboxError('Event/checkpoint commit failed; do not publish the transition') from None

    def checkpoint(self):
        self._owned()
        row = self.db.execute('SELECT value FROM checkpoint WHERE singleton=1').fetchone()
        return json.loads(row[0]) if row else None

    def pending(self, now=0, limit=100):
        self._owned()
        if not 1 <= limit <= 100:
            raise ValueError('Invalid batch limit')
        rows = self.db.execute("SELECT payload,sha256 FROM events WHERE status='pending' "
                               'AND next_attempt<=? ORDER BY sequence LIMIT ?', (now, limit)).fetchall()
        return [(json.loads(body), digest) for body, digest in rows]

    def retry(self, events, now, delay):
        self._owned()
        with self.db:
            self.db.executemany("UPDATE events SET attempts=attempts+1,next_attempt=? "
                                "WHERE event_id=? AND status='pending'",
                                [(now + delay, str(event['event_id'])) for event in events])

    def acknowledge(self, submitted, receipts):
        """Validate the ENTIRE acknowledgement before changing any local status."""
        self._owned()
        expected = {str(item['event_id']): (item['sequence'], sha) for item, sha in submitted}
        if (not isinstance(receipts, list) or not all(isinstance(row, dict) for row in receipts)
                or len(receipts) != len(expected) or len({x.get('event_id') for x in receipts}) != len(expected)):
            raise OutboxError('Incomplete or duplicate acknowledgement')
        updates = []
        for row in receipts:
            key = str(row.get('event_id'))
            if (key not in expected or (row.get('sequence'), row.get('sha256')) != expected[key]
                    or row.get('disposition') not in {'pending', 'shadow', 'fixture', 'history', 'rejected'}
                    or row.get('reason') not in {'ACCEPTED', 'STALE', 'CONFIG_CHANGED', 'MANUAL_CHANGED',
                                               'INVALID', 'PENDING_GAP', 'PROTECTED', 'CONTEXT_REQUIRED'}):
                raise OutboxError('Acknowledgement does not match immutable events')
            status = 'quarantined' if row['disposition'] == 'rejected' else 'delivered'
            updates.append((status, row['disposition'], row['reason'], key))
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.executemany('UPDATE events SET status=?,disposition=?,reason=? WHERE event_id=?', updates)
            self.db.execute('COMMIT')
        except sqlite3.DatabaseError:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise OutboxError('Acknowledgement not saved; original events remain retryable') from None

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        if self.lock is not None:
            self.lock.close()
            self.lock = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
