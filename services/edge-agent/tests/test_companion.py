"""Loopback boundary/session tests with synthetic frames and a simulated authority API."""

import secrets
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from restaurant_edge.cloud_client import CloudFailure
from restaurant_edge.companion import COOKIE, create_companion
from restaurant_edge.source_config import SourceDefinition, SourceRegistry
from restaurant_edge.video_sources import synthetic_mp4

ORIGIN="http://127.0.0.1:8765"


class FakeAuthority:
    def __init__(self, source):
        self.source=source
        self.allowed=True
        self.closed=False
        self.paths=[]

    def login(self, email, password):
        return self.request("GET","/v1/me")

    def request(self, method, path, body=None):
        self.paths.append((method,path))
        s=self.source
        if path=="/v1/me":
            return {"id":str(uuid4()),"display_name":"Synthetic installer","access":[{
                "role":"installer","organization":{"id":str(s.organization_id),"name":"Synthetic A"},
                "locations":[{"id":str(s.location_id),"name":"Synthetic lab"}]}]}
        if path.endswith('/preview-authorization'):
            if not self.allowed:
                raise CloudFailure(403)
            now=datetime.now(UTC)
            return {"camera_id":str(s.camera_id),"location_id":str(s.location_id),
                "organization_id":str(s.organization_id),"source_reference":s.reference,
                "expires_at":(now+timedelta(minutes=15)).isoformat(),
                "session_deadline":(now+timedelta(minutes=5)).isoformat(),"server_time":now.isoformat()}
        if path.endswith(str(s.camera_id)):
            return {"id":str(s.camera_id),"organization_id":str(s.organization_id),"source_reference":s.reference}
        raise CloudFailure(404)

    def close(self):
        self.closed=True


class FakeCapture:
    def __init__(self,source,fps,loop):
        self.source=source
        self.stopped=False
    def start(self):pass
    def stop(self):self.stopped=True
    def health(self):
        return {"status":"ONLINE","synthetic":True,"width":20,"height":20,"sequence":1,
                "generation":"synthetic","frame_age_seconds":0}
    def frame(self):
        assert not self.stopped
        return cv2.imencode('.jpg',np.zeros((20,20,3),dtype=np.uint8))[1].tobytes()


@pytest.fixture
def local(tmp_path):
    path=synthetic_mp4(tmp_path/'synthetic.mp4',seconds=.2)
    source=SourceDefinition(reference='synthetic',organization_id=uuid4(),location_id=uuid4(),
        camera_id=uuid4(),kind='mp4',authorized=True,synthetic=True,file=str(path))
    clients=[]
    def factory():
        client=FakeAuthority(source)
        clients.append(client)
        return client
    app=create_companion(SourceRegistry([source],[tmp_path]),cloud_factory=factory,capture_factory=FakeCapture)
    with TestClient(app,base_url=ORIGIN) as client:
        yield client,app.state.companion,source,clients


def login(client):
    response=client.post('/local/v1/login',json={'email':'synthetic@example.invalid','password':secrets.token_urlsafe(24)},headers={'Origin':ORIGIN})
    assert response.status_code==200
    return {'Origin':ORIGIN,'X-CSRF-Token':response.json()['csrf_token']}


def start(client,source,headers):
    return client.post('/local/v1/start',json={'location_id':str(source.location_id),
        'camera_id':str(source.camera_id),'reference':source.reference},headers=headers)


def test_anonymous_host_origin_csrf_and_response_security(local):
    client,_state,source,authorities=local
    assert client.get('/local/v1/frame').status_code==401
    assert client.get('/',headers={'Host':'evil.invalid'}).status_code==403
    assert client.post('/local/v1/login',json={},headers={'Origin':'https://evil.invalid'}).status_code==403
    headers=login(client)
    attributes = client.cookies.jar._cookies['127.0.0.1']['/'][COOKIE]._rest
    assert 'HttpOnly' in attributes and attributes.get('SameSite') == 'strict'
    assert client.post('/local/v1/start',json={},headers={'Origin':ORIGIN}).status_code==403
    assert start(client,source,headers).status_code==200
    response=client.get('/local/v1/frame')
    assert response.status_code==200 and response.content.startswith(b'\xff\xd8')
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-frame-options']=='DENY'
    assert 'connect-src' in response.headers['content-security-policy']
    assert all('frame' not in path and method=='GET' for method,path in authorities[0].paths)


def test_revoke_permission_stops_capture_and_prevents_stale_frame(local):
    client,state,source,authorities=local
    headers=login(client)
    assert start(client,source,headers).status_code==200
    capture=state.active
    authorities[0].allowed=False
    state.owner.next_check=0
    assert client.get('/local/v1/health').status_code==403
    assert capture.stopped and state.active is None
    assert client.get('/local/v1/frame').status_code==403


def test_exact_cached_deadline_cannot_be_extended_by_passive_reads(local):
    client,state,source,_authorities=local
    headers=login(client)
    assert start(client,source,headers).status_code==200
    session=state.owner
    deadline=session.authorized_until
    for _ in range(3):assert client.get('/local/v1/frame').status_code==200
    assert session.authorized_until==deadline
    session.authorized_until=time.monotonic()-1
    assert client.get('/local/v1/frame').status_code==403
    assert state.active is None


def test_different_local_session_cannot_see_or_stop_another_reader(local):
    client,state,source,_authorities=local
    headers=login(client)
    assert start(client,source,headers).status_code==200
    capture=state.active
    # Distinct cookie/client despite using another permitted synthetic human login.
    with TestClient(client.app,base_url=ORIGIN) as other:
        second=login(other)
        assert other.get('/local/v1/health').json()['status']=='STOPPED'
        assert other.get('/local/v1/frame').status_code==409
        assert other.post('/local/v1/stop',json={},headers=second).status_code==200
        assert not capture.stopped
        assert start(other,source,second).status_code==409


def test_private_validation_input_never_echoed_and_large_requests_rejected(local):
    client,_state,_source,_authorities=local
    headers=login(client)
    canary=secrets.token_urlsafe(24)
    response=client.post('/local/v1/start',json={'reference':canary+':/'},headers=headers)
    assert response.status_code==422 and canary not in response.text
    assert client.post('/local/v1/start',content=b'x'*40000,
        headers={**headers,'Content-Type':'application/json'}).status_code==413


def test_logout_releases_reader_and_cloud_session(local):
    client,state,source,authorities=local
    headers=login(client)
    assert start(client,source,headers).status_code==200
    capture=state.active
    assert client.post('/local/v1/logout',json={},headers=headers).status_code==200
    assert capture.stopped and authorities[0].closed and state.active is None
    assert client.get('/local/v1/frame').status_code==401
