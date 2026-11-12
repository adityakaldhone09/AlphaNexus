from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    companies,
    documents,
    research,
    news,
    financials,
    corporate_actions,
    market_events,
    forecasts,
    watchlist,
    rag,
    agent,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health & Engines"])
api_router.include_router(companies.router, prefix="/companies", tags=["Companies"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents & Ingestion"])
api_router.include_router(research.router, prefix="/research", tags=["AI Research & RAG"])
api_router.include_router(research.router, prefix="/chat", tags=["Chat"])
api_router.include_router(rag.router, prefix="/rag", tags=["Financial RAG Engine"])
api_router.include_router(agent.router, prefix="/agent", tags=["Agentic Research"])
api_router.include_router(news.router, prefix="/news", tags=["News Intelligence"])
api_router.include_router(financials.router, tags=["Financial Analytics"])
api_router.include_router(corporate_actions.router, prefix="/corporate-actions", tags=["Corporate Actions"])
api_router.include_router(market_events.router, prefix="/market-events", tags=["Market Events & Deals"])
api_router.include_router(forecasts.router, tags=["Forecasting Engine"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["Watchlist"])

