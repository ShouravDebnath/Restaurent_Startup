"""Integration tests require an explicitly named, disposable PostgreSQL test database."""

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from restaurant_api.database import get_engine
from restaurant_api.main import create_app
from restaurant_api.management import migrate, provision_runtime, seed_demo
from restaurant_api.models import LocationGrant, Membership, User
from restaurant_api.security import passwords
from restaurant_api.settings import get_settings

ROOT = Path(__file__).resolve().parents[3]
ORIGIN = "http://localhost:3000"


@dataclass(repr=False)
class LoginClient:
    client: TestClient
    csrf: str

    def request(self, method, path, **kwargs):
        headers = {"origin": ORIGIN, "x-csrf-token": self.csrf}
        headers.update(kwargs.pop("headers", {}))
        return self.client.request(method, path, headers=headers, **kwargs)


@dataclass(repr=False)
class Suite:
    admin: object
    runtime: object
    app: object
    seed: dict
    namespace: str

    def login(self, account):
        client = TestClient(self.app, client=("test-" + uuid4().hex, 50000))
        response = client.post(
            "/v1/auth/session",
            json={
                "email": account["email"],
                "password": account["password"],
            },
            headers={"origin": ORIGIN},
        )
        assert response.status_code == 200
        return LoginClient(client, response.json()["csrf_token"])

    def account(self, role="staff", member=True):
        user_id, member_id = uuid4(), uuid4()
        email, password = f"{uuid4().hex}@example.invalid", secrets.token_urlsafe(24)
        with Session(self.admin) as db, db.begin():
            db.add(
                User(
                    id=user_id,
                    email=email,
                    display_name="Synthetic test user",
                    password_hash=passwords.hash(password),
                )
            )
            db.flush()
            if member:
                org = self.seed["organizations"]["a"]
                db.add(
                    Membership(id=member_id, user_id=user_id, organization_id=org["id"], role=role)
                )
                db.flush()
                db.add(
                    LocationGrant(
                        membership_id=member_id,
                        organization_id=org["id"],
                        location_id=org["locations"][0],
                    )
                )
        return {"user_id": user_id, "member_id": member_id, "email": email, "password": password}


@pytest.fixture(scope="session")
def suite(tmp_path_factory):
    admin_url = os.environ.get("PHASE2_TEST_ADMIN_URL")
    if admin_url:
        url = make_url(admin_url)
    else:
        manifest = ROOT / ".secrets" / "phase2-test.json"
        if not manifest.exists():
            pytest.fail(
                "Start the isolated Phase 2 test database; see PHASE_02.md. No tests skipped."
            )
        config = json.loads(manifest.read_text(encoding="utf-8"))
        from sqlalchemy.engine import URL

        url = URL.create(
            "postgresql+psycopg",
            username=config["username"],
            password=config["password"],
            host="127.0.0.1",
            port=config["port"],
            database=config["database"],
        )
    if not (url.database or "").startswith("phase2_security_test"):
        pytest.fail("Refusing integration tests outside an explicitly named Phase 2 test database.")
    admin = create_engine(url, hide_parameters=True)
    with admin.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == url.database
    migrate(admin)
    runtime_user = "restaurant_test_" + uuid4().hex[:10]
    runtime_password = secrets.token_urlsafe(36)
    provision_runtime(admin, runtime_user, runtime_password)
    runtime_url = url.set(username=runtime_user, password=runtime_password)
    namespace = "test-" + uuid4().hex[:10]
    private = tmp_path_factory.mktemp("phase2-private") / "accounts.json"
    seed = seed_demo(admin, private, namespace)
    patch = pytest.MonkeyPatch()
    patch.setenv("DATABASE_URL", runtime_url.render_as_string(hide_password=False))
    get_settings.cache_clear()
    get_engine.cache_clear()
    runtime = get_engine()
    yield Suite(admin, runtime, create_app(), seed, namespace)
    runtime.dispose()
    admin.dispose()
    patch.undo()
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture(scope="session")
def clients(suite):
    result = {key: suite.login(value) for key, value in suite.seed["accounts"].items()}
    yield result
    for value in result.values():
        value.client.close()
