from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class EngineDetail(BaseModel):
    name: str
    state: str
    provider: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    details: Optional[str] = None
    configured: bool = False
    connected: Optional[bool] = None
    verified: bool = False
    latency_ms: Optional[float] = None
    last_successful_operation: Optional[datetime] = None
    error_category: Optional[str] = None
    error_message: Optional[str] = None
    last_checked: datetime


class EnginesSummaryResponse(BaseModel):
    status: str
    timestamp: str
    total_engines: int
    ready_count: int
    degraded_count: int
    configured_count: int = 0
    unavailable_count: int = 0
    disabled_count: int
    failed_count: int
    engines: Dict[str, EngineDetail]


class HealthResponse(BaseModel):
    status: str
    environment: str
    data_mode: str
    timestamp: datetime = datetime.utcnow()
    database_connected: bool
    version: str = "1.0.0"
