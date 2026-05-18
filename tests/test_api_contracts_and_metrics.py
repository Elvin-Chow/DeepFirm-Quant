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
from backend.cors import configured_origin_regex, configured_origins
from backend.error_handling import INTERNAL_ERROR_DETAIL
from backend.request_controls import reset_request_limiters
from models import ViewSpec
from models.risk_engine import RiskEngine, RiskEvaluationRequest, RiskEvaluationResult


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

    def test_backtest_uses_market_specific_benchmark_and_risk_free_fallback(self) -> None:
        dates = pd.date_range("2026-01-01", periods=90, freq="B")
        benchmark_df = pd.DataFrame(
            {
                "Date": dates,
                "Close": 100.0 * np.exp(np.linspace(0.00, 0.04, len(dates))),
            }
        )
        market_cases = {
            "us": {
                "tickers": ["AAA", "BBB"],
                "expected_symbol": "SPY",
                "expected_name": "SPDR S&P 500 ETF Trust",
                "expected_risk_free_detail": "Deterministic fallback (2.00% annualized)",
                "expected_warning_fragment": "Risk-free rate",
            },
            "hk": {
                "tickers": ["0005.HK", "0007.HK"],
                "expected_symbol": "^HSI",
                "expected_name": "Hang Seng Index",
                "expected_risk_free_detail": "HKMA 91-day Exchange Fund Bills fallback (2.00% annualized)",
                "expected_warning_fragment": "Hong Kong risk-free rate",
            },
            "cn": {
                "tickers": ["600519", "000001"],
                "expected_symbol": "000300",
                "expected_name": "CSI 300 Index",
                "expected_risk_free_detail": "ChinaBond 3-month government bond yield fallback (2.00% annualized)",
                "expected_warning_fragment": "China A-share risk-free rate",
            },
            "jp": {
                "tickers": ["7203.T", "6758.T"],
                "expected_symbol": "^N225",
                "expected_name": "Nikkei 225",
                "expected_risk_free_detail": "Tokyo Overnight Average Rate proxy fallback (0.75% annualized)",
                "expected_warning_fragment": "Japan risk-free rate",
                "expected_risk_free_rate": 0.0075,
            },
            "tw": {
                "tickers": ["2330.TW", "2317.TW"],
                "expected_symbol": "^TWII",
                "expected_name": "TAIEX",
                "expected_risk_free_detail": "Central Bank of the Republic of China discount rate fallback (2.00% annualized)",
                "expected_warning_fragment": "Taiwan risk-free rate",
            },
        }

        class FakeFetcher:
            last_source = "cache"
            last_source_detail = "cache (test)"
            data_warnings: list[str] = []
            allow_sandbox_data = False

            def fetch_us_equity(self, symbol, start_date, end_date):
                if symbol == "^IRX":
                    raise RuntimeError("risk-free unavailable")
                self.last_source = "benchmark"
                self.last_source_detail = symbol
                return SimpleNamespace(data=benchmark_df)

        def fake_benchmark(fetcher, symbol, start_date, end_date, market):
            fetcher.last_source = "benchmark"
            fetcher.last_source_detail = symbol
            return benchmark_df

        def fake_risk_free(fetcher, requested_rate, asof=None, market="us"):
            config = market_cases[market]
            return (
                config.get("expected_risk_free_rate", 0.02),
                "fallback",
                config["expected_risk_free_detail"],
                [f"{config['expected_warning_fragment']} was unavailable; defaulted for test."],
            )

        for market, config in market_cases.items():
            with self.subTest(market=market):
                tickers = config["tickers"]
                price_df = pd.DataFrame(
                    {
                        tickers[0]: 100.0 * np.exp(np.linspace(0.00, 0.08, len(dates))),
                        tickers[1]: 120.0 * np.exp(np.linspace(0.00, 0.05, len(dates))),
                    },
                    index=dates,
                )
                payload = api.PortfolioOptimizeRequest(
                    tickers=tickers,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 5, 15),
                    weights=[0.5, 0.5],
                    market=market,
                    backtest_enabled=True,
                    risk_free_rate=None,
                    use_market_cap_prior=False,
                )

                with patch.object(
                    api.analysis_service,
                    "fetch_benchmark_prices",
                    side_effect=fake_benchmark,
                ), patch.object(
                    api.analysis_service,
                    "resolve_risk_free_rate",
                    side_effect=fake_risk_free,
                ):
                    result = api.analysis_service.optimize_portfolio_from_prices(
                        payload,
                        FakeFetcher(),
                        price_df,
                        portfolio_source="cache",
                        portfolio_source_detail="cache (test)",
                    )

                self.assertEqual(result.benchmark_symbol, config["expected_symbol"])
                self.assertEqual(result.benchmark_name, config["expected_name"])
                self.assertEqual(result.benchmark_source, "benchmark")
                self.assertEqual(result.benchmark_source_detail, config["expected_symbol"])
                self.assertEqual(result.risk_free_rate_source, "fallback")
                self.assertEqual(
                    result.risk_free_rate_source_detail,
                    config["expected_risk_free_detail"],
                )
                self.assertAlmostEqual(result.risk_free_rate, config.get("expected_risk_free_rate", 0.02))
                self.assertTrue(
                    any(
                        config["expected_warning_fragment"] in warning
                        for warning in result.methodology_warnings
                    )
                )

    def test_risk_evaluation_uses_market_specific_benchmark_and_risk_free_curve(self) -> None:
        dates = pd.date_range("2026-01-01", periods=30, freq="B")
        benchmark_df = pd.DataFrame(
            {
                "Date": dates,
                "Close": 100.0 * np.exp(np.linspace(0.00, 0.03, len(dates))),
            }
        )

        class FakeFetcher:
            last_source = "benchmark"
            last_source_detail = "benchmark detail"
            data_warnings: list[str] = []
            allow_sandbox_data = False

        market_cases = {
            "hk": {
                "tickers": ["0005.HK", "0007.HK"],
                "expected_symbol": "^HSI",
                "expected_name": "Hang Seng Index",
                "expected_risk_free_symbol": "HKMA_EFB_91D",
                "expected_risk_free_name": "HKD 91D EFB",
                "risk_free_source": "hkma",
                "risk_free_detail": "HKMA 91-day Exchange Fund Bills yield",
            },
            "cn": {
                "tickers": ["600519", "000001"],
                "expected_symbol": "000300",
                "expected_name": "CSI 300 Index",
                "expected_risk_free_symbol": "CHINABOND_CGB_3M",
                "expected_risk_free_name": "CNY 3M CGB",
                "risk_free_source": "chinabond",
                "risk_free_detail": "ChinaBond 3-month government bond yield",
            },
            "tw": {
                "tickers": ["2330.TW", "2317.TW"],
                "expected_symbol": "^TWII",
                "expected_name": "TAIEX",
                "expected_risk_free_symbol": "CBC_DISCOUNT_RATE",
                "expected_risk_free_name": "TWD policy rate",
                "risk_free_source": "fallback",
                "risk_free_detail": "Central Bank of the Republic of China discount rate fallback (2.00% annualized)",
            },
        }

        def fake_benchmark(fetcher, symbol, start_date, end_date, market):
            fetcher.last_source = "benchmark"
            fetcher.last_source_detail = symbol
            return benchmark_df

        def fake_risk_free(fetcher, requested_rate, asof=None, market="us"):
            config = market_cases[market]
            return 0.02, config["risk_free_source"], config["risk_free_detail"], []

        for market, config in market_cases.items():
            with self.subTest(market=market):
                tickers = config["tickers"]
                price_df = pd.DataFrame(
                    {
                        tickers[0]: 100.0 * np.exp(np.linspace(0.00, 0.05, len(dates))),
                        tickers[1]: 100.0 * np.exp(np.linspace(0.00, 0.02, len(dates))),
                    },
                    index=dates,
                )
                request = RiskEvaluationRequest(
                    tickers=tickers,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 2, 15),
                    weights=[0.5, 0.5],
                    market=market,
                )
                result = RiskEvaluationResult(
                    tickers=tickers,
                    historical_es=-0.01,
                    monte_carlo_es=-0.01,
                    confidence_level=0.99,
                    cumulative_returns=[0.0] * (len(dates) - 1),
                    performance_dates=dates[1:].strftime("%Y-%m-%d").tolist(),
                )

                with patch.object(
                    api.analysis_service,
                    "make_fetcher",
                    side_effect=lambda api_key, allow_sandbox_data: FakeFetcher(),
                ), patch.object(
                    api.analysis_service,
                    "fetch_benchmark_prices",
                    side_effect=fake_benchmark,
                ), patch.object(
                    api.analysis_service,
                    "resolve_risk_free_rate",
                    side_effect=fake_risk_free,
                ):
                    api.analysis_service.attach_risk_benchmark(result, request, price_df)

                self.assertEqual(result.benchmark_symbol, config["expected_symbol"])
                self.assertEqual(result.benchmark_name, config["expected_name"])
                self.assertEqual(result.benchmark_source_detail, config["expected_symbol"])
                self.assertGreater(len(result.benchmark_cumulative_returns), 0)
                self.assertEqual(result.risk_free_symbol, config["expected_risk_free_symbol"])
                self.assertEqual(result.risk_free_name, config["expected_risk_free_name"])
                self.assertEqual(result.risk_free_source, config["risk_free_source"])
                self.assertEqual(result.risk_free_source_detail, config["risk_free_detail"])
                self.assertEqual(len(result.risk_free_cumulative_returns), len(dates) - 1)

    def test_hk_benchmark_fetch_uses_hk_equity_path(self) -> None:
        dates = pd.date_range("2026-01-01", periods=3, freq="B")

        class FakeFetcher:
            called_hk = False

            def fetch_hk_equity(self, symbol, start_date, end_date):
                self.called_hk = True
                return SimpleNamespace(data=pd.DataFrame({"Date": dates, "Close": [100.0, 101.0, 102.0]}))

            def fetch_us_equity(self, symbol, start_date, end_date):
                raise AssertionError("HK benchmark must not use the US equity path")

        fetcher = FakeFetcher()

        df = api.analysis_service.fetch_benchmark_prices(
            fetcher,
            "^HSI",
            date(2026, 1, 1),
            date(2026, 1, 5),
            "hk",
        )

        self.assertTrue(fetcher.called_hk)
        self.assertEqual(list(df.columns), ["Date", "Close"])


class CorsContractTests(unittest.TestCase):
    def test_origin_allow_list_disables_default_regex(self) -> None:
        with patch.dict(os.environ, {"ALLOW_ORIGINS": "https://risk.example.com"}, clear=True):
            self.assertIsNone(configured_origin_regex())

    def test_hosted_environment_requires_allow_origins(self) -> None:
        with patch.dict(os.environ, {"VERCEL": "1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ALLOW_ORIGINS"):
                configured_origins()

    def test_hosted_environment_allow_list_stays_strict(self) -> None:
        with patch.dict(
            os.environ,
            {"VERCEL": "1", "ALLOW_ORIGINS": "https://risk.example.com"},
            clear=True,
        ):
            self.assertEqual(configured_origins(), ["https://risk.example.com"])
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
        self.assertTrue(response.json().get("request_id"))

    def test_internal_error_response_is_redacted_with_request_id(self) -> None:
        reset_request_limiters()
        request_id = "test-request-id"

        with patch.object(api.analysis_service, "run_analysis", side_effect=RuntimeError("internal secret")):
            response = TestClient(api.app).post(
                "/api/v1/analysis/run",
                headers={"X-Request-ID": request_id},
                json={
                    "tickers": ["AAA", "BBB"],
                    "start_date": "2026-01-01",
                    "end_date": "2026-06-30",
                    "weights": [0.5, 0.5],
                },
            )

        body = response.json()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(body["detail"], INTERNAL_ERROR_DETAIL)
        self.assertEqual(body["request_id"], request_id)
        self.assertEqual(response.headers.get("X-Request-ID"), request_id)
        self.assertNotIn("internal secret", str(body))

    def test_request_body_limit_returns_request_id(self) -> None:
        reset_request_limiters()
        request_id = "oversize-request-id"

        with patch.dict(os.environ, {"DFQ_MAX_BODY_BYTES": "20"}, clear=False):
            response = TestClient(api.app).post(
                "/api/v1/analysis/run",
                headers={"X-Request-ID": request_id},
                json={"payload": "x" * 100},
            )

        body = response.json()
        self.assertEqual(response.status_code, 413)
        self.assertEqual(body["request_id"], request_id)
        self.assertEqual(response.headers.get("X-Request-ID"), request_id)

    def test_rate_limit_returns_429_with_request_id(self) -> None:
        reset_request_limiters()
        request_id = "rate-limit-request-id"
        client = TestClient(api.app)

        with patch.dict(os.environ, {"DFQ_RATE_LIMIT_PER_MINUTE": "1"}, clear=False):
            first = client.post(
                "/api/v1/analysis/run",
                headers={"X-Forwarded-For": "203.0.113.1"},
                json={},
            )
            second = client.post(
                "/api/v1/analysis/run",
                headers={
                    "X-Forwarded-For": "203.0.113.1",
                    "X-Request-ID": request_id,
                },
                json={},
            )

        self.assertEqual(first.status_code, 422)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["request_id"], request_id)
        self.assertEqual(second.headers.get("X-Request-ID"), request_id)

    def test_hosted_entrypoint_allows_vercel_preflight(self) -> None:
        origin = "https://deep-firm-quant.vercel.app"
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
        origin = "https://deep-firm-quant.vercel.app"
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

    def test_full_api_root_probe_is_available(self) -> None:
        response = TestClient(api.app).get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_analysis_parallelism_is_opt_in(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(api.analysis_service.parallel_analysis_enabled())

        with patch.dict(os.environ, {"DFQ_ANALYSIS_PARALLEL": "true"}, clear=True):
            self.assertTrue(api.analysis_service.parallel_analysis_enabled())

if __name__ == "__main__":
    unittest.main()
