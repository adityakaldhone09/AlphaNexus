from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db, check_database_health, is_sqlite
from app.database.mongodb import mongodb_manager
from app.core.registry import engine_registry
from app.schemas.health import HealthResponse, EnginesSummaryResponse
from app.services.audit_service import get_cached_integrations_status, run_integrations_audit

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    """Basic health probe indicating backend server is operational."""
    db_status = check_database_health()
    return HealthResponse(
        status="Healthy" if db_status["reachable"] else "Degraded",
        environment=settings.APP_ENV,
        data_mode=settings.DATA_MODE,
        timestamp=datetime.utcnow(),
        database_connected=db_status["reachable"],
        version="1.0.0",
    )


@router.get("/health/engines", response_model=EnginesSummaryResponse)
def get_engines_health(refresh: bool = Query(False)):
    """
    Central Engine Registry status dashboard.
    Returns the real-time health and initialization state of all core engines
    (Database, pgvector, Embeddings, LLM, RAG, News, Analytics, Forecasting).
    """
    if refresh:
        engine_registry.initialize_engines(verify=True)
    return engine_registry.get_summary()


@router.post("/health/refresh")
def refresh_system_health():
    """Run explicit engine and configured integration checks."""
    integrations = run_integrations_audit(probe_ai=True)
    engine_registry.initialize_engines(verify=True)
    return {
        "engines": engine_registry.get_summary(),
        "integrations": integrations,
    }


@router.get("/health/config")
def get_safe_system_configuration():
    """Expose operational configuration without credentials or connection strings."""
    primary_llm = (
        "Google Gemini"
        if settings.GEMINI_API_KEY
        else "Groq"
        if settings.GROQ_API_KEY
        else None
    )
    db_health = check_database_health()
    return {
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "data_mode": settings.DATA_MODE,
        "database": {
            "provider": "SQLite development fallback"
            if is_sqlite
            else "Configured relational database",
            "reachable": db_health["reachable"],
            "fallback": is_sqlite,
        },
        "mongodb": {
            "configured": bool(mongodb_manager.uri),
            "database": mongodb_manager.db_name if mongodb_manager.uri else None,
            "connected": mongodb_manager.is_connected,
        },
        "llm": {
            "primary_provider": primary_llm,
            "gemini": {
                "configured": bool(settings.GEMINI_API_KEY),
                "model": settings.GEMINI_MODEL,
                "fallback_model": settings.GEMINI_FALLBACK_MODEL,
            },
            "groq": {
                "configured": bool(settings.GROQ_API_KEY),
                "model": settings.GROQ_MODEL,
                "fallback_model": settings.GROQ_FALLBACK_MODEL,
            },
        },
        "embedding": {
            "model": settings.EMBEDDING_MODEL_NAME,
            "dimension": settings.EMBEDDING_DIMENSION,
            "device": settings.EMBEDDING_DEVICE,
            "batch_size": settings.EMBEDDING_BATCH_SIZE,
        },
        "rag": {
            "chunk_size": settings.RAG_CHUNK_SIZE,
            "chunk_overlap": settings.RAG_CHUNK_OVERLAP,
            "retrieval_top_k": settings.RAG_RETRIEVAL_TOP_K,
            "hybrid_search_enabled": settings.RAG_HYBRID_ENABLED,
            "reranking_enabled": settings.RAG_RERANKING_ENABLED,
        },
        "integrations": {
            "dhan_configured": bool(
                settings.DHAN_CLIENT_ID and settings.DHAN_ACCESS_TOKEN
            ),
            "marketaux_configured": bool(settings.MARKETAUX_API_TOKEN),
            "fmp_configured": bool(settings.FMP_API_KEY),
            "supabase_storage_configured": bool(
                settings.SUPABASE_URL and (settings.effective_supabase_service_role_key or settings.effective_supabase_anon_key)
            ),
            "supabase_db_configured": bool(settings.DATABASE_URL),
        },
    }


@router.get("/health/engines/{engine_id}")
def get_engine_health(engine_id: str):
    engine = engine_registry.get(engine_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Engine not found")
    return engine.model_dump(mode="json")


@router.get("/health/integrations")
def get_integrations_audit(probe: bool = Query(False)):
    """
    Returns cached/configuration status by default. Set probe=true to explicitly
    verify provider connectivity and run Gemini/Groq generation tests.
    """
    if probe:
        return run_integrations_audit(probe_ai=True)
    return get_cached_integrations_status()


@router.get("/health/diagnostics")
def get_health_diagnostics():
    """Return sanitized diagnostics derived from the latest engine/provider checks."""
    engines = engine_registry.get_summary()["engines"]
    integrations = get_cached_integrations_status()["integrations"]
    issues = []
    for engine_id, engine in engines.items():
        if engine["error_message"]:
            issues.append({
                "timestamp": engine["last_checked"],
                "severity": "error",
                "component": engine["name"],
                "message": engine["error_message"],
                "category": engine["error_category"],
            })
        elif engine["state"] in ("Degraded", "Configured"):
            issues.append({
                "timestamp": engine["last_checked"],
                "severity": "warning",
                "component": engine["name"],
                "message": engine["details"],
                "category": engine_id,
            })
    for integration in integrations:
        if integration.get("error_message"):
            issues.append({
                "timestamp": integration.get("last_successful_test"),
                "severity": "error"
                if integration["status"] == "Unavailable"
                else "warning",
                "component": integration["provider"],
                "message": integration["error_message"],
                "category": integration.get("error_category"),
            })
    issues.sort(key=lambda issue: issue["timestamp"] or "", reverse=True)
    return {"issues": issues[:100], "count": len(issues)}
