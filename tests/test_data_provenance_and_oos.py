import unittest
import warnings
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd

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
        returns_df = self._returns(2)

        with self.assertRaisesRegex(ValueError, "at least 3 complete finite"):
            RiskEngine.split_returns(returns_df, 0.20)

    def test_split_returns_preserves_minimum_train_and_test_samples(self) -> None:
        returns_df = self._returns(3)

        train_df, test_df = RiskEngine.split_returns(returns_df, 0.20)

        self.assertEqual(len(train_df), 2)
        self.assertEqual(len(test_df), 1)

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
    def test_synthetic_factor_fallback_marks_factor_source(self) -> None:
        analyzer = FactorAnalyzer()

        with patch("models.factor_models.requests.get", side_effect=RuntimeError("network unavailable")):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                factors_df = analyzer.fetch_kf_french_factors(
                    date(2026, 1, 1),
                    date(2026, 1, 31),
                )

        self.assertEqual(factors_df.attrs["factor_source"], "synthetic")
        self.assertTrue(factors_df.attrs["factor_is_synthetic"])

        portfolio_returns = pd.Series(
            np.linspace(0.001, 0.002, len(factors_df)),
            index=factors_df.index,
        )
        result = analyzer.regress_portfolio(portfolio_returns, factors_df)

        self.assertEqual(result.factor_source, "synthetic")
        self.assertTrue(result.factor_is_synthetic)


class FetcherCacheTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
