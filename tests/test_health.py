"""Tests for the health check endpoint."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """GET /health returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok", "database": "connected"}


def test_health_is_json(client: TestClient) -> None:
    """GET /health returns application/json."""
    response = client.get("/health")
    assert response.headers["content-type"] == "application/json"
