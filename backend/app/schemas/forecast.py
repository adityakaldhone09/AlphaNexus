from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class ForecastGenerateRequest(BaseModel):
    metric_name: Literal["revenue", "net_profit", "ebitda", "eps"] = "revenue"
    forecast_horizon_years: int = Field(default=3, ge=1, le=5)


class ForecastPeriodItem(BaseModel):
    period: str
    base: float
    bullish: float
    bearish: float
    confidence_intervals: Dict[str, Any]


class ForecastResponse(BaseModel):
    status: str
    company_id: Optional[str] = None
    company_symbol: str
    metric_name: str
    historical: List[Dict[str, Any]] = Field(default_factory=list)
    historical_points: Optional[int] = None
    forecasts: List[ForecastPeriodItem] = Field(default_factory=list)
    evaluation: Optional[Dict[str, Any]] = None
    disclaimer: str = ""
    message: Optional[str] = None
