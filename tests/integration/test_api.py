"""
Integration tests for ALPHANEXUS FastAPI endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import is_sqlite

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Operational"


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_engine_health_reports_observed_state():
    response = client.get("/api/v1/health/engines")
    assert response.status_code == 200
    data = response.json()
    assert data["total_engines"] == len(data["engines"])
    assert "configured_count" in data
    assert "unavailable_count" in data
    assert all(
        {"state", "configured", "verified", "last_checked"} <= engine.keys()
        for engine in data["engines"].values()
    )


def test_safe_system_configuration_does_not_expose_credentials():
    response = client.get("/api/v1/health/config")
    assert response.status_code == 200
    data = response.json()
    assert "api_key" not in str(data).lower()
    assert "access_token" not in str(data).lower()


def test_integration_status_matches_active_database_and_probe_state():
    response = client.get("/api/v1/health/integrations")
    assert response.status_code == 200
    integrations = response.json()["integrations"]
    database = next(
        item for item in integrations
        if item["provider"] in ("SQLite (development fallback)", "PostgreSQL")
    )
    if is_sqlite:
        assert database["status"] == "Degraded"
        assert database["model"] == "SQLite"
    else:
        assert database["status"] == "Connected"
        assert database["model"] == "PostgreSQL"

    untested = [item for item in integrations if item["status"] == "Configured"]
    assert all(item["error_message"] is None for item in untested)
    assert all(item["error_category"] is None for item in untested)


def test_companies_list_endpoint():
    response = client.get("/api/v1/companies?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
