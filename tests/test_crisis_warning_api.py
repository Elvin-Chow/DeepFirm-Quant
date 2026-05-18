import asyncio
import unittest
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
from pydantic import ValidationError

from backend import main as api
from models import (
    CrisisWarningDiagnostics,
    CrisisWarningDriver,
    CrisisWarningResult,
    CrisisWarningUnavailableError,
    OptimizationResult,
    RiskEvaluationResult,
)


def make_price_frame(rows: int = 140) -> pd.DataFrame:
    dates = pd.date_range("2026-01-05", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "AAA": 100.0 * np.exp(np.linspace(0.0, 0.08, rows)),
            "BBB": 90.0 * np.exp(np.linspace(0.0, 0.05, rows)),
        },
        index=dates,
    )


def make_crisis_result() -> CrisisWarningResult:
    return CrisisWarningResult(
        crisis_probability=0.67,
        warning_level="High",
        model_name="XGBClassifier",
        model_version="test-version",
        horizon=5,
        target_definition="Future 5D portfolio log return below trailing 5% threshold.",
        base_value=0.22,
        top_risk_drivers=[
            CrisisWarningDriver(
                feature="rolling_volatility_20d",
                feature_value=0.03,
                shap_value=0.11,
                direction="increase_risk",
            )
        ],
        risk_reducers=[],
        explanation="Test crisis warning.",
        diagnostics=CrisisWarningDiagnostics(
            model_health="ok",
            training_market_scope=["us", "hk", "cn", "jp", "tw"],
            required_market_scope=["us", "hk", "cn", "jp", "tw"],
            covered_market_scope=["us", "hk", "cn", "jp", "tw"],
            skipped_market_scope=[],
            is_global_complete=True,
            artifact_hash="a" * 64,
            feature_schema_hash="b" * 64,
            validation_status="ok",
            probability_calibrated=False,
            shap_fallback_used=False,
        ),
        source="test",
        source_detail="test detail",
    )


class CrisisWarningApiTests(unittest.TestCase):
    def test_endpoint_returns_crisis_warning(self) -> None:
        payload = api.CrisisWarningRequest(
            tickers=["AAA", "BBB"],
            weights=[0.5, 0.5],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            horizon=5,
        )

        with patch.object(api.crisis_warning_service, "evaluate", return_value=make_crisis_result()):
            result = asyncio.run(api.crisis_warning(payload))

        self.assertEqual(result.warning_level, "High")
        self.assertEqual(result.top_risk_drivers[0].direction, "increase_risk")
        diagnostics = result.model_dump()["diagnostics"]
        self.assertEqual(
            diagnostics["training_market_scope"],
            ["us", "hk", "cn", "jp", "tw"],
        )
        self.assertEqual(
            diagnostics["required_market_scope"],
            ["us", "hk", "cn", "jp", "tw"],
        )
        self.assertEqual(
            diagnostics["covered_market_scope"],
            ["us", "hk", "cn", "jp", "tw"],
        )
        self.assertEqual(diagnostics["skipped_market_scope"], [])
        self.assertTrue(diagnostics["is_global_complete"])
        self.assertEqual(diagnostics["artifact_hash"], "a" * 64)
        self.assertEqual(diagnostics["feature_schema_hash"], "b" * 64)
        self.assertEqual(diagnostics["validation_status"], "ok")

    def test_endpoint_artifact_missing_returns_503_before_fetch(self) -> None:
        payload = api.CrisisWarningRequest(
            tickers=["AAA", "BBB"],
            weights=[0.5, 0.5],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            horizon=5,
        )

        with patch.object(api.crisis_warning_service.store, "get", side_effect=CrisisWarningUnavailableError("missing artifact")):
            with patch.object(api.RiskEngine, "_fetch_prices") as fetch_prices:
                with self.assertRaises(api.HTTPException) as raised:
                    asyncio.run(api.crisis_warning(payload))

        self.assertEqual(raised.exception.status_code, 503)
        fetch_prices.assert_not_called()

    def test_invalid_horizon_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            api.CrisisWarningRequest(
                tickers=["AAA", "BBB"],
                weights=[0.5, 0.5],
                start_date=date(2026, 1, 1),
                end_date=date(2026, 6, 30),
                horizon=2,
            )

    def test_analysis_run_can_return_crisis_warning(self) -> None:
        price_df = make_price_frame()
        risk_result = RiskEvaluationResult(
            tickers=["AAA", "BBB"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
        )
        optimization_result = OptimizationResult(
            tickers=["AAA", "BBB"],
            prior_returns=[0.1, 0.1],
            prior_weights=[0.5, 0.5],
            posterior_returns=[0.1, 0.1],
            posterior_weights=[0.5, 0.5],
            risk_aversion=2.5,
        )
        payload = api.AnalysisRunRequest(
            tickers=["AAA", "BBB"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            weights=[0.5, 0.5],
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )

        def fetch_prices_once(engine, tickers, start_date, end_date, market_mode):
            engine.fetcher._mark_source("cache", "cache (test)")
            return price_df

        with patch.object(api.RiskEngine, "_fetch_prices", autospec=True, side_effect=fetch_prices_once) as fetch_prices:
            with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                with patch.object(api.analysis_service, "run_alpha_from_prices", side_effect=ValueError("alpha unavailable")):
                    with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                        with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                            with patch.object(api.MLRiskEngine, "evaluate_from_prices", side_effect=ValueError("short sample")):
                                with patch.object(api.analysis_service.crisis_warning_service, "evaluate_from_prices", return_value=make_crisis_result()) as crisis_eval:
                                    with patch.object(api.analysis_service, "optimize_portfolio_from_prices", return_value=optimization_result):
                                        result = asyncio.run(api.run_analysis(payload))

        self.assertEqual(fetch_prices.call_count, 1)
        crisis_eval.assert_called_once()
        self.assertIsNotNone(result.crisis_warning)
        self.assertEqual(result.crisis_warning.warning_level, "High")

    def test_analysis_run_requires_crisis_warning_success(self) -> None:
        price_df = make_price_frame()
        risk_result = RiskEvaluationResult(
            tickers=["AAA", "BBB"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
        )
        optimization_result = OptimizationResult(
            tickers=["AAA", "BBB"],
            prior_returns=[0.1, 0.1],
            prior_weights=[0.5, 0.5],
            posterior_returns=[0.1, 0.1],
            posterior_weights=[0.5, 0.5],
            risk_aversion=2.5,
        )
        payload = api.AnalysisRunRequest(
            tickers=["AAA", "BBB"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            weights=[0.5, 0.5],
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )

        with patch.object(api.RiskEngine, "_fetch_prices", return_value=price_df):
            with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                with patch.object(api.analysis_service, "run_alpha_from_prices", side_effect=ValueError("alpha unavailable")):
                    with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                        with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                            with patch.object(api.MLRiskEngine, "evaluate_from_prices", side_effect=ValueError("short sample")):
                                with patch.object(api.analysis_service.crisis_warning_service, "evaluate_from_prices", side_effect=ValueError("missing feature")):
                                    with patch.object(api.analysis_service, "optimize_portfolio_from_prices", return_value=optimization_result) as optimize:
                                        with self.assertRaises(api.HTTPException) as raised:
                                            asyncio.run(api.run_analysis(payload))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("missing feature", str(raised.exception.detail))
        optimize.assert_not_called()

    def test_analysis_run_skips_crisis_when_disabled(self) -> None:
        price_df = make_price_frame()
        risk_result = RiskEvaluationResult(
            tickers=["AAA", "BBB"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
        )
        optimization_result = OptimizationResult(
            tickers=["AAA", "BBB"],
            prior_returns=[0.1, 0.1],
            prior_weights=[0.5, 0.5],
            posterior_returns=[0.1, 0.1],
            posterior_weights=[0.5, 0.5],
            risk_aversion=2.5,
        )
        payload = api.AnalysisRunRequest(
            tickers=["AAA", "BBB"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            weights=[0.5, 0.5],
            risk_free_rate=0.0,
            use_market_cap_prior=False,
            crisis_enabled=False,
        )

        with patch.object(api.RiskEngine, "_fetch_prices", return_value=price_df):
            with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                with patch.object(api.analysis_service, "run_alpha_from_prices", side_effect=ValueError("alpha unavailable")):
                    with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                        with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                            with patch.object(api.MLRiskEngine, "evaluate_from_prices", side_effect=ValueError("short sample")):
                                with patch.object(api.analysis_service.crisis_warning_service, "evaluate_from_prices") as crisis_eval:
                                    with patch.object(api.analysis_service, "optimize_portfolio_from_prices", return_value=optimization_result):
                                        result = asyncio.run(api.run_analysis(payload))

        crisis_eval.assert_not_called()
        self.assertIsNone(result.crisis_warning)


if __name__ == "__main__":
    unittest.main()
