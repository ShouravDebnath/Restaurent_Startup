from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


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
    app = FastAPI(title="Restaurant AI Monitoring API", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="restaurant-ai-api",
            environment="development",
            checked_at=datetime.now(UTC),
        )

    @app.get("/v1/demo/tenant", response_model=DemoTenantResponse)
    def demo_tenant() -> DemoTenantResponse:
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

    return app


app = create_app()
