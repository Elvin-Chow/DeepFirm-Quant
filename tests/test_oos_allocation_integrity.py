import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from backend.schemas import PortfolioOptimizeRequest
from backend.services import PortfolioAnalysisService
from models import (
    MLRiskForecastResult,
    MLModelDiagnostics,
    MarketRegimeResult,
    RiskAnomalyResult,
    RiskEngine,
)


class FakeFetcher:
    def __init__(self) -> None:
        self.last_source = "cache"
        self.last_source_detail = "cache (test)"
        self.data_warnings: list[str] = []
        self.allow_sandbox_data = False


class OOSAllocationIntegrityTests(unittest.TestCase):
    tickers = ["AAA", "BBB"]

    def _price_frame_with_test_crisis(self) -> pd.DataFrame:
        rows = 180
        x = np.linspace(0.0, 10.0 * np.pi, rows)
        returns = np.column_stack(
            [
                0.0004 + 0.0010 * np.sin(x),
                0.0003 + 0.0010 * np.cos(x * 0.8),
            ]
        )
        crisis_window = 36
        stress_x = np.linspace(0.0, 6.0 * np.pi, crisis_window)
        returns[-crisis_window:, :] = np.column_stack(
            [
                -0.012 + 0.035 * np.sin(stress_x),
                -0.010 + 0.032 * np.cos(stress_x),
            ]
        )
        base = np.full((1, returns.shape[1]), 100.0)
        prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
        matrix = np.vstack([base, prices])
        index = pd.date_range("2026-01-02", periods=len(matrix), freq="B")
        return pd.DataFrame(matrix, index=index, columns=self.tickers)

    def _benchmark_frame(self, price_df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Date": price_df.index,
                "Close": 100.0 * np.exp(np.linspace(0.0, 0.04, len(price_df))),
            }
        )

    def _payload(self, price_df: pd.DataFrame) -> PortfolioOptimizeRequest:
        return PortfolioOptimizeRequest(
            tickers=self.tickers,
            start_date=pd.Timestamp(price_df.index[0]).date(),
            end_date=pd.Timestamp(price_df.index[-1]).date(),
            weights=[0.5, 0.5],
            allocation_mode="smart",
            backtest_enabled=True,
            test_ratio=0.20,
            risk_free_rate=0.0,
            use_market_cap_prior=False,
            oos_guard_enabled=True,
        )

    def _train_asof(self, price_df: pd.DataFrame) -> str:
        returns_df = RiskEngine.compute_log_returns(price_df)
        train_df, _ = RiskEngine.split_returns(returns_df, 0.20)
        return train_df.index[-1].strftime("%Y-%m-%d")

    def _diagnostics(self, asof_date: str, confidence: float = 0.9) -> MLModelDiagnostics:
        return MLModelDiagnostics(
            model_name="test",
            model_version="test",
            asof_date=asof_date,
            confidence=confidence,
        )

    def test_smart_allocation_uses_train_asof_when_test_window_has_crisis(self) -> None:
        service = PortfolioAnalysisService()
        price_df = self._price_frame_with_test_crisis()
        train_asof = self._train_asof(price_df)
        seen_asofs: dict[str, list[str]] = {"ml": [], "regime": [], "anomaly": []}

        def frame_asof(frame: pd.DataFrame) -> str:
            return pd.Timestamp(frame.index[-1]).date().isoformat()

        def ml_eval(**kwargs) -> MLRiskForecastResult:
            asof = frame_asof(kwargs["price_df"])
            seen_asofs["ml"].append(asof)
            future_signal = asof > train_asof
            return MLRiskForecastResult(
                ml_var=-0.06 if future_signal else -0.005,
                ml_es=-0.08 if future_signal else -0.008,
                risk_score=95 if future_signal else 12,
                risk_level="Extreme" if future_signal else "Low",
                model_name="test",
                horizon=5,
                confidence_level=0.95,
                diagnostics=self._diagnostics(asof),
            )

        def regime_eval(**kwargs) -> MarketRegimeResult:
            asof = frame_asof(kwargs["price_df"])
            seen_asofs["regime"].append(asof)
            future_signal = asof > train_asof
            regime = "Crisis" if future_signal else "Normal"
            return MarketRegimeResult(
                current_regime=regime,
                smoothed_regime=regime,
                regime_probabilities={
                    "Normal": 0.0 if future_signal else 1.0,
                    "High Volatility": 0.0,
                    "Crisis": 1.0 if future_signal else 0.0,
                },
                volatility_multiplier=2.0 if future_signal else 1.0,
                correlation_multiplier=1.5 if future_signal else 1.0,
                recommended_stress_level="Extreme" if future_signal else "Normal",
                diagnostics=self._diagnostics(asof),
            )

        def anomaly_eval(**kwargs) -> RiskAnomalyResult:
            asof = frame_asof(kwargs["price_df"])
            seen_asofs["anomaly"].append(asof)
            future_signal = asof > train_asof
            return RiskAnomalyResult(
                anomaly_score=0.95 if future_signal else 0.10,
                is_anomaly=future_signal,
                alert_level="Extreme" if future_signal else "Low",
                decision_impact="force_oos_guard" if future_signal else "none",
                diagnostics=self._diagnostics(asof),
            )

        ml_engine = Mock()
        ml_engine.return_value.evaluate_from_prices.side_effect = ml_eval
        regime_detector = Mock()
        regime_detector.return_value.evaluate_from_prices.side_effect = regime_eval
        anomaly_detector = Mock()
        anomaly_detector.return_value.evaluate_from_prices.side_effect = anomaly_eval

        with patch.object(
            service,
            "fetch_benchmark_prices",
            return_value=self._benchmark_frame(price_df),
        ), patch(
            "models.allocation_policy.MLRiskEngine",
            ml_engine,
        ), patch(
            "models.allocation_policy.MarketRegimeDetector",
            regime_detector,
        ), patch(
            "models.allocation_policy.RiskAnomalyDetector",
            anomaly_detector,
        ):
            result = service.optimize_portfolio_from_prices(
                self._payload(price_df),
                FakeFetcher(),
                price_df,
                portfolio_source="cache",
                portfolio_source_detail="cache (test)",
            )

        self.assertIsNotNone(result.allocation_policy)
        policy = result.allocation_policy
        self.assertEqual(policy.policy_asof, train_asof)
        self.assertTrue(policy.oos_leakage_guard)
        self.assertEqual(policy.risk_level, "Low")
        self.assertEqual(policy.regime, "Normal")
        self.assertEqual(policy.anomaly_impact, "none")
        self.assertGreater(policy.max_weight, 0.70)
        self.assertLess(policy.turnover_penalty, 0.015)
        self.assertEqual(seen_asofs["ml"], [train_asof])
        self.assertEqual(seen_asofs["regime"], [train_asof])
        self.assertEqual(seen_asofs["anomaly"], [train_asof])
        self.assertEqual(result.policy_asof, train_asof)
        self.assertTrue(result.oos_leakage_guard)

    def test_optimizer_rejects_precomputed_signal_after_train_asof(self) -> None:
        service = PortfolioAnalysisService()
        price_df = self._price_frame_with_test_crisis()
        full_sample_asof = pd.Timestamp(price_df.index[-1]).date().isoformat()
        payload = self._payload(price_df)
        ml_result = MLRiskForecastResult(
            ml_var=-0.06,
            ml_es=-0.08,
            risk_score=95,
            risk_level="Extreme",
            model_name="test",
            horizon=5,
            confidence_level=0.95,
            diagnostics=self._diagnostics(full_sample_asof),
        )

        with self.assertRaisesRegex(ValueError, "回测完整性错误"):
            service.optimize_portfolio_from_prices(
                payload,
                FakeFetcher(),
                price_df,
                portfolio_source="cache",
                portfolio_source_detail="cache (test)",
                ml_result=ml_result,
            )


if __name__ == "__main__":
    unittest.main()
