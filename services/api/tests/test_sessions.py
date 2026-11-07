import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from restaurant_api.main import create_app
from restaurant_api.models import AuthSession, User
from restaurant_api.security import digest
from restaurant_api.settings import Settings, get_settings

ORIGIN = "http://localhost:3000"


def test_non_ascii_csrf_is_rejected_without_server_error(suite, clients):
    loc = suite.seed["organizations"]["a"]["locations"][0]
    response = clients["a_owner"].client.post(
        f"/v1/locations/{loc}/tables",
        json={"label": "Rejected"},
        headers={b"origin": ORIGIN.encode(), b"x-csrf-token": b"\xff"},
    )
    assert response.status_code == 403


def test_api_refuses_administrative_database_connection(suite, monkeypatch):
    from restaurant_api import database

    monkeypatch.setattr(database, "get_engine", lambda: suite.admin)
    with TestClient(suite.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503


def test_login_uses_cookie_without_returning_session_token(suite):
    account = suite.account()
    actor = suite.login(account)
    cookie = actor.client.cookies.get(get_settings().cookie_name)
    response = actor.request("GET", "/v1/auth/csrf")
    assert response.status_code == 200
    assert cookie not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["csrf_token"] == actor.csrf
    with Session(suite.admin) as db:
        record = db.get(AuthSession, digest(cookie))
        assert record is not None
        assert record.token_digest != cookie
        assert db.scalar(
            select(User.password_hash).where(User.id == account["user_id"])
        ).startswith("$argon2id$")


@pytest.mark.parametrize(
    "which", ["missing", "forged", "expired", "idle", "revoked", "disabled_user"]
)
def test_invalid_sessions_are_rejected(suite, which):
    account = suite.account()
    actor = suite.login(account)
    cookie = actor.client.cookies.get(get_settings().cookie_name)
    with Session(suite.admin) as db, db.begin():
        session = db.get(AuthSession, digest(cookie))
        if which == "expired":
            session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif which == "idle":
            session.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
        elif which == "revoked":
            session.revoked = True
        elif which == "disabled_user":
            db.get(User, account["user_id"]).enabled = False
    if which in {"missing", "forged"}:
        actor.client.cookies.clear()
        if which == "forged":
            actor.client.cookies.set(get_settings().cookie_name, secrets.token_urlsafe(32))
    assert actor.request("GET", "/v1/me").status_code == 401


def test_logout_revokes_stolen_copy_and_login_rotates_session(suite):
    account = suite.account()
    actor = suite.login(account)
    old = actor.client.cookies.get(get_settings().cookie_name)
    login = actor.client.post(
        "/v1/auth/session",
        json={
            "email": account["email"],
            "password": account["password"],
        },
        headers={"origin": ORIGIN},
    )
    assert login.status_code == 200
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=strict" in login.headers["set-cookie"].lower()
    assert "domain=" not in login.headers["set-cookie"].lower()
    new = actor.client.cookies.get(get_settings().cookie_name)
    assert new != old
    with TestClient(suite.app) as stolen:
        stolen.cookies.set(get_settings().cookie_name, old)
        assert stolen.get("/v1/me").status_code == 401
    actor.csrf = login.json()["csrf_token"]
    assert actor.request("DELETE", "/v1/auth/session").status_code == 204
    assert actor.client.get("/v1/me").status_code == 401
    with TestClient(suite.app) as stolen:
        stolen.cookies.set(get_settings().cookie_name, new)
        assert stolen.get("/v1/me").status_code == 401


@pytest.mark.parametrize("variant", ["no_origin", "foreign_origin", "no_csrf", "wrong_csrf"])
def test_mutations_require_origin_and_csrf(suite, clients, variant):
    loc = suite.seed["organizations"]["a"]["locations"][0]
    headers = {"origin": ORIGIN, "x-csrf-token": clients["a_owner"].csrf}
    if variant == "no_origin":
        headers.pop("origin")
    elif variant == "foreign_origin":
        headers["origin"] = "https://attacker.example.invalid"
    elif variant == "no_csrf":
        headers.pop("x-csrf-token")
    else:
        headers["x-csrf-token"] = secrets.token_urlsafe(32)
    response = clients["a_owner"].client.post(
        f"/v1/locations/{loc}/tables", json={"label": "Rejected"}, headers=headers
    )
    assert response.status_code == 403


def test_login_rejects_foreign_or_missing_origin(suite):
    account = suite.account()
    with TestClient(suite.app) as client:
        body = {"email": account["email"], "password": account["password"]}
        assert client.post("/v1/auth/session", json=body).status_code == 403
        assert (
            client.post(
                "/v1/auth/session",
                json=body,
                headers={
                    "origin": "https://attacker.example.invalid",
                },
            ).status_code
            == 403
        )


def test_failed_logins_are_persistently_throttled_without_enumeration(suite):
    account = suite.account()
    with TestClient(suite.app, client=(uuid4().hex, 50000)) as client:
        invalid = secrets.token_urlsafe(24)
        existing = client.post(
            "/v1/auth/session",
            json={"email": account["email"], "password": invalid},
            headers={"origin": ORIGIN},
        )
        missing_email = f"{uuid4().hex}@example.invalid"
        missing = client.post(
            "/v1/auth/session",
            json={"email": missing_email, "password": invalid},
            headers={"origin": ORIGIN},
        )
        assert existing.status_code == missing.status_code == 401
        assert existing.json()["error"]["message"] == missing.json()["error"]["message"]
        for _ in range(9):
            assert (
                client.post(
                    "/v1/auth/session",
                    json={"email": missing_email, "password": invalid},
                    headers={"origin": ORIGIN},
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/v1/auth/session",
                json={"email": missing_email, "password": invalid},
                headers={"origin": ORIGIN},
            ).status_code
            == 429
        )


def test_password_validation_does_not_echo_submitted_values(suite):
    secret = secrets.token_urlsafe(150)
    with TestClient(suite.app) as client:
        response = client.post(
            "/v1/auth/session",
            json={
                "email": "synthetic@example.invalid",
                "password": secret,
            },
            headers={"origin": ORIGIN},
        )
        assert response.status_code == 422
        assert secret not in response.text
        assert "input" not in response.text


def test_secure_cookie_configuration(suite, monkeypatch):
    with pytest.raises(ValidationError):
        Settings(app_env="production", cookie_secure=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://testserver")
    get_settings.cache_clear()
    try:
        account = suite.account()
        with TestClient(
            create_app(), base_url="https://testserver", client=(uuid4().hex, 50000)
        ) as client:
            response = client.post(
                "/v1/auth/session",
                json={
                    "email": account["email"],
                    "password": account["password"],
                },
                headers={"origin": "https://testserver"},
            )
            assert response.status_code == 200
            header = response.headers["set-cookie"].lower()
            assert "__host-restaurant_session=" in header and "; secure" in header
            assert "httponly" in header and "samesite=strict" in header
            assert client.get("/v1/me").status_code == 200
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
