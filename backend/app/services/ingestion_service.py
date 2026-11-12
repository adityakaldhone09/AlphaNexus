"""
ALPHANEXUS – Data Normalization & Ingestion Service
==================================================
Orchestrates live data ingestion from IndianAPI, DhanHQ, Marketaux,
NewsAPI, and Finnhub into Supabase PostgreSQL tables.
"""

from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger
from app.models.company import Company, CompanyIdentifier
from app.models.financial import StockPrice, FinancialStatement, FinancialMetric
from app.models.corporate_action import CorporateAction
from app.models.market_event import MarketEvent
from app.models.news import NewsArticle
from app.integrations.market_data.indianapi import IndianAPIProvider
from app.integrations.market_data.dhan import DhanHQProvider
from app.integrations.news_providers.marketaux import MarketauxProvider
from app.integrations.news_providers.newsapi import NewsAPIProvider
from app.integrations.external_sources.finnhub import FinnhubProvider
from app.integrations.external_sources.fmp import FMPProvider
from app.engines.news.service import news_service


class IngestionService:
    """
    Centralized ingestion and normalization coordinator.
    Retrieves live data from external providers, normalizes the schemas,
    and updates/persists them in Supabase PostgreSQL.
    """

    def __init__(self):
        self.indian_api = IndianAPIProvider()
        self.dhan = DhanHQProvider()
        self.marketaux = MarketauxProvider()
        self.news_api = NewsAPIProvider()
        self.finnhub = FinnhubProvider()
        self.fmp = FMPProvider()

    def ingest_company_market_data(self, db: Session, symbol: str) -> Dict[str, Any]:
        """
        Ingests real-time quotes, technicals, historical prices, corporate actions,
        and announcements for a specific company symbol using IndianAPI.
        """
        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
        company = db.query(Company).filter(Company.symbol == clean_symbol).first()

        results: Dict[str, Any] = {
            "symbol": clean_symbol,
            "company_id": str(company.id) if company else None,
            "quote_updated": False,
            "prices_ingested": 0,
            "corporate_actions_ingested": 0,
            "events_ingested": 0,
            "financials_ingested": 0,
            "errors": [],
        }

        # 1. Fetch live stock data from IndianAPI
        stock_res = self.indian_api.get_stock(clean_symbol)
        if not stock_res.get("is_live"):
            results["errors"].append(stock_res.get("error") or "Failed to fetch stock data")
        else:
            try:
                if not company:
                    company = Company(
                        symbol=clean_symbol,
                        name=stock_res.get("company_name") or clean_symbol,
                        exchange="NSE",
                        is_active=True,
                    )
                    db.add(company)
                    db.commit()
                    db.refresh(company)
                    results["company_id"] = str(company.id)

                # Update live quote and fundamentals
                if stock_res.get("current_price") is not None:
                    company.current_price = stock_res["current_price"]
                if stock_res.get("percent_change") is not None:
                    company.day_change_percent = stock_res["percent_change"]
                if stock_res.get("year_high") is not None:
                    try:
                        company.week_52_high = float(stock_res["year_high"])
                    except (ValueError, TypeError):
                        pass
                if stock_res.get("year_low") is not None:
                    try:
                        company.week_52_low = float(stock_res["year_low"])
                    except (ValueError, TypeError):
                        pass
                if stock_res.get("industry") and not company.industry:
                    company.industry = stock_res["industry"]

                # Extract company profile description if present
                profile = stock_res.get("company_profile") or {}
                if profile.get("companyDescription") and not company.description:
                    company.description = profile["companyDescription"]

                # Extract key ratios from keyMetrics if present
                metrics = stock_res.get("keyMetrics") or {}
                val_metrics = metrics.get("valuation") or {}
                if val_metrics.get("pe"):
                    try:
                        company.pe_ratio = float(val_metrics["pe"])
                    except (ValueError, TypeError):
                        pass
                if val_metrics.get("pb"):
                    try:
                        company.pb_ratio = float(val_metrics["pb"])
                    except (ValueError, TypeError):
                        pass

                company.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(company)
                results["quote_updated"] = True
            except Exception as e:
                db.rollback()
                logger.error("Error updating company quote for %s: %s", clean_symbol, str(e))
                results["errors"].append(f"Quote update error: {str(e)}")

        if not company:
            return results

        # 2. Ingest Historical Prices (1m series)
        try:
            hist_res = self.indian_api.get_historical_data(clean_symbol, period="1m")
            if hist_res.get("is_live"):
                prices = hist_res.get("prices", [])
                ingested_count = 0
                for pt in prices:
                    p_date_str = pt.get("date")
                    p_close = pt.get("close")
                    if not p_date_str or p_close is None:
                        continue
                    try:
                        p_date = datetime.strptime(p_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    # Check if already exists
                    existing = db.query(StockPrice).filter(
                        StockPrice.company_id == company.id,
                        StockPrice.date == p_date,
                    ).first()

                    if not existing:
                        sp = StockPrice(
                            company_id=company.id,
                            date=p_date,
                            open=p_close,
                            high=p_close,
                            low=p_close,
                            close=p_close,
                            volume=0,
                            currency="INR",
                        )
                        db.add(sp)
                        ingested_count += 1
                    else:
                        existing.close = p_close

                db.commit()
                results["prices_ingested"] = ingested_count
        except Exception as e:
            db.rollback()
            logger.error("Error ingesting historical prices for %s: %s", clean_symbol, str(e))
            results["errors"].append(f"Prices ingestion error: {str(e)}")

        # 3. Ingest Corporate Actions
        try:
            corp_res = self.indian_api.get_corporate_actions(clean_symbol)
            if corp_res.get("is_live"):
                actions_count = 0
                div_data = corp_res.get("dividends", {}).get("data", [])
                for row in div_data:
                    # Header: ['Record Date', 'Ex-Date', 'Dividend Percentage', 'Details']
                    if len(row) >= 4:
                        ex_date_raw = row[1]
                        percentage = row[2]
                        details_text = row[3]
                        parsed_ex_date = None
                        try:
                            parsed_ex_date = datetime.strptime(ex_date_raw, "%d-%m-%Y").date()
                        except (ValueError, TypeError):
                            pass

                        # Deduplicate
                        existing_ca = db.query(CorporateAction).filter(
                            CorporateAction.company_id == company.id,
                            CorporateAction.action_type == "Dividend",
                            CorporateAction.details == details_text,
                        ).first()

                        if not existing_ca:
                            ca = CorporateAction(
                                company_id=company.id,
                                action_type="Dividend",
                                details=details_text,
                                ratio_or_amount=f"Dividend {percentage}",
                                ex_date=parsed_ex_date,
                                source="IndianAPI",
                            )
                            db.add(ca)
                            actions_count += 1

                db.commit()
                results["corporate_actions_ingested"] = actions_count
        except Exception as e:
            db.rollback()
            logger.error("Error ingesting corporate actions for %s: %s", clean_symbol, str(e))
            results["errors"].append(f"Corporate actions error: {str(e)}")

        # 4. Ingest Announcements / Market Events
        try:
            ann_res = self.indian_api.get_recent_announcements(clean_symbol)
            if ann_res.get("is_live"):
                events_count = 0
                for item in ann_res.get("announcements", []):
                    title_text = item.get("title", "")
                    link_url = item.get("link", "")
                    date_str = item.get("date", "")
                    parsed_event_date = date.today()
                    try:
                        parsed_event_date = datetime.strptime(date_str, "%d-%m-%Y").date()
                    except (ValueError, TypeError):
                        pass

                    if not title_text:
                        continue

                    existing_ev = db.query(MarketEvent).filter(
                        MarketEvent.company_id == company.id,
                        MarketEvent.title == title_text[:255],
                    ).first()

                    if not existing_ev:
                        ev = MarketEvent(
                            company_id=company.id,
                            event_type="Exchange Announcement",
                            title=title_text[:255],
                            description=title_text,
                            disclosed_date=parsed_event_date,
                            source_url=link_url[:500] if link_url else None,
                        )
                        db.add(ev)
                        events_count += 1

                db.commit()
                results["events_ingested"] = events_count
        except Exception as e:
            db.rollback()
            logger.error("Error ingesting announcements for %s: %s", clean_symbol, str(e))
            results["errors"].append(f"Events error: {str(e)}")

        # 5. Ingest Financial Statements & Metrics if available
        try:
            fin_list = stock_res.get("financials", [])
            fin_count = 0
            for fin_item in fin_list:
                fiscal_year = fin_item.get("FiscalYear") or "FY24"
                end_date_raw = fin_item.get("EndDate")
                period_end = date.today()
                try:
                    if end_date_raw:
                        period_end = datetime.strptime(end_date_raw.split("T")[0], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass

                stmt_type = "income_statement" if "income" in str(fin_item).lower() else "balance_sheet"
                existing_stmt = db.query(FinancialStatement).filter(
                    FinancialStatement.company_id == company.id,
                    FinancialStatement.statement_type == stmt_type,
                    FinancialStatement.financial_year == str(fiscal_year),
                ).first()

                if not existing_stmt:
                    fs = FinancialStatement(
                        company_id=company.id,
                        statement_type=stmt_type,
                        period_type="annual",
                        financial_year=str(fiscal_year),
                        period_end_date=period_end,
                        raw_data=fin_item.get("stockFinancialMap", {}),
                        source="IndianAPI",
                    )
                    db.add(fs)
                    fin_count += 1

            db.commit()
            results["financials_ingested"] = fin_count
        except Exception as e:
            db.rollback()
            logger.error("Error ingesting financials for %s: %s", clean_symbol, str(e))
            results["errors"].append(f"Financials error: {str(e)}")

        return results

    def sync_all_active_companies(self, db: Session) -> Dict[str, Any]:
        """Runs the ingestion pipeline for all active companies in the database."""
        active = db.query(Company).filter(Company.is_active == True).all()
        summary = {
            "total_companies": len(active),
            "synced": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for c in active:
            res = self.ingest_company_market_data(db, c.symbol)
            summary["synced"].append(res)
        return summary

    def sync_multi_source_news(self, db: Session, limit_per_source: int = 15) -> Dict[str, Any]:
        """
        Pulls news from IndianAPI, Marketaux, and NewsAPI, normalizes,
        and persists into Supabase PostgreSQL using the NewsService classifier.
        """
        active_companies = db.query(Company).filter(Company.is_active == True).all()
        company_symbols = [c.symbol for c in active_companies]

        results = {
            "indianapi_articles_found": 0,
            "marketaux_articles_found": 0,
            "newsapi_articles_found": 0,
            "articles_stored": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": [],
        }

        # 1. IndianAPI News
        if self.indian_api.is_configured:
            indian_res = self.indian_api.get_market_news()
            if indian_res.get("is_live"):
                raw_list = indian_res.get("articles", [])
                results["indianapi_articles_found"] = len(raw_list)
                results["sources"].append("IndianAPI")
                for item in raw_list[:limit_per_source]:
                    normalized = {
                        "title": item.get("title", ""),
                        "description": item.get("summary", ""),
                        "content": item.get("summary", ""),
                        "url": item.get("url", ""),
                        "source": item.get("source") or "IndianAPI",
                        "publisher": item.get("source") or "Indian Financial Wire",
                        "published_at": item.get("pub_date"),
                        "image_url": item.get("image_url"),
                    }
                    stored = news_service.process_and_store_article(
                        db, normalized, active_companies=active_companies
                    )
                    if stored:
                        results["articles_stored"] += 1

        # 2. Marketaux News
        if self.marketaux.is_configured:
            marketaux_articles = self.marketaux.fetch_news(symbols=company_symbols[:5], limit=limit_per_source)
            results["marketaux_articles_found"] = len(marketaux_articles)
            if marketaux_articles:
                results["sources"].append("Marketaux")
                for item in marketaux_articles:
                    stored = news_service.process_and_store_article(
                        db, item, active_companies=active_companies
                    )
                    if stored:
                        results["articles_stored"] += 1

        # 3. NewsAPI News
        if self.news_api.is_configured:
            query = " OR ".join([f'"{c.name}"' for c in active_companies[:3]] + ["Sensex", "Nifty 50"])
            newsapi_res = self.news_api.search_news(query=query, page_size=limit_per_source)
            if newsapi_res.get("is_live"):
                raw_news = newsapi_res.get("articles", [])
                results["newsapi_articles_found"] = len(raw_news)
                results["sources"].append("NewsAPI")
                for item in raw_news:
                    stored = news_service.process_and_store_article(
                        db, item, active_companies=active_companies
                    )
                    if stored:
                        results["articles_stored"] += 1

        return results


ingestion_service = IngestionService()

