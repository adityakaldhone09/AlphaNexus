import platform
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

from .config import settings


class EngineState(str, Enum):
    READY = "Ready"
    CONNECTED = "Connected"
    CONFIGURED = "Configured"
    DEGRADED = "Degraded"
    DISABLED = "Disabled"
    INITIALIZING = "Initializing"
    UNAVAILABLE = "Unavailable"
    UNKNOWN = "Unknown"
    FAILED = "Failed"


class EngineInfo(BaseModel):
    name: str
    state: EngineState
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


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EngineRegistry:
    """Reports observed runtime state separately from configured state."""

    def __init__(self):
        self._engines: Dict[str, EngineInfo] = {}
        self.initialize_engines()

    def initialize_engines(self, verify: bool = False) -> None:
        checked_at = _now()
        engines: Dict[str, EngineInfo] = {}

        def add(
            key: str,
            name: str,
            state: EngineState,
            *,
            provider: Optional[str],
            description: str,
            details: str,
            configured: bool = True,
            connected: Optional[bool] = None,
            verified: bool = False,
            version: Optional[str] = None,
            latency_ms: Optional[float] = None,
            last_successful_operation: Optional[datetime] = None,
            error_category: Optional[str] = None,
            error_message: Optional[str] = None,
        ) -> None:
            engines[key] = EngineInfo(
                name=name,
                state=state,
                provider=provider,
                description=description,
                details=details,
                configured=configured,
                connected=connected,
                verified=verified,
                version=version,
                latency_ms=latency_ms,
                last_successful_operation=last_successful_operation,
                error_category=error_category,
                error_message=error_message,
                last_checked=checked_at,
            )

        add(
            "backend",
            "Application Backend",
            EngineState.READY,
            provider="FastAPI",
            version=f"Python {platform.python_version()}",
            description="HTTP API process and application runtime.",
            details="API process is serving requests.",
            verified=True,
            connected=True,
            last_successful_operation=checked_at,
        )

        from .database import check_database_health, is_sqlite

        database_health = check_database_health()
        database_ok = bool(database_health.get("reachable"))
        database_state = (
            EngineState.DEGRADED
            if database_ok and is_sqlite
            else EngineState.CONNECTED
            if database_ok
            else EngineState.UNAVAILABLE
        )
        add(
            "database",
            "Relational Database",
            database_state,
            provider="SQLite (development fallback)" if is_sqlite else "Configured SQL database",
            description="Relational persistence used by company, financial, forecast, and research APIs.",
            details=(
                "Reachable; the process is using its SQLite development fallback."
                if database_ok and is_sqlite
                else "Database connection verified."
                if database_ok
                else "The configured relational database is unreachable."
            ),
            configured=bool(settings.DATABASE_URL) or is_sqlite,
            connected=database_ok,
            verified=database_ok,
            last_successful_operation=checked_at if database_ok else None,
            error_category=None if database_ok else "database",
            error_message=None if database_ok else "Database connectivity check failed.",
        )

        from app.database.mongodb import mongodb_manager

        mongo_health = mongodb_manager.check_health()
        mongo_connected = bool(mongo_health.get("connected"))
        mongo_configured = bool(mongodb_manager.uri)
        add(
            "mongodb",
            "MongoDB",
            EngineState.CONNECTED
            if mongo_connected
            else EngineState.UNAVAILABLE
            if mongo_configured
            else EngineState.DISABLED,
            provider="MongoDB Atlas" if mongo_configured else None,
            description="Document, conversation, and MongoDB Atlas integration status.",
            details=(
                f"Connected to database '{mongodb_manager.db_name}'."
                if mongo_connected
                else "MongoDB is configured but unreachable."
                if mongo_configured
                else "MONGODB_URI is not configured."
            ),
            configured=mongo_configured,
            connected=mongo_connected,
            verified=mongo_connected,
            last_successful_operation=checked_at if mongo_connected else None,
            error_category=None if mongo_connected or not mongo_configured else "network",
            error_message=None
            if mongo_connected or not mongo_configured
            else "MongoDB connectivity check failed; credentials and network access may need attention.",
        )

        vector_state = (
            EngineState.UNAVAILABLE
            if database_ok and is_sqlite
            else EngineState.CONNECTED
            if database_ok and database_health.get("pgvector_available")
            else EngineState.CONFIGURED
            if database_ok
            else EngineState.UNAVAILABLE
        )
        vector_details = (
            "RAG retrieval uses SQLAlchemy/pgvector, but the active SQLite fallback has no pgvector; retrieval is unavailable."
            if database_ok and is_sqlite
            else "RAG retrieval uses SQLAlchemy with pgvector."
            if database_ok and database_health.get("pgvector_available")
            else "RAG retrieval is wired to pgvector; extension availability has not been verified."
            if database_ok
            else "Vector retrieval is unavailable while the relational database is unreachable."
        )
        add(
            "vector_store",
            "Vector Retrieval Store",
            vector_state,
            provider="pgvector" if database_ok else None,
            description="Vector backend actually used by the RAG retrieval service.",
            details=vector_details,
            configured=database_ok,
            connected=bool(database_health.get("pgvector_available")),
            verified=bool(database_health.get("pgvector_available")),
            last_successful_operation=checked_at
            if database_health.get("pgvector_available")
            else None,
            error_category="vector_store"
            if vector_state in (EngineState.DEGRADED, EngineState.UNAVAILABLE)
            else None,
            error_message=(
                "The active database does not provide pgvector; vector retrieval is unavailable."
                if vector_state in (EngineState.DEGRADED, EngineState.UNAVAILABLE)
                else None
            ),
        )

        from app.engines.rag.embeddings import embedding_engine

        embedding_latency: Optional[float] = None
        embedding_error: Optional[str] = None
        embedding_verified = False
        if verify:
            started = time.monotonic()
            try:
                vector = embedding_engine.generate_query_embedding("health check")
                embedding_verified = embedding_engine.validate_embedding_dimension(vector)
                embedding_latency = round((time.monotonic() - started) * 1000, 1)
                if not embedding_verified:
                    embedding_error = "Embedding output dimension does not match configuration."
            except Exception:
                embedding_latency = round((time.monotonic() - started) * 1000, 1)
                embedding_error = "Embedding generation failed."
        embedding_info = embedding_engine.get_model_info()
        fallback_mode = bool(embedding_info.get("fallback_mode"))
        embedding_ready = embedding_verified or bool(embedding_info.get("loaded"))
        embedding_state = (
            EngineState.DEGRADED
            if fallback_mode or embedding_error
            else EngineState.READY
            if embedding_ready
            else EngineState.CONFIGURED
        )
        add(
            "embedding",
            "Embedding Engine",
            embedding_state,
            provider="Sentence Transformers" if not fallback_mode else "Deterministic fallback",
            version=str(embedding_info.get("version_tag", "")) or None,
            description="Generates normalized vectors for document and query retrieval.",
            details=(
                embedding_error
                or "Deterministic non-semantic fallback is active."
                if fallback_mode
                else "Embedding generation and output dimension verified."
                if embedding_verified
                else "Model loaded; run a health refresh to verify inference."
                if embedding_ready
                else "Embedding model is configured but not loaded."
            ),
            configured=True,
            connected=embedding_verified if verify else None,
            verified=embedding_verified,
            latency_ms=embedding_latency,
            last_successful_operation=checked_at if embedding_verified else None,
            error_category="embedding" if embedding_error else None,
            error_message=embedding_error,
        )

        from app.integrations.llm.base import get_provider_health

        llm_configurations = [
            ("gemini", "Google Gemini", settings.GEMINI_API_KEY, settings.GEMINI_MODEL),
            ("groq", "Groq", settings.GROQ_API_KEY, settings.GROQ_MODEL),
        ]
        for key, name, api_key, model in llm_configurations:
            health = get_provider_health(name, model, bool(api_key))
            state_map = {
                "Connected": EngineState.CONNECTED,
                "Degraded": EngineState.DEGRADED,
                "Configured": EngineState.CONFIGURED,
                "Unavailable": EngineState.CONFIGURED if api_key else EngineState.DISABLED,
                "Not configured": EngineState.DISABLED,
            }
            provider_state = state_map.get(health["connection_status"], EngineState.UNKNOWN)
            add(
                key,
                name,
                provider_state,
                provider=name if api_key else None,
                version=health.get("active_model") or model if api_key else None,
                description=f"{name} text generation provider.",
                details=health.get("error_message")
                or (
                    "Provider generation was verified."
                    if health.get("last_successful_test")
                    else "Credentials are configured; connectivity has not been tested."
                    if api_key
                    else "Provider credentials are not configured."
                ),
                configured=bool(api_key),
                connected=provider_state in (EngineState.CONNECTED, EngineState.DEGRADED)
                if health.get("last_successful_test")
                else None,
                verified=bool(health.get("last_successful_test")),
                last_successful_operation=(
                    datetime.fromisoformat(health["last_successful_test"])
                    if health.get("last_successful_test")
                    else None
                ),
                error_category=health.get("error_category"),
                error_message=health.get("error_message"),
            )

        rag_state = (
            EngineState.DEGRADED
            if fallback_mode or vector_state in (EngineState.DEGRADED, EngineState.UNAVAILABLE)
            else EngineState.READY
            if verify and embedding_verified and database_ok
            else EngineState.CONFIGURED
        )
        add(
            "rag",
            "RAG Pipeline",
            rag_state,
            provider="SQLAlchemy / pgvector",
            version="1.0.0",
            description="Document extraction, chunking, embeddings, retrieval, and citation pipeline.",
            details=(
                "Retrieval is partially available: an embedding or vector-store fallback is active."
                if rag_state == EngineState.DEGRADED
                else "Database and embedding checks passed; no end-to-end document retrieval test was run."
                if verify
                else "Pipeline is initialized; run a retrieval query to verify document-level results."
            ),
            configured=True,
            connected=database_ok and embedding_verified if verify else None,
            verified=verify and database_ok and embedding_verified,
            last_successful_operation=checked_at
            if verify and database_ok and embedding_verified
            else None,
        )

        storage_configured = bool(
            settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY
        )
        storage_provider = "Supabase Storage" if storage_configured else "Local filesystem"
        storage_state = (
            EngineState.CONFIGURED
            if storage_configured
            else EngineState.READY
            if not verify and settings.LOCAL_UPLOAD_DIR
            else EngineState.CONNECTED
            if verify
            else EngineState.CONFIGURED
        )
        storage_latency: Optional[float] = None
        if verify and not storage_configured:
            import os
            import tempfile

            started = time.monotonic()
            try:
                os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
                with tempfile.TemporaryFile(dir=settings.LOCAL_UPLOAD_DIR) as test_file:
                    test_file.write(b"health-check")
                    test_file.flush()
                storage_latency = round((time.monotonic() - started) * 1000, 1)
                storage_state = EngineState.READY
            except OSError:
                storage_state = EngineState.UNAVAILABLE
        add(
            "storage",
            "Document Storage",
            storage_state,
            provider=storage_provider,
            description="Configured destination for uploaded financial documents.",
            details=(
                "Local storage read/write check passed."
                if verify and storage_state == EngineState.READY
                else "Cloud storage is configured; connectivity has not been verified by this page."
                if storage_configured
                else "Local upload directory is configured; run refresh to verify write access."
            ),
            configured=True,
            connected=storage_state in (EngineState.READY, EngineState.CONNECTED)
            if verify and not storage_configured
            else None,
            verified=verify
            and not storage_configured
            and storage_state in (EngineState.READY, EngineState.CONNECTED),
            latency_ms=storage_latency,
            last_successful_operation=checked_at
            if verify
            and not storage_configured
            and storage_state in (EngineState.READY, EngineState.CONNECTED)
            else None,
            error_category="storage" if storage_state == EngineState.UNAVAILABLE else None,
            error_message="Local upload directory is not writable."
            if storage_state == EngineState.UNAVAILABLE
            else None,
        )

        news_configured = bool(settings.MARKETAUX_API_TOKEN)
        news_state = EngineState.CONFIGURED if news_configured else (
            EngineState.DEGRADED if settings.DATA_MODE.lower() == "demo" else EngineState.DISABLED
        )
        add(
            "news",
            "News Intelligence",
            news_state,
            provider="Marketaux" if news_configured else "Demo fixtures"
            if settings.DATA_MODE.lower() == "demo"
            else None,
            description="News ingestion and classification service.",
            details="Provider credentials are configured; live connectivity has not been tested."
            if news_configured
            else "Live news provider is not configured; demo fixtures may be used."
            if settings.DATA_MODE.lower() == "demo"
            else "No live news provider is configured.",
            configured=news_configured,
            connected=None,
        )

        market_configured = bool(settings.DHAN_CLIENT_ID and settings.DHAN_ACCESS_TOKEN)
        add(
            "market_data",
            "Market Data Provider",
            EngineState.CONFIGURED
            if market_configured
            else EngineState.DEGRADED
            if settings.DATA_MODE.lower() == "demo"
            else EngineState.DISABLED,
            provider="DhanHQ" if market_configured else "Seeded market data"
            if settings.DATA_MODE.lower() == "demo"
            else None,
            description="Live NSE/BSE market data integration.",
            details="DhanHQ credentials are configured; connectivity has not been tested."
            if market_configured
            else "Live market data is not configured; demo data may be available."
            if settings.DATA_MODE.lower() == "demo"
            else "No live market data provider is configured.",
            configured=market_configured,
        )

        try:
            import numpy
            import pandas
            from app.engines.forecasting.models.baseline import BaselineForecaster

            if verify:
                started = time.monotonic()
                BaselineForecaster().fit_predict([1.0, 2.0, 3.0], forecast_steps=1)
                analytics_latency = round((time.monotonic() - started) * 1000, 1)
            else:
                analytics_latency = None
            analytics_state = EngineState.READY
            analytics_error = None
            analytics_details = (
                "Deterministic analytics and forecast smoke test passed."
                if verify
                else f"Numerical dependencies available (NumPy {numpy.__version__}, pandas {pandas.__version__})."
            )
        except Exception:
            analytics_state = EngineState.UNAVAILABLE
            analytics_latency = None
            analytics_error = "Analytics dependencies or deterministic calculation check failed."
            analytics_details = analytics_error
        add(
            "analytics",
            "Financial Analytics",
            analytics_state,
            provider="NumPy / pandas",
            description="Deterministic financial ratios and calculation engine.",
            details=analytics_details,
            configured=True,
            connected=analytics_state == EngineState.READY if verify else None,
            verified=verify and analytics_state == EngineState.READY,
            latency_ms=analytics_latency,
            last_successful_operation=checked_at
            if verify and analytics_state == EngineState.READY
            else None,
            error_category="analytics" if analytics_error else None,
            error_message=analytics_error,
        )

        forecast_state = EngineState.CONFIGURED
        forecast_error = None
        forecast_latency: Optional[float] = None
        if verify:
            started = time.monotonic()
            try:
                from app.engines.forecasting.models.baseline import BaselineForecaster

                predictions, _ = BaselineForecaster().fit_predict(
                    [1.0, 2.0, 3.0], forecast_steps=1
                )
                if len(predictions) != 1:
                    raise ValueError("Unexpected forecast output.")
                forecast_state = EngineState.READY
                forecast_latency = round((time.monotonic() - started) * 1000, 1)
            except Exception:
                forecast_state = EngineState.UNAVAILABLE
                forecast_error = "Forecast model smoke test failed."
        add(
            "forecasting",
            "Forecasting Engine",
            forecast_state,
            provider="Baseline linear trend",
            version="1.0",
            description="Financial forecasting and scenario analysis.",
            details="Prediction smoke test passed."
            if forecast_state == EngineState.READY
            else "Forecast dependencies are configured; refresh to run a prediction smoke test."
            if forecast_state == EngineState.CONFIGURED
            else forecast_error or "Forecast engine unavailable.",
            configured=True,
            connected=forecast_state == EngineState.READY if verify else None,
            verified=verify and forecast_state == EngineState.READY,
            latency_ms=forecast_latency,
            last_successful_operation=checked_at
            if verify and forecast_state == EngineState.READY
            else None,
            error_category="forecasting" if forecast_error else None,
            error_message=forecast_error,
        )

        self._engines = engines

    def register(self, key: str, info: EngineInfo) -> None:
        self._engines[key] = info

    def get(self, key: str) -> Optional[EngineInfo]:
        return self._engines.get(key)

    def update_state(
        self,
        key: str,
        state: EngineState,
        details: Optional[str] = None,
    ) -> None:
        if key in self._engines:
            self._engines[key].state = state
            if details:
                self._engines[key].details = details
            self._engines[key].last_checked = _now()

    def get_all(self) -> Dict[str, EngineInfo]:
        return self._engines

    def get_summary(self) -> Dict[str, Any]:
        states = [engine.state for engine in self._engines.values()]
        if EngineState.UNAVAILABLE in states or EngineState.FAILED in states:
            overall = "Critical"
        elif any(
            state in (EngineState.DEGRADED, EngineState.CONFIGURED, EngineState.UNKNOWN)
            for state in states
        ):
            overall = "Degraded"
        elif EngineState.INITIALIZING in states:
            overall = "Initializing"
        else:
            overall = "Operational"

        return {
            "status": overall,
            "timestamp": _now().isoformat(),
            "total_engines": len(self._engines),
            "ready_count": sum(
                1
                for state in states
                if state in (EngineState.READY, EngineState.CONNECTED)
            ),
            "degraded_count": sum(
                1 for state in states if state == EngineState.DEGRADED
            ),
            "configured_count": sum(
                1 for state in states if state == EngineState.CONFIGURED
            ),
            "unavailable_count": sum(
                1
                for state in states
                if state in (EngineState.UNAVAILABLE, EngineState.FAILED)
            ),
            "disabled_count": sum(
                1 for state in states if state == EngineState.DISABLED
            ),
            "failed_count": sum(
                1
                for state in states
                if state in (EngineState.UNAVAILABLE, EngineState.FAILED)
            ),
            "engines": {
                key: engine.model_dump(mode="json")
                for key, engine in self._engines.items()
            },
        }


engine_registry = EngineRegistry()
