import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from models.crisis_warning_engine import (
    CrisisWarningArtifactStore,
    CrisisWarningEngine,
)


class FakeLoadedModel:
    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        probabilities = np.full(len(frame), 0.5, dtype=float)
        return np.column_stack([1.0 - probabilities, probabilities])


class CrisisWarningArtifactTests(unittest.TestCase):
    def _write_artifact_files(
        self,
        root: Path,
        horizon: int,
        include_model: bool = True,
        include_schema: bool = True,
        include_metadata: bool = True,
        include_background: bool = True,
    ) -> Path:
        directory = root / f"global_h{horizon}"
        directory.mkdir(parents=True, exist_ok=True)
        if include_model:
            (directory / "xgb_crisis_model.json").write_text("{}", encoding="utf-8")
        if include_schema:
            schema = {
                "feature_names": CrisisWarningEngine.feature_columns,
                "feature_count": len(CrisisWarningEngine.feature_columns),
                "horizon": horizon,
            }
            (directory / "feature_schema.json").write_text(
                json.dumps(schema),
                encoding="utf-8",
            )
        if include_metadata:
            metadata = {
                "model_name": "XGBClassifier",
                "model_version": f"test-h{horizon}",
                "training_start": "2025-01-01",
                "training_end": "2025-12-31",
                "n_observations": 300,
                "n_training_rows": 180,
                "positive_events": 16,
                "positive_rate": 0.088,
                "validation_metrics": {"roc_auc": 0.7},
                "warnings": [],
            }
            (directory / "training_metadata.json").write_text(
                json.dumps(metadata),
                encoding="utf-8",
            )
        if include_background:
            background = pd.DataFrame(
                np.zeros((3, len(CrisisWarningEngine.feature_columns))),
                columns=CrisisWarningEngine.feature_columns,
            )
            background.to_csv(directory / "shap_background_sample.csv", index=False)
        return directory

    def test_model_file_missing_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact_files(root, 5, include_model=False)
            store = CrisisWarningArtifactStore(root)

            with self.assertRaises(FileNotFoundError):
                store.load_horizon(5)

    def test_schema_file_missing_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact_files(root, 5, include_schema=False)
            store = CrisisWarningArtifactStore(root)

            with self.assertRaises(FileNotFoundError):
                store.load_horizon(5)

    def test_background_missing_degrades_explanation_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact_files(root, 5, include_background=False)
            store = CrisisWarningArtifactStore(root)

            with patch.object(CrisisWarningArtifactStore, "_load_model", return_value=FakeLoadedModel()):
                artifact = store.load_horizon(5)

            self.assertTrue(artifact.background_sample.empty)
            self.assertTrue(any("background sample" in warning for warning in artifact.load_warnings))
            self.assertEqual(artifact.metadata["model_version"], "test-h5")

    def test_horizon_artifacts_load_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact_files(root, 1)
            self._write_artifact_files(root, 5)
            store = CrisisWarningArtifactStore(root)

            with patch.object(CrisisWarningArtifactStore, "_load_model", return_value=FakeLoadedModel()):
                store.load_available(horizons=(1, 5))

            self.assertTrue(store.is_ready(1))
            self.assertTrue(store.is_ready(5))
            self.assertEqual(store.get(1).metadata["model_version"], "test-h1")
            self.assertEqual(store.get(5).metadata["model_version"], "test-h5")


if __name__ == "__main__":
    unittest.main()
