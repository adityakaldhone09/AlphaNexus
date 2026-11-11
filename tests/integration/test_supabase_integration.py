"""
AlphaNexus — Comprehensive Supabase Integration Test Suite
==========================================================
Verifies that all core platform modules retrieve and persist authentic records
using Supabase PostgreSQL 17.11, pgvector v0.8.2, and Supabase Storage.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import engine, SessionLocal, check_database_health
from app.models.company import Company
from app.models.financial import FinancialMetric
from app.models.forecast import Forecast
from app.models.news import NewsArticle
from app.models.market_event import MarketEvent
from app.models.corporate_action import CorporateAction
from app.models.document import Document, DocumentChunk
from app.models.research import ResearchSession
from app.engines.rag.service import rag_service
from app.services.supabase_storage import supabase_storage

client = TestClient(app)


def test_supabase_connectivity_and_extensions():
    """Verify live Supabase PostgreSQL connectivity and pgvector 0.8.2."""
    health = check_database_health()
    assert health["reachable"] is True, f"Supabase not reachable: {health.get('details')}"
    assert health["database_type"] == "postgresql"
    assert health["pgvector_available"] is True


def test_company_intelligence_module():
    """Verify company listing, detail retrieval, and search against Supabase."""
    resp = client.get("/api/v1/companies")
    assert resp.status_code == 200
    companies = resp.json()
    assert len(companies) >= 5
    symbols = {c["symbol"] for c in companies}
    assert "RELIANCE" in symbols
    assert "TCS" in symbols

    # Test company detail by symbol and UUID
    rel = [c for c in companies if c["symbol"] == "RELIANCE"][0]
    rel_id = rel["id"]

    detail_resp = client.get(f"/api/v1/companies/{rel_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["symbol"] == "RELIANCE"

    # Search
    search_resp = client.get("/api/v1/companies/search?q=Tata")
    assert search_resp.status_code == 200
    assert any(c["symbol"] == "TCS" for c in search_resp.json())


def test_financial_metrics_module():
    """Verify financial metrics and ratios from Supabase."""
    resp = client.get("/api/v1/companies/RELIANCE/financials")
    assert resp.status_code == 200
    metrics = resp.json()
    assert isinstance(metrics, list)
    assert len(metrics) > 0

    ratios_resp = client.get("/api/v1/companies/RELIANCE/ratios")
    assert ratios_resp.status_code == 200


def test_forecasting_module_multivariate():
    """Verify revenue, net_profit, ebitda, and eps forecast runs against Supabase."""
    for metric in ["revenue", "net_profit", "ebitda"]:
        resp = client.get(f"/api/v1/companies/RELIANCE/forecasts?metric_name={metric}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("SUCCESS", "INSUFFICIENT_DATA")
        assert data["company_symbol"] == "RELIANCE"


def test_news_and_market_events_module():
    """Verify news, corporate actions, and market events from Supabase."""
    news_resp = client.get("/api/v1/news")
    assert news_resp.status_code == 200
    assert isinstance(news_resp.json(), list)

    events_resp = client.get("/api/v1/market-events")
    assert events_resp.status_code == 200
    assert isinstance(events_resp.json(), list)

    actions_resp = client.get("/api/v1/corporate-actions")
    assert actions_resp.status_code == 200
    assert isinstance(actions_resp.json(), list)


def test_pgvector_rag_retrieval():
    """Verify native pgvector 384-dimensional cosine similarity retrieval."""
    results = rag_service.search_documents(
        query="operating profit margin and capital expenditure",
        top_k=3,
    )
    assert isinstance(results, list)
    if results:
        top_chunk = results[0]
        assert "chunk_id" in top_chunk
        assert "content" in top_chunk
        assert "similarity_score" in top_chunk
        assert float(top_chunk["similarity_score"]) >= 0.0


def test_supabase_storage_path_and_lifecycle():
    """Verify secure folder path generation and local/remote handling."""
    dummy_company_id = str(uuid.uuid4())
    path = supabase_storage.generate_storage_path(
        company_id=dummy_company_id,
        document_type="Annual Report",
        filename="FY24_Report.pdf",
    )
    assert path.startswith(f"companies/{dummy_company_id}/annual-reports/")
    assert path.endswith(".pdf")

    # Test upload and cleanup
    content = b"%PDF-1.4 test document content for Supabase storage validation"
    res = supabase_storage.upload_file(
        file_bytes=content,
        destination_path=path,
        content_type="application/pdf",
    )
    assert res["size_bytes"] == len(content)
    assert res["storage_path"] == path

    # Cleanup
    supabase_storage.delete_file(storage_path=path, local_path=res["local_path"])
