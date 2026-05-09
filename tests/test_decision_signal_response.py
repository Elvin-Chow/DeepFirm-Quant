import unittest

import numpy as np

from models.portfolio_opt import BayesianOptimizer


class DecisionSignalResponseTests(unittest.TestCase):
    """Verify the optimizer reacts to the alpha signal under the default penalties."""

    def setUp(self) -> None:
        self.optimizer = BayesianOptimizer()
        self.tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
        self.prior_returns = np.array([0.20, 0.10, 0.05, -0.05, -0.10])
        self.cov_matrix = np.eye(5) * 0.04
        self.prior_weights = np.array([0.20, 0.20, 0.20, 0.20, 0.20])

    def test_raw_posterior_diverges_from_equal_weight_prior_under_defaults(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=self.tickers,
            prior_returns=self.prior_returns,
            cov_matrix=self.cov_matrix,
            views=[],
            weights=self.prior_weights.tolist(),
        )

        raw_posterior = np.asarray(result.raw_posterior_weights)
        l1_distance = float(np.abs(raw_posterior - self.prior_weights).sum())

        self.assertAlmostEqual(float(raw_posterior.sum()), 1.0, places=6)
        self.assertGreaterEqual(l1_distance, 0.10)

    def test_higher_expected_return_assets_receive_higher_weight(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=self.tickers,
            prior_returns=self.prior_returns,
            cov_matrix=self.cov_matrix,
            views=[],
            weights=self.prior_weights.tolist(),
        )

        raw_posterior = np.asarray(result.raw_posterior_weights)
        positive_mask = self.prior_returns > 0
        negative_mask = self.prior_returns < 0

        positive_weight_sum = float(raw_posterior[positive_mask].sum())
        negative_weight_sum = float(raw_posterior[negative_mask].sum())

        self.assertGreater(positive_weight_sum, negative_weight_sum)
        for pos_idx in np.flatnonzero(positive_mask):
            for neg_idx in np.flatnonzero(negative_mask):
                self.assertGreater(float(raw_posterior[pos_idx]), float(raw_posterior[neg_idx]))

    def test_negative_return_asset_receives_lowest_weight(self) -> None:
        result = self.optimizer.optimize_with_views(
            tickers=self.tickers,
            prior_returns=self.prior_returns,
            cov_matrix=self.cov_matrix,
            views=[],
            weights=self.prior_weights.tolist(),
        )

        raw_posterior = np.asarray(result.raw_posterior_weights)
        worst_asset_idx = int(np.argmin(self.prior_returns))

        self.assertEqual(int(np.argmin(raw_posterior)), worst_asset_idx)
        self.assertLess(float(raw_posterior[worst_asset_idx]), float(self.prior_weights[worst_asset_idx]))


if __name__ == "__main__":
    unittest.main()
