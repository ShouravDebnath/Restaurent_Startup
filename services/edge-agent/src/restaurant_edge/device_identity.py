"""Device signing keys belong to Windows Credential Locker, never a JSON file."""

import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SERVICE = 'RestaurantAI.Phase6.Device.Ed25519'


def vault():
    if os.name != 'nt':
        raise RuntimeError('Device key storage is verified only for the current Windows user')
    from keyring.backends.Windows import WinVaultKeyring
    return WinVaultKeyring()


def public_identity(key, key_id):
    raw = key.public_key().public_bytes_raw()
    return {'version': 1, 'key_id': str(key_id),
            'public_key': base64.b64encode(raw).decode(),
            'fingerprint': hashlib.sha256(raw).hexdigest()}


def create_identity(path, *, backend=None):
    path = Path(path)
    if path.exists():
        raise RuntimeError('Identity exists; use the explicit rotation flow')
    backend = backend or vault()
    key, key_id = Ed25519PrivateKey.generate(), uuid4()
    if backend.get_password(SERVICE, str(key_id)) is not None:
        raise RuntimeError('Key identity already exists')
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                            serialization.NoEncryption())
    backend.set_password(SERVICE, str(key_id), base64.b64encode(raw).decode())
    if backend.get_password(SERVICE, str(key_id)) != base64.b64encode(raw).decode():
        raise RuntimeError('Secure key persistence failed')
    identity = public_identity(key, key_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(identity, handle, indent=2)
    return identity


def load_identity(path, *, backend=None):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    encoded = (backend or vault()).get_password(SERVICE, value['key_id'])
    if not encoded:
        raise RuntimeError('Device key unavailable in current Windows account')
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(encoded, validate=True))
    if public_identity(key, value['key_id']) != value:
        raise RuntimeError('Public identity does not match the secure key')
    return value, key
