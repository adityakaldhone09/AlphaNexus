# EquiLens AI – API Health Check & Operational Runbook

This document details health monitoring endpoints, probe behaviors, latency benchmarks, and troubleshooting procedures for EquiLens AI.

---

## 1. Health Monitoring Endpoints

### A. Basic Health Probe
- **Endpoint:** `GET /api/v1/health`
- **Purpose:** Fast container/load-balancer health check.
- **Example Response:**
  ```json
  {
    "status": "Healthy",
    "environment": "development",
    "data_mode": "demo",
    "timestamp": "2026-11-09T09:10:00.000Z",
    "database_connected": true,
    "version": "1.0.0"
  }
  ```

### B. Core Engine Registry
- **Endpoint:** `GET /api/v1/health/engines`
- **Purpose:** Detailed status of all 11 internal platform engines (Backend, Database, pgvector, Embeddings, LLM, RAG, Storage, News, Market Data, Financial Analytics, Forecasting).
- **Status States:** `Ready`, `Degraded`, `Disabled`, `Failed`.

### C. External Integrations Audit Probe
- **Endpoint:** `GET /api/v1/health/integrations`
- **Purpose:** Returns a cached/configuration snapshot by default. Add `?probe=true` to explicitly check configured integrations, list accessible AI models, and run short Gemini/Groq generation tests; live tests may consume provider quota.
- **AI Provider Fields:** `configured_model`, `active_model`, `connection_status`, `last_successful_test`, `error_category`, and sanitized `error_message`.
- **Example Response:**
  ```json
  {
    "timestamp": "2026-11-09T09:10:19.000Z",
    "total_integrations": 9,
    "connected_count": 6,
    "degraded_count": 2,
    "failed_count": 0,
    "not_configured_count": 1,
    "integrations": [
      {
        "provider": "Google Gemini",
        "status": "Connected",
        "configured": true,
        "operational": true,
        "model": "gemini-3.5-flash",
        "http_status": 200,
        "latency_ms": 3740.8,
        "information": "Inference verified (79 tokens). Active model: gemini-3.5-flash",
        "error": null
      },
      {
        "provider": "Groq",
        "status": "Connected",
        "configured": true,
        "operational": true,
        "model": "qwen/qwen3.8-27b",
        "http_status": 200,
        "latency_ms": 391.2,
        "information": "High-speed inference verified (27 tokens). Active model: qwen/qwen3.8-27b",
        "error": null
      },
      {
        "provider": "PostgreSQL / Supabase",
        "status": "Connected",
        "configured": true,
        "operational": true,
        "model": "PostgreSQL 17.11 (Supabase)",
        "http_status": 200,
        "latency_ms": 916.0,
        "information": "Relational DB active (postgresql). Schema & migrations verified.",
        "error": null
      },
      {
        "provider": "pgvector",
        "status": "Connected",
        "configured": true,
        "operational": true,
        "model": "pgvector v0.8.2",
        "http_status": 200,
        "latency_ms": 5.0,
        "information": "Vector similarity search operational for 384-dimensional dense embeddings.",
        "error": null
      },
      {
        "provider": "DhanHQ",
        "status": "Degraded",
        "configured": true,
        "operational": true,
        "model": "DhanHQ Account APIs",
        "http_status": 200,
        "latency_ms": 180.2,
        "information": "Client ID & token authenticated (HTTP 200 on funds). Data APIs require separate Dhan Data subscription (Code 806). Operating with verified NSE/BSE fixtures.",
        "error": "Data APIs not Subscribed (Error 806) on /v2/marketfeed/ltp"
      },
      {
        "provider": "Marketaux",
        "status": "Connected",
        "configured": true,
        "operational": true,
        "model": "Marketaux News v1",
        "http_status": 200,
        "latency_ms": 911.6,
        "information": "Live financial news stream operational. Quota remaining: 95 calls.",
        "error": null
      },
      {
        "provider": "Financial Modeling Prep (FMP)",
        "status": "Degraded",
        "configured": true,
        "operational": true,
        "model": "FMP /stable",
        "http_status": 200,
        "latency_ms": 1332.9,
        "information": "Global profiles active (AAPL verified). Indian equities (.NS/.BO) restricted by FMP subscription tier (HTTP 402) - using local fundamental data engine.",
        "error": "HTTP 402: Indian Equities (.NS/.BO) are premium query parameters not included in current subscription tier."
      },
      {
        "provider": "Langfuse",
        "status": "Connected",
        "configured": true,
        "operational": true,
        "model": "Langfuse Cloud (US)",
        "http_status": 207,
        "latency_ms": 1534.3,
        "information": "Trace & generation telemetry active at https://us.cloud.langfuse.com.",
        "error": null
      },
      {
        "provider": "Sentry",
        "status": "Not Configured",
        "configured": false,
        "operational": false,
        "model": null,
        "http_status": null,
        "latency_ms": 0,
        "information": "SENTRY_DSN is not configured. Local structured logging active.",
        "error": null
      }
    ]
  }
  ```

---

## 2. Operational Troubleshooting Matrix

| Symptom | Probable Cause | Corrective Action |
|---|---|---|
| `could not translate host name "...@db..."` | Database password contains `@` character. | `normalize_db_url()` automatically converts `@` to `%40`. If connecting externally, ensure password is URL-encoded. |
| `relation "citations" does not exist` | Database tables not yet migrated. | Run `alembic upgrade head` or `Base.metadata.create_all(bind=engine)`. |
| Gemini model-not-found response | Configured model is absent from the account's `generateContent` catalog. | Keep `GEMINI_MODEL` configurable; explicitly test with `?probe=true`. The adapter discovers an accessible catalog fallback, or use `GEMINI_FALLBACK_MODEL` to pin one. |
| Groq model-not-found response | Configured model is absent from the account's model catalog. | Keep `GROQ_MODEL` configurable; explicitly test with `?probe=true`. The adapter discovers an accessible catalog fallback, or use `GROQ_FALLBACK_MODEL` to pin one. |
| DhanHQ `806 Data APIs not Subscribed` | Dhan Trading API key is valid, but Market Data add-on is inactive. | Activate Data APIs subscription on web.dhan.co, or continue with verified platform fixtures. |
| FMP `402 Payment Required` on `.NS` tickers | Account tier does not include Indian exchange symbols. | Upgrade FMP tier or use the built-in NSE/BSE fundamental data engine. |
| Langfuse `401 UnauthorizedError: Confirm host` | Region mismatch between API key and endpoint. | Set `LANGFUSE_HOST=https://us.cloud.langfuse.com` for US accounts, or `https://cloud.langfuse.com` for EU accounts. |
