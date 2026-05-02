import unittest
import warnings

import numpy as np

from models.portfolio_opt import BayesianOptimizer, ViewSpec
from models.risk_engine import RiskEngine


class WeightNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.optimizer = BayesianOptimizer()
        self.tickers = ["AAA", "BBB"]
        self.prior_returns = np.array([0.01, 0.02])
        self.cov_matrix = np.array([[0.10, 0.01], [0.01, 0.20]])
        self.views = [
            ViewSpec(assets=["AAA"], expected_return=0.03, confidence=0.50)
        ]

    def test_risk_engine_zero_weights_fallback_to_equal_weights(self) -> None:
        weights = RiskEngine._normalize_weights([0.0, 0.0], 2)

        np.testing.assert_allclose(weights, np.array([0.5, 0.5]))

    def test_risk_engine_valid_weights_are_normalized(self) -> None:
        weights = RiskEngine._normalize_weights([25.0, 75.0], 2)

        np.testing.assert_allclose(weights, np.array([0.25, 0.75]))

    def test_optimizer_zero_prior_weights_fallback_without_warning(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            result = self.optimizer.optimize_with_views(
                tickers=self.tickers,
                prior_returns=self.prior_returns,
                cov_matrix=self.cov_matrix,
                views=self.views,
                weights=[0.0, 0.0],
                max_weight=1.0,
            )

        prior_weights = np.asarray(result.prior_weights)
        self.assertTrue(np.isfinite(prior_weights).all())
        self.assertAlmostEqual(float(prior_weights.sum()), 1.0, places=6)

    def test_optimizer_non_finite_prior_weights_fallback(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=self.tickers,
            prior_returns=self.prior_returns,
            cov_matrix=self.cov_matrix,
            views=self.views,
            weights=[np.nan, 1.0],
            max_weight=1.0,
        )

        prior_weights = np.asarray(result.prior_weights)
        self.assertTrue(np.isfinite(prior_weights).all())
        self.assertAlmostEqual(float(prior_weights.sum()), 1.0, places=6)

    def test_optimizer_valid_prior_weights_are_preserved(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=self.tickers,
            prior_returns=self.prior_returns,
            cov_matrix=self.cov_matrix,
            views=self.views,
            weights=[0.20, 0.80],
            max_weight=1.0,
        )

        np.testing.assert_allclose(
            np.asarray(result.prior_weights),
            np.array([0.20, 0.80]),
            atol=1e-8,
        )


if __name__ == "__main__":
    unittest.main()
