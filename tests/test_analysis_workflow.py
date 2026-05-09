import asyncio
import unittest
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd

from backend import main as api
from data_pipeline.exceptions import DataFetcherError
from models import (
    FactorRegressionResult,
    MLRiskForecastResult,
    MarketRegimeResult,
    OptimizationResult,
    RiskAnomalyResult,
    RiskEvaluationResult,
)


class AnalysisWorkflowTests(unittest.TestCase):
    def test_full_analysis_reuses_single_price_frame_for_optimization(self) -> None:
        price_df = pd.DataFrame(
            {
                "AAA": np.linspace(100.0, 120.0, 120),
                "BBB": np.linspace(80.0, 96.0, 120),
            },
            index=pd.date_range("2026-01-01", periods=120, freq="B"),
        )
        risk_result = RiskEvaluationResult(
            tickers=["AAA", "BBB"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
        )
        alpha_result = FactorRegressionResult(
            alpha=0.001,
            beta_mkt=1.0,
            beta_smb=0.1,
            beta_hml=0.1,
            beta_rmw=0.1,
            beta_cma=0.1,
            t_stat_alpha=1.0,
            t_stat_mkt=1.0,
            t_stat_smb=1.0,
            t_stat_hml=1.0,
            t_stat_rmw=1.0,
            t_stat_cma=1.0,
            p_value_alpha=0.1,
            p_value_mkt=0.1,
            p_value_smb=0.1,
            p_value_hml=0.1,
            p_value_rmw=0.1,
            p_value_cma=0.1,
            r_squared=0.5,
            adj_r_squared=0.4,
            n_observations=100,
        )
        optimization_result = OptimizationResult(
            tickers=["AAA", "BBB"],
            prior_returns=[0.1, 0.1],
            prior_weights=[0.5, 0.5],
            posterior_returns=[0.1, 0.1],
            posterior_weights=[0.5, 0.5],
            risk_aversion=2.5,
        )
        anomaly_result = RiskAnomalyResult(
            anomaly_score=0.1,
            is_anomaly=False,
            alert_level="Low",
        )
        regime_result = MarketRegimeResult(
            current_regime="Normal",
            regime_probabilities={"Normal": 1.0, "High Volatility": 0.0, "Crisis": 0.0},
            volatility_multiplier=1.0,
            correlation_multiplier=1.0,
            recommended_stress_level="Normal",
        )
        ml_result = MLRiskForecastResult(
            ml_var=0.01,
            ml_es=0.012,
            risk_score=20,
            risk_level="Low",
            model_name="test",
            horizon=5,
            confidence_level=0.95,
        )
        payload = api.AnalysisRunRequest(
            tickers=["AAA", "BBB"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )

        def fetch_prices_once(engine, tickers, start_date, end_date, market_mode):
            engine.fetcher._mark_source("cache", "cache (yfinance)")
            return price_df

        helper_calls = []

        def optimize_from_prices(payload, fetcher, passed_price_df, **kwargs):
            helper_calls.append((passed_price_df, kwargs))
            return optimization_result

        with self.assertLogs(api.logger.name, level="INFO") as logs:
            with patch.object(api.RiskEngine, "_fetch_prices", autospec=True, side_effect=fetch_prices_once) as fetch_prices:
                with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                    with patch.object(api.factor_analyzer, "fetch_kf_french_factors", return_value=pd.DataFrame()):
                        with patch.object(api.factor_analyzer, "regress_portfolio", return_value=alpha_result):
                            with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", return_value=anomaly_result):
                                with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", return_value=regime_result):
                                    with patch.object(api.MLRiskEngine, "evaluate_from_prices", return_value=ml_result):
                                        with patch.object(api.analysis_service, "optimize_portfolio_from_prices", side_effect=optimize_from_prices):
                                            result = asyncio.run(api.run_analysis(payload))

        self.assertEqual(fetch_prices.call_count, 1)
        self.assertEqual(len(helper_calls), 1)
        self.assertIs(helper_calls[0][0], price_df)
        self.assertEqual(helper_calls[0][1]["portfolio_source"], "cache")
        self.assertEqual(result.optimization.tickers, ["AAA", "BBB"])
        self.assertTrue(any("analysis run completed" in message for message in logs.output))

    def test_full_analysis_keeps_decision_result_when_alpha_is_unavailable(self) -> None:
        price_df = pd.DataFrame(
            {"AAA": np.linspace(100.0, 120.0, 120)},
            index=pd.date_range("2026-01-01", periods=120, freq="B"),
        )
        risk_result = RiskEvaluationResult(
            tickers=["AAA"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
        )
        optimization_result = OptimizationResult(
            tickers=["AAA"],
            prior_returns=[0.1],
            prior_weights=[1.0],
            posterior_returns=[0.1],
            posterior_weights=[1.0],
            risk_aversion=2.5,
        )
        payload = api.AnalysisRunRequest(
            tickers=["AAA"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )
        alpha_error = DataFetcherError(
            message="real factors unavailable",
            symbol="fama_french_factors",
            source="kenneth_french",
        )

        with patch.object(api.RiskEngine, "_fetch_prices", return_value=price_df):
            with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                with patch.object(api.analysis_service, "run_alpha_from_prices", side_effect=alpha_error):
                    with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                        with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                            with patch.object(api.MLRiskEngine, "evaluate_from_prices", side_effect=ValueError("short sample")):
                                with patch.object(api, "_optimize_portfolio_from_prices", return_value=optimization_result):
                                    result = asyncio.run(api.run_analysis(payload))

        self.assertIsNone(result.alpha)
        self.assertEqual(result.alpha_status, "unavailable")
        self.assertEqual(result.alpha_message, "real factors unavailable")
        self.assertEqual(result.optimization.tickers, ["AAA"])


if __name__ == "__main__":
    unittest.main()
