import unittest
import warnings
from tempfile import TemporaryDirectory
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests
from yfinance.exceptions import YFRateLimitError

from data_pipeline.exceptions import DataFetcherError
from data_pipeline.fetcher import SmartFetcher
from models.factor_models import FactorAnalyzer
from models.risk_engine import RiskEngine


class OOSSampleValidationTests(unittest.TestCase):
    def _returns(self, rows: int) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "AAA": np.linspace(0.001, 0.003, rows),
                "BBB": np.linspace(0.002, 0.004, rows),
            },
            index=pd.date_range("2026-01-02", periods=rows, freq="B"),
        )

    def test_split_returns_rejects_insufficient_training_sample(self) -> None:
        returns_df = self._returns(31)

        with self.assertRaisesRegex(ValueError, "at least 32 complete finite"):
            RiskEngine.split_returns(returns_df, 0.20)

    def test_split_returns_preserves_minimum_train_and_test_samples(self) -> None:
        returns_df = self._returns(40)

        train_df, test_df = RiskEngine.split_returns(returns_df, 0.20)

        self.assertEqual(len(train_df), 10)
        self.assertEqual(len(test_df), 30)

    def test_prepare_optimization_inputs_rejects_non_finite_training_rows(self) -> None:
        returns_df = self._returns(3)
        returns_df.iloc[0, 0] = np.nan
        returns_df.iloc[1, 1] = np.inf

        with self.assertRaisesRegex(ValueError, "at least 2 complete finite"):
            RiskEngine.prepare_optimization_inputs(returns_df, 2)

    def test_prepare_optimization_inputs_returns_finite_psd_covariance(self) -> None:
        returns_df = pd.DataFrame(
            {
                "AAA": [0.001, 0.001, 0.001],
                "BBB": [0.002, 0.002, 0.002],
            },
            index=pd.date_range("2026-01-02", periods=3, freq="B"),
        )

        prior_returns, cov_matrix = RiskEngine.prepare_optimization_inputs(returns_df, 2)

        self.assertEqual(prior_returns.shape, (2,))
        self.assertEqual(cov_matrix.shape, (2, 2))
        self.assertTrue(np.isfinite(prior_returns).all())
        self.assertTrue(np.isfinite(cov_matrix).all())
        self.assertGreaterEqual(float(np.linalg.eigvalsh(cov_matrix).min()), 0.0)


class FactorProvenanceTests(unittest.TestCase):
    def test_factor_fetch_failure_does_not_generate_synthetic_by_default(self) -> None:
        analyzer = FactorAnalyzer(cache_path=None, request_timeout=0.01, request_attempts=1)

        with patch("models.factor_models.requests.get", side_effect=RuntimeError("network unavailable")):
            with self.assertRaisesRegex(DataFetcherError, "failed to fetch Kenneth French data"):
                analyzer.fetch_kf_french_factors(
                    date(2026, 1, 1),
                    date(2026, 1, 31),
                )

    def test_synthetic_factor_fallback_requires_explicit_test_mode(self) -> None:
        analyzer = FactorAnalyzer(cache_path=None, request_timeout=0.01, request_attempts=1)

        with patch.dict("os.environ", {"DFQ_ALLOW_SYNTHETIC_FACTORS": "1"}):
            with patch("models.factor_models.requests.get", side_effect=RuntimeError("network unavailable")):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    factors_df = analyzer.fetch_kf_french_factors(
                        date(2026, 1, 1),
                        date(2026, 4, 30),
                    )

        self.assertEqual(factors_df.attrs["factor_source"], "synthetic")
        self.assertTrue(factors_df.attrs["factor_is_synthetic"])
        self.assertIn("RMW", factors_df.columns)
        self.assertIn("CMA", factors_df.columns)

        portfolio_returns = pd.Series(
            np.linspace(0.001, 0.002, len(factors_df)),
            index=factors_df.index,
        )
        result = analyzer.regress_portfolio(portfolio_returns, factors_df)

        self.assertEqual(result.factor_source, "synthetic")
        self.assertTrue(result.factor_is_synthetic)
        self.assertTrue(np.isfinite(result.beta_rmw))
        self.assertTrue(np.isfinite(result.beta_cma))

    def test_factor_cache_truncates_to_real_coverage(self) -> None:
        factors = pd.DataFrame(
            {
                "Mkt-RF": np.linspace(0.001, 0.002, 65),
                "SMB": np.linspace(0.0001, 0.0002, 65),
                "HML": np.linspace(0.0001, 0.0002, 65),
                "RMW": np.linspace(0.0001, 0.0002, 65),
                "CMA": np.linspace(0.0001, 0.0002, 65),
                "RF": np.full(65, 0.0001),
            },
            index=pd.date_range("2026-01-01", periods=65, freq="B", name="Date"),
        )

        with TemporaryDirectory() as tmp_dir:
            analyzer = FactorAnalyzer(cache_path=f"{tmp_dir}/factors.parquet")
            analyzer._write_disk_factor_cache(factors)

            result = analyzer.fetch_kf_french_factors(
                date(2026, 1, 1),
                date(2026, 6, 30),
            )

        self.assertEqual(result.attrs["factor_source"], "kenneth_french")
        self.assertFalse(result.attrs["factor_is_synthetic"])
        self.assertEqual(result.attrs["alpha_status"], "truncated")
        self.assertEqual(result.attrs["factor_available_through"], "2026-04-01")
        self.assertEqual(result.index.max().strftime("%Y-%m-%d"), "2026-04-01")

    def test_factor_disk_cache_is_used_before_network(self) -> None:
        factors = pd.DataFrame(
            {
                "Mkt-RF": np.linspace(0.001, 0.002, 22),
                "SMB": np.linspace(0.0001, 0.0002, 22),
                "HML": np.linspace(0.0001, 0.0002, 22),
                "RMW": np.linspace(0.0001, 0.0002, 22),
                "CMA": np.linspace(0.0001, 0.0002, 22),
                "RF": np.full(22, 0.0001),
            },
            index=pd.date_range("2026-01-01", periods=22, freq="B", name="Date"),
        )

        with TemporaryDirectory() as tmp_dir:
            analyzer = FactorAnalyzer(cache_path=f"{tmp_dir}/factors.parquet")
            analyzer._write_disk_factor_cache(factors)

            with patch("models.factor_models.requests.get") as get:
                result = analyzer.fetch_kf_french_factors(
                    date(2026, 1, 1),
                    date(2026, 1, 31),
                )

        get.assert_not_called()
        self.assertEqual(result.attrs["factor_source"], "kenneth_french")
        self.assertFalse(result.attrs["factor_is_synthetic"])
        self.assertEqual(len(result), 22)


class FetcherCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        SmartFetcher._yf_cooldown_until = 0.0
        SmartFetcher._yahoo_chart_cooldown_until = 0.0
        SmartFetcher._yf_last_call_time = 0.0

    def test_runtime_cache_can_be_disabled_by_environment(self) -> None:
        with patch.dict("os.environ", {"DFQ_DISABLE_CACHE": "1"}):
            fetcher = SmartFetcher()

        self.assertFalse(fetcher.cache_enabled)
        self.assertIsNone(
            fetcher._read_result_cache(
                "us_equity",
                "AAA",
                date(2026, 1, 1),
                date(2026, 1, 31),
            )
        )

    def test_yfinance_rate_limit_does_not_silently_use_sandbox(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")

            with patch.object(fetcher, "_fetch_yahoo_chart", side_effect=YFRateLimitError()):
                with patch("data_pipeline.fetcher.yf.Ticker") as ticker_cls:
                    ticker_cls.return_value.history.side_effect = YFRateLimitError()

                    with self.assertRaisesRegex(DataFetcherError, "Unable to fetch real price data"):
                        fetcher.fetch_us_equity(
                            "AAA",
                            date(2026, 1, 1),
                            date(2026, 1, 31),
                        )

        self.assertNotEqual(fetcher.last_source, "sandbox")

    def test_yfinance_rate_limit_reuses_complete_cache_without_stale_warning(self) -> None:
        prices = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-01", periods=22, freq="B"),
                "Close": np.linspace(100.0, 110.0, 22),
            }
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache", cache_expire_hours=0)
            fetcher._write_result_cache(
                prices,
                "us_equity",
                "AAA",
                date(2026, 1, 1),
                date(2026, 1, 31),
                provider="yfinance",
            )

            with patch.object(fetcher, "_fetch_yahoo_chart", side_effect=YFRateLimitError()):
                with patch("data_pipeline.fetcher.yf.Ticker") as ticker_cls:
                    ticker_cls.return_value.history.side_effect = YFRateLimitError()
                    response = fetcher.fetch_us_equity(
                        "AAA",
                        date(2026, 1, 1),
                        date(2026, 1, 31),
                    )

        self.assertEqual(fetcher.last_source, "cache")
        self.assertNotIn("cached prices", " ".join(fetcher.data_warnings))
        self.assertGreaterEqual(response.records, 20)

    def test_complete_cache_requires_recent_end_coverage(self) -> None:
        prices = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-01", "2026-01-23", freq="B"),
                "Close": np.linspace(100.0, 110.0, 17),
            }
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")
            fetcher._write_result_cache(
                prices,
                "us_equity",
                "AAA",
                date(2026, 1, 1),
                date(2026, 1, 30),
                provider="yfinance",
            )

            cached = fetcher._read_result_cache(
                "us_equity",
                "AAA",
                date(2026, 1, 1),
                date(2026, 1, 30),
            )

        self.assertIsNone(cached)

    def test_us_cache_one_business_day_short_misses_normal_read(self) -> None:
        prices = pd.DataFrame(
            {
                "Date": pd.date_range("2026-05-01", "2026-05-14", freq="B"),
                "Close": np.linspace(100.0, 110.0, 10),
            }
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")
            fetcher._write_result_cache(
                prices,
                "us_equity",
                "AAA",
                date(2026, 5, 1),
                date(2026, 5, 16),
                provider="yahoo_chart",
            )

            cached = fetcher._read_result_cache(
                "us_equity",
                "AAA",
                date(2026, 5, 1),
                date(2026, 5, 16),
            )
            stale_cached = fetcher._read_price_cache(
                "us_equity",
                "AAA",
                date(2026, 5, 1),
                date(2026, 5, 16),
                allow_stale=True,
                allow_partial=True,
            )

        self.assertIsNone(cached)
        self.assertIsNotNone(stale_cached)

    def test_incomplete_symbol_cache_falls_through_to_exact_window_cache(self) -> None:
        short_prices = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-01", "2026-01-23", freq="B"),
                "Close": np.linspace(100.0, 110.0, 17),
                "__provider": "yfinance",
            }
        )
        full_prices = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-01", "2026-01-30", freq="B"),
                "Close": np.linspace(100.0, 112.0, 22),
                "__provider": "yfinance",
                "__provider_x": "legacy",
                "__provider_y": "legacy",
            }
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")
            short_prices.to_parquet(fetcher._price_cache_path("us_equity", "AAA"), index=False)
            full_prices.to_parquet(
                fetcher._result_cache_path(
                    "us_equity",
                    "AAA",
                    date(2026, 1, 1),
                    date(2026, 1, 30),
                ),
                index=False,
            )

            cached = fetcher._read_result_cache(
                "us_equity",
                "AAA",
                date(2026, 1, 1),
                date(2026, 1, 30),
            )

        self.assertIsNotNone(cached)
        assert cached is not None
        self.assertEqual(pd.to_datetime(cached["Date"]).max().date(), date(2026, 1, 30))
        self.assertEqual(list(cached.columns), ["Date", "Close"])

    def test_cache_write_cleans_provider_suffix_columns_before_merge(self) -> None:
        existing = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-01", "2026-01-09", freq="B"),
                "Close": np.linspace(100.0, 104.0, 7),
                "__provider": "yfinance",
                "__provider_x": "legacy",
                "__provider_y": "legacy",
            }
        )
        latest = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-12", "2026-01-20", freq="B"),
                "Close": np.linspace(105.0, 111.0, 7),
            }
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")
            symbol_path = fetcher._price_cache_path("us_equity", "AAA")
            existing.to_parquet(symbol_path, index=False)

            fetcher._write_result_cache(
                latest,
                "us_equity",
                "AAA",
                date(2026, 1, 12),
                date(2026, 1, 20),
                provider="yahoo_chart",
            )
            stored = pd.read_parquet(symbol_path)

        self.assertEqual(pd.to_datetime(stored["Date"]).min().date(), date(2026, 1, 1))
        self.assertEqual(pd.to_datetime(stored["Date"]).max().date(), date(2026, 1, 20))
        self.assertEqual(list(stored.columns), ["Date", "Close", "__provider"])

    def test_yfinance_rate_limit_can_use_partial_stale_cache(self) -> None:
        prices = pd.DataFrame(
            {
                "Date": pd.date_range("2026-01-01", periods=15, freq="B"),
                "Close": np.linspace(100.0, 106.0, 15),
            }
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache", cache_expire_hours=0)
            fetcher._write_result_cache(
                prices,
                "us_equity",
                "AAA",
                date(2026, 1, 1),
                date(2026, 1, 31),
                provider="yfinance",
            )

            with patch.object(fetcher, "_fetch_yahoo_chart", side_effect=YFRateLimitError()):
                with patch("data_pipeline.fetcher.yf.Ticker") as ticker_cls:
                    ticker_cls.return_value.history.side_effect = YFRateLimitError()
                    response = fetcher.fetch_us_equity(
                        "AAA",
                        date(2026, 1, 1),
                        date(2026, 1, 31),
                    )

        self.assertEqual(fetcher.last_source, "stale_cache")
        self.assertIn("cached prices", " ".join(fetcher.data_warnings))
        self.assertGreaterEqual(response.records, 13)

    def test_yahoo_chart_http_429_falls_back_to_yfinance(self) -> None:
        response = requests.Response()
        response.status_code = 429
        error = requests.exceptions.HTTPError("429 Too Many Requests", response=response)
        prices = pd.DataFrame(
            {"Close": np.linspace(100.0, 110.0, 22)},
            index=pd.date_range("2026-01-01", periods=22, freq="B"),
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")

            with patch.object(fetcher, "_fetch_yahoo_chart", side_effect=error):
                with patch("data_pipeline.fetcher.yf.Ticker") as ticker_cls:
                    ticker_cls.return_value.history.return_value = prices
                    fetcher.fetch_us_equity(
                        "AAA",
                        date(2026, 1, 1),
                        date(2026, 1, 31),
                    )
                    ticker_cls.assert_called_once()

        self.assertEqual(fetcher.last_source, "yfinance")
        self.assertEqual(SmartFetcher._yf_cooldown_until, 0.0)
        self.assertGreater(SmartFetcher._yahoo_chart_cooldown_until, 0.0)

    def test_yfinance_history_uses_bounded_timeout(self) -> None:
        prices = pd.DataFrame(
            {"Close": np.linspace(100.0, 110.0, 22)},
            index=pd.date_range("2026-01-01", periods=22, freq="B"),
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")

            with patch.object(fetcher, "_fetch_yahoo_chart", side_effect=RuntimeError("chart unavailable")):
                with patch.object(fetcher, "_yfinance_timeout_seconds", return_value=2.5):
                    with patch("data_pipeline.fetcher.yf.Ticker") as ticker_cls:
                        ticker_cls.return_value.history.return_value = prices
                        fetcher.fetch_us_equity(
                            "AAA",
                            date(2026, 1, 1),
                            date(2026, 1, 31),
                        )

        self.assertEqual(ticker_cls.return_value.history.call_args.kwargs["timeout"], 2.5)

    def test_yfinance_batch_download_uses_bounded_timeout(self) -> None:
        dates = pd.date_range("2026-01-01", periods=22, freq="B")
        batch_df = pd.DataFrame(
            np.column_stack([
                np.linspace(100.0, 110.0, len(dates)),
                np.linspace(200.0, 210.0, len(dates)),
            ]),
            index=dates,
            columns=pd.MultiIndex.from_product([["Close"], ["AAA", "BBB"]]),
        )

        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(cache_name=f"{tmp_dir}/http_cache")

            with patch.object(fetcher, "_fetch_yahoo_chart", side_effect=RuntimeError("chart unavailable")):
                with patch.object(fetcher, "_yfinance_timeout_seconds", return_value=2.5):
                    with patch("data_pipeline.fetcher.yf.download", return_value=batch_df) as download:
                        fetcher.fetch_equity_batch(
                            ["AAA", "BBB"],
                            date(2026, 1, 1),
                            date(2026, 1, 31),
                        )

        self.assertEqual(download.call_args.kwargs["timeout"], 2.5)

    def test_sandbox_data_requires_opt_in(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            fetcher = SmartFetcher(
                cache_name=f"{tmp_dir}/http_cache",
                allow_sandbox_data=True,
            )

            with patch.object(fetcher, "_fetch_yahoo_chart", side_effect=YFRateLimitError()):
                with patch("data_pipeline.fetcher.yf.Ticker") as ticker_cls:
                    ticker_cls.return_value.history.side_effect = YFRateLimitError()
                    response = fetcher.fetch_us_equity(
                        "AAA",
                        date(2026, 1, 1),
                        date(2026, 1, 31),
                    )

        self.assertEqual(fetcher.last_source, "sandbox")
        self.assertEqual(fetcher.last_source_detail, "sandbox demo")
        self.assertGreater(response.records, 0)

    def test_repeated_batch_fetch_uses_symbol_cache(self) -> None:
        dates = pd.date_range("2026-01-01", periods=22, freq="B")
        batch_df = pd.DataFrame(
            np.column_stack([
                np.linspace(100.0, 110.0, len(dates)),
                np.linspace(200.0, 210.0, len(dates)),
            ]),
            index=dates,
            columns=pd.MultiIndex.from_product([["Close"], ["AAA", "BBB"]]),
        )

        with TemporaryDirectory() as tmp_dir:
            cache_name = f"{tmp_dir}/http_cache"
            first = SmartFetcher(cache_name=cache_name)
            second = SmartFetcher(cache_name=cache_name)

            with patch.object(first, "_fetch_yahoo_chart") as first_chart:
                first_chart.side_effect = [
                    pd.DataFrame({"Date": dates, "Close": batch_df[("Close", "AAA")].values}),
                    pd.DataFrame({"Date": dates, "Close": batch_df[("Close", "BBB")].values}),
                ]
                first.fetch_equity_batch(
                    ["AAA", "BBB"],
                    date(2026, 1, 1),
                    date(2026, 1, 31),
                )
                second.fetch_equity_batch(
                    ["AAA", "BBB"],
                    date(2026, 1, 1),
                    date(2026, 1, 31),
                )

        self.assertEqual(first_chart.call_count, 2)
        self.assertEqual(second.last_source, "cache")


if __name__ == "__main__":
    unittest.main()
