from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import logger
from app.core.database import Base, engine, SessionLocal
from app.core.registry import engine_registry
from app.api.v1.router import api_router
from app.api.routes import routes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info(f"Initializing {settings.APP_NAME} in {settings.APP_ENV} mode...")
    
    # Ensure database schema is created
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas verified.")
    except Exception as e:
        logger.error(f"Error ensuring database tables: {e}")

    # Check and initialize seed demo data if in demo mode
    try:
        from app.services.seed_service import seed_initial_market_data
        from app.services.company_discovery import company_discovery_service
        db = SessionLocal()
        try:
            seed_initial_market_data(db)
            company_discovery_service.seed_universe_identifiers(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Seed data initialization notice: {e}")

    # Refresh central registry
    engine_registry.initialize_engines()
    logger.info("ALPHANEXUS Core Engines successfully initialized and ready.")

    yield

    # Shutdown actions
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title="ALPHANEXUS – AI Financial Intelligence & Equity Research API",
    description=(
        "Production API powering ALPHANEXUS: Evidence-grounded equity research, "
        "RAG document intelligence, deterministic financial analytics, forecasting, "
        "and market deal tracking for Indian equities (NSE/BSE) and global markets."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_DEBUG else settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(routes_router, prefix="/api")


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "tagline": "See Beyond the Stock Price.",
        "version": "1.0.0",
        "status": "Operational",
        "api_docs": "/docs",
        "engines_status": f"{settings.API_V1_PREFIX}/health/engines",
    }


