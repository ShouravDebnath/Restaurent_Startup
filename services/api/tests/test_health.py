from fastapi.testclient import TestClient

from restaurant_api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "restaurant-ai-api"


def test_demo_tenant_is_explicitly_synthetic() -> None:
    response = client.get("/v1/demo/tenant")

    assert response.status_code == 200
    assert response.json()["demo"] is True
    assert len(response.json()["tables"]) == 4
