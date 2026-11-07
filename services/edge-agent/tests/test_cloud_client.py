"""Only synthetic canaries; metadata requests must remain fixed-destination and bounded."""

import base64
import secrets
import sys
from uuid import uuid4

import httpx
import pytest

from restaurant_edge.cloud_client import CloudClient, CloudFailure
from restaurant_edge.rtsp_gateway import authorization
from restaurant_edge.secret_store import CameraCredential, account, backend, read, save
from restaurant_edge.source_config import SourceDefinition
from restaurant_edge.video_sources import SourceFailure


@pytest.mark.parametrize('url',['http://camera.invalid',f'https://synthetic:{uuid4().hex}@example.invalid',
                                'https://example.invalid/path','https://example.invalid?destination=1'])
def test_authority_destination_must_be_a_fixed_safe_origin(url):
    with pytest.raises(ValueError):
        CloudClient(url,'http://localhost:3000')


@pytest.mark.parametrize('path',['https://other.invalid/v1/me','/v1/../private','//other.invalid/v1/me'])
def test_metadata_client_cannot_become_an_arbitrary_proxy(path):
    client=CloudClient('http://127.0.0.1:8000','http://localhost:3000')
    try:
        with pytest.raises(CloudFailure):
            client.request('GET',path)
    finally:
        client.close()


@pytest.mark.parametrize('failure',['redirect','oversized','network'])
def test_metadata_redirect_size_and_network_fail_closed(failure):
    calls=[]
    def respond(request):
        calls.append(request.url.host)
        if failure=='network':raise httpx.ConnectError('synthetic failure')
        if failure=='redirect':return httpx.Response(302,headers={'Location':'https://other.invalid'})
        return httpx.Response(200,content=b'x'*2_000_001)
    client=CloudClient('http://127.0.0.1:8000','http://localhost:3000',transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(CloudFailure):client.request('GET','/v1/me')
        assert calls==['127.0.0.1']
    finally:client.close()


def test_rtsp_credential_authentication_does_not_embed_password_in_digest():
    username,password='synthetic-reader',secrets.token_urlsafe(32)
    credential=CameraCredential(username,password)
    digest=authorization('Digest realm="camera", nonce="synthetic", qop="auth", algorithm=SHA-256',
                         credential,'DESCRIBE','rtsp://10.0.0.1:554/video')
    assert digest.startswith('Digest ') and password not in digest
    basic=authorization('Basic realm="camera"',credential,'DESCRIBE','rtsp://10.0.0.1:554/video')
    assert base64.b64decode(basic[6:]).decode()==username+':'+password
    assert password not in repr(credential)
    with pytest.raises(SourceFailure,match='CAMERA_AUTHORIZATION_FAILED'):
        authorization('Digest algorithm=unsupported',credential,'DESCRIBE','rtsp://10.0.0.1:554/video')


@pytest.mark.skipif(sys.platform!='win32',reason='Actual Windows Credential Locker requires Windows')
def test_actual_windows_credential_store_canary_round_trip():
    # A unique account; never read/change a configured camera credential.
    source=SourceDefinition(reference='canary',organization_id=uuid4(),location_id=uuid4(),
        camera_id=uuid4(),authorized=True,kind='rtsp',host='10.0.0.1')
    store=backend()
    assert store.get_password('RestaurantEdgePhase4',account(source)) is None
    username,password='synthetic-canary',secrets.token_urlsafe(32)
    try:
        save(source,username,password)
        value=read(source)
        assert value.username==username and value.password==password
    finally:
        store.delete_password('RestaurantEdgePhase4',account(source))
    assert store.get_password('RestaurantEdgePhase4',account(source)) is None
