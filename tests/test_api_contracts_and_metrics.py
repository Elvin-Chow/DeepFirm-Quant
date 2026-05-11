import unittest
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
from pydantic import ValidationError

from backend import main as api
from models import ViewSpec
from models.risk_engine import RiskEngine


class PerformanceMetricTests(unittest.TestCase):
    def test_performance_metrics_use_log_return_compounding(self) -> None:
        returns_df = pd.DataFrame(
            {"strategy": [np.log(1.10), np.log(0.90)]},
            index=pd.date_range("2026-01-02", periods=2, freq="B"),
        )

        metrics = RiskEngine.compute_performance_metrics(returns_df, np.array([1.0]))

        self.assertAlmostEqual(metrics["cumulative_returns"][0], 0.10, places=10)
        self.assertAlmostEqual(metrics["cumulative_returns"][1], -0.01, places=10)
        self.assertAlmostEqual(metrics["max_drawdown"], -0.10, places=10)


class ApiContractTests(unittest.TestCase):
    def test_duplicate_tickers_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            api.AnalysisRunRequest(
                tickers=["AAA", "aaa"],
                start_date=date(2026, 1, 1),
                end_date=date(2026, 6, 30),
            )

    def test_weight_length_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            api.AnalysisRunRequest(
                tickers=["AAA", "BBB"],
                start_date=date(2026, 1, 1),
                end_date=date(2026, 6, 30),
                weights=[1.0],
            )

    def test_unknown_view_asset_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            api.PortfolioOptimizeRequest(
                tickers=["AAA"],
                start_date=date(2026, 1, 1),
                end_date=date(2026, 6, 30),
                views=[ViewSpec(assets=["BBB"], expected_return=0.05)],
            )

    def test_mixed_backtest_exposes_benchmark_and_risk_free_fallback(self) -> None:
        dates = pd.date_range("2026-01-01", periods=90, freq="B")
        price_df = pd.DataFrame(
            {
                "AAA": 100.0 * np.exp(np.linspace(0.00, 0.08, len(dates))),
                "BBB": 120.0 * np.exp(np.linspace(0.00, 0.05, len(dates))),
            },
            index=dates,
        )
        benchmark_df = pd.DataFrame(
            {
                "Date": dates,
                "Close": 100.0 * np.exp(np.linspace(0.00, 0.04, len(dates))),
            }
        )

        class FakeFetcher:
            last_source = "cache"
            last_source_detail = "cache (test)"
            data_warnings: list[str] = []

            def fetch_us_equity(self, symbol, start_date, end_date):
                if symbol == "^IRX":
                    raise RuntimeError("risk-free unavailable")
                self.last_source = "benchmark"
                self.last_source_detail = symbol
                return SimpleNamespace(data=benchmark_df)

        payload = api.PortfolioOptimizeRequest(
            tickers=["AAA", "BBB"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 15),
            weights=[0.5, 0.5],
            market="mixed",
            backtest_enabled=True,
            risk_free_rate=None,
            use_market_cap_prior=False,
        )

        result = api.analysis_service.optimize_portfolio_from_prices(
            payload,
            FakeFetcher(),
            price_df,
            portfolio_source="cache",
            portfolio_source_detail="cache (test)",
        )

        self.assertEqual(result.benchmark_symbol, "ACWI")
        self.assertEqual(result.benchmark_name, "iShares MSCI ACWI ETF")
        self.assertEqual(result.benchmark_source, "benchmark")
        self.assertEqual(result.benchmark_source_detail, "ACWI")
        self.assertEqual(result.risk_free_rate_source, "fallback")
        self.assertEqual(
            result.risk_free_rate_source_detail,
            "Deterministic fallback (2.00% annualized)",
        )
        self.assertAlmostEqual(result.risk_free_rate, 0.02)
        self.assertTrue(any("Risk-free rate" in warning for warning in result.methodology_warnings))


if __name__ == "__main__":
    unittest.main()
