import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger


class FinnhubProvider:
    """
    Adapter for Finnhub Financial API (https://finnhub.io).
    Provides global equity quotes, company profiles, market news,
    sentiment indicators, and financial metrics.
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        self.api_key = api_key or settings.effective_finnhub_key
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Finnhub-Token": self.api_key or "",
            "User-Agent": "AlphaNexus-MarketAnalytics/1.0",
        }

    def check_availability(self) -> Dict[str, Any]:
        """Probes Finnhub and returns health diagnostics."""
        if not self.is_configured:
            return {
                "available": False,
                "provider": "Finnhub",
                "status": "Not configured",
                "reason": "FINHUB_API_KEY / FINNHUB_API_KEY is not configured.",
                "http_status": None,
                "latency_ms": 0,
            }

        t0 = time.time()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.BASE_URL}/quote",
                    params={"symbol": "AAPL"},
                    headers=self._headers(),
                )
                lat = round((time.time() - t0) * 1000, 1)

                if res.status_code == 200:
                    data = res.json()
                    # Finnhub returns { "c": 0, ... } or quote object
                    return {
                        "available": True,
                        "provider": "Finnhub",
                        "status": "Connected",
                        "model": "Finnhub API v1",
                        "http_status": 200,
                        "latency_ms": lat,
                        "information": "Global equities, quotes, and market feeds active.",
                        "error": None,
                    }
                elif res.status_code in (401, 403):
                    return {
                        "available": False,
                        "provider": "Finnhub",
                        "status": "Unavailable",
                        "model": "Finnhub",
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "error_category": "authentication",
                        "information": "Finnhub authentication failed.",
                        "error": f"HTTP {res.status_code}: Invalid or unauthorized API key.",
                    }
                elif res.status_code == 429:
                    return {
                        "available": False,
                        "provider": "Finnhub",
                        "status": "Degraded",
                        "model": "Finnhub",
                        "http_status": 429,
                        "latency_ms": lat,
                        "error_category": "quota",
                        "information": "Finnhub API rate limit reached.",
                        "error": "HTTP 429: Rate limit exceeded (60 calls/min limit).",
                    }
                else:
                    return {
                        "available": False,
                        "provider": "Finnhub",
                        "status": "Unavailable",
                        "model": "Finnhub",
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "error_category": "provider_error",
                        "information": "Finnhub returned an error.",
                        "error": f"HTTP {res.status_code}: {res.text[:100]}",
                    }
        except httpx.TimeoutException:
            lat = round((time.time() - t0) * 1000, 1)
            return {
                "available": False,
                "provider": "Finnhub",
                "status": "Unavailable",
                "model": "Finnhub",
                "http_status": 504,
                "latency_ms": lat,
                "error_category": "network",
                "information": "Request to Finnhub timed out.",
                "error": "Gateway timeout connecting to Finnhub.",
            }
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            return {
                "available": False,
                "provider": "Finnhub",
                "status": "Unavailable",
                "model": "Finnhub",
                "http_status": 500,
                "latency_ms": lat,
                "error_category": "network",
                "information": "Exception connecting to Finnhub.",
                "error": str(e),
            }

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetches real-time quote for a global symbol (e.g. AAPL, MSFT)."""
        if not self.is_configured:
            return {"is_live": False, "symbol": symbol, "error": "Finnhub not configured."}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.BASE_URL}/quote",
                    params={"symbol": symbol.upper()},
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "is_live": True,
                        "provider": "Finnhub",
                        "symbol": symbol.upper(),
                        "current_price": data.get("c"),
                        "change": data.get("d"),
                        "percent_change": data.get("dp"),
                        "high": data.get("h"),
                        "low": data.get("l"),
                        "open": data.get("o"),
                        "previous_close": data.get("pc"),
                        "timestamp": data.get("t"),
                    }
                return {
                    "is_live": False,
                    "symbol": symbol,
                    "http_status": res.status_code,
                    "error": f"HTTP {res.status_code}: {res.text[:120]}",
                }
        except Exception as e:
            logger.error("Finnhub get_quote exception for %s: %s", symbol, str(e))
            return {"is_live": False, "symbol": symbol, "error": str(e)}

    def get_company_profile(self, symbol: str) -> Dict[str, Any]:
        """Fetches company profile and metadata."""
        if not self.is_configured:
            return {"is_live": False, "symbol": symbol, "error": "Finnhub not configured."}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.BASE_URL}/stock/profile2",
                    params={"symbol": symbol.upper()},
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "is_live": True,
                        "provider": "Finnhub",
                        "symbol": symbol.upper(),
                        "name": data.get("name"),
                        "ticker": data.get("ticker"),
                        "country": data.get("country"),
                        "currency": data.get("currency"),
                        "exchange": data.get("exchange"),
                        "ipo": data.get("ipo"),
                        "market_capitalization": data.get("marketCapitalization"),
                        "share_outstanding": data.get("shareOutstanding"),
                        "finnhub_industry": data.get("finnhubIndustry"),
                        "weburl": data.get("weburl"),
                        "logo": data.get("logo"),
                    }
                return {
                    "is_live": False,
                    "symbol": symbol,
                    "http_status": res.status_code,
                    "error": f"HTTP {res.status_code}: {res.text[:120]}",
                }
        except Exception as e:
            logger.error("Finnhub get_company_profile exception for %s: %s", symbol, str(e))
            return {"is_live": False, "symbol": symbol, "error": str(e)}

    def get_market_news(self, category: str = "general") -> Dict[str, Any]:
        """Fetches global market news from Finnhub."""
        if not self.is_configured:
            return {"is_live": False, "articles": [], "error": "Finnhub not configured."}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.BASE_URL}/news",
                    params={"category": category},
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    articles = []
                    for item in (data if isinstance(data, list) else []):
                        articles.append({
                            "title": item.get("headline"),
                            "description": item.get("summary"),
                            "url": item.get("url"),
                            "source": item.get("source") or "Finnhub",
                            "published_at": datetime.fromtimestamp(
                                item.get("datetime", int(time.time())), timezone.utc
                            ).isoformat(),
                            "image_url": item.get("image"),
                            "category": item.get("category"),
                        })
                    return {
                        "is_live": True,
                        "provider": "Finnhub",
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
            logger.error("Finnhub get_market_news exception: %s", str(e))
            return {"is_live": False, "articles": [], "error": str(e)}

