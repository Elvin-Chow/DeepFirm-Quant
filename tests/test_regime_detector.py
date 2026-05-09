import os
import unittest

import numpy as np
import pandas as pd

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

from models.regime_detector import MarketRegimeDetector


class MarketRegimeDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = MarketRegimeDetector()

    def _prices_from_returns(self, returns: np.ndarray) -> pd.DataFrame:
        returns = np.asarray(returns, dtype=float)
        base = np.full((1, returns.shape[1]), 100.0)
        prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
        price_matrix = np.vstack([base, prices])
        index = pd.date_range("2025-01-02", periods=len(price_matrix), freq="B")
        columns = [f"AAA{i}" for i in range(returns.shape[1])]
        return pd.DataFrame(price_matrix, index=index, columns=columns)

    def _regime_returns(self, assets: int = 2) -> np.ndarray:
        stable_x = np.linspace(0.0, 6.0 * np.pi, 70)
        high_x = np.linspace(0.0, 8.0 * np.pi, 50)
        crisis_x = np.linspace(0.0, 10.0 * np.pi, 50)

        columns = []
        for idx in range(assets):
            stable = 0.0005 + 0.0015 * np.sin(stable_x * (1.0 + idx * 0.10) + idx)
            high_vol = 0.0001 + 0.0120 * np.sin(high_x * (1.0 + idx * 0.05) + idx * 0.30)
            crisis = -0.0030 + 0.0200 * np.sin(crisis_x + idx * 0.08)
            columns.append(np.concatenate([stable, high_vol, crisis]))
        return np.column_stack(columns)

    def test_normal_price_data_returns_current_regime(self) -> None:
        prices = self._prices_from_returns(self._regime_returns())

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            source="test",
        )

        self.assertIn(result.current_regime, {"Normal", "High Volatility", "Crisis"})
        self.assertIn(result.smoothed_regime, {"Normal", "High Volatility", "Crisis"})
        self.assertGreaterEqual(result.transition_confidence, 0.0)
        self.assertGreaterEqual(result.persistence_days, 0)
        self.assertIsNotNone(result.diagnostics)
        self.assertEqual(result.source, "test")

    def test_result_contains_normalized_regime_probabilities(self) -> None:
        prices = self._prices_from_returns(self._regime_returns())

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            source="test",
        )

        self.assertEqual(
            set(result.regime_probabilities.keys()),
            {"Normal", "High Volatility", "Crisis"},
        )
        self.assertAlmostEqual(sum(result.regime_probabilities.values()), 1.0, places=6)

    def test_result_contains_stress_parameters(self) -> None:
        prices = self._prices_from_returns(self._regime_returns())

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            source="test",
        )

        self.assertIn(result.volatility_multiplier, {1.0, 1.5, 2.0})
        self.assertIn(result.correlation_multiplier, {1.0, 1.2, 1.5})
        self.assertIn(result.recommended_stress_level, {"Normal", "High", "Extreme"})

    def test_insufficient_sample_raises_clear_error(self) -> None:
        short_returns = self._regime_returns()[:40]
        prices = self._prices_from_returns(short_returns)

        with self.assertRaisesRegex(ValueError, "at least 60 complete finite"):
            self.detector.evaluate_from_prices(
                tickers=["AAA0", "AAA1"],
                price_df=prices,
                weights=[0.5, 0.5],
                source="test",
            )

    def test_single_asset_portfolio_handles_correlation_features(self) -> None:
        prices = self._prices_from_returns(self._regime_returns(assets=1))
        features = self.detector.build_feature_frame(prices, np.array([1.0]))

        self.assertTrue(np.isfinite(features.to_numpy(dtype=float)).all())
        self.assertTrue(np.allclose(features["average_correlation_20d"].to_numpy(), 0.0))
        self.assertTrue(np.allclose(features["max_correlation_20d"].to_numpy(), 0.0))

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0"],
            price_df=prices,
            weights=[1.0],
            source="test",
        )
        self.assertIn(result.current_regime, {"Normal", "High Volatility", "Crisis"})

    def test_gaussian_mixture_model_returns_valid_result(self) -> None:
        prices = self._prices_from_returns(self._regime_returns())

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            model_type="gaussian_mixture",
            source="test",
        )

        self.assertIn(result.current_regime, {"Normal", "High Volatility", "Crisis"})
        self.assertAlmostEqual(sum(result.regime_probabilities.values()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
