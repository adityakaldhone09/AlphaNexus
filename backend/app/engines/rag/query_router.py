"""
EquiLens AI – Financial Query Router
=====================================
Classifies incoming user queries into one of 5 routes:

  1. DOCUMENT_RAG         – needs semantic/hybrid retrieval over uploaded docs
  2. STRUCTURED_ANALYTICS – needs structured DB queries (ratios, growth, comparisons)
  3. HYBRID               – needs both RAG + analytics (e.g., "why did margins drop")
  4. NEWS_EVENTS          – needs news/market-event engine
  5. MARKET_DATA          – needs live price/market data provider

Also rewrites ambiguous queries:
  - Normalises company names / tickers
  - Identifies financial year from query text
  - Normalises financial metric terminology
  - Generates multi-query variants for complex questions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from app.core.logging import logger


class QueryRoute(str, Enum):
    DOCUMENT_RAG = "document_rag"
    STRUCTURED_ANALYTICS = "structured_analytics"
    HYBRID = "hybrid"
    NEWS_EVENTS = "news_events"
    MARKET_DATA = "market_data"


@dataclass
class RoutingResult:
    route: QueryRoute
    confidence: float
    rewritten_queries: List[str]          # 1..3 rewrite variants
    financial_year_hint: Optional[str]
    company_hint: Optional[str]
    metric_hints: List[str]
    reasoning: str
    filters_suggested: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Signal keyword sets
# ---------------------------------------------------------------------------

_DOC_RAG_SIGNALS = [
    "annual report", "filing", "mention", "discuss", "according to",
    "what does", "explain", "describe", "risk factor", "contingent",
    "auditor", "note to", "management comment", "outlook",
    "chairman", "director report", "investor presentation",
    "transcript", "concall", "disclosure", "agreement", "contract terms",
]

_ANALYTICS_SIGNALS = [
    "calculate", "compute", "ratio", "margin", "growth rate",
    "compare", "trend", "historical", "five year", "cagr",
    "revenue growth", "profit margin", "roe", "roce", "ebitda margin",
    "eps", "pe ratio", "pb ratio", "debt to equity", "current ratio",
    "working capital", "free cash flow", "capex",
]

_HYBRID_SIGNALS = [
    "why did", "reason for", "cause of", "impact of",
    "how did", "what caused", "decline in", "fall in",
    "explain the change", "performance analysis",
    "financial impact", "deal size", "acquisition cost",
    "compare performance", "sector vs",
]

_NEWS_SIGNALS = [
    "announcement", "deal", "contract win", "acquisition",
    "merger", "joint venture", "latest news", "recent",
    "corporate action", "dividend", "buyback", "split", "bonus",
    "press release", "regulatory", "sebi order", "government contract",
]

_MARKET_DATA_SIGNALS = [
    "stock price", "share price", "market cap", "52 week",
    "intraday", "historical price", "volume", "nse price",
    "bse price", "live quote", "current price", "today's price",
]

# Common financial year patterns
_FY_RE = re.compile(
    r"""
        (?:fy|financial\s+year|year|q[1-4])\s*
        (?:20)?(\d{2})[/-]?(?:20)?(\d{2})?
        |
        20(\d{2})[-/]20?(\d{2})
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Indian company ticker / known names
_COMPANY_ALIASES: Dict[str, str] = {
    "reliance": "RELIANCE",
    "ril": "RELIANCE",
    "tcs": "TCS",
    "tata consultancy": "TCS",
    "infosys": "INFY",
    "infy": "INFY",
    "hdfc bank": "HDFCBANK",
    "hdfcbank": "HDFCBANK",
    "larsen": "LT",
    "l&t": "LT",
    "wipro": "WIPRO",
    "hcl": "HCLTECH",
    "icici bank": "ICICIBANK",
    "sbi": "SBIN",
    "kotak": "KOTAKBANK",
    "maruti": "MARUTI",
    "bajaj finance": "BAJFINANCE",
    "asian paints": "ASIANPAINT",
}

# Financial metric normalisation
_METRIC_ALIASES: Dict[str, str] = {
    "net profit": "net_profit",
    "pat": "net_profit",
    "profit after tax": "net_profit",
    "revenue": "revenue",
    "sales": "revenue",
    "total income": "revenue",
    "ebitda": "ebitda",
    "operating profit": "ebitda",
    "operating income": "ebitda",
    "eps": "eps",
    "earnings per share": "eps",
    "roe": "roe",
    "return on equity": "roe",
    "roce": "roce",
    "debt to equity": "debt_to_equity",
    "d/e": "debt_to_equity",
    "current ratio": "current_ratio",
    "pe": "pe_ratio",
    "p/e": "pe_ratio",
    "pb": "pb_ratio",
    "price to book": "pb_ratio",
    "free cash flow": "free_cash_flow",
    "fcf": "free_cash_flow",
}


class QueryRouter:
    """
    Rule-based financial query router and rewriter.
    Deliberately avoids calling an LLM for routing (keeps latency low).
    """

    def route(
        self,
        query: str,
        company_hint: Optional[str] = None,
        session_context: Optional[str] = None,
    ) -> RoutingResult:
        """
        Classify and rewrite a user query.

        Args:
            query: Raw user query text
            company_hint: Pre-selected company (from UI company selector)
            session_context: Recent conversation context (optional)

        Returns:
            RoutingResult with route, rewrites, and extracted hints
        """
        q_lower = query.lower().strip()

        # Signal scoring
        doc_score = sum(1 for s in _DOC_RAG_SIGNALS if s in q_lower)
        ana_score = sum(1 for s in _ANALYTICS_SIGNALS if s in q_lower)
        hyb_score = sum(1 for s in _HYBRID_SIGNALS if s in q_lower)
        news_score = sum(1 for s in _NEWS_SIGNALS if s in q_lower)
        mkt_score = sum(1 for s in _MARKET_DATA_SIGNALS if s in q_lower)

        scores = {
            QueryRoute.DOCUMENT_RAG: doc_score * 1.2,
            QueryRoute.STRUCTURED_ANALYTICS: ana_score * 1.0,
            QueryRoute.HYBRID: hyb_score * 1.5 + (doc_score + ana_score) * 0.3,
            QueryRoute.NEWS_EVENTS: news_score * 1.1,
            QueryRoute.MARKET_DATA: mkt_score * 2.0,  # strong signal if present
        }

        best_route = max(scores, key=scores.__getitem__)
        best_score = scores[best_route]

        # Fallback: any question with a company name → document RAG
        if best_score == 0:
            best_route = QueryRoute.DOCUMENT_RAG
            best_score = 1.0

        confidence = min(1.0, best_score / 5.0)

        # Extract FY hint
        fy_hint = self._extract_fy(q_lower)

        # Extract company hint
        co_hint = company_hint or self._extract_company(q_lower)

        # Extract metric hints
        metric_hints = self._extract_metrics(q_lower)

        # Generate rewritten query variants
        rewrites = self._rewrite(query, fy_hint, co_hint, metric_hints)

        # Build suggested filters
        filters: Dict[str, Any] = {}
        if fy_hint:
            filters["financial_year"] = fy_hint
        if co_hint:
            filters["company_symbol"] = co_hint

        reasoning = (
            f"Route: {best_route.value} (conf={confidence:.2f}) | "
            f"Signals: doc={doc_score} ana={ana_score} hyb={hyb_score} "
            f"news={news_score} mkt={mkt_score}"
        )

        logger.debug(f"[QueryRouter] {reasoning}")

        return RoutingResult(
            route=best_route,
            confidence=confidence,
            rewritten_queries=rewrites,
            financial_year_hint=fy_hint,
            company_hint=co_hint,
            metric_hints=metric_hints,
            reasoning=reasoning,
            filters_suggested=filters,
        )

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_fy(self, text: str) -> Optional[str]:
        m = _FY_RE.search(text)
        if not m:
            return None
        groups = m.groups()
        y1 = groups[0] or groups[2]
        if y1:
            try:
                y1_int = int(y1)
                if y1_int < 100:
                    y1_int += 2000
                # FY24 means the year ENDING in 2024 (Indian FY convention)
                return f"FY{y1_int % 100:02d}"
            except ValueError:
                pass
        return None

    def _extract_company(self, text: str) -> Optional[str]:
        for alias, ticker in _COMPANY_ALIASES.items():
            if alias in text:
                return ticker
        from app.services.company_discovery import MASTER_EQUITIES_UNIVERSE
        upper_text = text.upper()
        for item in MASTER_EQUITIES_UNIVERSE:
            if re.search(rf"\b{re.escape(item['symbol'])}\b", upper_text) or item["name"].lower() in text:
                return item["symbol"]
            for alias in item.get("aliases", []):
                if len(alias) > 2 and re.search(rf"\b{re.escape(alias)}\b", text, re.IGNORECASE):
                    return item["symbol"]
        return None

    def _extract_metrics(self, text: str) -> List[str]:
        found = []
        for alias, canonical in _METRIC_ALIASES.items():
            if alias in text and canonical not in found:
                found.append(canonical)
        return found[:5]

    def _rewrite(
        self,
        query: str,
        fy_hint: Optional[str],
        company_hint: Optional[str],
        metrics: List[str],
    ) -> List[str]:
        """Generate up to 3 query variants for multi-query retrieval."""
        variants = [query]

        # Add FY context if missing
        if fy_hint and fy_hint.lower() not in query.lower():
            variants.append(f"{query} for {fy_hint}")

        # Add company context if known
        if company_hint and company_hint.lower() not in query.lower():
            variants.append(f"{company_hint}: {query}")

        # Metric expansion
        for metric in metrics[:2]:
            normalised = metric.replace("_", " ")
            if normalised not in query.lower():
                variants.append(f"{query} – specifically {normalised}")

        return list(dict.fromkeys(variants))[:3]  # deduplicate, keep 3

    def route_query(self, query: str) -> str:
        """
        Convenience alias returning a simple string route label.
        Used by unit tests expecting one of: 'financial', 'hybrid', 'dense', 'general'.
        """
        result = self.route(query)
        mapping = {
            "document_rag": "dense",
            "structured_analytics": "financial",
            "hybrid": "hybrid",
            "news_events": "dense",
            "market_data": "financial",
        }
        return mapping.get(result.route.value, "general")


query_router = QueryRouter()
