import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger


class NewsAPIProvider:
    """
    Adapter for NewsAPI (https://newsapi.org).
    Provides global and Indian business headlines, company search,
    and financial journalism aggregation.
    """

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        self.api_key = api_key or settings.NEWSAPI_API_KEY
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Api-Key": self.api_key or "",
            "User-Agent": "AlphaNexus-NewsService/1.0",
        }

    def check_availability(self) -> Dict[str, Any]:
        """Probes the NewsAPI service and returns health diagnostics."""
        if not self.is_configured:
            return {
                "available": False,
                "provider": "NewsAPI",
                "status": "Not configured",
                "reason": "NEWSAPI_API_KEY is not configured.",
                "http_status": None,
                "latency_ms": 0,
            }

        t0 = time.time()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.BASE_URL}/everything",
                    params={"q": "India finance OR economy", "pageSize": 1, "language": "en"},
                    headers=self._headers(),
                )
                lat = round((time.time() - t0) * 1000, 1)

                if res.status_code == 200:
                    return {
                        "available": True,
                        "provider": "NewsAPI",
                        "status": "Connected",
                        "model": "NewsAPI v2",
                        "http_status": 200,
                        "latency_ms": lat,
                        "information": "Global and Indian news stream operational.",
                        "error": None,
                    }
                elif res.status_code in (401, 403):
                    return {
                        "available": False,
                        "provider": "NewsAPI",
                        "status": "Unavailable",
                        "model": "NewsAPI",
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "error_category": "authentication",
                        "information": "NewsAPI authentication rejected.",
                        "error": f"HTTP {res.status_code}: Invalid or unauthorized API key.",
                    }
                elif res.status_code == 429:
                    return {
                        "available": False,
                        "provider": "NewsAPI",
                        "status": "Degraded",
                        "model": "NewsAPI",
                        "http_status": 429,
                        "latency_ms": lat,
                        "error_category": "quota",
                        "information": "NewsAPI rate limit or daily quota reached.",
                        "error": "HTTP 429: Rate limit exceeded.",
                    }
                else:
                    return {
                        "available": False,
                        "provider": "NewsAPI",
                        "status": "Unavailable",
                        "model": "NewsAPI",
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "error_category": "provider_error",
                        "information": "NewsAPI returned an error.",
                        "error": f"HTTP {res.status_code}: {res.text[:100]}",
                    }
        except httpx.TimeoutException:
            lat = round((time.time() - t0) * 1000, 1)
            return {
                "available": False,
                "provider": "NewsAPI",
                "status": "Unavailable",
                "model": "NewsAPI",
                "http_status": 504,
                "latency_ms": lat,
                "error_category": "network",
                "information": "Request to NewsAPI timed out.",
                "error": "Gateway timeout connecting to NewsAPI.",
            }
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            return {
                "available": False,
                "provider": "NewsAPI",
                "status": "Unavailable",
                "model": "NewsAPI",
                "http_status": 500,
                "latency_ms": lat,
                "error_category": "network",
                "information": "Exception connecting to NewsAPI.",
                "error": str(e),
            }

    def _normalize_article(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        source_info = raw.get("source") or {}
        source_name = source_info.get("name") or "NewsAPI"
        return {
            "title": raw.get("title") or "Untitled",
            "description": raw.get("description") or "",
            "content": raw.get("content") or "",
            "url": raw.get("url") or "",
            "source": source_name,
            "publisher": source_name,
            "author": raw.get("author") or "",
            "published_at": raw.get("publishedAt") or datetime.now(timezone.utc).isoformat(),
            "image_url": raw.get("urlToImage"),
        }

    def get_top_business_news(self, country: str = "in", page_size: int = 15) -> Dict[str, Any]:
        """Fetches top business headlines for a specific country (e.g. 'in', 'us')."""
        if not self.is_configured:
            return {"is_live": False, "articles": [], "error": "NewsAPI not configured."}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.BASE_URL}/top-headlines",
                    params={"country": country, "category": "business", "pageSize": page_size},
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    articles = [
                        self._normalize_article(a)
                        for a in data.get("articles", [])
                        if a.get("title") and a.get("url")
                    ]
                    return {
                        "is_live": True,
                        "provider": "NewsAPI",
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
            logger.error("NewsAPI get_top_business_news exception: %s", str(e))
            return {"is_live": False, "articles": [], "error": str(e)}

    def search_news(self, query: str, page_size: int = 15, language: str = "en") -> Dict[str, Any]:
        """Searches news articles matching a search query or company name."""
        if not self.is_configured:
            return {"is_live": False, "articles": [], "error": "NewsAPI not configured."}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(
                    f"{self.BASE_URL}/everything",
                    params={
                        "q": query,
                        "pageSize": page_size,
                        "language": language,
                        "sortBy": "publishedAt",
                    },
                    headers=self._headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    articles = [
                        self._normalize_article(a)
                        for a in data.get("articles", [])
                        if a.get("title") and a.get("url") and "[Removed]" not in a.get("title", "")
                    ]
                    return {
                        "is_live": True,
                        "provider": "NewsAPI",
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
            logger.error("NewsAPI search_news exception for %s: %s", query, str(e))
            return {"is_live": False, "articles": [], "error": str(e)}

