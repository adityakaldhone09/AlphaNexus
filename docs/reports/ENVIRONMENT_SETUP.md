# EquiLens AI – Environment Setup & Configuration Guide

This guide details all configuration variables, credential formats, regional requirements, and fallback mechanisms for EquiLens AI.

---

## 1. Environment File Hierarchy

The backend loads configuration files using Pydantic Settings with the following precedence:
1. Shell environment variables (highest priority)
2. `equilens-ai/backend/.env`
3. `equilens-ai/.env`
4. `.env` (repository root)

> [!IMPORTANT]
> Keep `equilens-ai/.env` and `equilens-ai/backend/.env` synchronized. Never commit real credentials to Git. Both files are permanently ignored by `.gitignore`.

---

## 2. Configuration Groups & Specifications

### A. Application Settings
| Variable | Default | Recommended | Description |
|---|---|---|---|
| `APP_ENV` | `development` | `development` / `production` | Application operating mode. |
| `APP_NAME` | `EquiLens AI` | `EquiLens AI` | System branding identifier. |
| `APP_DEBUG` | `true` | `false` in production | Verbose tracebacks and logging. |
| `DATA_MODE` | `demo` | `demo` / `live` | Toggles live market sync vs. curated verified fixtures. |
| `FRONTEND_URL` | `http://localhost:5173` | UI base URL | Permitted CORS origin for frontend client. |
| `BACKEND_URL` | `http://localhost:8000` | API base URL | FastAPI root URL for client requests. |

---

### B. Database & Supabase (PostgreSQL + pgvector)
| Variable | Format / Example | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres` | Primary SQLAlchemy connection string. If password contains `@`, it will be auto-encoded as `%40`. |
| `DIRECT_URL` | `postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres` | Direct connection string for Alembic migrations. |
| `SUPABASE_URL` | `https://[PROJECT-ID].supabase.co` | Supabase project API gateway. |
| `SUPABASE_ANON_KEY` | JWT anon token | Public key for browser/frontend authentication. |
| `SUPABASE_SERVICE_ROLE_KEY` | JWT service token | Secret key for backend storage bucket management (NEVER expose to frontend). |
| `SUPABASE_STORAGE_BUCKET` | `equilens-documents` | Target bucket for financial document uploads. |

---

### C. AI & LLM Providers
| Variable | Recommended Value | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio Key | Required for Google Gemini synthesis. |
| `GEMINI_MODEL` | A model available to the account | The selected model is checked against the live `generateContent` catalog during an explicit health test. |
| `GEMINI_FALLBACK_MODEL` | Optional model ID | If unset, the adapter selects an accessible `generateContent` fallback from the live catalog after a model-not-found response. |
| `GROQ_API_KEY` | `gsk_...` | High-speed inference API key. |
| `GROQ_MODEL` | A model available to the account | The selected model is checked against the account's model catalog during an explicit health test. |
| `GROQ_FALLBACK_MODEL` | Optional model ID | If unset, the adapter selects an accessible chat model from the live catalog after a model-not-found response. |

---

### D. Dense Embeddings & Vector Search
| Variable | Value | Description |
|---|---|---|
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-en-v1.5` | Dense sentence transformer embedding model. |
| `EMBEDDING_DIMENSION` | `384` | Vector dimensionality matching the pgvector column definition. |
| `EMBEDDING_DEVICE` | `cpu` (or `cuda` / `mps`) | Execution hardware for embedding inferences. |

---

### E. Financial Market Data & News
| Variable | Format | Description |
|---|---|---|
| `DHAN_CLIENT_ID` | 10-digit account ID | DhanHQ Client identifier. |
| `DHAN_ACCESS_TOKEN` | JWT Bearer token | Daily access token for DhanHQ APIs. |
| `MARKETAUX_API_TOKEN` | 40-character token | Token for Marketaux financial news and announcements feed. |
| `FMP_API_KEY` | 32-character key | Financial Modeling Prep fundamentals key (`/stable` endpoints). |

---

### F. Observability & Monitoring
| Variable | Value | Notes |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-...` | Langfuse project public identifier. |
| `LANGFUSE_SECRET_KEY` | `sk-lf-...` | Langfuse ingestion secret key. |
| `LANGFUSE_HOST` | `https://us.cloud.langfuse.com` | Ensure host matches project region (`us.` vs EU `cloud.langfuse.com`). |
| `SENTRY_DSN` | Sentry ingest DSN | Optional production error reporting. |

---

### G. Security & Authentication
| Variable | Value | Notes |
|---|---|---|
| `SECRET_KEY` | 64+ char random hex string | HMAC secret for signing internal session JWT tokens. |
| `ALGORITHM` | `HS256` | JWT signature algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24 hours) | Session lifetime. |

---

## 3. Verifying Your Configuration

Run the diagnostic verification script from the repository:

```bash
cd equilens-ai
backend/.venv/bin/python scripts/verify_environment.py
```

Expected output:
```text
[Database]
  Reachable       : YES
  Type            : postgresql (Supabase)
  pgvector Active : YES (v0.8.2)

[Embedding Engine]
  Model           : BAAI/bge-small-en-v1.5
  Vector Generated: YES (length: 384, norm: 1.0)

[Central Engine Registry]
  Ready Engines   : 7 / 11
  Degraded / Demo : 3
  Disabled        : 1
```
