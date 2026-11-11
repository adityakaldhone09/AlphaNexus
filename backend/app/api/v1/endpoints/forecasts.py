from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import get_db, parse_uuid
from app.models.company import Company
from app.engines.forecasting.service import ForecastCompanyNotFound, forecasting_service
from app.schemas.forecast import ForecastResponse, ForecastGenerateRequest

router = APIRouter()


def _find_company(db: Session, company_id: str) -> Company:
    parsed_id = parse_uuid(company_id)
    if parsed_id is not None:
        company = db.query(Company).filter(Company.id == parsed_id).first()
        if company is not None:
            return company
    company = db.query(Company).filter(Company.symbol == company_id.upper()).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _database_error(db: Session) -> None:
    db.rollback()
    raise HTTPException(
        status_code=503,
        detail={
            "code": "forecast_database_error",
            "message": "Forecast data is temporarily unavailable.",
        },
    )


@router.get("/companies/{company_id}/forecasts", response_model=ForecastResponse)
def get_company_forecasts(
    company_id: str,
    metric_name: Literal["revenue", "net_profit", "ebitda", "eps"] = Query(
        "revenue", description="revenue, net_profit, ebitda, eps"
    ),
    db: Session = Depends(get_db),
):
    try:
        company = _find_company(db, company_id)
        return forecasting_service.generate_company_forecast(
            db=db,
            company_id=company.id,
            metric_name=metric_name,
            forecast_horizon_years=3,
        )
    except SQLAlchemyError:
        _database_error(db)
    except ForecastCompanyNotFound:
        raise HTTPException(status_code=404, detail="Company not found")


@router.post("/companies/{company_id}/forecasts/generate", response_model=ForecastResponse)
def generate_forecast(
    company_id: str,
    payload: ForecastGenerateRequest,
    db: Session = Depends(get_db),
):
    try:
        company = _find_company(db, company_id)
        return forecasting_service.generate_company_forecast(
            db=db,
            company_id=company.id,
            metric_name=payload.metric_name,
            forecast_horizon_years=payload.forecast_horizon_years,
        )
    except SQLAlchemyError:
        _database_error(db)
    except ForecastCompanyNotFound:
        raise HTTPException(status_code=404, detail="Company not found")
