import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.core.config import settings
from app.integrations.market_data.indianapi import IndianAPIProvider
from app.integrations.news_providers.newsapi import NewsAPIProvider
from app.integrations.external_sources.finnhub import FinnhubProvider
from app.services.audit_service import run_integrations_audit, get_cached_integrations_status
from app.services.ingestion_service import IngestionService
from app.models.company import Company
from app.models.financial import StockPrice
from app.models.corporate_action import CorporateAction


# ==============================================================================
# IndianAPI Provider Tests
# ==============================================================================

def test_indianapi_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "INDIANAPI_API_KEY", None)
    provider = IndianAPIProvider()
    assert not provider.is_configured
    health = provider.check_availability()
    assert health["available"] is False
    assert health["status"] == "Not configured"
    quote = provider.get_stock("RELIANCE")
    assert quote["is_live"] is False


def test_indianapi_get_stock_parsing(monkeypatch):
    monkeypatch.setattr(settings, "INDIANAPI_API_KEY", "mock-test-key")
    provider = IndianAPIProvider()

    mock_response_data = {
        "companyName": "Test Reliance Ltd",
        "industry": "Oil & Gas",
        "currentPrice": {"NSE": "1350.50", "BSE": "1350.25"},
        "percentChange": 1.25,
        "yearHigh": 1600.0,
        "yearLow": 1100.0,
        "companyProfile": {"companyDescription": "Major conglomerate."},
        "keyMetrics": {"valuation": {"pe": "24.5", "pb": "2.1"}},
        "financials": [{"FiscalYear": "FY25", "stockFinancialMap": {"revenue": 100000}}],
    }

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = mock_response_data

    with patch("httpx.Client.get", return_value=mock_res):
        res = provider.get_stock("RELIANCE.NS")
        assert res["is_live"] is True
        assert res["symbol"] == "RELIANCE"
        assert res["company_name"] == "Test Reliance Ltd"
        assert res["current_price"] == 1350.50
        assert res["percent_change"] == 1.25
        assert res["year_high"] == 1600.0


def test_indianapi_historical_period_normalization(monkeypatch):
    monkeypatch.setattr(settings, "INDIANAPI_API_KEY", "mock-test-key")
    provider = IndianAPIProvider()

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "datasets": [
            {
                "metric": "Price",
                "values": [["2026-11-01", "1300.00"], ["2026-11-02", "1310.00"]],
            }
        ]
    }

    with patch("httpx.Client.get", return_value=mock_res) as mock_get:
        res = provider.get_historical_data("TCS", period="1y")
        assert res["is_live"] is True
        assert res["count"] == 2
        assert res["prices"][0]["date"] == "2026-11-01"
        assert res["prices"][0]["close"] == 1300.00
        # Verify period was mapped to '1yr'
        mock_get.assert_called_once()
        call_params = mock_get.call_args[1].get("params", {})
        assert call_params.get("period") == "1yr"


def test_indianapi_check_availability_auth_error(monkeypatch):
    monkeypatch.setattr(settings, "INDIANAPI_API_KEY", "bad-key")
    provider = IndianAPIProvider()

    mock_res = MagicMock()
    mock_res.status_code = 403
    mock_res.text = "Forbidden"

    with patch("httpx.Client.get", return_value=mock_res):
        health = provider.check_availability()
        assert health["available"] is False
        assert health["status"] == "Unavailable"
        assert health["error_category"] == "authentication"
        # Secrets must never be exposed
        assert "bad-key" not in str(health)


# ==============================================================================
# NewsAPI Provider Tests
# ==============================================================================

def test_newsapi_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "NEWSAPI_API_KEY", None)
    provider = NewsAPIProvider()
    assert not provider.is_configured
    health = provider.check_availability()
    assert health["available"] is False
    assert health["status"] == "Not configured"


def test_newsapi_search_and_normalize(monkeypatch):
    monkeypatch.setattr(settings, "NEWSAPI_API_KEY", "mock-news-key")
    provider = NewsAPIProvider()

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "status": "ok",
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "author": "Journalist",
                "title": "Nifty surges 200 points on IT rally",
                "description": "Indian equity markets hit new highs.",
                "url": "https://reuters.com/market-rally",
                "publishedAt": "2026-11-12T05:00:00Z",
                "content": "Full article body here...",
            },
            {
                "title": "[Removed]",
                "url": "https://example.com/removed",
            },
        ],
    }

    with patch("httpx.Client.get", return_value=mock_res):
        res = provider.search_news("Nifty")
        assert res["is_live"] is True
        assert res["count"] == 1  # [Removed] item filtered out
        article = res["articles"][0]
        assert article["title"] == "Nifty surges 200 points on IT rally"
        assert article["source"] == "Reuters"
        assert article["publisher"] == "Reuters"


# ==============================================================================
# Finnhub Provider Tests
# ==============================================================================

def test_finnhub_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "FINHUB_API_KEY", None)
    monkeypatch.setattr(settings, "FINNHUB_API_KEY", None)
    provider = FinnhubProvider()
    assert not provider.is_configured
    health = provider.check_availability()
    assert health["available"] is False
    assert health["status"] == "Not configured"


def test_finnhub_quote_parsing(monkeypatch):
    monkeypatch.setattr(settings, "FINHUB_API_KEY", "mock-finnhub-key")
    provider = FinnhubProvider()

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "c": 250.75,
        "d": 3.25,
        "dp": 1.31,
        "h": 252.0,
        "l": 248.5,
        "o": 249.0,
        "pc": 247.5,
        "t": 1794400000,
    }

    with patch("httpx.Client.get", return_value=mock_res):
        quote = provider.get_quote("AAPL")
        assert quote["is_live"] is True
        assert quote["symbol"] == "AAPL"
        assert quote["current_price"] == 250.75
        assert quote["change"] == 3.25
        assert quote["percent_change"] == 1.31


# ==============================================================================
# Audit Service Sanitization Tests
# ==============================================================================

def test_audit_service_includes_all_providers_without_leaks():
    """Verify all 13 providers are audited without leaking keys or tokens."""
    audit = run_integrations_audit(probe_ai=False)
    providers = [item["provider"] for item in audit["integrations"]]

    expected_providers = [
        "Google Gemini",
        "Groq",
        # Accept either PostgreSQL (production) or SQLite fallback (local dev)
        # "PostgreSQL" or "SQLite (development fallback)"
        "pgvector",
        "Supabase Storage",
        "MongoDB Atlas",
        "IndianAPI",
        "DhanHQ",
        "Marketaux",
        "NewsAPI",
        "Financial Modeling Prep (FMP)",
        "Finnhub",
        "Langfuse",
        "Sentry",
    ]

    for p in expected_providers:
        assert p in providers, f"Provider {p} missing from audit report"

    # DB provider check: either PostgreSQL or SQLite fallback should be present
    db_providers = [p for p in providers if "PostgreSQL" in p or "SQLite" in p]
    assert len(db_providers) >= 1, "No database provider found in audit report"

    # Verify no credentials or API keys are leaked in the audit output
    audit_str = str(audit)
    assert "Bearer " not in audit_str
    if settings.INDIANAPI_API_KEY:
        assert settings.INDIANAPI_API_KEY not in audit_str
    if settings.DHAN_ACCESS_TOKEN:
        assert settings.DHAN_ACCESS_TOKEN not in audit_str
    if settings.MARKETAUX_API_TOKEN:
        assert settings.MARKETAUX_API_TOKEN not in audit_str
    if settings.NEWSAPI_API_KEY:
        assert settings.NEWSAPI_API_KEY not in audit_str
    if settings.FMP_API_KEY:
        assert settings.FMP_API_KEY not in audit_str
    if settings.effective_finnhub_key:
        assert settings.effective_finnhub_key not in audit_str
    if settings.GEMINI_API_KEY:
        assert settings.GEMINI_API_KEY not in audit_str
    if settings.GROQ_API_KEY:
        assert settings.GROQ_API_KEY not in audit_str
    if settings.LANGFUSE_SECRET_KEY:
        assert settings.LANGFUSE_SECRET_KEY not in audit_str
    if settings.MONGODB_URI and "@" in settings.MONGODB_URI:
        user_info = settings.MONGODB_URI.split("@")[0].split("//")[-1]
        if ":" in user_info:
            passwd = user_info.split(":")[1]
            if len(passwd) > 3:
                assert passwd not in audit_str

