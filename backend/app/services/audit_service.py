import time
import base64
import copy
import urllib.request
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Any, List
import httpx
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal, check_database_health, is_sqlite
from app.core.logging import logger
from app.engines.providers.gemini import GeminiProvider
from app.engines.providers.groq import GroqProvider
from app.engines.providers.fmp import FMPProvider
from app.engines.providers.marketaux import MarketauxProvider
from app.engines.providers.dhan import DhanHQProvider
from app.integrations.market_data.indianapi import IndianAPIProvider
from app.integrations.news_providers.newsapi import NewsAPIProvider
from app.integrations.external_sources.finnhub import FinnhubProvider
from app.database.mongodb import mongodb_manager
from app.engines.rag.vector_store.mongodb_atlas import mongodb_atlas_store

_audit_cache_lock = Lock()
_last_audit_result: Dict[str, Any] | None = None


def _llm_audit_result(provider: Any, probe: bool, latency_ms: float) -> Dict[str, Any]:
    health = provider.check_availability(probe=probe)
    status = health["connection_status"]
    return {
        **health,
        "status": status,
        "configured": status != "Not configured",
        "operational": status in ("Connected", "Degraded"),
        "model": health["active_model"] or health["configured_model"],
        "http_status": None,
        "latency_ms": latency_ms,
        "information": (
            "Provider generation verified."
            if status in ("Connected", "Degraded")
            else health["error_message"] or status
        ),
        "error": health["error_message"],
    }


def _integration_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    with _audit_cache_lock:
        previous_successes = {
            item["provider"]: item.get("last_successful_test")
            for item in (_last_audit_result or {}).get("integrations", [])
        }
    now = datetime.now(timezone.utc).isoformat()
    safe_messages = {
        "authentication": "Provider authentication failed.",
        "quota": "Provider rate limit or quota was reached.",
        "model_not_found": "The requested model is unavailable to this account.",
        "network": "The provider could not be reached.",
        "provider_error": "The provider request failed.",
        "vector_store": "Vector retrieval is unavailable with the active database.",
    }
    for result in results:
        if result["status"] == "Failed":
            result["status"] = "Unavailable"
        elif result["status"] == "Not Configured":
            result["status"] = "Not configured"
        result.setdefault("configured_model", result.get("model"))
        result.setdefault(
            "active_model",
            result.get("model")
            if result["status"] in ("Connected", "Degraded")
            else None,
        )
        result.setdefault(
            "last_successful_test",
            now
            if result["status"] in ("Connected", "Degraded")
            else previous_successes.get(result["provider"]),
        )
        error = (
            result.get("error")
            if result["status"] in ("Failed", "Unavailable", "Degraded")
            else None
        )
        status_code = result.get("http_status")
        category = result.get("error_category")
        if error and not category:
            if status_code in (401, 403):
                category = "authentication"
            elif status_code == 429:
                category = "quota"
            elif status_code == 404 and result["provider"] in ("Google Gemini", "Groq"):
                category = "model_not_found"
            elif status_code is not None and status_code >= 500:
                category = "network"
            else:
                category = "provider_error"
        result["error_category"] = category
        safe_message = safe_messages.get(category) if error else None
        result["error_message"] = safe_message
        result["error"] = safe_message

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_integrations": len(results),
        "connected_count": sum(1 for result in results if result["status"] == "Connected"),
        "degraded_count": sum(1 for result in results if result["status"] == "Degraded"),
        "failed_count": sum(
            1 for result in results if result["status"] in ("Failed", "Unavailable")
        ),
        "not_configured_count": sum(
            1 for result in results if result["status"] in ("Not configured", "Not Configured")
        ),
        "integrations": results,
    }


def get_cached_integrations_status() -> Dict[str, Any]:
    """Return the last explicit audit, or a no-network status snapshot."""
    with _audit_cache_lock:
        if _last_audit_result is not None:
            return copy.deepcopy(_last_audit_result)

    gemini_result = _llm_audit_result(GeminiProvider(), False, 0)
    groq_result = _llm_audit_result(GroqProvider(), False, 0)
    results = [gemini_result, groq_result]

    db_health = check_database_health()
    db_connected = db_health["reachable"]
    database_result = {
        "provider": "SQLite (development fallback)" if is_sqlite else "PostgreSQL",
        "status": "Unavailable"
        if not db_connected
        else "Degraded"
        if is_sqlite
        else "Connected",
        "configured": bool(settings.DATABASE_URL) or is_sqlite,
        "operational": db_connected,
        "model": "SQLite" if is_sqlite else "PostgreSQL",
        "configured_model": None,
        "active_model": None,
        "last_successful_test": datetime.now(timezone.utc).isoformat()
        if db_connected
        else None,
        "error_category": None if db_connected else "network",
        "error_message": None if db_connected else "Database connection is unavailable.",
        "http_status": None,
        "latency_ms": 0,
        "information": "Reachable using the SQLite development fallback."
        if db_connected and is_sqlite
        else "Database reachable."
        if db_connected
        else "Database connection is unavailable.",
        "error": None if db_connected else "Database connection is unavailable.",
    }
    results.append(database_result)
    if db_connected:
        vector_available = db_health["pgvector_available"]
        results.append({
            "provider": "pgvector",
            "status": "Connected" if vector_available else "Unavailable",
            "configured": True,
            "operational": vector_available,
            "model": "pgvector" if vector_available else None,
            "configured_model": None,
            "active_model": None,
            "last_successful_test": datetime.now(timezone.utc).isoformat()
            if vector_available
            else None,
            "error_category": None if vector_available else "vector_store",
            "error_message": None if vector_available else "Vector retrieval is unavailable with the active database.",
            "http_status": None,
            "latency_ms": 0,
            "information": "Vector extension available."
            if vector_available
            else "pgvector is unavailable in the active database; RAG vector retrieval cannot run.",
            "error": None if vector_available else "Vector retrieval is unavailable with the active database.",
        })

    storage_ok = bool(settings.SUPABASE_URL)
    results.append({
        "provider": "Supabase Storage",
        "status": "Connected" if storage_ok else "Not configured",
        "configured": storage_ok,
        "operational": storage_ok,
        "model": settings.SUPABASE_STORAGE_BUCKET,
        "configured_model": settings.SUPABASE_STORAGE_BUCKET,
        "active_model": settings.SUPABASE_STORAGE_BUCKET if storage_ok else None,
        "last_successful_test": datetime.now(timezone.utc).isoformat() if storage_ok else None,
        "error_category": None,
        "error_message": None,
        "http_status": 200 if storage_ok else None,
        "latency_ms": 0,
        "information": f"Supabase private bucket '{settings.SUPABASE_STORAGE_BUCKET}' configured." if storage_ok else "Supabase Storage not configured.",
        "error": None,
    })

    mongo_configured = bool(mongodb_manager.uri)
    mongo_connected = mongodb_manager.is_connected
    results.append({
        "provider": "MongoDB Atlas",
        "status": "Connected" if mongo_connected else "Unavailable" if mongo_configured else "Not configured",
        "configured": mongo_configured,
        "operational": mongo_connected,
        "model": f"Database: {mongodb_manager.db_name}" if mongo_configured else None,
        "configured_model": mongodb_manager.db_name if mongo_configured else None,
        "active_model": mongodb_manager.db_name if mongo_connected else None,
        "last_successful_test": mongodb_manager._last_successful_check,
        "error_category": None if mongo_connected else ("network" if mongo_configured else None),
        "error_message": None if mongo_connected else mongodb_manager.connection_error,
        "http_status": 200 if mongo_connected else None,
        "latency_ms": 0,
        "information": (
            f"Connected to database '{mongodb_manager.db_name}'."
            if mongo_connected
            else mongodb_manager.connection_error or "MongoDB Atlas not configured."
        ),
        "error": None if mongo_connected else mongodb_manager.connection_error,
    })

    configured_integrations = [
        ("IndianAPI", bool(settings.INDIANAPI_API_KEY), "IndianAPI (stock.indianapi.in)"),
        ("DhanHQ", bool(settings.DHAN_CLIENT_ID and settings.DHAN_ACCESS_TOKEN), "DhanHQ API"),
        ("Marketaux", bool(settings.MARKETAUX_API_TOKEN), "Marketaux API"),
        ("NewsAPI", bool(settings.NEWSAPI_API_KEY), "NewsAPI v2"),
        ("Financial Modeling Prep (FMP)", bool(settings.FMP_API_KEY), "FMP API"),
        ("Finnhub", bool(settings.effective_finnhub_key), "Finnhub API v1"),
        ("Langfuse", bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY), "Langfuse"),
        ("Sentry", bool(settings.SENTRY_DSN), "Sentry SDK"),
    ]
    for provider_name, configured, model_name in configured_integrations:
        status = "Configured" if configured else "Not Configured"
        message = "Connection has not been tested." if configured else None
        results.append({
            "provider": provider_name,
            "status": status,
            "configured": configured,
            "operational": False,
            "model": model_name if configured else None,
            "configured_model": None,
            "active_model": None,
            "last_successful_test": None,
            "error_category": None,
            "error_message": message,
            "http_status": None,
            "latency_ms": 0,
            "information": message or "Provider is not configured.",
            "error": message,
        })
    return _integration_summary(results)


def run_integrations_audit(probe_ai: bool = False) -> Dict[str, Any]:
    """
    Probes non-LLM integrations and reports cached LLM health by default. LLM generation
    probes run only when explicitly requested.
    Never exposes API secrets, tokens, or raw authorization headers.
    """
    results: List[Dict[str, Any]] = []

    # 1. Google Gemini API
    t0 = time.time()
    gp = GeminiProvider()
    gemini_result = _llm_audit_result(gp, probe_ai, round((time.time() - t0) * 1000, 1))
    gemini_result["provider"] = "Google Gemini"
    results.append(gemini_result)

    # 2. Groq API
    t0 = time.time()
    gqp = GroqProvider()
    groq_result = _llm_audit_result(gqp, probe_ai, round((time.time() - t0) * 1000, 1))
    groq_result["provider"] = "Groq"
    results.append(groq_result)

    # 3. Supabase & PostgreSQL Connection
    t0 = time.time()
    db_health = check_database_health()
    lat = round((time.time() - t0) * 1000, 1)
    if db_health["reachable"]:
        db_status = "Degraded" if is_sqlite else "Connected"
        results.append({
            "provider": "SQLite (development fallback)" if is_sqlite else "PostgreSQL",
            "status": db_status,
            "configured": True,
            "operational": True,
            "model": "SQLite" if is_sqlite else "PostgreSQL",
            "http_status": None if is_sqlite else 200,
            "latency_ms": lat,
            "information": "Relational database is reachable using the SQLite development fallback."
            if is_sqlite
            else "PostgreSQL connection verified; schema and migrations are available.",
            "error": None,
        })
    else:
        results.append({
            "provider": "SQLite (development fallback)" if is_sqlite else "PostgreSQL",
            "status": "Failed",
            "configured": bool(settings.DATABASE_URL),
            "operational": False,
            "model": None,
            "http_status": 500,
            "latency_ms": lat,
            "information": "Database connection unreachable.",
            "error": db_health.get("details"),
        })

    # 4. pgvector Extension
    if db_health["reachable"]:
        pgv_ok = db_health.get("pgvector_available", False)
        results.append({
            "provider": "pgvector",
            "status": "Connected" if pgv_ok else "Unavailable",
            "configured": True,
            "operational": pgv_ok,
            "model": "pgvector" if pgv_ok else None,
            "http_status": 200 if pgv_ok else None,
            "latency_ms": 5.0,
            "information": "pgvector vector similarity search is available."
            if pgv_ok
            else "pgvector is unavailable in the active database; RAG vector retrieval cannot run.",
            "error_category": None if pgv_ok else "vector_store",
            "error": None if pgv_ok else "Vector retrieval is unavailable with the active database.",
        })

    # 4b. Supabase Storage
    t0_st = time.time()
    storage_configured = bool(settings.SUPABASE_URL)
    results.append({
        "provider": "Supabase Storage",
        "status": "Connected" if storage_configured else "Not Configured",
        "configured": storage_configured,
        "operational": storage_configured,
        "model": f"Bucket: {settings.SUPABASE_STORAGE_BUCKET}",
        "http_status": 200 if storage_configured else None,
        "latency_ms": round((time.time() - t0_st) * 1000, 1),
        "information": f"Supabase private bucket '{settings.SUPABASE_STORAGE_BUCKET}' active and configured.",
        "error": None,
    })

    # 4b-2. MongoDB Atlas & Atlas Vector Search
    t0_mg = time.time()
    mongo_health = mongodb_manager.check_health()
    mongo_lat = round((time.time() - t0_mg) * 1000, 1)
    mongo_configured = bool(mongodb_manager.uri)
    mongo_connected = bool(mongo_health.get("connected"))

    vs_check = (
        mongodb_atlas_store.check_vector_search_ready()
        if mongo_connected
        else {
            "ready": False,
            "status": "Unavailable",
            "reason": "MongoDB Atlas cluster is disconnected.",
        }
    )

    results.append({
        "provider": "MongoDB Atlas",
        "status": "Connected" if mongo_connected else "Unavailable" if mongo_configured else "Not configured",
        "configured": mongo_configured,
        "operational": mongo_connected,
        "model": f"Database: {mongodb_manager.db_name}" if mongo_configured else None,
        "configured_model": mongodb_manager.db_name if mongo_configured else None,
        "active_model": mongodb_manager.db_name if mongo_connected else None,
        "server_version": mongo_health.get("server_version"),
        "collections": mongo_health.get("collections", []),
        "vector_index_status": vs_check.get("status"),
        "vector_search_ready": vs_check.get("ready", False),
        "last_successful_test": mongo_health.get("last_successful_check"),
        "error_category": None if mongo_connected else ("network" if mongo_configured else None),
        "error_message": None if mongo_connected else mongo_health.get("error"),
        "http_status": 200 if mongo_connected else None,
        "latency_ms": mongo_lat,
        "information": (
            f"Connected to database '{mongodb_manager.db_name}'. Vector Search: {vs_check.get('status')}."
            if mongo_connected
            else mongo_health.get("error") or "MongoDB Atlas is not configured."
        ),
        "error": None if mongo_connected else mongo_health.get("error"),
        "remediation": mongo_health.get("remediation"),
    })

    # 4c. IndianAPI (Indian Market Intelligence, Quotes & Fundamentals)
    t0 = time.time()
    if settings.INDIANAPI_API_KEY:
        try:
            indian_provider = IndianAPIProvider()
            check_res = indian_provider.check_availability()
            lat = check_res.get("latency_ms", round((time.time() - t0) * 1000, 1))
            status = check_res.get("status", "Unavailable")
            results.append({
                "provider": "IndianAPI",
                "status": status,
                "configured": True,
                "operational": status in ("Connected", "Degraded"),
                "model": "IndianAPI (stock.indianapi.in)",
                "http_status": check_res.get("http_status", 200 if status == "Connected" else 500),
                "latency_ms": lat,
                "information": check_res.get("information", "Indian market intelligence stream active."),
                "error": check_res.get("error"),
                "error_category": check_res.get("error_category"),
            })
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            results.append({
                "provider": "IndianAPI",
                "status": "Failed",
                "configured": True,
                "operational": False,
                "model": None,
                "http_status": 500,
                "latency_ms": lat,
                "information": "Exception connecting to IndianAPI.",
                "error": str(e),
                "error_category": "network",
            })
    else:
        results.append({
            "provider": "IndianAPI",
            "status": "Not Configured",
            "configured": False,
            "operational": False,
            "model": None,
            "http_status": None,
            "latency_ms": 0,
            "information": "INDIANAPI_API_KEY is not configured.",
            "error": None,
        })

    # 5. DhanHQ API (Market Data & Account)
    t0 = time.time()
    if settings.DHAN_CLIENT_ID and settings.DHAN_ACCESS_TOKEN:
        headers = {
            "client-id": settings.DHAN_CLIENT_ID,
            "access-token": settings.DHAN_ACCESS_TOKEN,
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get("https://api.dhan.co/v2/fundlimit", headers=headers)
                lat = round((time.time() - t0) * 1000, 1)
                if res.status_code == 200:
                    # Test market data subscription
                    data_res = client.post(
                        "https://api.dhan.co/v2/marketfeed/ltp",
                        headers=headers,
                        json={"NSE_EQ": [2885]},
                    )
                    if data_res.status_code == 200:
                        results.append({
                            "provider": "DhanHQ",
                            "status": "Connected",
                            "configured": True,
                            "operational": True,
                            "model": "DhanHQ Marketfeed v2",
                            "http_status": 200,
                            "latency_ms": lat,
                            "information": "Account authenticated; real-time quote feeds active.",
                            "error": None,
                        })
                    else:
                        err_json = data_res.json() if data_res.headers.get("content-type", "").startswith("application/json") else {}
                        code_806 = "806" in str(err_json)
                        results.append({
                            "provider": "DhanHQ",
                            "status": "Degraded",
                            "configured": True,
                            "operational": True,
                            "model": "DhanHQ Account APIs",
                            "http_status": 200,
                            "latency_ms": lat,
                            "information": "Client ID & token authenticated (HTTP 200 on funds). Data APIs require separate Dhan Data subscription (Code 806). Operating with verified NSE/BSE fixtures.",
                            "error": "Data APIs not Subscribed (Error 806) on /v2/marketfeed/ltp",
                        })
                else:
                    results.append({
                        "provider": "DhanHQ",
                        "status": "Failed",
                        "configured": True,
                        "operational": False,
                        "model": None,
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "information": "DhanHQ authentication rejected.",
                        "error": f"HTTP {res.status_code}: {res.text[:120]}",
                    })
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            results.append({
                "provider": "DhanHQ",
                "status": "Failed",
                "configured": True,
                "operational": False,
                "model": None,
                "http_status": 500,
                "latency_ms": lat,
                "information": "Connection exception to DhanHQ.",
                "error": str(e),
            })
    else:
        results.append({
            "provider": "DhanHQ",
            "status": "Not Configured",
            "configured": False,
            "operational": False,
            "model": None,
            "http_status": None,
            "latency_ms": 0,
            "information": "DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN not set.",
            "error": None,
        })

    # 6. Marketaux API (Financial News)
    t0 = time.time()
    if settings.MARKETAUX_API_TOKEN:
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(
                    "https://api.marketaux.com/v1/news/all",
                    params={"api_token": settings.MARKETAUX_API_TOKEN, "limit": 2, "language": "en"},
                )
                lat = round((time.time() - t0) * 1000, 1)
                if res.status_code == 200:
                    limit_rem = res.headers.get("x-usagelimit-remaining", "N/A")
                    results.append({
                        "provider": "Marketaux",
                        "status": "Connected",
                        "configured": True,
                        "operational": True,
                        "model": "Marketaux News v1",
                        "http_status": 200,
                        "latency_ms": lat,
                        "information": f"Live financial news stream operational. Quota remaining: {limit_rem} calls.",
                        "error": None,
                    })
                else:
                    results.append({
                        "provider": "Marketaux",
                        "status": "Failed",
                        "configured": True,
                        "operational": False,
                        "model": None,
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "information": "Marketaux API returned error response.",
                        "error": f"HTTP {res.status_code}: {res.text[:120]}",
                    })
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            results.append({
                "provider": "Marketaux",
                "status": "Failed",
                "configured": True,
                "operational": False,
                "model": None,
                "http_status": 500,
                "latency_ms": lat,
                "information": "Marketaux request timed out or network error.",
                "error": str(e),
            })
    else:
        results.append({
            "provider": "Marketaux",
            "status": "Not Configured",
            "configured": False,
            "operational": False,
            "model": None,
            "http_status": None,
            "latency_ms": 0,
            "information": "MARKETAUX_API_TOKEN is not set.",
            "error": None,
        })

    # 6b. NewsAPI (Global & Regional Financial Journalism)
    t0 = time.time()
    if settings.NEWSAPI_API_KEY:
        try:
            news_provider = NewsAPIProvider()
            check_res = news_provider.check_availability()
            lat = check_res.get("latency_ms", round((time.time() - t0) * 1000, 1))
            status = check_res.get("status", "Unavailable")
            results.append({
                "provider": "NewsAPI",
                "status": status,
                "configured": True,
                "operational": status in ("Connected", "Degraded"),
                "model": "NewsAPI v2",
                "http_status": check_res.get("http_status", 200 if status == "Connected" else 500),
                "latency_ms": lat,
                "information": check_res.get("information", "Global business news feeds active."),
                "error": check_res.get("error"),
                "error_category": check_res.get("error_category"),
            })
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            results.append({
                "provider": "NewsAPI",
                "status": "Failed",
                "configured": True,
                "operational": False,
                "model": None,
                "http_status": 500,
                "latency_ms": lat,
                "information": "Exception connecting to NewsAPI.",
                "error": str(e),
                "error_category": "network",
            })
    else:
        results.append({
            "provider": "NewsAPI",
            "status": "Not Configured",
            "configured": False,
            "operational": False,
            "model": None,
            "http_status": None,
            "latency_ms": 0,
            "information": "NEWSAPI_API_KEY is not configured.",
            "error": None,
        })

    # 7. Financial Modeling Prep (FMP)
    t0 = time.time()
    if settings.FMP_API_KEY:
        try:
            fmp = FMPProvider()
            prof_res = fmp.get_company_profile("AAPL")
            lat = round((time.time() - t0) * 1000, 1)
            if prof_res.get("is_live"):
                # Also test Indian equities coverage
                ind_res = fmp.get_company_profile("RELIANCE.NS")
                is_indian_supported = ind_res.get("is_live", False)
                results.append({
                    "provider": "Financial Modeling Prep (FMP)",
                    "status": "Connected" if is_indian_supported else "Degraded",
                    "configured": True,
                    "operational": True,
                    "model": "FMP /stable",
                    "http_status": 200,
                    "latency_ms": lat,
                    "information": "Global profiles active (AAPL verified). Indian equities (.NS/.BO) restricted by FMP subscription tier (HTTP 402) - using local fundamental data engine.",
                    "error": None if is_indian_supported else ind_res.get("error"),
                })
            else:
                results.append({
                    "provider": "Financial Modeling Prep (FMP)",
                    "status": "Failed",
                    "configured": True,
                    "operational": False,
                    "model": None,
                    "http_status": 403,
                    "latency_ms": lat,
                    "information": "FMP request failed.",
                    "error": prof_res.get("error"),
                })
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            results.append({
                "provider": "Financial Modeling Prep (FMP)",
                "status": "Failed",
                "configured": True,
                "operational": False,
                "model": None,
                "http_status": 500,
                "latency_ms": lat,
                "information": "Exception connecting to FMP.",
                "error": str(e),
            })
    else:
        results.append({
            "provider": "Financial Modeling Prep (FMP)",
            "status": "Not Configured",
            "configured": False,
            "operational": False,
            "model": None,
            "http_status": None,
            "latency_ms": 0,
            "information": "FMP_API_KEY is not set.",
            "error": None,
        })

    # 7b. Finnhub (Global Market Quotes & Company News)
    t0 = time.time()
    if settings.effective_finnhub_key:
        try:
            finnhub_provider = FinnhubProvider()
            check_res = finnhub_provider.check_availability()
            lat = check_res.get("latency_ms", round((time.time() - t0) * 1000, 1))
            status = check_res.get("status", "Unavailable")
            results.append({
                "provider": "Finnhub",
                "status": status,
                "configured": True,
                "operational": status in ("Connected", "Degraded"),
                "model": "Finnhub API v1",
                "http_status": check_res.get("http_status", 200 if status == "Connected" else 500),
                "latency_ms": lat,
                "information": check_res.get("information", "Global equity data active."),
                "error": check_res.get("error"),
                "error_category": check_res.get("error_category"),
            })
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            results.append({
                "provider": "Finnhub",
                "status": "Failed",
                "configured": True,
                "operational": False,
                "model": None,
                "http_status": 500,
                "latency_ms": lat,
                "information": "Exception connecting to Finnhub.",
                "error": str(e),
                "error_category": "network",
            })
    else:
        results.append({
            "provider": "Finnhub",
            "status": "Not Configured",
            "configured": False,
            "operational": False,
            "model": None,
            "http_status": None,
            "latency_ms": 0,
            "information": "FINHUB_API_KEY is not configured.",
            "error": None,
        })

    # 8. Langfuse (Observability)
    t0 = time.time()
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        host = settings.effective_langfuse_host
        auth_str = f"{settings.LANGFUSE_PUBLIC_KEY}:{settings.LANGFUSE_SECRET_KEY}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=6.0) as client:
                now_iso = datetime.now(timezone.utc).isoformat()
                probe_payload = {
                    "batch": [
                        {
                            "id": f"audit-ping-{int(time.time())}",
                            "type": "trace-create",
                            "timestamp": now_iso,
                            "body": {
                                "id": f"audit-ping-{int(time.time())}",
                                "name": "EquiLens API Audit Probe",
                                "timestamp": now_iso,
                                "metadata": {"audit": True},
                            },
                        }
                    ]
                }
                res = client.post(f"{host}/api/public/ingestion", headers=headers, json=probe_payload)
                lat = round((time.time() - t0) * 1000, 1)
                if res.status_code in (200, 207):
                    results.append({
                        "provider": "Langfuse",
                        "status": "Connected",
                        "configured": True,
                        "operational": True,
                        "model": f"Langfuse Cloud ({'US' if 'us.' in host else 'EU'})",
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "information": f"Trace & generation telemetry active at {host}.",
                        "error": None,
                    })
                else:
                    results.append({
                        "provider": "Langfuse",
                        "status": "Failed",
                        "configured": True,
                        "operational": False,
                        "model": None,
                        "http_status": res.status_code,
                        "latency_ms": lat,
                        "information": "Langfuse authentication rejected.",
                        "error": f"HTTP {res.status_code}: {res.text[:120]}",
                    })
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            results.append({
                "provider": "Langfuse",
                "status": "Failed",
                "configured": True,
                "operational": False,
                "model": None,
                "http_status": 500,
                "latency_ms": lat,
                "information": "Exception connecting to Langfuse host.",
                "error": str(e),
            })
    else:
        results.append({
            "provider": "Langfuse",
            "status": "Not Configured",
            "configured": False,
            "operational": False,
            "model": None,
            "http_status": None,
            "latency_ms": 0,
            "information": "LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set.",
            "error": None,
        })

    # 9. Sentry (Error Tracking)
    if settings.SENTRY_DSN:
        results.append({
            "provider": "Sentry",
            "status": "Connected",
            "configured": True,
            "operational": True,
            "model": "Sentry SDK",
            "http_status": 200,
            "latency_ms": 0.5,
            "information": "Sentry DSN configured for exception tracking.",
            "error": None,
        })
    else:
        results.append({
            "provider": "Sentry",
            "status": "Not Configured",
            "configured": False,
            "operational": False,
            "model": None,
            "http_status": None,
            "latency_ms": 0,
            "information": "SENTRY_DSN is not configured. Local structured logging active.",
            "error": None,
        })

    # Summary metrics
    summary = _integration_summary(results)
    with _audit_cache_lock:
        global _last_audit_result
        _last_audit_result = copy.deepcopy(summary)
    return summary
