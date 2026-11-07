from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from restaurant_api.routes import router
from restaurant_api.security import Db
from restaurant_api.settings import get_settings


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str
    checked_at: datetime


class DemoTable(BaseModel):
    id: str
    label: str
    state: Literal["AVAILABLE", "OCCUPIED", "RESET_PENDING", "UNKNOWN"]
    state_since: datetime


class DemoTenantResponse(BaseModel):
    demo: bool
    organization_id: str
    organization_name: str
    location_id: str
    location_name: str
    time_zone: str
    tables: list[DemoTable]


def create_app() -> FastAPI:
    app = FastAPI(title="Restaurant AI Monitoring API", version="0.2.0")
    app.include_router(router)

    def error_response(request, status, message):
        codes = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            429: "rate_limited",
            503: "unavailable",
        }
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": codes.get(status, "request_failed"),
                    "message": message,
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                }
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.middleware("http")
    async def request_headers(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return error_response(request, error.status_code, str(error.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Pydantic's default response can echo submitted passwords or secret URLs.
        return error_response(request, 422, "Request fields are invalid; check the API schema.")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        if isinstance(error, IntegrityError):
            return error_response(
                request, 409, "Change conflicts with existing data or constraints."
            )
        return error_response(request, 503, "Database operation unavailable.")

    @app.get("/ready", response_model=HealthResponse)
    def ready(db: Db) -> HealthResponse:
        db.execute(text("SELECT * FROM security.profile()"))
        return health()

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="restaurant-ai-api",
            environment=get_settings().app_env,
            checked_at=datetime.now(UTC),
        )

    @app.get("/v1/demo/tenant", response_model=DemoTenantResponse)
    def demo_tenant() -> DemoTenantResponse:
        if not get_settings().demo_mode:
            raise HTTPException(404, "Resource not found.")
        now = datetime.now(UTC)
        return DemoTenantResponse(
            demo=True,
            organization_id="org_demo",
            organization_name="Demo Restaurant Group",
            location_id="loc_demo_downtown",
            location_name="Downtown Dining Room",
            time_zone="America/New_York",
            tables=[
                DemoTable(id="table_01", label="T01", state="AVAILABLE", state_since=now),
                DemoTable(id="table_02", label="T02", state="OCCUPIED", state_since=now),
                DemoTable(id="table_03", label="T03", state="RESET_PENDING", state_since=now),
                DemoTable(id="table_04", label="T04", state="UNKNOWN", state_since=now),
            ],
        )

    original_openapi = app.openapi

    def openapi_with_session_security():
        schema = original_openapi()
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["SessionCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": get_settings().cookie_name,
            "description": "HttpOnly session cookie; writes also require Origin and X-CSRF-Token.",
        }
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                if (
                    path.startswith("/v1/")
                    and path != "/v1/demo/tenant"
                    and not (path == "/v1/auth/session" and method == "post")
                    and method in {"get", "post", "patch", "put", "delete"}
                ):
                    operation["security"] = [{"SessionCookie": []}]
        return schema

    app.openapi = openapi_with_session_security
    return app


app = create_app()
