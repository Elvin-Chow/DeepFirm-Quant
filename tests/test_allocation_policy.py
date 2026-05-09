import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from models import MLRiskForecastResult, MarketRegimeResult, RiskAnomalyResult
from models.allocation_policy import AllocationPolicyEngine


class AllocationPolicyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = AllocationPolicyEngine()
        self.tickers = ["AAA", "BBB", "CCC"]

    def _prices_from_returns(self, returns: np.ndarray) -> pd.DataFrame:
        returns = np.asarray(returns, dtype=float)
        base = np.full((1, returns.shape[1]), 100.0)
        prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
        matrix = np.vstack([base, prices])
        index = pd.date_range("2025-01-02", periods=len(matrix), freq="B")
        return pd.DataFrame(
            matrix,
            index=index,
            columns=self.tickers[: returns.shape[1]],
        )

    def _low_risk_returns(self, rows: int = 180) -> np.ndarray:
        x = np.linspace(0.0, 8.0 * np.pi, rows)
        return np.column_stack(
            [
                0.0004 + 0.0010 * np.sin(x),
                0.0003 + 0.0010 * np.cos(x * 0.7),
                0.0002 + 0.0008 * np.sin(x * 1.3),
            ]
        )

    def _high_risk_returns(self, rows: int = 180) -> np.ndarray:
        x = np.linspace(0.0, 8.0 * np.pi, rows)
        common = 0.018 * np.sin(x)
        returns = np.column_stack(
            [
                common + 0.006 * np.cos(x * 1.2),
                common * 0.95 + 0.005 * np.sin(x * 0.8),
                common * 1.05 - 0.005 * np.cos(x * 1.1),
            ]
        )
        returns[-25:, :] -= 0.012
        return returns

    def test_professional_mode_preserves_manual_controls(self) -> None:
        prices = self._prices_from_returns(self._low_risk_returns())

        result = self.engine.resolve_from_prices(
            tickers=self.tickers,
            price_df=prices,
            weights=[0.5, 0.3, 0.2],
            mode="professional",
            requested_max_weight=0.62,
            requested_min_weight=0.03,
            requested_turnover_penalty=0.011,
            requested_concentration_penalty=0.012,
        )

        self.assertEqual(result.mode, "professional")
        self.assertEqual(result.max_weight, 0.62)
        self.assertEqual(result.min_weight, 0.03)
        self.assertEqual(result.turnover_penalty, 0.011)
        self.assertEqual(result.concentration_penalty, 0.012)
        self.assertEqual(result.confidence, 1.0)

    def test_smart_mode_returns_feasible_controls(self) -> None:
        prices = self._prices_from_returns(self._low_risk_returns())

        result = self.engine.resolve_from_prices(
            tickers=self.tickers,
            price_df=prices,
            weights=[1.0 / 3.0] * 3,
            mode="smart",
            requested_max_weight=0.40,
            requested_min_weight=0.02,
            requested_turnover_penalty=0.005,
            requested_concentration_penalty=0.005,
        )

        self.assertEqual(result.mode, "smart")
        self.assertGreaterEqual(result.max_weight, 1.0 / len(self.tickers))
        self.assertLessEqual(result.max_weight, 1.0)
        self.assertGreaterEqual(result.min_weight, 0.0)
        self.assertLessEqual(result.min_weight, 0.20)
        self.assertGreaterEqual(result.turnover_penalty, 0.0)
        self.assertGreaterEqual(result.concentration_penalty, 0.0)
        self.assertTrue(result.reasons)

    def test_two_asset_smart_mode_keeps_rebalance_room(self) -> None:
        prices = self._prices_from_returns(self._low_risk_returns()[:, :2])
        tickers = self.tickers[:2]

        result = self.engine.resolve_from_prices(
            tickers=tickers,
            price_df=prices,
            weights=[0.5, 0.5],
            mode="smart",
            requested_max_weight=0.40,
            requested_min_weight=0.02,
            requested_turnover_penalty=0.005,
            requested_concentration_penalty=0.005,
        )

        self.assertEqual(result.mode, "smart")
        self.assertGreater(result.max_weight, 0.55)
        self.assertNotAlmostEqual(result.max_weight, 0.50, places=3)
        self.assertTrue(
            any("Two-asset portfolio" in reason for reason in result.reasons)
        )

    def test_high_risk_sample_tightens_controls(self) -> None:
        low = self.engine.resolve_from_prices(
            tickers=self.tickers,
            price_df=self._prices_from_returns(self._low_risk_returns()),
            weights=[1.0 / 3.0] * 3,
            mode="smart",
            requested_max_weight=0.40,
            requested_min_weight=0.02,
            requested_turnover_penalty=0.005,
            requested_concentration_penalty=0.005,
        )
        high = self.engine.resolve_from_prices(
            tickers=self.tickers,
            price_df=self._prices_from_returns(self._high_risk_returns()),
            weights=[1.0 / 3.0] * 3,
            mode="smart",
            requested_max_weight=0.40,
            requested_min_weight=0.02,
            requested_turnover_penalty=0.005,
            requested_concentration_penalty=0.005,
        )

        self.assertLessEqual(high.max_weight, low.max_weight)
        self.assertGreaterEqual(high.turnover_penalty, low.turnover_penalty)
        self.assertGreaterEqual(high.concentration_penalty, low.concentration_penalty)

    def test_smart_mode_reuses_precomputed_ml_signals(self) -> None:
        prices = self._prices_from_returns(self._low_risk_returns())
        ml_result = MLRiskForecastResult(
            ml_var=0.02,
            ml_es=0.03,
            risk_score=80,
            risk_level="High",
            model_name="test",
            horizon=5,
            confidence_level=0.95,
        )
        regime_result = MarketRegimeResult(
            current_regime="High Volatility",
            smoothed_regime="High Volatility",
            regime_probabilities={"Normal": 0.1, "High Volatility": 0.8, "Crisis": 0.1},
            volatility_multiplier=1.5,
            correlation_multiplier=1.2,
            recommended_stress_level="High",
        )
        anomaly_result = RiskAnomalyResult(
            anomaly_score=0.7,
            is_anomaly=True,
            alert_level="Medium",
            decision_impact="tighten_constraints",
        )

        with patch("models.allocation_policy.MLRiskEngine") as ml_engine:
            with patch("models.allocation_policy.MarketRegimeDetector") as regime_detector:
                with patch("models.allocation_policy.RiskAnomalyDetector") as anomaly_detector:
                    result = self.engine.resolve_from_prices(
                        tickers=self.tickers,
                        price_df=prices,
                        weights=[1.0 / 3.0] * 3,
                        mode="smart",
                        requested_max_weight=0.40,
                        requested_min_weight=0.02,
                        requested_turnover_penalty=0.005,
                        requested_concentration_penalty=0.005,
                        ml_result=ml_result,
                        regime_result=regime_result,
                        anomaly_result=anomaly_result,
                    )

        ml_engine.assert_not_called()
        regime_detector.assert_not_called()
        anomaly_detector.assert_not_called()
        self.assertEqual(result.risk_level, "High")
        self.assertEqual(result.regime, "High Volatility")
        self.assertEqual(result.anomaly_impact, "tighten_constraints")


if __name__ == "__main__":
    unittest.main()
