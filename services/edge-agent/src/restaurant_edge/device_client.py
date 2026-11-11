"""Separate machine-only HTTPS client. No human cookie, password, proxy or redirect."""

import random
import ssl
import threading
import time
from urllib.parse import urlsplit

import httpx

from restaurant_edge.device_protocol import MAX_BODY, encode, parse_json
from restaurant_edge.device_signatures import sign
from restaurant_edge.outbox import OutboxError


class DeviceUnavailable(RuntimeError):
    pass


class DeviceRevoked(DeviceUnavailable):
    pass


class ProcessingLease:
    """Memory-only authority. Every process start needs a fresh online response.

    Certificate-verified HTTPS authenticates the response. Nothing on disk can
    restore this lease, and wall-clock changes cannot lengthen it.
    """
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.deadline = 0.0
        self.configuration = None
        self.last_clock = None
        self.lock = threading.RLock()

    def renew(self, reply, expected_device):
        with self.lock:
            return self._renew(reply, expected_device)

    def _renew(self, reply, expected_device):
        now = self.clock()
        seconds = reply.get('lease_seconds')
        configuration = reply.get('configuration')
        if (type(seconds) is not int or not 0 <= seconds <= 3600 or not isinstance(configuration, dict)
                or configuration.get('device_id') != str(expected_device)
                or configuration.get('processing_enabled') is not True or seconds == 0):
            self.revoke()
            return False
        self.deadline, self.last_clock = now+seconds, now
        self.configuration = configuration
        return True

    def active(self):
        with self.lock:
            return self._active()

    def _active(self):
        now = self.clock()
        if self.last_clock is not None and now < self.last_clock:
            self.revoke()
            return False
        self.last_clock = now
        return self.configuration is not None and now < self.deadline

    def revoke(self):
        with self.lock:
            self.deadline, self.configuration = 0, None


class LeaseGuard:
    """Stop native processing independently of slow sender/network operations."""
    def __init__(self, lease, stop_native):
        self.lease, self.stop_native = lease, stop_native
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._run, name='device-processing-lease', daemon=True)

    def _run(self):
        while not self.done.wait(.05):
            if not self.lease.active():
                self.stop_native()
                return

    def start(self):
        self.thread.start()

    def close(self):
        self.done.set()
        self.thread.join(timeout=7)
        if self.thread.is_alive():
            raise RuntimeError('Processing lease guard did not stop')


class DeviceClient:
    def __init__(self, origin, ca_file, key_id, private_key, *, transport=None):
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
            raise ValueError('Configure one exact HTTPS backend origin')
        self.origin = origin.rstrip('/')
        self.key_id, self.private_key = key_id, private_key
        context = ssl.create_default_context(cafile=str(ca_file))
        self.http = httpx.Client(verify=context, trust_env=False, follow_redirects=False,
                                 timeout=httpx.Timeout(10, connect=3, pool=3),
                                 limits=httpx.Limits(max_connections=2, max_keepalive_connections=0),
                                 transport=transport)

    def post(self, path, value, *, signed=True):
        if path not in {'/v1/edge/pairings', '/v1/edge/pairings/proof', '/v1/edge/events',
                        '/v1/edge/batches', '/v1/edge/heartbeat'}:
            raise ValueError('Only fixed device endpoints are allowed')
        body = encode(value)
        if len(body) > MAX_BODY:
            raise ValueError('Device message too large')
        if signed:
            request = sign('POST', self.origin+path, body, self.key_id, self.private_key)
            headers = dict(request.headers)
        else:
            headers = {'content-type': 'application/json'}
        try:
            with self.http.stream('POST', self.origin+path, content=body, headers=headers) as response:
                if response.status_code in {401, 403}:
                    raise DeviceRevoked('Device authorization failed; retain its queue and stop processing')
                if response.status_code != 200:
                    raise DeviceUnavailable('Backend did not accept the request; queue retained')
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 262144:
                        raise DeviceUnavailable('Backend response exceeded its bound')
                try:
                    result = parse_json(bytes(data)) if len(data)<=MAX_BODY else None
                except (ValueError,UnicodeDecodeError):
                    raise DeviceUnavailable('Backend response is invalid; queue retained') from None
                if not isinstance(result, dict):
                    raise DeviceUnavailable('Backend response is invalid or too large')
                return result
        except httpx.HTTPError:
            raise DeviceUnavailable('HTTPS backend unavailable; queue retained') from None

    def close(self):
        self.http.close()


class Synchronizer:
    """Network happens after Outbox.commit, never inside its transaction."""
    def __init__(self, outbox, client, *, clock=time.time, jitter=random.uniform):
        self.outbox, self.client, self.clock, self.jitter = outbox, client, clock, jitter
        self.failures = 0
        self.revoked = False

    def tick(self):
        if self.revoked:
            return False
        now = self.clock()
        submitted = self.outbox.pending(now)
        if not submitted:
            return False
        # Preserve sequence order and obey BOTH event-count and encoded-byte limits.
        while len(encode({'events': [item for item, _ in submitted]})) > MAX_BODY:
            submitted.pop()
        events = [item for item, _ in submitted]
        try:
            response = self.client.post('/v1/edge/events', {'events': events})
            self.outbox.acknowledge(submitted, response.get('receipts', []))
            self.failures = 0
            return True
        except DeviceRevoked:
            self.revoked = True
            raise
        except (DeviceUnavailable, OutboxError):
            self.failures += 1
            delay = min(60, 2**min(self.failures, 6)) * self.jitter(0.8, 1.2)
            self.outbox.retry(events, now, delay)
            return False
