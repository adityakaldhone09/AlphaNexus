"""
AlphaNexus — LangChain Research Tools
=======================================
7 typed, validated tools for financial equity research:

  1. get_company_live_data      — IndianAPI: price, profile, financials
  2. get_company_announcements  — IndianAPI: exchange announcements
  3. get_corporate_actions      — IndianAPI: dividends, splits, bonus
  4. get_market_news            — IndianAPI + Marketaux: live news
  5. retrieve_company_documents — pgvector RAG: indexed filings
  6. calculate_financial_ratios — FinancialCalculator: deterministic ratios
  7. get_company_profile_db     — PostgreSQL: stored company metadata

All tools:
- Return explicit "data_unavailable" when a provider is not configured
- Never fabricate financial figures
- Include retrieval timestamp in every live response
- Handle errors gracefully without raising to the LLM
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.integrations.market_data.indianapi import IndianAPIProvider
from app.integrations.news_providers.marketaux import MarketauxProvider


# ---------------------------------------------------------------------------
# Shared provider instances (created once, reused across all tool calls)
# ---------------------------------------------------------------------------
_indian_api = IndianAPIProvider()
_marketaux   = MarketauxProvider()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_call(fn, *args, **kwargs) -> Dict[str, Any]:
    """Wraps any provider call; returns error dict on exception."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("Tool call failed: %s", exc)
        return {"is_live": False, "error": str(exc), "retrieved_at": _now_iso()}


# ---------------------------------------------------------------------------
# Tool 1 — Live company data (price, profile, financials, technicals)
# ---------------------------------------------------------------------------

@tool
def get_company_live_data(symbol: str) -> str:
    """
    Retrieve live stock quote, company profile, key financial metrics,
    and technical indicators for an NSE/BSE-listed Indian equity.

    Args:
        symbol: NSE ticker symbol, e.g. RELIANCE, TCS, HDFCBANK, INFY, LT

    Returns:
        JSON string with current price, key ratios, company profile,
        and financial highlights. Includes retrieval timestamp.
        Returns explicit unavailability message if provider is not configured.
    """
    result = _safe_call(_indian_api.get_stock, symbol)
    result["tool"] = "get_company_live_data"
    result["requested_symbol"] = symbol
    if not result.get("retrieved_at"):
        result["retrieved_at"] = _now_iso()
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Tool 2 — Exchange announcements (NSE/BSE)
# ---------------------------------------------------------------------------

@tool
def get_company_announcements(symbol: str) -> str:
    """
    Retrieve the latest exchange announcements (NSE/BSE) for an Indian equity.
    Includes board meeting outcomes, financial result notifications,
    corporate governance disclosures, and regulatory filings.

    Args:
        symbol: NSE ticker symbol, e.g. RELIANCE, TCS

    Returns:
        JSON string with list of announcements, each with date, category, subject.
    """
    result = _safe_call(_indian_api.get_recent_announcements, symbol)
    result["tool"] = "get_company_announcements"
    result["retrieved_at"] = _now_iso()
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Tool 3 — Corporate actions
# ---------------------------------------------------------------------------

@tool
def get_corporate_actions(symbol: str) -> str:
    """
    Retrieve corporate action history for an Indian equity including
    dividends, stock splits, bonus issues, rights issues, and board meetings.

    Args:
        symbol: NSE ticker symbol

    Returns:
        JSON string with dividends, splits, bonus, rights, and board meeting data.
    """
    result = _safe_call(_indian_api.get_corporate_actions, symbol)
    result["tool"] = "get_corporate_actions"
    result["retrieved_at"] = _now_iso()
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Tool 4 — Market news
# ---------------------------------------------------------------------------

@tool
def get_market_news(symbol: Optional[str] = None, keywords: Optional[str] = None) -> str:
    """
    Retrieve recent financial news for an Indian equity or market topic.
    Checks IndianAPI for company-specific news, then Marketaux for broader coverage.

    Args:
        symbol: Optional NSE ticker, e.g. RELIANCE. Leave empty for general market news.
        keywords: Optional search keywords, e.g. 'quarterly results FY25'

    Returns:
        JSON string with list of recent articles. Each article includes
        title, source, published date, and URL where available.
    """
    articles: List[Dict[str, Any]] = []
    source_used = "none"

    # Try IndianAPI market news first
    if _indian_api.is_configured:
        if symbol:
            ann = _safe_call(_indian_api.get_recent_announcements, symbol)
            raw = ann.get("announcements", [])
            if isinstance(raw, list):
                articles.extend(raw[:5])
        general = _safe_call(_indian_api.get_market_news)
        raw_gen = general.get("articles", [])
        if isinstance(raw_gen, list):
            articles.extend(raw_gen[:5])
        source_used = "IndianAPI"

    # Supplement with Marketaux
    if _marketaux.is_configured:
        syms = [symbol] if symbol else None
        mx_articles = _safe_call(_marketaux.fetch_news, syms, keywords, 8)
        if isinstance(mx_articles, list):
            articles.extend(mx_articles[:5])
        source_used = source_used + "+Marketaux" if source_used != "none" else "Marketaux"

    return json.dumps({
        "tool": "get_market_news",
        "symbol": symbol,
        "keywords": keywords,
        "source": source_used,
        "count": len(articles),
        "articles": articles[:10],
        "retrieved_at": _now_iso(),
        "is_live": bool(articles),
        "data_unavailable": not bool(articles),
    }, default=str)


# ---------------------------------------------------------------------------
# Tool 5 — Document RAG retrieval
# ---------------------------------------------------------------------------

@tool
def retrieve_company_documents(
    query: str,
    company_id: Optional[str] = None,
    financial_year: Optional[str] = None,
    document_type: Optional[str] = None,
    top_k: int = 6,
) -> str:
    """
    Retrieve relevant passages from indexed company filings using
    hybrid vector + keyword search over the pgvector knowledge base.
    Use this for annual reports, quarterly results, investor presentations,
    earnings call transcripts, and other uploaded financial documents.

    Args:
        query: Research question or topic to retrieve passages for
        company_id: Optional company UUID or ticker symbol to scope the search
        financial_year: Optional FY filter, e.g. 'FY24', 'FY25'
        document_type: Optional document type, e.g. 'Annual Report'
        top_k: Number of passages to retrieve (default 6, max 10)

    Returns:
        JSON string with retrieved passages, their source documents,
        page numbers, sections, and similarity scores.
    """
    try:
        from app.core.database import SessionLocal
        from app.engines.rag.vector_store import vector_store
        from app.engines.rag.embeddings import embedding_engine
        from app.models.company import Company

        db = SessionLocal()
        try:
            # Resolve ticker → UUID
            comp_uuid = None
            if company_id:
                import uuid as _uuid
                try:
                    comp_uuid = str(_uuid.UUID(company_id))
                except (ValueError, AttributeError):
                    # Try symbol lookup
                    c = db.query(Company).filter(Company.symbol == company_id.upper()).first()
                    if c:
                        comp_uuid = str(c.id)

            q_vec = embedding_engine.generate_query_embedding(query)
            chunks = vector_store.hybrid_search(
                db=db,
                query=query,
                query_embedding=q_vec,
                company_id=comp_uuid,
                financial_year=financial_year,
                document_type=document_type,
                top_k=min(top_k, 10),
            )

            passages = []
            for c in chunks:
                passages.append({
                    "document_title": c.get("document_title", ""),
                    "document_type": c.get("document_type", ""),
                    "financial_year": c.get("financial_year", ""),
                    "page_number": c.get("page_number"),
                    "section": c.get("section", ""),
                    "excerpt": (c.get("clean_text") or c.get("content", ""))[:500],
                    "similarity_score": c.get("similarity_score", 0),
                    "rrf_score": c.get("rrf_score"),
                })

            return json.dumps({
                "tool": "retrieve_company_documents",
                "query": query,
                "company_id": comp_uuid,
                "financial_year": financial_year,
                "retrieved_count": len(passages),
                "passages": passages,
                "data_unavailable": len(passages) == 0,
                "retrieved_at": _now_iso(),
            }, default=str)
        finally:
            db.close()

    except Exception as exc:
        logger.error("retrieve_company_documents failed: %s", exc)
        return json.dumps({
            "tool": "retrieve_company_documents",
            "data_unavailable": True,
            "error": str(exc),
            "retrieved_at": _now_iso(),
        })


# ---------------------------------------------------------------------------
# Tool 6 — Financial ratio calculation
# ---------------------------------------------------------------------------

@tool
def calculate_financial_ratios(
    revenue: Optional[float] = None,
    previous_revenue: Optional[float] = None,
    ebitda: Optional[float] = None,
    net_profit: Optional[float] = None,
    previous_net_profit: Optional[float] = None,
    shareholders_equity: Optional[float] = None,
    total_debt: Optional[float] = None,
    total_assets: Optional[float] = None,
    current_assets: Optional[float] = None,
    current_liabilities: Optional[float] = None,
    operating_cash_flow: Optional[float] = None,
    capital_expenditures: Optional[float] = None,
    current_price: Optional[float] = None,
    eps: Optional[float] = None,
) -> str:
    """
    Compute deterministic financial ratios from provided input values.
    All inputs are optional — only metrics with sufficient data are computed.
    Never estimates or invents values. Returns None for metrics missing required inputs.

    Args:
        revenue: Total revenue (₹ Crores)
        previous_revenue: Prior period revenue for YoY growth
        ebitda: EBITDA (₹ Crores)
        net_profit: PAT (₹ Crores)
        previous_net_profit: Prior period PAT for YoY growth
        shareholders_equity: Total equity (₹ Crores)
        total_debt: Total debt (₹ Crores)
        total_assets: Total assets (₹ Crores)
        current_assets: Current assets (₹ Crores)
        current_liabilities: Current liabilities (₹ Crores)
        operating_cash_flow: Operating cash flow (₹ Crores)
        capital_expenditures: Capex (₹ Crores, positive number)
        current_price: Current stock price (₹)
        eps: Earnings per share (₹)

    Returns:
        JSON string with all computable ratios and None for unavailable ones.
    """
    from app.engines.analytics.formulas import FinancialCalculator as FC

    statement = {
        "revenue": revenue, "previous_revenue": previous_revenue,
        "ebitda": ebitda, "net_profit": net_profit,
        "previous_net_profit": previous_net_profit,
        "shareholders_equity": shareholders_equity, "total_debt": total_debt,
        "total_assets": total_assets, "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "operating_cash_flow": operating_cash_flow,
        "capital_expenditures": capital_expenditures,
        "current_price": current_price, "eps": eps,
    }
    ratios = FC.compute_all_metrics(statement)

    return json.dumps({
        "tool": "calculate_financial_ratios",
        "inputs_provided": {k: v for k, v in statement.items() if v is not None},
        "computed_ratios": ratios,
        "note": "All ratios computed deterministically. None indicates insufficient input data.",
    }, default=str)


# ---------------------------------------------------------------------------
# Tool 7 — Company profile from database
# ---------------------------------------------------------------------------

@tool
def get_company_profile_db(symbol: str) -> str:
    """
    Retrieve stored company profile from the AlphaNexus database including
    sector, exchange, market cap, valuation metrics, and financial KPIs.

    Args:
        symbol: NSE ticker symbol, e.g. RELIANCE, TCS, HDFCBANK

    Returns:
        JSON string with company profile, latest financial metrics, and
        recent corporate actions stored in the system database.
    """
    try:
        from app.core.database import SessionLocal
        from app.models.company import Company
        from app.models.financial import FinancialMetric
        from app.core.database import parse_uuid

        db = SessionLocal()
        try:
            company = (
                db.query(Company)
                .filter(Company.symbol == symbol.upper())
                .first()
            )
            if not company:
                return json.dumps({
                    "tool": "get_company_profile_db",
                    "symbol": symbol,
                    "data_unavailable": True,
                    "message": f"Company '{symbol}' not found in AlphaNexus database.",
                })

            # Latest 8 financial metrics
            metrics = (
                db.query(FinancialMetric)
                .filter(FinancialMetric.company_id == company.id)
                .order_by(FinancialMetric.period_end_date.desc())
                .limit(16)
                .all()
            )

            metrics_out = [
                {
                    "metric": m.metric_name,
                    "value": float(m.value),
                    "unit": m.unit,
                    "financial_year": m.financial_year,
                    "period_type": m.period_type,
                    "is_consolidated": m.is_consolidated,
                }
                for m in metrics
            ]

            return json.dumps({
                "tool": "get_company_profile_db",
                "id": str(company.id),
                "symbol": company.symbol,
                "name": company.name,
                "exchange": company.exchange,
                "sector": company.sector,
                "industry": company.industry,
                "market_cap": float(company.market_cap) if company.market_cap else None,
                "current_price": float(company.current_price) if company.current_price else None,
                "day_change_percent": float(company.day_change_percent) if company.day_change_percent else None,
                "pe_ratio": float(company.pe_ratio) if company.pe_ratio else None,
                "pb_ratio": float(company.pb_ratio) if company.pb_ratio else None,
                "roe": float(company.roe) if company.roe else None,
                "roce": float(company.roce) if company.roce else None,
                "dividend_yield": float(company.dividend_yield) if company.dividend_yield else None,
                "week_52_high": float(company.week_52_high) if company.week_52_high else None,
                "week_52_low": float(company.week_52_low) if company.week_52_low else None,
                "description": company.description,
                "website": company.website,
                "financial_metrics": metrics_out,
                "data_source": "AlphaNexus PostgreSQL",
                "retrieved_at": _now_iso(),
            }, default=str)
        finally:
            db.close()
    except Exception as exc:
        logger.error("get_company_profile_db failed: %s", exc)
        return json.dumps({
            "tool": "get_company_profile_db",
            "symbol": symbol,
            "data_unavailable": True,
            "error": str(exc),
        })


# ---------------------------------------------------------------------------
# Exported tool list (order matters for the agent)
# ---------------------------------------------------------------------------
ALL_TOOLS = [
    get_company_live_data,
    get_company_announcements,
    get_corporate_actions,
    get_market_news,
    retrieve_company_documents,
    calculate_financial_ratios,
    get_company_profile_db,
]
