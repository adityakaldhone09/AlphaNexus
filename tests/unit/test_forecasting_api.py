from datetime import date
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import forecasts
from app.core.database import get_db
from app.models.company import Company
from app.models.financial import FinancialMetric
from app.models.forecast import Forecast


@pytest.fixture
def forecast_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Company.__table__.create(engine)
    FinancialMetric.__table__.create(engine)
    Forecast.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        Forecast.__table__.drop(engine)
        FinancialMetric.__table__.drop(engine)
        Company.__table__.drop(engine)
        engine.dispose()


@pytest.fixture
def forecast_client(forecast_database):
    test_app = FastAPI()
    test_app.include_router(forecasts.router, prefix="/api/v1")
    test_app.dependency_overrides[get_db] = lambda: forecast_database
    with TestClient(test_app) as client:
        yield client


def add_company(db, *, symbol="TEST", metrics=None):
    company = Company(id=uuid.uuid4(), symbol=symbol, name=f"{symbol} Company")
    db.add(company)
    db.flush()
    for metric_name, year, value in metrics or []:
        db.add(
            FinancialMetric(
                company_id=company.id,
                metric_name=metric_name,
                metric_category="growth",
                period_type="annual",
                financial_year=year,
                period_end_date=date(2000 + int(year[-2:]), 3, 31),
                value=value,
            )
        )
    db.commit()
    return company


def test_company_primary_key_is_uuid_and_forecast_uses_uuid_object(forecast_client, forecast_database):
    company = add_company(
        forecast_database,
        metrics=[("revenue", "FY22", 100), ("revenue", "FY23", 120)],
    )
    assert Company.__table__.c.id.type.as_uuid is True
    assert Company.__table__.c.id.type.python_type is uuid.UUID

    response = forecast_client.get(f"/api/v1/companies/{company.id}/forecasts?metric_name=revenue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["company_id"] == str(company.id)
    assert payload["metric_name"] == "revenue"
    assert payload["forecasts"][0]["period"] == "FY24"
    assert forecast_database.query(Forecast).count() == 9


def test_company_symbol_route_remains_supported(forecast_client, forecast_database):
    add_company(
        forecast_database,
        symbol="TEST",
        metrics=[("revenue", "FY22", 100), ("revenue", "FY23", 120)],
    )

    response = forecast_client.get("/api/v1/companies/test/forecasts")

    assert response.status_code == 200
    assert response.json()["company_symbol"] == "TEST"


@pytest.mark.parametrize("company_id", ["not-a-uuid", str(uuid.uuid4())])
def test_invalid_or_missing_company_identifier_returns_404(forecast_client, company_id):
    response = forecast_client.get(f"/api/v1/companies/{company_id}/forecasts")
    assert response.status_code == 404


def test_metric_selection_uses_requested_financial_metric(forecast_client, forecast_database):
    company = add_company(
        forecast_database,
        metrics=[
            ("revenue", "FY23", 120),
            ("revenue", "FY22", 100),
            ("net_profit", "FY23", 15),
            ("net_profit", "FY22", 10),
        ],
    )

    response = forecast_client.get(
        f"/api/v1/companies/{company.id}/forecasts?metric_name=net_profit"
    )

    assert response.status_code == 200
    assert response.json()["metric_name"] == "net_profit"
    assert [point["value"] for point in response.json()["historical"]] == [10, 15]


@pytest.mark.parametrize("metrics", [[], [("revenue", "FY23", 120)]])
def test_missing_or_insufficient_history_returns_structured_empty_forecast(
    forecast_client, forecast_database, metrics
):
    company = add_company(forecast_database, metrics=metrics)

    response = forecast_client.get(f"/api/v1/companies/{company.id}/forecasts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "INSUFFICIENT_DATA"
    assert payload["forecasts"] == []
    assert payload["historical_points"] == len(metrics)
    assert "Insufficient historical data" in payload["message"]
    assert forecast_database.query(Forecast).count() == 0


def test_invalid_metric_returns_422(forecast_client, forecast_database):
    company = add_company(forecast_database)

    response = forecast_client.get(
        f"/api/v1/companies/{company.id}/forecasts?metric_name=unsupported"
    )
    assert response.status_code == 422


def test_database_query_failure_returns_service_unavailable(
    forecast_client, monkeypatch
):
    def fail_query(*args, **kwargs):
        raise OperationalError("select", {}, Exception("database unavailable"))

    monkeypatch.setattr(forecasts, "_find_company", fail_query)

    response = forecast_client.get(f"/api/v1/companies/{uuid.uuid4()}/forecasts")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "forecast_database_error"
