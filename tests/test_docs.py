"""Tests for auto-generated API documentation."""

from fastapi.testclient import TestClient


def test_swagger_docs_available(client: TestClient) -> None:
    """GET /docs returns the Swagger UI page."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()


def test_openapi_schema_available(client: TestClient) -> None:
    """GET /openapi.json returns the OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "paths" in schema
    assert "/health" in schema["paths"]
