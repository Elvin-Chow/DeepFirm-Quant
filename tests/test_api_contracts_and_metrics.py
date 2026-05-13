import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from pydantic import ValidationError

import backend.app as hosted_entrypoint
from backend import main as api
from backend.cors import configured_origin_regex
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


class CorsContractTests(unittest.TestCase):
    def test_origin_allow_list_disables_default_regex(self) -> None:
        with patch.dict(os.environ, {"ALLOW_ORIGINS": "https://risk.example.com"}, clear=True):
            self.assertIsNone(configured_origin_regex())

    def test_hosted_root_probe_does_not_import_full_backend(self) -> None:
        with patch("backend.app._load_backend_app") as load_backend:
            response = TestClient(hosted_entrypoint.app).get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        load_backend.assert_not_called()

    def test_hosted_root_head_probe_does_not_import_full_backend(self) -> None:
        with patch("backend.app._load_backend_app") as load_backend:
            response = TestClient(hosted_entrypoint.app).head("/")

        self.assertEqual(response.status_code, 200)
        load_backend.assert_not_called()

    def test_hosted_entrypoint_routes_analysis_requests(self) -> None:
        response = TestClient(hosted_entrypoint.app).post("/api/v1/analysis/run", json={})

        self.assertEqual(response.status_code, 422)
        self.assertIsInstance(response.json().get("detail"), list)

    def test_hosted_entrypoint_allows_vercel_preflight(self) -> None:
        origin = "https://deepfirm-quant.vercel.app"
        response = TestClient(hosted_entrypoint.app).options(
            "/api/v1/analysis/run",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), origin)

    def test_hosted_entrypoint_allows_hugging_face_space_preflight(self) -> None:
        origin = "https://deepfirm-quant.hf.space"
        response = TestClient(hosted_entrypoint.app).options(
            "/api/v1/analysis/run",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), origin)

    def test_full_api_allows_vercel_preflight(self) -> None:
        origin = "https://deepfirm-quant.vercel.app"
        response = TestClient(api.app).options(
            "/api/v1/analysis/run",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), origin)

<<<<<<< HEAD
    def test_full_api_allows_hugging_face_space_preflight(self) -> None:
        origin = "https://deepfirm-quant.hf.space"
        response = TestClient(api.app).options(
            "/api/v1/analysis/run",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), origin)

=======
>>>>>>> bf824594f0ee281f7b2803614cc4f972e3834fd6
    def test_full_api_root_probe_is_available(self) -> None:
        response = TestClient(api.app).get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

<<<<<<< HEAD
    def test_analysis_parallelism_is_opt_in(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(api.analysis_service.parallel_analysis_enabled())

        with patch.dict(os.environ, {"DFQ_ANALYSIS_PARALLEL": "true"}, clear=True):
            self.assertTrue(api.analysis_service.parallel_analysis_enabled())

=======
>>>>>>> bf824594f0ee281f7b2803614cc4f972e3834fd6

if __name__ == "__main__":
    unittest.main()
