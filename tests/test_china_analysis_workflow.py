import asyncio
import time
import unittest
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from backend import main as api
from backend.services import ALPHA_UNSUPPORTED_MARKET_MESSAGES, PortfolioAnalysisService
from data_pipeline.fetcher import SmartFetcher
from models import OptimizationResult, RiskEvaluationResult


def make_price_frame(rows: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2026-01-05", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "600519": 100.0 * np.exp(np.linspace(0.0, 0.18, rows)),
            "300750": 80.0 * np.exp(np.linspace(0.0, 0.11, rows)),
        },
        index=dates,
    )


def make_benchmark_frame(rows: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2026-01-05", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "日期": dates.strftime("%Y-%m-%d"),
            "收盘": 100.0 * np.exp(np.linspace(0.0, 0.09, rows)),
        }
    )


class FakeOOSFetcher:
    def __init__(self) -> None:
        self.last_source = "akshare"
        self.last_source_detail = "AKShare A-share daily qfq"
        self.data_warnings: list[str] = []
        self.us_calls = 0
        self.yahoo_symbol = ""

    def _mark_source(self, source: str, detail: str) -> None:
        self.last_source = source
        self.last_source_detail = detail

    def fetch_us_equity(self, symbol, start_date, end_date):
        self.us_calls += 1
        raise AssertionError("CN benchmark and risk-free fallback must not call US equity fetch")

    def _fetch_yahoo_chart(self, symbol, start_date, end_date):
        self.yahoo_symbol = symbol
        return pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-05", periods=120, freq="B"),
                "Close": 100.0 * np.exp(np.linspace(0.0, 0.09, 120)),
            }
        )

    def _append_warning(self, message: str) -> None:
        if message not in self.data_warnings:
            self.data_warnings.append(message)

    def is_china_akshare_cooling_down(self) -> bool:
        return False

    def _register_china_akshare_failure(self) -> None:
        return None

    def _fetch_sandbox(self, symbol, start_date, end_date):
        dates = pd.date_range(start_date, end_date, freq="B")
        return pd.DataFrame({"Date": dates, "Close": np.linspace(100.0, 110.0, len(dates))})


class ChinaAnalysisWorkflowTests(unittest.TestCase):
    def test_jp_risk_comparison_uses_nikkei_and_tona_proxy(self) -> None:
        service = PortfolioAnalysisService()
        dates = pd.date_range("2026-01-05", periods=40, freq="B")
        price_df = pd.DataFrame(
            {"7203.T": 100.0 * np.exp(np.linspace(0.0, 0.08, len(dates)))},
            index=dates,
        )
        benchmark_df = pd.DataFrame(
            {
                "Date": dates,
                "Close": 100.0 * np.exp(np.linspace(0.0, 0.05, len(dates))),
            }
        )
        request = api.RiskEvaluationRequest(
            tickers=["7203.T"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            weights=[1.0],
            market="jp",
        )
        result = RiskEvaluationResult(
            tickers=["7203.T"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
            source="yahoo_chart",
            source_detail="Yahoo Finance chart API",
        )

        class FakeBenchmarkFetcher:
            last_source = "cache"
            last_source_detail = "cache (test)"
            data_warnings: list[str] = []

        def fake_fetch_benchmark(fetcher, symbol, start_date, end_date, market):
            self.assertEqual(symbol, "^N225")
            self.assertEqual(market, "jp")
            fetcher.last_source = "yahoo_chart"
            fetcher.last_source_detail = "Yahoo Finance chart API"
            return benchmark_df

        with patch.object(service, "make_fetcher", return_value=FakeBenchmarkFetcher()):
            with patch.object(service, "fetch_benchmark_prices", side_effect=fake_fetch_benchmark):
                service.attach_risk_benchmark(result, request, price_df)

        self.assertEqual(result.benchmark_symbol, "^N225")
        self.assertEqual(result.benchmark_name, "Nikkei 225")
        self.assertEqual(result.risk_free_symbol, "TONA")
        self.assertEqual(result.risk_free_name, "JPY RFR")
        self.assertEqual(result.risk_free_source, "fallback")
        self.assertEqual(
            result.risk_free_source_detail,
            "Tokyo Overnight Average Rate proxy fallback (0.75% annualized)",
        )
        self.assertTrue(any("Japan risk-free rate" in warning for warning in result.data_warnings))

    def test_tw_risk_comparison_uses_taiex_and_twd_policy_proxy(self) -> None:
        service = PortfolioAnalysisService()
        dates = pd.date_range("2026-01-05", periods=40, freq="B")
        price_df = pd.DataFrame(
            {"2330.TW": 100.0 * np.exp(np.linspace(0.0, 0.08, len(dates)))},
            index=dates,
        )
        benchmark_df = pd.DataFrame(
            {
                "Date": dates,
                "Close": 100.0 * np.exp(np.linspace(0.0, 0.05, len(dates))),
            }
        )
        request = api.RiskEvaluationRequest(
            tickers=["2330.TW"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            weights=[1.0],
            market="tw",
        )
        result = RiskEvaluationResult(
            tickers=["2330.TW"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
            source="yahoo_chart",
            source_detail="Yahoo Finance chart API",
        )

        class FakeBenchmarkFetcher:
            last_source = "cache"
            last_source_detail = "cache (test)"
            data_warnings: list[str] = []

        def fake_fetch_benchmark(fetcher, symbol, start_date, end_date, market):
            self.assertEqual(symbol, "^TWII")
            self.assertEqual(market, "tw")
            fetcher.last_source = "yahoo_chart"
            fetcher.last_source_detail = "Yahoo Finance chart API"
            return benchmark_df

        with patch.object(service, "make_fetcher", return_value=FakeBenchmarkFetcher()):
            with patch.object(service, "fetch_benchmark_prices", side_effect=fake_fetch_benchmark):
                service.attach_risk_benchmark(result, request, price_df)

        self.assertEqual(result.benchmark_symbol, "^TWII")
        self.assertEqual(result.benchmark_name, "TAIEX")
        self.assertEqual(result.risk_free_symbol, "CBC_DISCOUNT_RATE")
        self.assertEqual(result.risk_free_name, "TWD policy rate")
        self.assertEqual(result.risk_free_source, "fallback")
        self.assertEqual(
            result.risk_free_source_detail,
            "Central Bank of the Republic of China discount rate fallback (2.00% annualized)",
        )
        self.assertTrue(any("Taiwan risk-free rate" in warning for warning in result.data_warnings))

    def test_cn_oos_uses_csi300_benchmark_and_inverse_vol_prior_warning(self) -> None:
        service = PortfolioAnalysisService()
        fetcher = FakeOOSFetcher()
        price_df = make_price_frame()
        payload = api.PortfolioOptimizeRequest(
            tickers=["600519", "300750"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 31),
            weights=[0.5, 0.5],
            market="cn",
            backtest_enabled=True,
            test_ratio=0.30,
            risk_free_rate=None,
            use_market_cap_prior=True,
        )

        with patch.object(
            service,
            "fetch_cn_risk_free_rate",
            side_effect=RuntimeError("risk-free unavailable"),
        ), patch("backend.services.ak.index_zh_a_hist", return_value=make_benchmark_frame()) as index_hist:
            result = service.optimize_portfolio_from_prices(
                payload,
                fetcher,
                price_df,
                portfolio_source="akshare",
                portfolio_source_detail="AKShare A-share daily qfq",
            )

        index_hist.assert_called_once()
        self.assertEqual(fetcher.us_calls, 0)
        self.assertEqual(result.benchmark_symbol, "000300")
        self.assertEqual(result.benchmark_name, "CSI 300 Index")
        self.assertEqual(result.benchmark_source, "akshare")
        self.assertEqual(result.benchmark_source_detail, "AKShare CSI 300 index daily")
        self.assertEqual(result.risk_free_rate_source, "fallback")
        self.assertEqual(
            result.risk_free_rate_source_detail,
            "ChinaBond 3-month government bond yield fallback (2.00% annualized)",
        )
        self.assertAlmostEqual(result.risk_free_rate, 0.02)
        self.assertTrue(
            any("China A-share risk-free rate" in warning for warning in result.methodology_warnings)
        )
        self.assertTrue(
            any("CSI 300" in warning for warning in result.methodology_warnings)
        )
        self.assertTrue(
            any("China A-share market-cap prior" in warning for warning in result.methodology_warnings)
        )

    def test_cn_benchmark_falls_back_to_yahoo_when_akshare_disconnects(self) -> None:
        service = PortfolioAnalysisService()
        fetcher = FakeOOSFetcher()

        with patch(
            "backend.services.ak.index_zh_a_hist",
            side_effect=requests.ConnectionError("remote closed"),
        ):
            prices = service.fetch_benchmark_prices(
                fetcher,
                "000300",
                date(2026, 1, 1),
                date(2026, 7, 31),
                "cn",
            )

        self.assertEqual(fetcher.us_calls, 0)
        self.assertEqual(fetcher.yahoo_symbol, "000300.SS")
        self.assertEqual(fetcher.last_source, "yahoo_chart")
        self.assertIn("CSI 300 fallback", fetcher.last_source_detail)
        self.assertTrue(any("AKShare benchmark" in warning for warning in fetcher.data_warnings))
        self.assertEqual(list(prices.columns), ["Date", "Close"])

    def test_cn_benchmark_falls_back_to_yahoo_when_akshare_times_out(self) -> None:
        service = PortfolioAnalysisService()
        fetcher = FakeOOSFetcher()

        def slow_index_call(*args, **kwargs):
            time.sleep(0.05)
            return make_benchmark_frame()

        with patch("backend.services.ak.index_zh_a_hist", side_effect=slow_index_call) as index_hist:
            with patch.object(SmartFetcher, "_akshare_timeout_seconds", return_value=0.01):
                prices = service.fetch_benchmark_prices(
                    fetcher,
                    "000300",
                    date(2026, 1, 1),
                    date(2026, 7, 31),
                    "cn",
                )

        index_hist.assert_called_once()
        self.assertEqual(fetcher.us_calls, 0)
        self.assertEqual(fetcher.yahoo_symbol, "000300.SS")
        self.assertEqual(fetcher.last_source, "yahoo_chart")
        self.assertIn("CSI 300 fallback", fetcher.last_source_detail)
        self.assertTrue(any("AKShare benchmark" in warning for warning in fetcher.data_warnings))
        self.assertEqual(list(prices.columns), ["Date", "Close"])

    def test_hk_full_analysis_marks_alpha_unavailable_without_factor_call(self) -> None:
        dates = pd.date_range("2026-01-05", periods=90, freq="B")
        price_df = pd.DataFrame(
            {"0005.HK": 100.0 * np.exp(np.linspace(0.0, 0.12, len(dates)))},
            index=dates,
        )
        risk_result = RiskEvaluationResult(
            tickers=["0005.HK"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
            source="yahoo_chart",
            source_detail="Yahoo Finance chart API",
        )
        optimization_result = OptimizationResult(
            tickers=["0005.HK"],
            prior_returns=[0.1],
            prior_weights=[1.0],
            posterior_returns=[0.1],
            posterior_weights=[1.0],
            risk_aversion=2.5,
        )
        payload = api.AnalysisRunRequest(
            tickers=["0005.HK"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            weights=[1.0],
            market="hk",
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )

        def fetch_prices_once(engine, tickers, start_date, end_date, market_mode):
            engine.fetcher._mark_source("yahoo_chart", "Yahoo Finance chart API")
            return price_df

        with patch.object(api.RiskEngine, "_fetch_prices", autospec=True, side_effect=fetch_prices_once):
            with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                with patch.object(api.analysis_service, "run_alpha_from_prices") as run_alpha:
                    with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                        with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                            with patch.object(api.MLRiskEngine, "evaluate_from_prices", side_effect=ValueError("short sample")):
                                with patch.object(api.analysis_service, "optimize_portfolio_from_prices", return_value=optimization_result):
                                    result = asyncio.run(api.run_analysis(payload))

        run_alpha.assert_not_called()
        self.assertIsNone(result.alpha)
        self.assertEqual(result.alpha_status, "unavailable")
        self.assertEqual(
            result.alpha_message,
            ALPHA_UNSUPPORTED_MARKET_MESSAGES["hk"],
        )
        self.assertEqual(result.optimization.tickers, ["0005.HK"])

    def test_hk_alpha_endpoint_rejects_non_local_factor_attribution(self) -> None:
        payload = api.AlphaAnalysisRequest(
            tickers=["0005.HK"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="hk",
        )

        with self.assertRaises(api.HTTPException) as context:
            asyncio.run(api.fama_french_alpha(payload))

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, ALPHA_UNSUPPORTED_MARKET_MESSAGES["hk"])

    def test_cn_full_analysis_marks_alpha_unavailable_without_factor_call(self) -> None:
        price_df = make_price_frame(rows=90)[["600519"]]
        risk_result = RiskEvaluationResult(
            tickers=["600519"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
            source="akshare",
            source_detail="AKShare A-share daily qfq",
        )
        optimization_result = OptimizationResult(
            tickers=["600519"],
            prior_returns=[0.1],
            prior_weights=[1.0],
            posterior_returns=[0.1],
            posterior_weights=[1.0],
            risk_aversion=2.5,
        )
        payload = api.AnalysisRunRequest(
            tickers=["600519"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            weights=[1.0],
            market="cn",
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )

        def fetch_prices_once(engine, tickers, start_date, end_date, market_mode):
            engine.fetcher._mark_source("akshare", "AKShare A-share daily qfq")
            return price_df

        with patch.object(api.RiskEngine, "_fetch_prices", autospec=True, side_effect=fetch_prices_once):
            with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                with patch.object(api.analysis_service, "run_alpha_from_prices") as run_alpha:
                    with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                        with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                            with patch.object(api.MLRiskEngine, "evaluate_from_prices", side_effect=ValueError("short sample")):
                                with patch.object(api.analysis_service, "optimize_portfolio_from_prices", return_value=optimization_result):
                                    result = asyncio.run(api.run_analysis(payload))

        run_alpha.assert_not_called()
        self.assertIsNone(result.alpha)
        self.assertEqual(result.alpha_status, "unavailable")
        self.assertEqual(
            result.alpha_message,
            "China A-share factor attribution is not supported yet.",
        )
        self.assertEqual(result.optimization.tickers, ["600519"])

    def test_jp_full_analysis_marks_alpha_unavailable_without_factor_call(self) -> None:
        dates = pd.date_range("2026-01-05", periods=90, freq="B")
        price_df = pd.DataFrame(
            {"7203.T": 100.0 * np.exp(np.linspace(0.0, 0.12, len(dates)))},
            index=dates,
        )
        risk_result = RiskEvaluationResult(
            tickers=["7203.T"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
            source="yahoo_chart",
            source_detail="Yahoo Finance chart API",
        )
        optimization_result = OptimizationResult(
            tickers=["7203.T"],
            prior_returns=[0.1],
            prior_weights=[1.0],
            posterior_returns=[0.1],
            posterior_weights=[1.0],
            risk_aversion=2.5,
        )
        payload = api.AnalysisRunRequest(
            tickers=["7203.T"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            weights=[1.0],
            market="jp",
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )

        def fetch_prices_once(engine, tickers, start_date, end_date, market_mode):
            engine.fetcher._mark_source("yahoo_chart", "Yahoo Finance chart API")
            return price_df

        with patch.object(api.RiskEngine, "_fetch_prices", autospec=True, side_effect=fetch_prices_once):
            with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                with patch.object(api.analysis_service, "run_alpha_from_prices") as run_alpha:
                    with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                        with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                            with patch.object(api.MLRiskEngine, "evaluate_from_prices", side_effect=ValueError("short sample")):
                                with patch.object(api.analysis_service, "optimize_portfolio_from_prices", return_value=optimization_result):
                                    result = asyncio.run(api.run_analysis(payload))

        run_alpha.assert_not_called()
        self.assertIsNone(result.alpha)
        self.assertEqual(result.alpha_status, "unavailable")
        self.assertEqual(
            result.alpha_message,
            "Japan market factor attribution is not supported yet.",
        )
        self.assertEqual(result.optimization.tickers, ["7203.T"])

    def test_tw_full_analysis_marks_alpha_unavailable_without_factor_call(self) -> None:
        dates = pd.date_range("2026-01-05", periods=90, freq="B")
        price_df = pd.DataFrame(
            {"2330.TW": 100.0 * np.exp(np.linspace(0.0, 0.12, len(dates)))},
            index=dates,
        )
        risk_result = RiskEvaluationResult(
            tickers=["2330.TW"],
            historical_es=0.01,
            monte_carlo_es=0.012,
            confidence_level=0.99,
            source="yahoo_chart",
            source_detail="Yahoo Finance chart API",
        )
        optimization_result = OptimizationResult(
            tickers=["2330.TW"],
            prior_returns=[0.1],
            prior_weights=[1.0],
            posterior_returns=[0.1],
            posterior_weights=[1.0],
            risk_aversion=2.5,
        )
        payload = api.AnalysisRunRequest(
            tickers=["2330.TW"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            weights=[1.0],
            market="tw",
            risk_free_rate=0.0,
            use_market_cap_prior=False,
        )

        def fetch_prices_once(engine, tickers, start_date, end_date, market_mode):
            engine.fetcher._mark_source("yahoo_chart", "Yahoo Finance chart API")
            return price_df

        with patch.object(api.RiskEngine, "_fetch_prices", autospec=True, side_effect=fetch_prices_once):
            with patch.object(api.RiskEngine, "evaluate_from_prices", return_value=risk_result):
                with patch.object(api.analysis_service, "run_alpha_from_prices") as run_alpha:
                    with patch.object(api.RiskAnomalyDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                        with patch.object(api.MarketRegimeDetector, "evaluate_from_prices", side_effect=ValueError("short sample")):
                            with patch.object(api.MLRiskEngine, "evaluate_from_prices", side_effect=ValueError("short sample")):
                                with patch.object(api.analysis_service, "optimize_portfolio_from_prices", return_value=optimization_result):
                                    result = asyncio.run(api.run_analysis(payload))

        run_alpha.assert_not_called()
        self.assertIsNone(result.alpha)
        self.assertEqual(result.alpha_status, "unavailable")
        self.assertEqual(
            result.alpha_message,
            "Taiwan market factor attribution is not supported yet.",
        )
        self.assertEqual(result.optimization.tickers, ["2330.TW"])


if __name__ == "__main__":
    unittest.main()
