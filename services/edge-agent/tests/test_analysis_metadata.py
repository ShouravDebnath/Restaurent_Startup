"""AI background metadata reads may not serialize/block preview permission checks."""

import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from restaurant_edge.cloud_client import CloudClient, CloudFailure


def test_parallel_passive_get_does_not_hold_the_permission_client_lock():
    entered, release = threading.Event(), threading.Event()
    def respond(request):
        if request.url.path.endswith('/dashboard'):
            entered.set()
            release.wait(timeout=3)
        return httpx.Response(200, json={'safe': True})
    client = CloudClient('http://127.0.0.1:8000', 'http://localhost:3000',
                         transport=httpx.MockTransport(respond))
    try:
        with ThreadPoolExecutor(2) as pool:
            future = pool.submit(client.passive, '/v1/locations/synthetic/dashboard')
            assert entered.wait(timeout=2)
            assert client.request('GET', '/v1/preview-authorization') == {'safe': True}
            release.set()
            assert future.result(timeout=2) == {'safe': True}
        with pytest.raises(CloudFailure):
            client.request('POST', '/v1/locations/synthetic/dashboard', _parallel_read=True)
    finally:
        release.set()
        client.close()
