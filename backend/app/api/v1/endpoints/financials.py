from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db, parse_uuid
from app.models.company import Company
from app.models.financial import FinancialMetric, FinancialStatement
from app.engines.analytics.formulas import FinancialCalculator
from app.engines.analytics.peer_analyzer import PeerAnalyzer
from app.schemas.financial import (
    FinancialMetricResponse,
    FinancialStatementResponse,
    RatiosResponse,
    PeerCompareRequest,
    PeerCompareResponse,
)

router = APIRouter()


@router.get("/companies/{company_id}/financials", response_model=List[FinancialMetricResponse])
def get_company_financials(
    company_id: str,
    period_type: str = Query("annual", description="annual or quarterly"),
    metric_category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == parse_uuid(company_id)).first()
    if not company:
        company = db.query(Company).filter(Company.symbol == company_id.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    query = db.query(FinancialMetric).filter(
        FinancialMetric.company_id == company.id,
        FinancialMetric.period_type == period_type,
    )
    if metric_category:
        query = query.filter(FinancialMetric.metric_category == metric_category)

    return query.order_by(FinancialMetric.period_end_date.desc()).all()


@router.get("/companies/{company_id}/statements", response_model=List[FinancialStatementResponse])
def get_company_statements(
    company_id: str,
    statement_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == parse_uuid(company_id)).first()
    if not company:
        company = db.query(Company).filter(Company.symbol == company_id.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    query = db.query(FinancialStatement).filter(FinancialStatement.company_id == company.id)
    if statement_type:
        query = query.filter(FinancialStatement.statement_type == statement_type)

    return query.order_by(FinancialStatement.period_end_date.desc()).all()


@router.get("/companies/{company_id}/ratios", response_model=RatiosResponse)
def get_company_ratios(company_id: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == parse_uuid(company_id)).first()
    if not company:
        company = db.query(Company).filter(Company.symbol == company_id.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Aggregate latest annual statement data for deterministic calculation
    metrics = (
        db.query(FinancialMetric)
        .filter(
            FinancialMetric.company_id == company.id,
            FinancialMetric.period_type == "annual",
        )
        .order_by(FinancialMetric.period_end_date.desc())
        .all()
    )

    metrics_map = {m.metric_name: float(m.value) for m in metrics}

    # Add company current quote stats & sector context
    metrics_map["sector"] = company.sector
    metrics_map["current_price"] = float(company.current_price) if company.current_price else None
    metrics_map["pe_ratio"] = float(company.pe_ratio) if company.pe_ratio else None
    metrics_map["pb_ratio"] = float(company.pb_ratio) if company.pb_ratio else None

    computed = FinancialCalculator.compute_all_metrics(metrics_map)

    # If any fields were precomputed or in company table, merge them
    if company.roe:
        computed["roe"] = float(company.roe)
    if company.roce:
        computed["roce"] = float(company.roce)
    if company.pe_ratio:
        computed["pe_ratio"] = float(company.pe_ratio)
    if company.pb_ratio:
        computed["pb_ratio"] = float(company.pb_ratio)

    return RatiosResponse(
        company_symbol=company.symbol,
        computed_metrics=computed,
    )


@router.post("/companies/compare", response_model=PeerCompareResponse)
def compare_peers(payload: PeerCompareRequest, db: Session = Depends(get_db)):
    """Computes side-by-side benchmark comparison matrix for requested peer companies."""
    companies = (
        db.query(Company)
        .filter(Company.id.in_(payload.company_ids))
        .all()
    )
    if not companies:
        # Also try by symbol
        companies = (
            db.query(Company)
            .filter(Company.symbol.in_([s.upper() for s in payload.company_ids]))
            .all()
        )

    peer_data = []
    for c in companies:
        peer_data.append({
            "id": str(c.id),
            "symbol": c.symbol,
            "name": c.name,
            "sector": c.sector,
            "market_cap": float(c.market_cap) if c.market_cap else None,
            "current_price": float(c.current_price) if c.current_price else None,
            "pe_ratio": float(c.pe_ratio) if c.pe_ratio else None,
            "pb_ratio": float(c.pb_ratio) if c.pb_ratio else None,
            "roe": float(c.roe) if c.roe else None,
            "roce": float(c.roce) if c.roce else None,
            "dividend_yield": float(c.dividend_yield) if c.dividend_yield else None,
        })

    result = PeerAnalyzer.compare_companies(peer_data)
    return PeerCompareResponse(
        peer_count=result["peer_count"],
        benchmarks=result["benchmarks"],
        peers=result["peers"],
    )

