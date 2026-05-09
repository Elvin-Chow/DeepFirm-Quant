import unittest

import numpy as np
import pandas as pd

from models.anomaly_detector import RiskAnomalyDetector


class RiskAnomalyDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = RiskAnomalyDetector()

    def _prices_from_returns(self, returns: np.ndarray) -> pd.DataFrame:
        returns = np.asarray(returns, dtype=float)
        base = np.full((1, returns.shape[1]), 100.0)
        prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
        price_matrix = np.vstack([base, prices])
        index = pd.date_range("2025-01-02", periods=len(price_matrix), freq="B")
        columns = [f"AAA{i}" for i in range(returns.shape[1])]
        return pd.DataFrame(price_matrix, index=index, columns=columns)

    def _stable_returns(self, rows: int = 90, assets: int = 2) -> np.ndarray:
        x = np.linspace(0.0, 8.0 * np.pi, rows)
        columns = []
        for idx in range(assets):
            signal = 0.0005 + 0.001 * np.sin(x * (1.0 + idx * 0.35) + idx)
            columns.append(signal)
        return np.column_stack(columns)

    def test_stable_prices_return_valid_result_shape(self) -> None:
        prices = self._prices_from_returns(self._stable_returns())

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            source="test",
        )

        self.assertGreaterEqual(result.anomaly_score, 0.0)
        self.assertLessEqual(result.anomaly_score, 1.0)
        self.assertIn(result.alert_level, {"Low", "Medium", "High", "Extreme"})
        self.assertTrue(result.main_reasons)
        self.assertEqual(result.source, "test")
        self.assertTrue(result.reason_codes)
        self.assertTrue(result.structured_reasons)
        self.assertIn(result.decision_impact, {"none", "tighten_constraints", "freeze_rebalance", "force_oos_guard"})
        self.assertIsNotNone(result.diagnostics)

    def test_large_latest_drop_triggers_anomaly_reason(self) -> None:
        returns = self._stable_returns()
        returns[-1, :] = np.array([-0.18, -0.04])
        prices = self._prices_from_returns(returns)

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            source="test",
        )

        self.assertTrue(result.is_anomaly)
        self.assertIn("Large negative return", result.main_reasons)
        self.assertIn("LARGE_NEGATIVE_RETURN", result.reason_codes)

    def test_short_term_volatility_spike_adds_reason(self) -> None:
        returns = self._stable_returns()
        returns[-5:, :] = np.array(
            [
                [0.055, 0.050],
                [-0.050, -0.045],
                [0.060, 0.055],
                [-0.055, -0.050],
                [0.050, 0.045],
            ]
        )
        prices = self._prices_from_returns(returns)

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            source="test",
        )

        self.assertTrue(any("volatility" in reason.lower() for reason in result.main_reasons))

    def test_correlation_spike_adds_reason(self) -> None:
        stable = self._stable_returns(rows=80, assets=3)
        x = np.linspace(0.0, 3.0 * np.pi, 20)
        common = 0.002 * np.sin(x) + 0.0005
        correlated = np.column_stack(
            [
                common,
                common * 1.05 + 0.00001,
                common * 0.95 - 0.00001,
            ]
        )
        prices = self._prices_from_returns(np.vstack([stable, correlated]))

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1", "AAA2"],
            price_df=prices,
            weights=[1.0 / 3.0] * 3,
            source="test",
        )

        self.assertIn("Correlation spike", result.main_reasons)

    def test_invalid_latest_price_adds_data_quality_reason(self) -> None:
        prices = self._prices_from_returns(self._stable_returns())
        prices.iloc[-1, 0] = np.nan
        prices.iloc[-3, 1] = 0.0

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            source="test",
        )

        self.assertIn("Missing or invalid price data", result.main_reasons)
        self.assertTrue(result.is_anomaly)

    def test_single_asset_correlation_features_degrade_to_zero(self) -> None:
        prices = self._prices_from_returns(self._stable_returns(assets=1))
        features = self.detector.build_feature_frame(prices, np.array([1.0]))

        self.assertTrue(np.allclose(features["correlation_mean_20d"].to_numpy(), 0.0))
        self.assertTrue(np.allclose(features["correlation_change_20d"].to_numpy(), 0.0))

        result = self.detector.evaluate_from_prices(
            tickers=["AAA0"],
            price_df=prices,
            weights=[1.0],
            source="test",
        )
        self.assertGreaterEqual(result.anomaly_score, 0.0)
        self.assertLessEqual(result.anomaly_score, 1.0)


if __name__ == "__main__":
    unittest.main()
