"""Supervised sibling inference worker; non-authoritative local observations only."""

import contextlib
import multiprocessing
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from restaurant_edge.analysis_metrics import process_metrics
from restaurant_edge.association import associate
from restaurant_edge.capture import silence_native_output
from restaurant_edge.detectors.base import Person
from restaurant_edge.detectors.factory import detector_for
from restaurant_edge.process_guard import ReaderJob, watch_parent
from restaurant_edge.state_engine import StateEngine


def publish(mailbox, message):
    try:
        mailbox.put_nowait(message)
    except queue.Full:
        with contextlib.suppress(queue.Empty):
            mailbox.get_nowait()
        with contextlib.suppress(queue.Full):
            mailbox.put_nowait(message)


def inference_worker(artifact, incoming, outgoing, cancel, factory=detector_for):
    silence_native_output('mp4')
    watch_parent()
    detector = None
    try:
        detector = factory(artifact)
        publish(outgoing, {'kind': 'READY'})
        while not cancel.is_set():
            try:
                sample = incoming.get(timeout=.1)
            except queue.Empty:
                continue
            pixels = sample.pop('pixels')
            started = time.perf_counter()
            people = detector.detect(pixels)
            if len(people) > 128:
                raise ValueError('Output limit exceeded')
            publish(outgoing, {'kind': 'RESULT', 'frame': sample,
                'people': [{'box': p.box, 'score': p.score} for p in people],
                'metrics': getattr(detector, 'last_metrics', {}),
                'process': process_metrics(),
                'elapsed_ms': (time.perf_counter() - started) * 1000})
    except Exception:  # noqa: BLE001 - native boundary must not serialize private errors
        publish(outgoing, {'kind': 'ERROR', 'reason': 'INFERENCE_WORKER_FAILED'})
    finally:
        if detector:
            detector.close()
        outgoing.cancel_join_thread()
        outgoing.close()


class Analysis:
    def __init__(self, capture, config, artifact, manual_provider, *, worker=inference_worker):
        self.capture, self.config, self.artifact = capture, config, artifact
        self.manual_provider, self.worker = manual_provider, worker
        self.engine = StateEngine(config)
        self.engine.model_sha256 = artifact.sha256
        self.lock = threading.RLock()
        self.status, self.reason = 'STOPPED', None
        self.process = self.incoming = self.outgoing = self.cancel = self.job = None
        self.latest, self.metrics, self.people = None, {}, []
        self.started = self.submitted = self.manual_at = self.next_manual = 0
        self.pending = None
        self.executor = self.manual_future = None

    def start(self):
        with self.lock:
            self._manual(time.monotonic())
            ctx = multiprocessing.get_context('spawn')
            self.incoming, self.outgoing = ctx.Queue(maxsize=1), ctx.Queue(maxsize=1)
            self.cancel, self.job = ctx.Event(), ReaderJob()
            self.process = ctx.Process(target=self.worker,
                args=(self.artifact, self.incoming, self.outgoing, self.cancel), daemon=True)
            try:
                self.process.start()
                self.job.attach(self.process.pid)
                self.capture.enable_analysis(True)
                self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='analysis-metadata')
                self.status, self.started = 'LOADING', time.monotonic()
            except Exception:  # noqa: BLE001 - fail closed and dispose a partial native startup
                self.stop('ANALYSIS_START_FAILED', 'ERROR')
                raise RuntimeError('Analysis could not start') from None

    def _manual(self, now):
        data = self.manual_provider()
        self._apply_manual(data, now)

    def _apply_manual(self, data, now):
        location = data['location']
        if (str(location['id']) != str(self.config.location_id)
            or str(location['organization_id']) != str(self.config.organization_id)
            or data.get('tables_truncated')):
            raise ValueError('Incomplete or mismatched manual snapshot')
        ids = {str(r.table_id) for r in self.config.regions}
        rows = [row for row in data['tables'] if str(row['id']) in ids]
        if len(rows) != len(ids) or any(
                str(r['organization_id']) != str(self.config.organization_id) or
                str(r['location_id']) != str(self.config.location_id) for r in rows):
            raise ValueError('Manual table scope mismatch')
        self.engine.manual(rows, now, datetime.now(UTC).isoformat())
        self.manual_at, self.next_manual = time.monotonic(), time.monotonic() + 1

    def tick(self):
        with self.lock:
            if self.process is None:
                return
            now, utc = time.monotonic(), datetime.now(UTC).isoformat()
            if self.manual_future is not None and self.manual_future.done():
                try:
                    self._apply_manual(self.manual_future.result(), now)
                    self.manual_future = None
                except Exception:  # noqa: BLE001 - any authority/contract failure ends analysis
                    self.stop('MANUAL_AUTHORITY_UNAVAILABLE', 'ERROR')
                    return
            if now >= self.next_manual and self.manual_future is None:
                self.manual_future = self.executor.submit(self.manual_provider)
            if now - self.manual_at > 4:
                self.stop('MANUAL_AUTHORITY_STALE', 'ERROR')
                return
            source = self.capture.health()
            if source['status'] == 'FILE_ENDED':
                self.stop('NORMAL_SOURCE_COMPLETION', 'COMPLETED')
                return
            if source['status'] != 'ONLINE':
                self.people = []
                self.engine.invalidate('SOURCE_' + source['status'], now, utc)
            message = None
            try:
                message = self.outgoing.get_nowait()
            except (queue.Empty, OSError, EOFError):
                pass
            if message:
                if message['kind'] == 'ERROR':
                    self.stop('INFERENCE_WORKER_FAILED', 'ERROR')
                    return
                if message['kind'] == 'READY':
                    self.status = 'RUNNING'
                elif message['kind'] == 'RESULT':
                    frame = message['frame']
                    expected = self.pending
                    self.pending = None
                    if (source['status'] == 'ONLINE' and frame['generation'] == source.get('generation')
                        and now - self.manual_at <= 3
                        and expected == (frame['generation'], frame['sequence'])
                        and 0 <= now - frame['received_monotonic'] <= self.config.settings.result_max_age):
                        try:
                            people = tuple(Person(tuple(p['box']), p['score']) for p in message['people'])
                            if (len(people) > 128 or frame['width'] != self.config.source_width
                                or frame['height'] != self.config.source_height):
                                raise ValueError('Frame contract mismatch')
                            occupied = [k for k, t in self.engine.tables.items() if t.session_id and not t.departure_emitted]
                            observations = associate(people, self.config, occupied)
                            self.engine.media_seconds = frame.get('media_seconds')
                            self.engine.step(observations, frame['received_monotonic'], frame['received_at'],
                                             frame['generation'], frame['sequence'])
                            self.latest, self.people = frame, message['people']
                            self.metrics = {**message['metrics'], **message.get('process', {}), 'total_ms': message['elapsed_ms'],
                                            'frame_age_ms': (now - frame['received_monotonic']) * 1000}
                        except (ValueError, KeyError, TypeError):
                            self.stop('ANALYSIS_CONTRACT_REJECTED', 'ERROR')
                            return
            if self.status == 'LOADING' and now - self.started > 15:
                self.stop('MODEL_START_TIMEOUT', 'ERROR')
                return
            if self.pending is not None and now - self.submitted > 5:
                self.stop('INFERENCE_TIMEOUT', 'ERROR')
                return
            if not self.process.is_alive() and not message:
                self.stop('INFERENCE_EXITED', 'ERROR')
                return
            if self.latest is None or now - self.latest['received_monotonic'] > self.config.settings.result_max_age:
                self.people = []
                self.engine.invalidate('NO_FRESH_ANALYSIS', now, utc)
            if now - self.manual_at > 3:
                self.people = []
                self.engine.invalidate('MANUAL_SNAPSHOT_STALE', now, utc)
            if self.status == 'RUNNING' and self.pending is None and source['status'] == 'ONLINE':
                frame = self.capture.raw_frame()
                if frame is not None and 0 <= now - frame['received_monotonic'] <= self.config.settings.result_max_age:
                    self.pending = (frame['generation'], frame['sequence'])
                    self.submitted = now
                    publish(self.incoming, frame)

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            fresh = (self.latest is not None and now - self.latest['received_monotonic'] <= self.config.settings.result_max_age
                     and now - self.manual_at <= 3 and self.status == 'RUNNING')
            if not fresh:
                self.engine.invalidate(self.reason or 'NO_FRESH_ANALYSIS', now, datetime.now(UTC).isoformat())
            return {'status': self.status, 'reason': self.reason, 'authoritative': False,
                    'source': 'ai_local_shadow', 'analysis_run_id': self.engine.run_id,
                    'model': self.config.model, 'model_sha256': self.artifact.sha256,
                    'tables': self.engine.snapshot(now), 'detections': self.people if fresh else [],
                    'frame': self.latest if fresh else None, 'metrics': self.metrics if fresh else {},
                    'events_retained': len(self.engine.events), 'event_count': self.engine.event_number}

    def stop(self, reason='STOPPED_BY_USER', status='STOPPED'):
        with self.lock:
            self.capture.enable_analysis(False)
            if self.cancel:
                self.cancel.set()
            if self.process:
                if self.process.pid:
                    self.process.join(timeout=.25)
                    if self.process.is_alive():
                        self.process.terminate()
                        self.process.join(timeout=1)
                    if self.process.is_alive():
                        self.process.kill()
                        self.process.join(timeout=1)
                self.process.close()
                self.process = None
            for mailbox in (self.incoming, self.outgoing):
                if mailbox is not None:
                    mailbox.cancel_join_thread()
                    mailbox.close()
            self.incoming = self.outgoing = None
            if self.executor:
                self.executor.shutdown(wait=False, cancel_futures=True)
                self.executor = None
            if self.job:
                self.job.close()
                self.job = None
            self.latest, self.people, self.metrics = None, [], {}
            self.status, self.reason = status, reason
            self.engine.invalidate(reason, time.monotonic(), datetime.now(UTC).isoformat())
