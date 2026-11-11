"""RFC 9421 / RFC 9530 using the reviewed library, not custom canonicalization.

Mirrored in both packages; parity is enforced by tests.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from http_message_signatures import HTTPMessageSigner, HTTPMessageVerifier, algorithms
from http_message_signatures.resolvers import HTTPSignatureKeyResolver
from http_message_signatures.structures import CaseInsensitiveDict

COVERED = ('@method', '@authority', '@target-uri', 'content-type', 'content-digest', 'x-edge-key-id')
TAG = 'restaurant-edge-v1'


class KeyResolver(HTTPSignatureKeyResolver):
    def __init__(self, key_id, public_key=None, private_key=None):
        self.key_id, self.public_key, self.private_key = str(key_id), public_key, private_key

    def resolve_public_key(self, key_id):
        if key_id != self.key_id or self.public_key is None:
            raise ValueError('Unknown key')
        return self.public_key

    def resolve_private_key(self, key_id):
        if key_id != self.key_id or self.private_key is None:
            raise ValueError('Unknown key')
        return self.private_key


def sign(method, url, body, key_id, private_key, *, now=None, nonce=None):
    now = now or datetime.now(UTC)
    request = SimpleNamespace(method=method.upper(), url=url, content=body,
        headers=CaseInsensitiveDict({'content-type': 'application/json', 'x-edge-key-id': str(key_id)}))
    HTTPMessageSigner(signature_algorithm=algorithms.ED25519,
                      key_resolver=KeyResolver(key_id, private_key=private_key)).sign(
        request, key_id=str(key_id), created=now, expires=now + timedelta(seconds=120),
        nonce=nonce or uuid4().hex, label='edge', tag=TAG, covered_component_ids=COVERED, body=body)
    return request


def verify(method, url, headers, body, key_id, public_key, *, now=None):
    now = now or datetime.now(UTC)
    if headers.get('content-type') != 'application/json' or headers.get('x-edge-key-id') != str(key_id):
        raise ValueError('Invalid signed headers')
    message = SimpleNamespace(method=method, url=url, headers=headers, content=body)
    verifier = HTTPMessageVerifier(signature_algorithm=algorithms.ED25519,
                                   key_resolver=KeyResolver(key_id, public_key=public_key))
    results = verifier.verify(message, expect_tag=TAG, expect_label='edge',
                              require_components=COVERED, body=body, max_age=timedelta(seconds=240))
    if len(results) != 1:
        raise ValueError('One signature required')
    params = results[0].parameters
    created, expires, nonce = params.get('created'), params.get('expires'), params.get('nonce')
    if (type(created) is not int or type(expires) is not int or not 0 < expires-created <= 120
            or not created-120 <= now.timestamp() <= expires+120
            or not isinstance(nonce, str) or len(nonce) != 32
            or any(c not in '0123456789abcdef' for c in nonce)):
        raise ValueError('Invalid signature lifetime or nonce')
    return nonce
