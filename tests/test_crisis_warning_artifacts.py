import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from models.crisis_warning_artifact_hash import (
    ARTIFACT_HASH_ALGORITHM,
    compute_artifact_hash,
    sha256_file,
)
from models.crisis_warning_engine import (
    CrisisWarningArtifactStore,
    CrisisWarningEngine,
    CrisisWarningUnavailableError,
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
        include_calibration: bool = False,
        metadata_overrides: dict[str, object] | None = None,
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
        if include_background:
            background = pd.DataFrame(
                np.zeros((3, len(CrisisWarningEngine.feature_columns))),
                columns=CrisisWarningEngine.feature_columns,
            )
            background.to_csv(directory / "shap_background_sample.csv", index=False)
        if include_calibration:
            (directory / "calibration.json").write_text(
                json.dumps(
                    {
                        "method": "isotonic",
                        "x_thresholds": [0.0, 1.0],
                        "y_thresholds": [0.0, 1.0],
                    }
                ),
                encoding="utf-8",
            )
        if include_metadata:
            artifact_hash, artifact_hash_files = compute_artifact_hash(directory)
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
                "artifact_hash": artifact_hash,
                "artifact_hash_algorithm": ARTIFACT_HASH_ALGORITHM,
                "artifact_hash_files": artifact_hash_files,
                "warnings": [],
            }
            schema_path = directory / "feature_schema.json"
            if schema_path.exists():
                metadata["feature_schema_hash"] = sha256_file(schema_path)
            if metadata_overrides:
                metadata.update(metadata_overrides)
            (directory / "training_metadata.json").write_text(
                json.dumps(metadata),
                encoding="utf-8",
            )
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

    def test_partial_diversified_global_artifact_loads_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact_files(
                root,
                5,
                metadata_overrides={
                    "training_domain": "diversified_global",
                    "global_domain_complete": False,
                    "domain_coverage_status": "partial",
                    "missing_training_markets": ["jp", "tw"],
                },
            )
            store = CrisisWarningArtifactStore(root)

            with patch.object(CrisisWarningArtifactStore, "_load_model", return_value=FakeLoadedModel()):
                artifact = store.load_horizon(5)

            self.assertFalse(artifact.metadata["global_domain_complete"])
            self.assertFalse(artifact.metadata["is_global_complete"])
            self.assertEqual(
                artifact.metadata["validation_status"],
                "partial_market_coverage",
            )
            self.assertEqual(
                set(artifact.metadata["skipped_market_scope"]),
                {"jp", "tw"},
            )
            self.assertTrue(
                any("partial market coverage" in warning for warning in artifact.load_warnings)
            )

    def test_legacy_diversified_metadata_missing_contract_is_not_global_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact_files(
                root,
                5,
                metadata_overrides={
                    "training_domain": "diversified_global",
                    "training_market_scope": "cn,hk,us",
                },
            )
            store = CrisisWarningArtifactStore(root)

            with patch.object(CrisisWarningArtifactStore, "_load_model", return_value=FakeLoadedModel()):
                artifact = store.load_horizon(5)

            self.assertFalse(artifact.metadata["is_global_complete"])
            self.assertFalse(artifact.metadata["global_domain_complete"])
            self.assertEqual(
                artifact.metadata["validation_status"],
                "partial_market_coverage",
            )
            self.assertEqual(
                set(artifact.metadata["required_market_scope"]),
                {"us", "hk", "cn", "jp", "tw"},
            )
            self.assertEqual(
                set(artifact.metadata["covered_market_scope"]),
                {"cn", "hk", "us"},
            )
            self.assertEqual(
                set(artifact.metadata["skipped_market_scope"]),
                {"jp", "tw"},
            )
            self.assertTrue(
                any("partial market coverage" in warning for warning in artifact.load_warnings)
            )

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

    def test_feature_schema_hash_mismatch_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_artifact_files(
                root,
                5,
                metadata_overrides={"feature_schema_hash": "0" * 64},
            )
            store = CrisisWarningArtifactStore(root)

            with patch.object(CrisisWarningArtifactStore, "_load_model", return_value=FakeLoadedModel()):
                store.load_available(horizons=(5,))

            self.assertFalse(store.is_ready(5))
            with self.assertRaisesRegex(
                CrisisWarningUnavailableError,
                "feature schema hash",
            ):
                store.get(5)

    def test_artifact_hash_mismatch_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = self._write_artifact_files(root, 5)
            (directory / "shap_background_sample.csv").write_text(
                "tampered\n",
                encoding="utf-8",
            )
            store = CrisisWarningArtifactStore(root)

            with patch.object(CrisisWarningArtifactStore, "_load_model", return_value=FakeLoadedModel()):
                store.load_available(horizons=(5,))

            self.assertFalse(store.is_ready(5))
            with self.assertRaisesRegex(
                CrisisWarningUnavailableError,
                "artifact hash",
            ):
                store.get(5)

    def test_artifact_hash_detects_calibration_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = self._write_artifact_files(root, 5, include_calibration=True)
            (directory / "calibration.json").write_text(
                json.dumps(
                    {
                        "method": "isotonic",
                        "x_thresholds": [0.0, 1.0],
                        "y_thresholds": [0.25, 0.75],
                    }
                ),
                encoding="utf-8",
            )
            store = CrisisWarningArtifactStore(root)

            with patch.object(CrisisWarningArtifactStore, "_load_model", return_value=FakeLoadedModel()):
                store.load_available(horizons=(5,))

            self.assertFalse(store.is_ready(5))
            with self.assertRaisesRegex(
                CrisisWarningUnavailableError,
                "artifact hash",
            ):
                store.get(5)


if __name__ == "__main__":
    unittest.main()
