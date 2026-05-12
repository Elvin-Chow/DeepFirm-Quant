import json
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from models.crisis_warning_engine import (
    CalibrationMapping,
    CrisisWarningArtifact,
    CrisisWarningEngine,
    CrisisWarningService,
)


class FakeProbabilityModel:
    def __init__(self, probability: float = 0.72) -> None:
        self.probability = probability

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        probabilities = np.full(len(frame), self.probability, dtype=float)
        return np.column_stack([1.0 - probabilities, probabilities])


class FakeStore:
    def __init__(self, artifact: CrisisWarningArtifact) -> None:
        self.artifact = artifact

    def get(self, horizon: int) -> CrisisWarningArtifact:
        return self.artifact


class CrisisWarningEngineTests(unittest.TestCase):
    def _prices_from_returns(self, returns: np.ndarray) -> pd.DataFrame:
        returns = np.asarray(returns, dtype=float)
        base = np.full((1, returns.shape[1]), 100.0)
        prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
        price_matrix = np.vstack([base, prices])
        index = pd.date_range("2025-01-02", periods=len(price_matrix), freq="B")
        columns = [f"AAA{i}" for i in range(returns.shape[1])]
        return pd.DataFrame(price_matrix, index=index, columns=columns)

    def _tail_rich_returns(self, rows: int = 320, assets: int = 2) -> np.ndarray:
        x = np.linspace(0.0, 20.0 * np.pi, rows)
        base = 0.0004 + 0.006 * np.sin(x)
        shocks = np.zeros(rows)
        shocks[70::19] = -0.055
        columns = []
        for idx in range(assets):
            columns.append(base + shocks + 0.001 * np.cos(x * (1.0 + idx * 0.05)))
        return np.column_stack(columns)

    def _artifact(
        self,
        probability: float = 0.72,
        calibration: CalibrationMapping | None = None,
        metadata_overrides: dict | None = None,
    ) -> CrisisWarningArtifact:
        feature_names = CrisisWarningEngine.feature_columns
        metadata = {
            "model_name": "XGBClassifier",
            "model_version": "test-version",
            "training_start": "2025-01-01",
            "training_end": "2025-12-31",
            "n_observations": 320,
            "n_training_rows": 190,
            "positive_events": 18,
            "positive_rate": 0.0947,
            "validation_metrics": {"validation_positive_events": 4.0, "roc_auc": 0.75},
            "warnings": [],
        }
        metadata.update(metadata_overrides or {})
        schema = {
            "feature_names": feature_names,
            "feature_count": len(feature_names),
            "horizon": 5,
        }
        return CrisisWarningArtifact(
            horizon=5,
            directory=Path("artifacts/crisis_warning/global_h5"),
            model=FakeProbabilityModel(probability),
            feature_schema=schema,
            metadata=metadata,
            background_sample=pd.DataFrame(columns=feature_names),
            calibration=calibration,
            load_warnings=[],
        )

    def test_future_horizon_return_uses_forward_returns(self) -> None:
        index = pd.date_range("2025-01-02", periods=5, freq="B")
        returns = pd.Series([0.01, -0.02, -0.03, 0.04, 0.05], index=index)

        future = CrisisWarningEngine.future_horizon_returns(returns, 2)

        self.assertAlmostEqual(future.iloc[0], -0.05)
        self.assertAlmostEqual(future.iloc[1], 0.01)
        self.assertTrue(np.isnan(future.iloc[-1]))

    def test_dynamic_quantile_threshold_is_shifted(self) -> None:
        index = pd.date_range("2025-01-02", periods=90, freq="B")
        returns = pd.Series(0.001, index=index)
        returns.iloc[70:75] = -0.50

        threshold = CrisisWarningEngine.dynamic_tail_threshold(returns, 1, 0.05)

        self.assertGreater(threshold.iloc[70], -0.10)
        self.assertLess(threshold.iloc[76], -0.10)

    def test_training_frame_requires_positive_tail_events(self) -> None:
        prices = self._prices_from_returns(np.full((220, 2), 0.001))

        with self.assertRaisesRegex(ValueError, "positive tail events"):
            CrisisWarningEngine.build_training_frame(
                prices,
                np.array([0.5, 0.5]),
                horizon=5,
                tail_quantile=0.05,
            )

    def test_training_frame_can_build_tail_labels(self) -> None:
        prices = self._prices_from_returns(self._tail_rich_returns())

        _, _, label_frame = CrisisWarningEngine.build_training_frame(
            prices,
            np.array([0.6, 0.4]),
            horizon=5,
            tail_quantile=0.10,
        )

        self.assertGreaterEqual(len(label_frame), CrisisWarningEngine.min_training_rows)
        self.assertGreaterEqual(
            int(label_frame["tail_event"].sum()),
            CrisisWarningEngine.min_positive_events,
        )
        self.assertTrue(np.isfinite(label_frame[CrisisWarningEngine.feature_columns].to_numpy()).all())

    def test_warning_level_thresholds(self) -> None:
        self.assertEqual(CrisisWarningEngine.warning_level(0.34), "Low")
        self.assertEqual(CrisisWarningEngine.warning_level(0.35), "Medium")
        self.assertEqual(CrisisWarningEngine.warning_level(0.60), "High")
        self.assertEqual(CrisisWarningEngine.warning_level(0.80), "Extreme")

    def test_feature_schema_order_mismatch_raises(self) -> None:
        names = CrisisWarningEngine.feature_columns.copy()
        swapped = names.copy()
        swapped[0], swapped[1] = swapped[1], swapped[0]

        with self.assertRaisesRegex(ValueError, "feature schema"):
            CrisisWarningEngine.validate_feature_schema(swapped, names)

    def test_service_formats_shap_drivers_and_reducers(self) -> None:
        prices = self._prices_from_returns(self._tail_rich_returns(rows=140))
        artifact = self._artifact(probability=0.72)
        shap_values = np.zeros(len(CrisisWarningEngine.feature_columns), dtype=float)
        shap_values[0] = 0.12
        shap_values[1] = -0.05

        with patch.object(CrisisWarningEngine, "shap_values", return_value=(shap_values, 0.42, False, [])):
            result = CrisisWarningService(store=FakeStore(artifact)).evaluate_from_prices(
                tickers=["AAA0", "AAA1"],
                price_df=prices,
                weights=[0.5, 0.5],
                horizon=5,
                source="test",
                source_detail="test detail",
                data_warnings=["sample warning"],
            )

        self.assertAlmostEqual(result.crisis_probability, 0.72)
        self.assertEqual(result.warning_level, "High")
        self.assertEqual(result.base_value, 0.42)
        self.assertEqual(result.top_risk_drivers[0].direction, "increase_risk")
        self.assertEqual(result.risk_reducers[0].direction, "decrease_risk")
        self.assertFalse(result.diagnostics.shap_fallback_used)
        self.assertEqual(result.source, "test")
        payload = json.loads(result.model_dump_json())
        self.assertIn("crisis_probability", payload)

    def test_service_warns_when_calibration_bucket_is_flat_and_near_base_rate(self) -> None:
        prices = self._prices_from_returns(self._tail_rich_returns(rows=140))
        calibration = CalibrationMapping(
            x_thresholds=np.array([0.10, 0.20, 0.30, 0.40]),
            y_thresholds=np.array([0.02, 0.04, 0.057, 0.057]),
        )
        artifact = self._artifact(
            probability=0.35,
            calibration=calibration,
            metadata_overrides={
                "positive_rate": 0.054,
                "validation_metrics": {
                    "validation_positive_events": 20.0,
                    "positive_rate": 0.05,
                    "roc_auc": 0.72,
                    "pr_auc": 0.18,
                    "calibration_error": 0.02,
                },
            },
        )

        with patch.object(CrisisWarningEngine, "shap_values", return_value=(np.zeros(len(CrisisWarningEngine.feature_columns)), 0.05, False, [])):
            result = CrisisWarningService(store=FakeStore(artifact)).evaluate_from_prices(
                tickers=["AAA0", "AAA1"],
                price_df=prices,
                weights=[0.5, 0.5],
                horizon=5,
            )

        self.assertAlmostEqual(result.crisis_probability, 0.057)
        self.assertEqual(result.diagnostics.model_health, "degraded")
        self.assertIn(
            CrisisWarningService.calibration_bucket_warning,
            result.diagnostics.warnings,
        )
        self.assertIn(
            CrisisWarningService.calibration_base_rate_warning,
            result.diagnostics.warnings,
        )

    def test_service_degrades_weak_validation_metrics(self) -> None:
        prices = self._prices_from_returns(self._tail_rich_returns(rows=140))
        artifact = self._artifact(
            probability=0.18,
            metadata_overrides={
                "validation_metrics": {
                    "validation_positive_events": 20.0,
                    "positive_rate": 0.05,
                    "roc_auc": 0.56,
                    "pr_auc": 0.055,
                    "calibration_error": 0.12,
                },
            },
        )

        with patch.object(CrisisWarningEngine, "shap_values", return_value=(np.zeros(len(CrisisWarningEngine.feature_columns)), 0.05, False, [])):
            result = CrisisWarningService(store=FakeStore(artifact)).evaluate_from_prices(
                tickers=["AAA0", "AAA1"],
                price_df=prices,
                weights=[0.5, 0.5],
                horizon=5,
            )

        self.assertEqual(result.diagnostics.model_health, "degraded")
        self.assertIn(CrisisWarningService.weak_roc_auc_warning, result.diagnostics.warnings)
        self.assertIn(CrisisWarningService.weak_pr_auc_warning, result.diagnostics.warnings)
        self.assertIn(
            CrisisWarningService.elevated_calibration_error_warning,
            result.diagnostics.warnings,
        )

    def test_service_without_calibration_keeps_raw_probability_path(self) -> None:
        prices = self._prices_from_returns(self._tail_rich_returns(rows=140))
        artifact = self._artifact(
            probability=0.31,
            metadata_overrides={
                "validation_metrics": {
                    "validation_positive_events": 20.0,
                    "positive_rate": 0.05,
                    "roc_auc": 0.72,
                    "pr_auc": 0.18,
                    "calibration_error": 0.02,
                },
            },
        )

        with patch.object(CrisisWarningEngine, "shap_values", return_value=(np.zeros(len(CrisisWarningEngine.feature_columns)), 0.05, False, [])):
            result = CrisisWarningService(store=FakeStore(artifact)).evaluate_from_prices(
                tickers=["AAA0", "AAA1"],
                price_df=prices,
                weights=[0.5, 0.5],
                horizon=5,
            )

        self.assertAlmostEqual(result.crisis_probability, 0.31)
        self.assertEqual(result.diagnostics.model_health, "ok")
        self.assertFalse(result.diagnostics.probability_calibrated)
        self.assertNotIn(
            CrisisWarningService.calibration_bucket_warning,
            result.diagnostics.warnings,
        )

    def test_service_rejects_non_finite_latest_feature_row(self) -> None:
        prices = self._prices_from_returns(self._tail_rich_returns(rows=140))
        artifact = self._artifact(probability=0.72)

        with patch(
            "models.crisis_warning_engine.MLRiskEngine.build_feature_frame",
            return_value=pd.DataFrame(
                [[np.nan] + [0.0] * (len(CrisisWarningEngine.feature_columns) - 1)],
                index=[pd.Timestamp("2025-07-01")],
                columns=CrisisWarningEngine.feature_columns,
            ),
        ):
            with self.assertRaisesRegex(ValueError, "non-finite"):
                CrisisWarningService(store=FakeStore(artifact)).evaluate_from_prices(
                    tickers=["AAA0", "AAA1"],
                    price_df=prices,
                    weights=[0.5, 0.5],
                    horizon=5,
                )


if __name__ == "__main__":
    unittest.main()
