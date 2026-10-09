from fastapi.testclient import TestClient

from app import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "media-api"
    assert data["version"] == "1.0.0"