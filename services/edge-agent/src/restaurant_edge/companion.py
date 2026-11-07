"""Loopback-only authenticated camera calibration. No cloud video forwarding."""

import asyncio
import hashlib
import hmac
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from restaurant_edge.capture import Capture
from restaurant_edge.cloud_client import CloudClient, CloudFailure

ROLES = {"owner", "org_admin", "manager", "installer"}
COOKIE = "restaurant_local_setup"
STATIC = Path(__file__).parent / "static"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Login(Strict):
    email: str = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=512)


class Start(Strict):
    location_id: UUID
    camera_id: UUID
    reference: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    sampling_fps: float = Field(default=2, ge=0.5, le=10)
    loop: bool = Field(default=False, strict=True)


class Save(Strict):
    location_id: UUID
    camera_id: UUID
    table_id: UUID
    polygon: list[list[float]] = Field(min_length=3, max_length=64)
    source_width: int = Field(ge=1, le=32768)
    source_height: int = Field(ge=1, le=32768)
    zone_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)
    request_key: UUID
    view_metadata: dict = Field(default_factory=lambda: {"format_version":1,"rotation":0,"mirrored":False})


class LocalSession:
    def __init__(self, cloud, token):
        self.cloud = cloud
        self.csrf = hmac.new(token.encode(), b"local-phase4-csrf", hashlib.sha256).hexdigest()
        self.created = time.monotonic()
        self.permission_lock = threading.RLock()
        self.authorized_until = 0.0
        self.next_check = 0.0
        self.location = self.camera = self.source = None
        self.permission_error = None
        self.valid = True


class Companion:
    def __init__(self, registry, cloud_factory, capture_factory=Capture):
        self.registry, self.cloud_factory, self.capture_factory = registry, cloud_factory, capture_factory
        self.sessions = {}
        self.lock = threading.RLock()
        self.active = self.owner = None
        self.last_login_attempts = []

    @staticmethod
    def key(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def login(self, email, password):
        with self.lock:
            now = time.monotonic()
            self.last_login_attempts = [t for t in self.last_login_attempts if now - t < 60]
            if len(self.last_login_attempts) >= 10 or len(self.sessions) >= 8:
                raise HTTPException(429, "Local setup limit reached; wait or sign out.")
            self.last_login_attempts.append(now)
        cloud = self.cloud_factory()
        try:
            me = cloud.login(email, password)
            if not any(row["role"] in ROLES and row["locations"] for row in me["access"]):
                raise CloudFailure(403)
        except Exception:
            cloud.close()
            raise
        token = secrets.token_urlsafe(32)
        session = LocalSession(cloud, token)
        with self.lock:
            self.sessions[self.key(token)] = session
        return token, session

    def session(self, token):
        with self.lock:
            session = self.sessions.get(self.key(token)) if 32 <= len(token) <= 128 else None
        if not session or not session.valid or time.monotonic() - session.created >= 3600:
            if session:
                self.logout(token)
            raise HTTPException(401, "Local setup sign-in required.")
        return session

    def stop(self, session):
        with self.lock:
            if self.owner is session:
                capture = self.active
                self.active = self.owner = None
                if capture:
                    capture.stop()

    def logout(self, token):
        with self.lock:
            session = self.sessions.pop(self.key(token), None)
        if session:
            session.valid = False
            self.stop(session)
            session.cloud.close()

    def permission(self, session, *, force=False):
        with session.permission_lock:
            now = time.monotonic()
            if not session.camera:
                raise HTTPException(409, "Select a camera and explicitly start preview first.")
            if session.permission_error and not force:
                raise HTTPException(session.permission_error, "Preview authorization is unavailable or ended.")
            if not force and session.authorized_until and now >= session.authorized_until:
                session.permission_error = 403
                self.stop(session)
                raise HTTPException(403, "Preview permission or human session expired.")
            if not force and now < min(session.next_check, session.authorized_until):
                return
            try:
                data = session.cloud.request("GET", f"/v1/locations/{session.location}/cameras/{session.camera}/preview-authorization")
                server = datetime.fromisoformat(data["server_time"])
                seconds = min((datetime.fromisoformat(data[k]) - server).total_seconds()
                              for k in ["expires_at", "session_deadline"])
                if seconds <= 0 or data["source_reference"] != session.source.reference:
                    raise CloudFailure(403)
                if (str(data["organization_id"]),str(data["location_id"]),str(data["camera_id"])) != (
                    str(session.source.organization_id),str(session.source.location_id),str(session.source.camera_id)):
                    raise CloudFailure(403)
                session.authorized_until = now + seconds
                if session.authorized_until <= time.monotonic():
                    raise CloudFailure(403)
                session.next_check = time.monotonic() + 1.0
                session.permission_error = None
            except (CloudFailure, KeyError, ValueError, TypeError) as error:
                session.permission_error = error.status if isinstance(error, CloudFailure) else 503
                session.authorized_until = session.next_check = 0
                self.stop(session)
                raise HTTPException(session.permission_error, "Preview authorization is unavailable or ended.") from None

    def tick(self):
        with self.lock:
            session = self.owner
            expired = [key for key,value in self.sessions.items() if time.monotonic()-value.created >= 3600]
            stale = [self.sessions.pop(key) for key in expired]
        for old in stale:
            old.valid = False
            self.stop(old)
            old.cloud.close()
        if session and session.valid:
            try:
                self.permission(session)
            except HTTPException:
                pass

    def close(self):
        with self.lock:
            values = list(self.sessions.values())
            self.sessions.clear()
        for session in values:
            session.valid = False
            self.stop(session)
            session.cloud.close()


def create_companion(registry, *, api_url="http://127.0.0.1:8000", api_origin="http://localhost:3000",
                     port=8765, cloud_factory=None, capture_factory=Capture):
    origin = f"http://127.0.0.1:{port}"
    state = Companion(registry, cloud_factory or (lambda: CloudClient(api_url, api_origin)), capture_factory)

    @asynccontextmanager
    async def lifespan(app):
        async def monitor():
            while True:
                await asyncio.sleep(0.1)
                await asyncio.to_thread(state.tick)
        task = asyncio.create_task(monitor())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.to_thread(state.close)

    app = FastAPI(title="Local camera setup", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.companion = state

    def error(status, message):
        return JSONResponse({"error": {"code": status, "message": message}}, status_code=status)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(exc.status_code, str(exc.detail))

    @app.exception_handler(CloudFailure)
    async def cloud_error(request, exc):
        return error(exc.status, "Cloud authorization or metadata request failed.")

    @app.exception_handler(RequestValidationError)
    async def validation(request, exc):
        return error(422, "Invalid setup fields; private input is not echoed.")

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.headers.get("host") != f"127.0.0.1:{port}":
            return error(403, "Invalid local Host.")
        supplied_origin = request.headers.get("origin")
        if (supplied_origin is not None and supplied_origin != origin) or (
                request.method not in {"GET", "HEAD"} and supplied_origin != origin):
            return error(403, "Invalid local Origin.")
        if request.method not in {"GET", "HEAD"}:
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return error(415, "Use a JSON setup request.")
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 32768:
                    return error(413, "Setup request exceeds the limit.")
            request._body = bytes(body)
            if request.url.path != "/local/v1/login":
                try:
                    session = state.session(request.cookies.get(COOKIE, ""))
                    if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
                        return error(403, "Local CSRF check failed.")
                except HTTPException as exc:
                    return error(exc.status_code, str(exc.detail))
        response = await call_next(request)
        response.headers.update({"Cache-Control":"no-store", "Pragma":"no-cache",
            "X-Content-Type-Options":"nosniff", "X-Frame-Options":"DENY",
            "Referrer-Policy":"no-referrer", "Content-Security-Policy":
            "default-src 'self'; connect-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"})
        return response

    def current(request):
        return state.session(request.cookies.get(COOKIE, ""))

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/static/{name}")
    def asset(name: str):
        if name not in {"editor.js", "style.css"}:
            raise HTTPException(404, "Not found.")
        return FileResponse(STATIC / name)

    @app.post("/local/v1/login")
    def login(body: Login, request: Request, response: Response):
        old = request.cookies.get(COOKIE)
        if old:
            state.logout(old)
        token, session = state.login(body.email, body.password.get_secret_value())
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=3600, path="/")
        return {"csrf_token": session.csrf}

    @app.get("/local/v1/session")
    def local_session(request: Request):
        session = current(request)
        session.cloud.request("GET", "/v1/me")
        return {"csrf_token": session.csrf}

    @app.post("/local/v1/logout")
    def logout(request: Request, response: Response):
        state.logout(request.cookies.get(COOKIE, ""))
        response.delete_cookie(COOKIE)
        return {"signed_out": True}

    @app.get("/local/v1/setup")
    def setup(request: Request, location_id: UUID | None = None):
        session = current(request)
        me = session.cloud.request("GET", "/v1/me")
        me["access"] = [row for row in me["access"] if row["role"] in ROLES]
        data = {"identity": me}
        if location_id:
            if not any(str(loc["id"]) == str(location_id) for row in me["access"] for loc in row["locations"]):
                raise HTTPException(404, "Location not found.")
            for kind in ["cameras", "tables", "table-zones"]:
                data[kind] = session.cloud.request("GET", f"/v1/locations/{location_id}/{kind}")
        return data

    @app.post("/local/v1/start")
    def start(body: Start, request: Request):
        session = current(request)
        state.stop(session)
        camera = session.cloud.request("GET", f"/v1/locations/{body.location_id}/cameras/{body.camera_id}")
        if camera["source_reference"] != body.reference:
            raise HTTPException(403, "Source reference does not match this camera.")
        source = registry.get(camera["organization_id"], body.location_id, body.camera_id, body.reference)
        if source is None:
            raise HTTPException(404, "Authorized local source is not configured.")
        session.location, session.camera, session.source = body.location_id, body.camera_id, source
        state.permission(session, force=True)
        with state.lock:
            if state.active is not None:
                raise HTTPException(409, "The single reader is in use by another setup session.")
            state.active = capture_factory(source, body.sampling_fps, body.loop)
            state.owner = session
            state.active.start()
        return {"started": True, "kind": source.kind, "synthetic": source.synthetic}

    @app.post("/local/v1/stop")
    def stop(request: Request):
        state.stop(current(request))
        return {"stopped": True}

    @app.get("/local/v1/health")
    def health(request: Request):
        session = current(request)
        if session.permission_error:
            raise HTTPException(session.permission_error, "Preview authorization ended.")
        if state.owner is not session:
            return {"status": "STOPPED", "reason": None}
        state.permission(session)
        with state.lock:
            if state.owner is not session:
                raise HTTPException(403, "Preview ended.")
            return {**state.active.health(), "preview_expires_in_seconds":
                    max(0, round(session.authorized_until - time.monotonic(), 1))}

    @app.get("/local/v1/frame")
    def frame(request: Request):
        session = current(request)
        state.permission(session)
        with state.lock:
            if state.owner is not session:
                raise HTTPException(404, "Preview not active.")
            image = state.active.frame()
            if image is None:
                raise HTTPException(409, "No current live frame is available.")
            info = state.active.health()
        return Response(image, media_type="image/jpeg", headers={
            "X-Frame-Width":str(info["width"]), "X-Frame-Height":str(info["height"]),
            "X-Frame-Sequence":str(info["sequence"]), "X-Frame-Generation":info["generation"]})

    @app.post("/local/v1/calibration")
    def save_calibration(body: Save, request: Request):
        session = current(request)
        if str(body.camera_id) != str(session.camera) or str(body.location_id) != str(session.location):
            raise HTTPException(404, "Camera not selected in this preview session.")
        state.permission(session, force=True)
        payload = body.model_dump(mode="json", exclude={"location_id", "zone_id", "expected_revision"})
        base = f"/v1/locations/{body.location_id}/table-zones"
        if body.zone_id:
            if body.expected_revision is None:
                raise HTTPException(422, "An expected revision is required.")
            payload["expected_revision"] = body.expected_revision
            return session.cloud.request("PUT", base + f"/{body.zone_id}", payload)
        return session.cloud.request("POST", base, payload)

    @app.get("/local/v1/revisions")
    def revisions(request: Request, location_id: UUID, zone_id: UUID):
        session = current(request)
        return session.cloud.request("GET", f"/v1/locations/{location_id}/table-zones/{zone_id}/revisions?limit=50")

    return app
