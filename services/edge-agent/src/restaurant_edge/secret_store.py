"""Explicit Windows Credential Locker only; no automatic plaintext or alternate backend."""

import json
import sys
from dataclasses import dataclass


@dataclass(repr=False, frozen=True)
class CameraCredential:
    username: str
    password: str


def backend():
    if sys.platform != "win32":
        raise RuntimeError("Windows camera credential storage is unavailable on this platform")
    from keyring.backends.Windows import WinVaultKeyring
    return WinVaultKeyring()


def account(source):
    return f"{source.organization_id}/{source.location_id}/{source.camera_id}"


def save(source, username, password):
    if not username or not password or len(username) > 128 or len(password) > 512:
        raise ValueError("Invalid camera credential fields")
    backend().set_password("RestaurantEdgePhase4", account(source),
                           json.dumps({"username": username, "password": password}))


def read(source):
    if not source.credential_required:
        return CameraCredential("", "")
    value = backend().get_password("RestaurantEdgePhase4", account(source))
    if not value:
        raise RuntimeError("Camera credential is not configured in the Windows store")
    try:
        data = json.loads(value)
        return CameraCredential(data["username"], data["password"])
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("Camera credential could not be loaded") from None
