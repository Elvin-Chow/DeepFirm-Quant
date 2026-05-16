import unittest
from datetime import date
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from data_pipeline.exceptions import DataFetcherError
from data_pipeline.fetcher import SmartFetcher
from models.risk_engine import RiskEngine, RiskEvaluationRequest


def make_china_prices(rows: int = 90, start: str = "2026-01-05") -> pd.DataFrame:
    dates = pd.date_range(start, periods=rows, freq="B")
    return pd.DataFrame(
        {
            "日期": dates.strftime("%Y-%m-%d"),
            "收盘": 100.0 * np.exp(np.linspace(0.0, 0.12, rows)),
        }
    )


class FakeAligner:
    def __init__(self) -> None:
        self.markets: list[str] = []

    def align_multiple(self, series_list, markets):
        self.markets = list(markets)
        return pd.concat([series.to_frame() for series in series_list], axis=1)


class FakeChinaFetcher:
    def __init__(self) -> None:
        self.last_source = "unknown"
        self.last_source_detail = "unknown"
        self.data_warnings: list[str] = []
        self.china_calls: list[str] = []
        self.batch_called = False

    def fetch_equity_batch(self, tickers, start_date, end_date):
        self.batch_called = True
        raise AssertionError("CN mode must not call batch equity fetch")

    def fetch_china_equity(self, symbol, start_date, end_date):
        self.china_calls.append(symbol)
        self.last_source = "akshare"
        self.last_source_detail = "AKShare A-share daily qfq"
        return SimpleNamespace(data=make_china_prices())


class ChinaPriceNormalizationTests(unittest.TestCase):
    def test_normalizes_akshare_columns_to_date_and_close(self) -> None:
        raw = make_china_prices(rows=3)

        normalized = RiskEngine._normalize_china_price_frame(raw, "600519")

        self.assertEqual(list(normalized.columns), ["Date", "Close"])
        self.assertEqual(len(normalized), 3)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(normalized["Date"]))
        self.assertTrue((normalized["Close"] > 0.0).all())

    def test_accepts_cached_or_fallback_date_close_columns(self) -> None:
        raw = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-05", periods=3, freq="B"),
                "Close": [100.0, 101.0, 102.0],
            }
        )

        normalized = RiskEngine._normalize_china_price_frame(raw, "600519")

        self.assertEqual(list(normalized.columns), ["Date", "Close"])
        self.assertEqual(len(normalized), 3)

    def test_rejects_empty_china_price_frame(self) -> None:
        with self.assertRaises(DataFetcherError):
            RiskEngine._normalize_china_price_frame(pd.DataFrame(), "600519")

    def test_rejects_non_positive_china_prices(self) -> None:
        raw = make_china_prices(rows=3)
        raw.loc[1, "收盘"] = 0.0

        with self.assertRaisesRegex(ValueError, "non-positive"):
            RiskEngine._normalize_china_price_frame(raw, "600519")

    def test_rejects_unparseable_china_dates(self) -> None:
        raw = make_china_prices(rows=3)
        raw.loc[1, "日期"] = "not-a-date"

        with self.assertRaisesRegex(ValueError, "unparseable"):
            RiskEngine._normalize_china_price_frame(raw, "600519")


class ChinaRiskEngineFetchTests(unittest.TestCase):
    def test_cn_fetch_flow_skips_batch_and_uses_sse_alignment(self) -> None:
        fetcher = FakeChinaFetcher()
        aligner = FakeAligner()
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)

        prices = engine._fetch_prices(
            ["600519", "300750"],
            date(2026, 1, 1),
            date(2026, 6, 30),
            market_mode="cn",
        )

        self.assertFalse(fetcher.batch_called)
        self.assertEqual(fetcher.china_calls, ["600519", "300750"])
        self.assertEqual(aligner.markets, ["SSE", "SSE"])
        self.assertEqual(list(prices.columns), ["600519", "300750"])

    def test_single_a_share_can_compute_risk_result(self) -> None:
        fetcher = FakeChinaFetcher()
        engine = RiskEngine(fetcher=fetcher, aligner=FakeAligner())
        request = RiskEvaluationRequest(
            tickers=["600519"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="cn",
            mc_paths=1_000,
        )

        result = engine.evaluate(request)

        self.assertEqual(result.tickers, ["600519"])
        self.assertTrue(np.isfinite(result.historical_es))
        self.assertTrue(np.isfinite(result.monte_carlo_es))
        self.assertEqual(result.source, "akshare")
        self.assertEqual(result.source_detail, "AKShare A-share daily qfq")

    def test_multiple_a_shares_compute_correlation_matrix(self) -> None:
        fetcher = FakeChinaFetcher()
        engine = RiskEngine(fetcher=fetcher, aligner=FakeAligner())
        request = RiskEvaluationRequest(
            tickers=["600519", "300750"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="cn",
            weights=[0.5, 0.5],
            mc_paths=1_000,
        )

        result = engine.evaluate(request)

        self.assertEqual(len(result.correlation_matrix), 2)
        self.assertEqual(len(result.correlation_matrix[0]), 2)
        self.assertAlmostEqual(result.correlation_matrix[0][0], 1.0)
        self.assertAlmostEqual(result.correlation_matrix[1][1], 1.0)

    def test_cn_fetch_attaches_price_quality_warnings(self) -> None:
        dates = pd.date_range("2026-01-05", periods=30, freq="B")
        raw = pd.DataFrame(
            {
                "日期": dates.strftime("%Y-%m-%d"),
                "收盘": [100.0] * 12 + list(np.linspace(101.0, 118.0, 18)),
            }
        )
        raw.loc[5, "日期"] = raw.loc[4, "日期"]

        class QualityFetcher(FakeChinaFetcher):
            def fetch_china_equity(self, symbol, start_date, end_date):
                self.china_calls.append(symbol)
                self.last_source = "akshare"
                self.last_source_detail = "AKShare A-share daily qfq"
                return SimpleNamespace(data=raw)

        fetcher = QualityFetcher()
        engine = RiskEngine(fetcher=fetcher, aligner=FakeAligner())
        request = RiskEvaluationRequest(
            tickers=["600519"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 31),
            market="cn",
            mc_paths=1_000,
        )

        result = engine.evaluate(request)
        warning_text = " ".join(result.data_warnings)

        self.assertIn("price sample is short", warning_text)
        self.assertIn("duplicate date rows", warning_text)
        self.assertIn("price coverage is low", warning_text)
        self.assertIn("unchanged for", warning_text)


class FakeJapanFetcher:
    def __init__(self) -> None:
        self.last_source = "unknown"
        self.last_source_detail = "unknown"
        self.data_warnings: list[str] = []
        self.jp_calls: list[str] = []
        self.batch_called = False

    def fetch_equity_batch(self, tickers, start_date, end_date):
        self.batch_called = True
        raise DataFetcherError(
            message="batch unavailable",
            symbol=",".join(tickers),
            source="yfinance",
        )

    def fetch_jp_equity(self, symbol, start_date, end_date):
        self.jp_calls.append(symbol)
        self.last_source = "yahoo_chart"
        self.last_source_detail = "Yahoo Finance chart API"
        dates = pd.date_range("2026-01-05", periods=90, freq="B")
        return SimpleNamespace(
            data=pd.DataFrame(
                {
                    "Date": dates,
                    "Close": 100.0 * np.exp(np.linspace(0.0, 0.10, len(dates))),
                }
            )
        )


class FakeTaiwanFetcher:
    def __init__(self) -> None:
        self.last_source = "unknown"
        self.last_source_detail = "unknown"
        self.data_warnings: list[str] = []
        self.tw_calls: list[str] = []
        self.batch_called = False

    def fetch_equity_batch(self, tickers, start_date, end_date):
        self.batch_called = True
        raise DataFetcherError(
            message="batch unavailable",
            symbol=",".join(tickers),
            source="yfinance",
        )

    def fetch_tw_equity(self, symbol, start_date, end_date):
        self.tw_calls.append(symbol)
        self.last_source = "yahoo_chart"
        self.last_source_detail = "Yahoo Finance chart API"
        dates = pd.date_range("2026-01-05", periods=90, freq="B")
        return SimpleNamespace(
            data=pd.DataFrame(
                {
                    "Date": dates,
                    "Close": 100.0 * np.exp(np.linspace(0.0, 0.10, len(dates))),
                }
            )
        )


class JapanRiskEngineFetchTests(unittest.TestCase):
    def test_jp_fetch_flow_uses_jpx_alignment(self) -> None:
        fetcher = FakeJapanFetcher()
        aligner = FakeAligner()
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)

        prices = engine._fetch_prices(
            ["7203.T"],
            date(2026, 1, 1),
            date(2026, 6, 30),
            market_mode="jp",
        )

        self.assertFalse(fetcher.batch_called)
        self.assertEqual(fetcher.jp_calls, ["7203.T"])
        self.assertEqual(aligner.markets, ["JPX"])
        self.assertEqual(list(prices.columns), ["7203.T"])

    def test_single_jp_equity_can_compute_risk_result(self) -> None:
        fetcher = FakeJapanFetcher()
        engine = RiskEngine(fetcher=fetcher, aligner=FakeAligner())
        request = RiskEvaluationRequest(
            tickers=["7203.T"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="jp",
            mc_paths=1_000,
        )

        result = engine.evaluate(request)

        self.assertEqual(result.tickers, ["7203.T"])
        self.assertTrue(np.isfinite(result.historical_es))
        self.assertTrue(np.isfinite(result.monte_carlo_es))
        self.assertEqual(result.source, "yahoo_chart")
        self.assertEqual(result.source_detail, "Yahoo Finance chart API")


class TaiwanRiskEngineFetchTests(unittest.TestCase):
    def test_tw_fetch_flow_uses_xtai_alignment(self) -> None:
        fetcher = FakeTaiwanFetcher()
        aligner = FakeAligner()
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)

        prices = engine._fetch_prices(
            ["2330.TW"],
            date(2026, 1, 1),
            date(2026, 6, 30),
            market_mode="tw",
        )

        self.assertFalse(fetcher.batch_called)
        self.assertEqual(fetcher.tw_calls, ["2330.TW"])
        self.assertEqual(aligner.markets, ["XTAI"])
        self.assertEqual(list(prices.columns), ["2330.TW"])

    def test_single_tw_equity_can_compute_risk_result(self) -> None:
        fetcher = FakeTaiwanFetcher()
        engine = RiskEngine(fetcher=fetcher, aligner=FakeAligner())
        request = RiskEvaluationRequest(
            tickers=["2330.TW"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            market="tw",
            mc_paths=1_000,
        )

        result = engine.evaluate(request)

        self.assertEqual(result.tickers, ["2330.TW"])
        self.assertTrue(np.isfinite(result.historical_es))
        self.assertTrue(np.isfinite(result.monte_carlo_es))
        self.assertEqual(result.source, "yahoo_chart")
        self.assertEqual(result.source_detail, "Yahoo Finance chart API")


class ChinaFetcherFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        SmartFetcher._china_akshare_cooldown_until = 0.0

    def tearDown(self) -> None:
        SmartFetcher._china_akshare_cooldown_until = 0.0

    def test_china_equity_falls_back_to_yahoo_when_akshare_disconnects(self) -> None:
        fallback = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-05", periods=5, freq="B"),
                "Close": np.linspace(100.0, 104.0, 5),
            }
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")
            with patch(
                "data_pipeline.fetcher.ak.stock_zh_a_hist",
                side_effect=requests.ConnectionError("remote closed"),
            ):
                with patch.object(fetcher, "_fetch_yahoo_chart", return_value=fallback) as yahoo:
                    response = fetcher.fetch_china_equity(
                        "600519",
                        date(2026, 1, 1),
                        date(2026, 1, 31),
                    )

        yahoo.assert_called_once()
        self.assertEqual(response.records, 5)
        self.assertEqual(fetcher.last_source, "yahoo_chart")
        self.assertIn("A-share fallback", fetcher.last_source_detail)
        self.assertTrue(any("AKShare A-share data" in warning for warning in fetcher.data_warnings))

    def test_china_equity_wraps_live_provider_failures(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")
            with patch(
                "data_pipeline.fetcher.ak.stock_zh_a_hist",
                side_effect=requests.ConnectionError("remote closed"),
            ):
                with patch.object(fetcher, "_fetch_yahoo_chart", side_effect=RuntimeError("fallback failed")):
                    with self.assertRaisesRegex(DataFetcherError, "Unable to fetch real A-share"):
                        fetcher.fetch_china_equity(
                            "600519",
                            date(2026, 1, 1),
                            date(2026, 1, 31),
                        )

    def test_china_equity_skips_akshare_during_provider_cooldown(self) -> None:
        fallback = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-05", periods=5, freq="B"),
                "Close": np.linspace(100.0, 104.0, 5),
            }
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")
            with patch(
                "data_pipeline.fetcher.ak.stock_zh_a_hist",
                side_effect=requests.ConnectionError("remote closed"),
            ) as akshare:
                with patch.object(fetcher, "_fetch_yahoo_chart", return_value=fallback) as yahoo:
                    first = fetcher.fetch_china_equity(
                        "600519",
                        date(2026, 1, 1),
                        date(2026, 1, 31),
                    )
                    second = fetcher.fetch_china_equity(
                        "300750",
                        date(2026, 1, 1),
                        date(2026, 1, 31),
                    )

        self.assertEqual(first.records, 5)
        self.assertEqual(second.records, 5)
        self.assertEqual(akshare.call_count, 1)
        self.assertEqual(yahoo.call_count, 2)


if __name__ == "__main__":
    unittest.main()
