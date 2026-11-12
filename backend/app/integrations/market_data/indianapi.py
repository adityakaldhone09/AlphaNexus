import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger


class IndianAPIProvider:
    """
    Adapter for IndianAPI (https://stock.indianapi.in).
    Provides real-time Indian equity quotes (NSE/BSE), company profiles,
    financial metrics, balance sheet/income statements, corporate actions,
    historical price series, recent announcements, and market news.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.INDIANAPI_API_KEY
        self.base_url = (base_url or settings.INDIANAPI_BASE_URL or "https://stock.indianapi.in").rstrip("/")
        self.timeout = float(timeout or settings.INDIANAPI_TIMEOUT or 15.0)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Api-Key": self.api_key or "",
            "Accept": "application/json",
            "User-Agent": "AlphaNexus-MarketIntelligence/1.0",
        }

    def check_availability(self) -> Dict[str, Any]:
        """Probes the IndianAPI service and returns health diagnostics."""
        if not self.is_configured:
            return {
                "available": False,
                "provider": "IndianAPI",
                "status": "Not configured",
                "reason": "INDIANAPI_API_KEY is not configured.",
                "http_status": None,
                "latency_ms": 0,
            }

        t0 = time.time()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.base_url}/news",
                    headers=self._headers(),
                )
                lat = round((time.time() - t0) * 1000, 1)

                if res.status_code == 200:
                    return {
                        "available": True,
                        "provider": "IndianAPI",
                        "status": "Connected",
                        "model": "IndianAPI (stock.indianapi.in)",
                        "http_status": 200,
                        "latency_ms": lat,
                        "information": "Indian equities, financials, news, and corporate actions active.",
                        "error": None,
                    }
                elif res.status_code in (401, 403):
                    return {
                        "available": False,
                        "provider": "IndianAPI",
                        "status": "Unavailable",
                        "model": "IndianAPI",
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "error_category": "authentication",
                        "information": "Authentication failed with IndianAPI.",
                        "error": f"HTTP {res.status_code}: Access forbidden or invalid API key.",
                    }
                elif res.status_code == 429:
                    return {
                        "available": False,
                        "provider": "IndianAPI",
                        "status": "Degraded",
                        "model": "IndianAPI",
                        "http_status": 429,
                        "latency_ms": lat,
                        "error_category": "quota",
                        "information": "IndianAPI rate limit reached.",
                        "error": "HTTP 429: Rate limit exceeded.",
                    }
                else:
                    return {
                        "available": False,
                        "provider": "IndianAPI",
                        "status": "Unavailable",
                        "model": "IndianAPI",
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "error_category": "provider_error",
                        "information": "IndianAPI returned an error response.",
                        "error": f"HTTP {res.status_code}: {res.text[:100]}",
                    }
        except httpx.TimeoutException:
            lat = round((time.time() - t0) * 1000, 1)
            return {
                "available": False,
                "provider": "IndianAPI",
                "status": "Unavailable",
                "model": "IndianAPI",
                "http_status": 504,
                "latency_ms": lat,
                "error_category": "network",
                "information": "Request to IndianAPI timed out.",
                "error": "Gateway timeout connecting to IndianAPI.",
            }
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            return {
                "available": False,
                "provider": "IndianAPI",
                "status": "Unavailable",
                "model": "IndianAPI",
                "http_status": 500,
                "latency_ms": lat,
                "error_category": "network",
                "information": "Exception connecting to IndianAPI.",
                "error": str(e),
            }

    def get_stock(self, symbol: str) -> Dict[str, Any]:
        """
        Retrieves company profile, current quote, technical data, key ratios,
        and financials for an Indian equity symbol (e.g., RELIANCE, TCS, INFY).
        """
        if not self.is_configured:
            return {"is_live": False, "symbol": symbol, "error": "IndianAPI not configured."}

        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.base_url}/stock",
                    params={"name": clean_symbol},
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    curr_price = data.get("currentPrice") or {}
                    nse_price = curr_price.get("NSE")
                    bse_price = curr_price.get("BSE")
                    price_val = None
                    try:
                        price_val = float(nse_price or bse_price) if (nse_price or bse_price) else None
                    except (ValueError, TypeError):
                        pass

                    return {
                        "is_live": True,
                        "provider": "IndianAPI",
                        "symbol": clean_symbol,
                        "company_name": data.get("companyName"),
                        "industry": data.get("industry"),
                        "current_price": price_val,
                        "current_price_raw": curr_price,
                        "percent_change": data.get("percentChange"),
                        "year_high": data.get("yearHigh"),
                        "year_low": data.get("yearLow"),
                        "company_profile": data.get("companyProfile", {}),
                        "key_metrics": data.get("keyMetrics", {}),
                        "financials": data.get("financials", []),
                        "stock_technical_data": data.get("stockTechnicalData", {}),
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    }
                return {
                    "is_live": False,
                    "symbol": clean_symbol,
                    "http_status": res.status_code,
                    "error": f"HTTP {res.status_code}: {res.text[:120]}",
                }
        except Exception as e:
            logger.error("IndianAPI get_stock exception for %s: %s", clean_symbol, str(e))
            return {"is_live": False, "symbol": clean_symbol, "error": str(e)}

    def get_historical_data(self, symbol: str, period: str = "1m") -> Dict[str, Any]:
        """
        Fetches historical price datasets for an Indian equity.
        Supported periods: '1m', '6m', '1yr', '3yr', '5yr', '10yr', 'max'.
        """
        if not self.is_configured:
            return {"is_live": False, "symbol": symbol, "error": "IndianAPI not configured."}

        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").strip().upper()

        period_map = {
            "1mo": "1m",
            "1m": "1m",
            "30d": "1m",
            "6mo": "6m",
            "6m": "6m",
            "1y": "1yr",
            "1yr": "1yr",
            "3y": "3yr",
            "3yr": "3yr",
            "5y": "5yr",
            "5yr": "5yr",
            "10y": "10yr",
            "10yr": "10yr",
            "max": "max",
            "all": "max",
        }
        api_period = period_map.get(period.lower(), "1m")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.base_url}/historical_data",
                    params={"stock_name": clean_symbol, "period": api_period, "filter": "price"},
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    datasets = data.get("datasets", [])
                    price_points: List[Dict[str, Any]] = []
                    for ds in datasets:
                        values = ds.get("values", [])
                        for row in values:
                            if len(row) >= 2:
                                try:
                                    price_points.append({
                                        "date": row[0],
                                        "close": float(row[1]),
                                    })
                                except (ValueError, TypeError):
                                    continue

                    return {
                        "is_live": True,
                        "symbol": clean_symbol,
                        "period": api_period,
                        "count": len(price_points),
                        "prices": price_points,
                        "raw_datasets": datasets,
                    }
                return {
                    "is_live": False,
                    "symbol": clean_symbol,
                    "http_status": res.status_code,
                    "error": f"HTTP {res.status_code}: {res.text[:120]}",
                }
        except Exception as e:
            logger.error("IndianAPI get_historical_data exception for %s: %s", clean_symbol, str(e))
            return {"is_live": False, "symbol": clean_symbol, "error": str(e)}

    def get_corporate_actions(self, symbol: str) -> Dict[str, Any]:
        """
        Retrieves corporate actions including dividends, board meetings,
        stock splits, bonus issues, and rights issues.
        """
        if not self.is_configured:
            return {"is_live": False, "symbol": symbol, "error": "IndianAPI not configured."}

        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.base_url}/corporate_actions",
                    params={"stock_name": clean_symbol},
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "is_live": True,
                        "symbol": clean_symbol,
                        "dividends": data.get("dividends", {}),
                        "board_meetings": data.get("board_meetings", {}),
                        "splits": data.get("splits", {}),
                        "bonus": data.get("bonus", {}),
                        "rights": data.get("rights", {}),
                    }
                return {
                    "is_live": False,
                    "symbol": clean_symbol,
                    "http_status": res.status_code,
                    "error": f"HTTP {res.status_code}: {res.text[:120]}",
                }
        except Exception as e:
            logger.error("IndianAPI get_corporate_actions exception for %s: %s", clean_symbol, str(e))
            return {"is_live": False, "symbol": clean_symbol, "error": str(e)}

    def get_recent_announcements(self, symbol: str) -> Dict[str, Any]:
        """Fetches company exchange announcements (BSE/NSE)."""
        if not self.is_configured:
            return {"is_live": False, "symbol": symbol, "error": "IndianAPI not configured."}

        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.base_url}/recent_announcements",
                    params={"stock_name": clean_symbol},
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    announcements = data if isinstance(data, list) else []
                    return {
                        "is_live": True,
                        "symbol": clean_symbol,
                        "announcements": announcements,
                    }
                return {
                    "is_live": False,
                    "symbol": clean_symbol,
                    "http_status": res.status_code,
                    "error": f"HTTP {res.status_code}: {res.text[:120]}",
                }
        except Exception as e:
            logger.error("IndianAPI get_recent_announcements exception for %s: %s", clean_symbol, str(e))
            return {"is_live": False, "symbol": clean_symbol, "error": str(e)}

    def get_market_news(self) -> Dict[str, Any]:
        """Fetches real-time Indian financial and market news."""
        if not self.is_configured:
            return {"is_live": False, "articles": [], "error": "IndianAPI not configured."}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.base_url}/news",
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    articles = data if isinstance(data, list) else []
                    return {
                        "is_live": True,
                        "provider": "IndianAPI",
                        "count": len(articles),
                        "articles": articles,
                    }
                return {
                    "is_live": False,
                    "articles": [],
                    "http_status": res.status_code,
                    "error": f"HTTP {res.status_code}: {res.text[:120]}",
                }
        except Exception as e:
            logger.error("IndianAPI get_market_news exception: %s", str(e))
            return {"is_live": False, "articles": [], "error": str(e)}

