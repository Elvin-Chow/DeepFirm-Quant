import json
import unittest

import numpy as np
import pandas as pd

from models.ml_risk_engine import MLRiskEngine


class MLRiskEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MLRiskEngine()

    def _prices_from_returns(self, returns: np.ndarray) -> pd.DataFrame:
        returns = np.asarray(returns, dtype=float)
        base = np.full((1, returns.shape[1]), 100.0)
        prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
        price_matrix = np.vstack([base, prices])
        index = pd.date_range("2025-01-02", periods=len(price_matrix), freq="B")
        columns = [f"AAA{i}" for i in range(returns.shape[1])]
        return pd.DataFrame(price_matrix, index=index, columns=columns)

    def _market_returns(self, rows: int = 180, assets: int = 2) -> np.ndarray:
        x = np.linspace(0.0, 12.0 * np.pi, rows)
        columns = []
        for idx in range(assets):
            trend = 0.0004 + 0.0001 * idx
            cycle = 0.006 * np.sin(x * (1.0 + idx * 0.12) + idx)
            shock = 0.003 * np.cos(x * (1.7 + idx * 0.08) - idx)
            columns.append(trend + cycle + shock)
        return np.column_stack(columns)

    def test_normal_price_data_returns_forecast_fields(self) -> None:
        prices = self._prices_from_returns(self._market_returns())

        result = self.engine.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.6, 0.4],
            horizon=5,
            confidence_level=0.95,
            source="test",
        )

        self.assertLessEqual(result.ml_var, 0.0)
        self.assertLessEqual(result.ml_es, result.ml_var)
        self.assertGreaterEqual(result.risk_score, 0)
        self.assertLessEqual(result.risk_score, 100)
        self.assertIn(result.risk_level, {"Low", "Medium", "High", "Extreme"})
        self.assertEqual(result.model_name, "GradientBoostingRegressor")
        self.assertEqual(result.horizon, 5)
        self.assertEqual(result.confidence_level, 0.95)
        self.assertTrue(result.top_features)
        self.assertLessEqual(len(result.top_features), 5)
        self.assertEqual(result.source, "test")
        self.assertIsNotNone(result.diagnostics)
        self.assertEqual(result.diagnostics.model_name, "GradientBoostingRegressor")
        self.assertIn("breach_rate", result.diagnostics.calibration_metrics)

    def test_horizon_one_can_run(self) -> None:
        prices = self._prices_from_returns(self._market_returns())

        result = self.engine.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            horizon=1,
            confidence_level=0.95,
            source="test",
        )

        self.assertEqual(result.horizon, 1)
        self.assertLessEqual(result.ml_var, 0.0)
        self.assertLessEqual(result.ml_es, result.ml_var)

    def test_horizon_five_can_run(self) -> None:
        prices = self._prices_from_returns(self._market_returns())

        result = self.engine.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            horizon=5,
            confidence_level=0.95,
            source="test",
        )

        self.assertEqual(result.horizon, 5)
        self.assertLessEqual(result.ml_var, 0.0)
        self.assertLessEqual(result.ml_es, result.ml_var)

    def test_risk_score_uses_historical_tail_scale_before_saturating(self) -> None:
        score, level = MLRiskEngine._risk_score(0.0604, reference_loss=0.0700)

        self.assertEqual(score, 69)
        self.assertEqual(level, "High")

        score, level = MLRiskEngine._risk_score(0.0900, reference_loss=0.0700)

        self.assertEqual(score, 100)
        self.assertEqual(level, "Extreme")

    def test_insufficient_sample_uses_fallback_forecast(self) -> None:
        prices = self._prices_from_returns(self._market_returns(rows=20))

        result = self.engine.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            horizon=5,
            confidence_level=0.95,
            source="test",
        )

        self.assertEqual(result.model_name, "HistoricalFallback")
        self.assertIsNotNone(result.diagnostics)
        self.assertTrue(result.diagnostics.fallback_used)
        self.assertIn("at least 80 complete finite", result.diagnostics.fallback_reason)

    def test_single_asset_portfolio_handles_correlation_features(self) -> None:
        prices = self._prices_from_returns(self._market_returns(assets=1))
        features = self.engine.build_feature_frame(prices, np.array([1.0]))

        self.assertTrue(np.allclose(features["correlation_mean_20d"].to_numpy(), 0.0))
        self.assertTrue(np.allclose(features["correlation_max_20d"].to_numpy(), 0.0))

        result = self.engine.evaluate_from_prices(
            tickers=["AAA0"],
            price_df=prices,
            weights=[1.0],
            horizon=5,
            confidence_level=0.95,
            source="test",
        )
        self.assertLessEqual(result.ml_var, 0.0)
        self.assertIn(result.risk_level, {"Low", "Medium", "High", "Extreme"})

    def test_result_is_json_serializable(self) -> None:
        prices = self._prices_from_returns(self._market_returns())

        result = self.engine.evaluate_from_prices(
            tickers=["AAA0", "AAA1"],
            price_df=prices,
            weights=[0.5, 0.5],
            horizon=5,
            confidence_level=0.95,
            source="test",
        )
        payload = json.loads(result.model_dump_json())

        self.assertIn("ml_var", payload)
        self.assertIn("ml_es", payload)
        self.assertIn("risk_score", payload)
        self.assertIn("risk_level", payload)
        self.assertIn("top_features", payload)


if __name__ == "__main__":
    unittest.main()
