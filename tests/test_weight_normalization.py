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

    def test_optimizer_user_prior_weights_respect_max_weight(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=["AAA", "BBB", "CCC"],
            prior_returns=np.array([0.01, 0.02, 0.03]),
            cov_matrix=np.eye(3) * 0.10,
            views=[],
            weights=[1.0, 0.0, 0.0],
            max_weight=0.40,
        )

        prior_weights = np.asarray(result.prior_weights)
        self.assertAlmostEqual(float(prior_weights.sum()), 1.0, places=6)
        self.assertLessEqual(float(prior_weights.max()), 0.40 + 1e-8)
        np.testing.assert_allclose(
            prior_weights,
            np.array([0.40, 0.30, 0.30]),
            atol=1e-8,
        )

    def test_optimizer_without_views_still_rebalances_user_prior(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=self.tickers,
            prior_returns=self.prior_returns,
            cov_matrix=self.cov_matrix,
            views=[],
            weights=[0.50, 0.50],
            max_weight=1.0,
        )

        expected_returns = (
            0.75 * np.asarray(result.prior_returns)
            + 0.25 * np.clip(self.prior_returns, -0.50, 0.50)
        )
        np.testing.assert_allclose(
            np.asarray(result.posterior_returns),
            expected_returns,
            atol=1e-12,
        )
        self.assertFalse(
            np.allclose(
                np.asarray(result.posterior_weights),
                np.asarray(result.prior_weights),
                atol=1e-8,
            )
        )
        self.assertAlmostEqual(float(np.sum(result.posterior_weights)), 1.0, places=6)

    def test_optimizer_clips_extreme_no_view_return_signal(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=self.tickers,
            prior_returns=np.array([10.0, -10.0]),
            cov_matrix=self.cov_matrix,
            views=[],
            weights=[0.50, 0.50],
            max_weight=1.0,
        )

        expected_returns = (
            0.75 * np.asarray(result.prior_returns)
            + 0.25 * np.array([0.50, -0.50])
        )
        np.testing.assert_allclose(
            np.asarray(result.posterior_returns),
            expected_returns,
            atol=1e-12,
        )
        self.assertTrue(np.isfinite(result.posterior_weights).all())

    def test_optimizer_keeps_low_return_asset_above_effective_floor(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=["AAA", "BBB", "CCC"],
            prior_returns=np.array([0.10, 0.06, -0.20]),
            cov_matrix=np.eye(3) * 0.01,
            views=[],
            weights=[1.0 / 3.0] * 3,
            max_weight=1.0,
            min_weight=0.02,
            turnover_penalty=0.0,
            concentration_penalty=0.0,
        )

        raw_weights = np.asarray(result.raw_posterior_weights)
        self.assertAlmostEqual(float(raw_weights.sum()), 1.0, places=6)
        self.assertGreaterEqual(float(raw_weights.min()), result.effective_min_weight - 1e-8)
        self.assertGreaterEqual(float(result.posterior_weights[2]), result.effective_min_weight - 1e-8)

    def test_optimizer_uses_dynamic_floor_for_large_portfolios(self) -> None:
        n_assets = 100
        result = self.optimizer.optimize_with_views(
            tickers=[f"AAA{i}" for i in range(n_assets)],
            prior_returns=np.linspace(0.02, -0.02, n_assets),
            cov_matrix=np.eye(n_assets) * 0.05,
            views=[],
            max_weight=0.20,
            min_weight=0.02,
            turnover_penalty=0.0,
            concentration_penalty=0.0,
        )

        weights = np.asarray(result.posterior_weights)
        self.assertAlmostEqual(result.effective_min_weight, 0.005, places=8)
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=6)
        self.assertGreaterEqual(float(weights.min()), result.effective_min_weight - 1e-8)

    def test_optimizer_respects_min_max_and_full_investment(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=["AAA", "BBB", "CCC", "DDD"],
            prior_returns=np.array([0.04, 0.03, 0.02, -0.01]),
            cov_matrix=np.eye(4) * 0.03,
            views=[],
            max_weight=0.50,
            min_weight=0.05,
            turnover_penalty=0.0,
            concentration_penalty=0.0,
        )

        weights = np.asarray(result.posterior_weights)
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=6)
        self.assertGreaterEqual(float(weights.min()), 0.05 - 1e-8)
        self.assertLessEqual(float(weights.max()), 0.50 + 1e-8)


if __name__ == "__main__":
    unittest.main()
