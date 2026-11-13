import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db, parse_uuid
from app.models.company import Company, CompanyIdentifier
from app.models.document import Document
from app.models.news import NewsArticle
from app.schemas.company import (
    CompanyResponse,
    CompanyDetailResponse,
    DiscoverCompanyRequest,
    SyncCompanyResponse,
)
from app.schemas.document import DocumentResponse
from app.schemas.news import NewsArticleResponse
from app.services.company_discovery import company_discovery_service

router = APIRouter()


@router.get("", response_model=List[CompanyResponse])
def list_companies(
    exchange: Optional[str] = Query(None, description="NSE or BSE filter"),
    sector: Optional[str] = Query(None, description="Sector filter"),
    search: Optional[str] = Query(None, description="Search term for symbol or name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Company).filter(Company.is_active == True)

    if exchange:
        query = query.filter(Company.exchange == exchange.upper())
    if sector:
        query = query.filter(Company.sector == sector)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Company.symbol.ilike(search_pattern),
                Company.name.ilike(search_pattern),
                Company.isin.ilike(search_pattern),
            )
        )

    return query.order_by(Company.market_cap.desc().nullslast()).offset(skip).limit(limit).all()


@router.get("/search", response_model=List[CompanyResponse])
def search_companies(
    q: str = Query(..., min_length=1, description="Company symbol, name, ISIN, or alias"),
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Universal multi-tiered company search across:
      1. Canonical database records
      2. Identifier cross-references (ISIN, BSE scrip, Aliases)
      3. Authoritative Master Equities Universe (NIFTY 100/200)
      4. Live exchange discovery via IndianAPI
    """
    results = company_discovery_service.search(db, query=q, limit=limit)
    return results


@router.post("/discover", response_model=CompanyDetailResponse)
def discover_company(
    payload: DiscoverCompanyRequest,
    db: Session = Depends(get_db),
):
    """
    Explicitly discovers, identifies, and provisions a company into the canonical
    database using its symbol, ISIN, BSE scrip code, or legal trade name.
    """
    company = company_discovery_service.resolve_or_create(db, payload.identifier)
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Company with identifier '{payload.identifier}' could not be resolved from authoritative sources.",
        )
    return company


@router.post("/sync", response_model=SyncCompanyResponse)
def sync_companies(
    db: Session = Depends(get_db),
):
    """
    Administrative refresh: synchronizes company identifiers, quotes, and metrics.
    """
    seeded_idents = company_discovery_service.seed_universe_identifiers(db)
    active_comps = db.query(Company).filter(Company.is_active == True).all()

    refreshed = 0
    for comp in active_comps:
        company_discovery_service.hydrate_company_data(db, comp)
        refreshed += 1

    db.commit()

    return SyncCompanyResponse(
        message=f"Successfully synced {refreshed} companies and seeded {seeded_idents} identifiers.",
        refreshed_count=refreshed,
        seeded_identifiers=seeded_idents,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/{company_id}", response_model=CompanyDetailResponse)
def get_company(company_id: str, db: Session = Depends(get_db)):
    """
    Retrieves a company by UUID, Symbol, or ISIN.
    If the company is in the Master Universe or live exchange feeds but not yet provisioned,
    it is dynamically discovered and provisioned on-the-fly.
    """
    company = None
    try:
        val_uuid = uuid.UUID(company_id)
        company = db.query(Company).filter(Company.id == val_uuid).first()
    except (ValueError, AttributeError):
        pass

    if not company:
        company = db.query(Company).filter(Company.symbol == company_id.upper()).first()

    if not company:
        company = db.query(Company).filter(Company.isin == company_id.upper()).first()

    # Dynamic Discovery Fallback
    if not company:
        company = company_discovery_service.resolve_or_create(db, company_id)

    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found.")
    return company


@router.get("/{company_id}/profile", response_model=Dict[str, Any])
def get_company_profile(company_id: str, db: Session = Depends(get_db)):
    """
    Unified company profile combining core corporate data, live market intelligence,
    identifiers, and update timestamps.
    """
    company = None
    try:
        val_uuid = uuid.UUID(company_id)
        company = db.query(Company).filter(Company.id == val_uuid).first()
    except (ValueError, AttributeError):
        pass

    if not company:
        company = company_discovery_service.resolve_or_create(db, company_id)

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Fetch normalized identifiers
    idents = db.query(CompanyIdentifier).filter(CompanyIdentifier.company_id == company.id).all()
    ident_list = [{"type": i.identifier_type, "value": i.identifier_value} for i in idents]

    return {
        "overview": {
            "id": str(company.id),
            "symbol": company.symbol,
            "name": company.name,
            "exchange": company.exchange,
            "isin": company.isin,
            "sector": company.sector,
            "industry": company.industry,
            "market_cap": float(company.market_cap) if company.market_cap else None,
            "currency": company.currency,
            "description": company.description,
            "website": company.website,
        },
        "market_intelligence": {
            "current_price": float(company.current_price) if company.current_price else None,
            "day_change": float(company.day_change) if company.day_change else None,
            "day_change_percent": float(company.day_change_percent) if company.day_change_percent else None,
            "week_52_high": float(company.week_52_high) if company.week_52_high else None,
            "week_52_low": float(company.week_52_low) if company.week_52_low else None,
            "pe_ratio": float(company.pe_ratio) if company.pe_ratio else None,
            "pb_ratio": float(company.pb_ratio) if company.pb_ratio else None,
            "dividend_yield": float(company.dividend_yield) if company.dividend_yield else None,
            "roe": float(company.roe) if company.roe else None,
            "roce": float(company.roce) if company.roce else None,
        },
        "identifiers": ident_list,
        "source": "AlphaNexus Central Registry & IndianAPI",
        "last_updated": company.updated_at.isoformat() if company.updated_at else datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{company_id}/documents", response_model=List[DocumentResponse])
def get_company_documents(company_id: str, db: Session = Depends(get_db)):
    """Retrieves all indexed financial documents for the company."""
    parsed_id = parse_uuid(company_id)
    query = db.query(Document)
    if parsed_id:
        query = query.filter(Document.company_id == parsed_id)
    else:
        comp = db.query(Company).filter(Company.symbol == company_id.upper()).first()
        if comp:
            query = query.filter(Document.company_id == comp.id)
        else:
            return []

    return query.order_by(Document.created_at.desc()).all()


@router.get("/{company_id}/news", response_model=List[NewsArticleResponse])
def get_company_news(company_id: str, db: Session = Depends(get_db)):
    """Retrieves verified news articles for the company."""
    parsed_id = parse_uuid(company_id)
    query = db.query(NewsArticle)
    if parsed_id:
        query = query.filter(NewsArticle.company_id == parsed_id)
    else:
        comp = db.query(Company).filter(Company.symbol == company_id.upper()).first()
        if comp:
            query = query.filter(NewsArticle.company_id == comp.id)
        else:
            return []

    return query.order_by(NewsArticle.published_at.desc().nullslast()).limit(30).all()
