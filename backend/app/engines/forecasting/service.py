import math
import re
from typing import List, Dict, Any, Optional
from datetime import date
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.company import Company
from app.models.financial import FinancialMetric, StockPrice
from app.models.forecast import Forecast, ForecastEvaluation
from app.engines.forecasting.models.baseline import BaselineForecaster
from app.engines.forecasting.scenarios import ScenarioGenerator
from app.engines.forecasting.validation import ForecastValidator
from app.core.logging import logger


SUPPORTED_METRICS = {"revenue", "net_profit", "ebitda", "eps"}
MIN_HISTORICAL_POINTS = 2


class ForecastCompanyNotFound(Exception):
    pass


class ForecastingService:
    """
    Forecasting Engine Orchestrator for EquiLens AI.
    Generates multi-period financial forecasts (Revenue, Net Profit, EBITDA, EPS)
    and stock price trend scenarios with walk-forward validation and clear disclaimers.
    """

    def __init__(self):
        self.baseline_model = BaselineForecaster()

    def generate_company_forecast(
        self,
        db: Session,
        company_id: UUID,
        metric_name: str = "revenue",
        forecast_horizon_years: int = 3,
    ) -> Dict[str, Any]:
        """
        Retrieves historical metrics for company, checks data adequacy,
        runs baseline model, generates Bull/Base/Bear scenarios, and persists forecast.
        """
        if metric_name not in SUPPORTED_METRICS:
            raise ValueError(f"Unsupported metric_name: {metric_name}")
        if not 1 <= forecast_horizon_years <= 5:
            raise ValueError("forecast_horizon_years must be between 1 and 5")

        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ForecastCompanyNotFound(str(company_id))

        # Query historical annual metrics
        metrics = (
            db.query(FinancialMetric)
            .filter(
                FinancialMetric.company_id == company.id,
                FinancialMetric.metric_name == metric_name,
                FinancialMetric.period_type == "annual",
            )
            .order_by(
                FinancialMetric.financial_year.asc(),
                FinancialMetric.is_consolidated.desc(),
                FinancialMetric.period_end_date.desc(),
            )
            .all()
        )

        history = []
        seen_periods = set()
        for metric in metrics:
            if metric.financial_year in seen_periods:
                continue
            try:
                value = float(metric.value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                seen_periods.add(metric.financial_year)
                history.append((metric, value))
        history.sort(key=lambda entry: (entry[0].period_end_date, entry[0].financial_year))

        if len(history) < MIN_HISTORICAL_POINTS:
            return {
                "status": "INSUFFICIENT_DATA",
                "company_id": str(company.id),
                "company_symbol": company.symbol,
                "metric_name": metric_name,
                "historical_points": len(history),
                "historical": [
                    {"period": metric.financial_year, "value": value}
                    for metric, value in history
                ],
                "forecasts": [],
                "evaluation": None,
                "disclaimer": ScenarioGenerator.DISCLAIMER,
                "message": (
                    f"Insufficient historical data ({len(history)} annual points). "
                    f"Minimum {MIN_HISTORICAL_POINTS} valid points required for forecasting."
                ),
            }

        history_values = [value for _, value in history]
        last_metric, _ = history[-1]
        last_fy_str = last_metric.financial_year
        year_match = re.fullmatch(r"FY(\d{2,4})", last_fy_str.strip(), re.IGNORECASE)
        if year_match:
            year_number = int(year_match.group(1))
            last_fy_num = year_number if year_number >= 1000 else 2000 + year_number
        elif last_metric.period_end_date:
            last_fy_num = last_metric.period_end_date.year
        else:
            return {
                "status": "INSUFFICIENT_DATA",
                "company_id": str(company.id),
                "company_symbol": company.symbol,
                "metric_name": metric_name,
                "historical_points": len(history),
                "historical": [
                    {"period": metric.financial_year, "value": value}
                    for metric, value in history
                ],
                "forecasts": [],
                "evaluation": None,
                "disclaimer": ScenarioGenerator.DISCLAIMER,
                "message": "The latest financial period could not be interpreted; no forecast was generated.",
            }

        # Fit model and predict
        future_preds, residual_std = self.baseline_model.fit_predict(
            history_values,
            forecast_steps=forecast_horizon_years,
        )

        forecast_periods = []
        for i, pred in enumerate(future_preds):
            target_year = last_fy_num + i + 1
            target_fy = f"FY{target_year % 100:02d}"
            scenarios = ScenarioGenerator.generate_scenarios(
                base_projection=pred,
                residual_std=residual_std,
                horizon_steps=i + 1,
            )
            forecast_periods.append({
                "period": target_fy,
                "base": scenarios["base"],
                "bullish": scenarios["bullish"],
                "bearish": scenarios["bearish"],
                "confidence_intervals": scenarios["confidence_intervals"],
            })

            # Persist to database
            target_date = date(target_year, 3, 31)
            for scen_name, val in [("Base", scenarios["base"]), ("Bullish", scenarios["bullish"]), ("Bearish", scenarios["bearish"])]:
                forecast_record = (
                    db.query(Forecast)
                    .filter(
                        Forecast.company_id == company.id,
                        Forecast.metric_name == metric_name,
                        Forecast.forecast_period == target_fy,
                        Forecast.scenario == scen_name,
                    )
                    .first()
                )
                if forecast_record is None:
                    forecast_record = Forecast(
                        company_id=company.id,
                        metric_name=metric_name,
                        forecast_period=target_fy,
                        scenario=scen_name,
                    )
                    db.add(forecast_record)
                forecast_record.model_type = "Trend_Baseline_v1"
                forecast_record.model_version = "1.0"
                forecast_record.target_date = target_date
                forecast_record.predicted_value = val
                forecast_record.confidence_interval_lower = scenarios["confidence_intervals"]["ci_95"]["lower"]
                forecast_record.confidence_interval_upper = scenarios["confidence_intervals"]["ci_95"]["upper"]
                forecast_record.assumptions = {"residual_std": residual_std, "horizon_step": i + 1}

        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Failed to persist financial forecast")
            raise

        # Compute validation metrics if at least 4 historical points exist
        eval_metrics = None
        if len(history_values) >= 4:
            train_vals = history_values[:-1]
            test_val = history_values[-1]
            val_preds, _ = self.baseline_model.fit_predict(train_vals, forecast_steps=1)
            eval_metrics = ForecastValidator.compute_metrics(
                actual=[test_val],
                predicted=val_preds,
            )

        return {
            "status": "SUCCESS",
            "company_id": str(company.id),
            "company_symbol": company.symbol,
            "metric_name": metric_name,
            "historical": [
                {"period": metric.financial_year, "value": value}
                for metric, value in history
            ],
            "forecasts": forecast_periods,
            "evaluation": eval_metrics,
            "disclaimer": ScenarioGenerator.DISCLAIMER,
        }


forecasting_service = ForecastingService()
