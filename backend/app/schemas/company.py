from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, UUID4, ConfigDict


class CompanyBase(BaseModel):
    symbol: str
    name: str
    exchange: str = "NSE"
    isin: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    current_price: Optional[float] = None
    day_change: Optional[float] = None
    day_change_percent: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    dividend_yield: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    currency: str = "INR"
    description: Optional[str] = None
    website: Optional[str] = None


class CompanyResponse(CompanyBase):
    id: Optional[UUID4] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: Optional[str] = "In Database"
    is_registered: Optional[bool] = True

    model_config = ConfigDict(from_attributes=True)


class CompanyDetailResponse(CompanyResponse):
    pass


class CompanySearchResult(CompanyBase):
    id: Optional[UUID4] = None
    status: str = "In Database"
    is_registered: bool = True

    model_config = ConfigDict(from_attributes=True)


class DiscoverCompanyRequest(BaseModel):
    identifier: str


class SyncCompanyResponse(BaseModel):
    message: str
    refreshed_count: int
    seeded_identifiers: int
    timestamp: str
