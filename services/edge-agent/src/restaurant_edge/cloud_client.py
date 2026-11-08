"""Per-human in-memory API client; fixed destination and explicit metadata routes only."""

import json
import threading
from contextlib import nullcontext
from urllib.parse import urlsplit

import httpx


class CloudFailure(Exception):
    def __init__(self, status=503):
        self.status = status
        super().__init__("Cloud authorization or metadata request failed")


class CloudClient:
    def __init__(self, base_url, origin, *, transport=None):
        parsed = urlsplit(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("Use a fixed API origin without credentials/path/query")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
            raise ValueError("Non-loopback API connections require HTTPS")
        self.client = httpx.Client(base_url=base_url, timeout=1.5, follow_redirects=False,
                                   trust_env=False, transport=transport)
        self.origin, self.csrf = origin, None
        self.lock = threading.RLock()

    def request(self, method, path, body=None, *, _parallel_read=False):
        if _parallel_read and method != 'GET':
            raise CloudFailure(422)
        if not path.startswith("/v1/") or ".." in path or "://" in path or "#" in path:
            raise CloudFailure(422)
        headers = {"Origin": self.origin}
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        try:
            with (nullcontext() if _parallel_read else self.lock), self.client.stream(method, path, json=body, headers=headers) as response:
                if response.status_code not in {200, 201, 204}:
                    raise CloudFailure(response.status_code if response.status_code in {401,403,404,409,422,429} else 503)
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise CloudFailure()
                return json.loads(data) if data else None
        except (httpx.HTTPError, ValueError):
            raise CloudFailure() from None

    def passive(self, path):
        # HTTPX Client supports shared-thread GETs. Keep slow AI metadata reads
        # out of the serialization lock used by the permission watchdog.
        return self.request('GET', path, _parallel_read=True)

    def login(self, email, password):
        result = self.request("POST", "/v1/auth/session", {"email": email, "password": password})
        self.csrf = result["csrf_token"]
        return self.request("GET", "/v1/me")

    def close(self):
        try:
            if self.csrf:
                self.request("DELETE", "/v1/auth/session")
        except CloudFailure:
            pass
        finally:
            self.csrf = None
            self.client.close()
