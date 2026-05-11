"""Explainable tail-risk warning engine backed by offline artifacts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from data_pipeline import MarketAligner, SmartFetcher
from models.market_validation import MarketMode
from models.ml_risk_engine import ForecastHorizon, MLRiskEngine, RiskLevel
from models.request_validation import normalize_tickers, validate_common_portfolio_contract
from models.risk_engine import RiskEngine
from models.xgboost_runtime import import_xgboost


TargetMethod = Literal["dynamic_quantile", "fixed_threshold"]
DriverDirection = Literal["increase_risk", "decrease_risk"]
CrisisModelHealth = Literal["ok", "degraded", "unavailable"]


class CrisisWarningUnavailableError(RuntimeError):
    """Raised when the requested crisis warning artifact is not ready."""


class CrisisWarningRequest(BaseModel):
    """Request payload for explainable tail-risk warning inference."""

    tickers: List[str] = Field(..., min_length=1)
    weights: List[float] = Field(default_factory=list)
    start_date: date
    end_date: date
    market: MarketMode = Field(default="us")
    api_key: Optional[str] = Field(default=None)
    allow_sandbox_data: bool = Field(default=False)
    horizon: ForecastHorizon = Field(default=5)
    tail_quantile: float = Field(default=0.05, ge=0.01, le=0.20)
    target_method: TargetMethod = Field(default="dynamic_quantile")
    fixed_threshold: Optional[float] = Field(default=None)
    explanation_top_n: int = Field(default=5, ge=1, le=10)

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, tickers: List[str]) -> List[str]:
        return normalize_tickers(tickers)

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, end_date: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        return end_date

    @model_validator(mode="after")
    def validate_contract(self) -> "CrisisWarningRequest":
        validate_common_portfolio_contract(self.tickers, self.market, self.weights)
        if self.target_method == "fixed_threshold":
            if self.fixed_threshold is None:
                raise ValueError("fixed_threshold is required when target_method is fixed_threshold")
            if float(self.fixed_threshold) >= 0.0:
                raise ValueError("fixed_threshold must be negative")
        return self


class CrisisWarningDriver(BaseModel):
    """One feature contribution in the crisis warning explanation."""

    feature: str
    feature_value: float
    shap_value: float
    direction: DriverDirection


class CrisisWarningDiagnostics(BaseModel):
    """Operational diagnostics for crisis warning inference."""

    model_health: CrisisModelHealth = Field(default="ok")
    asof_date: str = Field(default="")
    training_start: str = Field(default="")
    training_end: str = Field(default="")
    n_observations: int = Field(default=0, ge=0)
    n_training_rows: int = Field(default=0, ge=0)
    positive_events: int = Field(default=0, ge=0)
    positive_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    validation_metrics: Dict[str, float] = Field(default_factory=dict)
    validation_positive_events: int = Field(default=0, ge=0)
    probability_calibrated: bool = Field(default=False)
    shap_fallback_used: bool = Field(default=False)
    feature_count: int = Field(default=0, ge=0)
    warnings: List[str] = Field(default_factory=list)


class CrisisWarningResult(BaseModel):
    """Response payload for explainable tail-risk warning inference."""

    crisis_probability: float = Field(ge=0.0, le=1.0)
    warning_level: RiskLevel
    model_name: str
    model_version: str
    horizon: ForecastHorizon
    target_definition: str
    base_value: float
    top_risk_drivers: List[CrisisWarningDriver] = Field(default_factory=list)
    risk_reducers: List[CrisisWarningDriver] = Field(default_factory=list)
    explanation: str
    diagnostics: CrisisWarningDiagnostics
    source: str = Field(default="unknown")
    source_detail: str = Field(default="unknown")
    data_warnings: List[str] = Field(default_factory=list)


@dataclass(frozen=True)
class CalibrationMapping:
    """Serializable one-dimensional probability calibration mapping."""

    x_thresholds: np.ndarray
    y_thresholds: np.ndarray

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Optional["CalibrationMapping"]:
        if payload.get("method") != "isotonic":
            return None
        x_values = np.asarray(payload.get("x_thresholds", []), dtype=float)
        y_values = np.asarray(payload.get("y_thresholds", []), dtype=float)
        if x_values.size < 2 or x_values.shape != y_values.shape:
            return None
        finite = np.isfinite(x_values) & np.isfinite(y_values)
        x_values = x_values[finite]
        y_values = y_values[finite]
        if x_values.size < 2:
            return None
        order = np.argsort(x_values)
        return cls(x_values[order], np.clip(y_values[order], 0.0, 1.0))

    def predict(self, probability: float) -> float:
        value = float(np.clip(probability, 0.0, 1.0))
        calibrated = float(np.interp(value, self.x_thresholds, self.y_thresholds))
        return float(np.clip(calibrated, 0.0, 1.0))


@dataclass
class CrisisWarningArtifact:
    """Loaded model artifact and its supporting metadata."""

    horizon: ForecastHorizon
    directory: Path
    model: Any
    feature_schema: dict[str, Any]
    metadata: dict[str, Any]
    background_sample: pd.DataFrame
    calibration: Optional[CalibrationMapping] = None
    load_warnings: List[str] = None

    @property
    def feature_names(self) -> list[str]:
        names = self.feature_schema.get("feature_names", [])
        return [str(name) for name in names]

    @property
    def model_name(self) -> str:
        return str(self.metadata.get("model_name") or "XGBClassifier")

    @property
    def model_version(self) -> str:
        return str(self.metadata.get("model_version") or "crisis-warning-unversioned")


class CrisisWarningEngine:
    """Build crisis warning features, labels, levels, and explanations."""

    model_name = "XGBClassifier"
    feature_columns = MLRiskEngine.feature_columns
    schema_version = "crisis-warning-features-v1"
    min_return_observations = 180
    min_training_rows = 120
    min_positive_events = 10
    threshold_window = 252
    min_threshold_observations = 60

    @staticmethod
    def portfolio_returns(price_df: pd.DataFrame, weights: np.ndarray) -> pd.Series:
        prices = MLRiskEngine._normalize_price_frame(price_df)
        asset_returns = RiskEngine.compute_log_returns(prices)
        asset_returns = RiskEngine.sanitize_returns(asset_returns)
        if len(asset_returns) < CrisisWarningEngine.min_return_observations:
            raise ValueError(
                "at least 180 complete finite return observations are required for crisis warning"
            )
        if asset_returns.shape[1] != len(weights):
            raise ValueError("price data asset count does not match weights")
        return pd.Series(
            asset_returns.to_numpy(dtype=float) @ weights,
            index=asset_returns.index,
            name="portfolio_return",
        )

    @staticmethod
    def future_horizon_returns(portfolio_returns: pd.Series, horizon: ForecastHorizon) -> pd.Series:
        future = portfolio_returns.shift(-1).rolling(
            window=int(horizon),
            min_periods=int(horizon),
        ).sum()
        if horizon > 1:
            future = future.shift(-(int(horizon) - 1))
        return future

    @classmethod
    def dynamic_tail_threshold(
        cls,
        portfolio_returns: pd.Series,
        horizon: ForecastHorizon,
        tail_quantile: float,
    ) -> pd.Series:
        historical_horizon_return = portfolio_returns.rolling(
            window=int(horizon),
            min_periods=int(horizon),
        ).sum()
        return historical_horizon_return.rolling(
            window=cls.threshold_window,
            min_periods=cls.min_threshold_observations,
        ).quantile(float(tail_quantile)).shift(1)

    @classmethod
    def build_label_frame(
        cls,
        features: pd.DataFrame,
        portfolio_returns: pd.Series,
        horizon: ForecastHorizon,
        tail_quantile: float = 0.05,
        target_method: TargetMethod = "dynamic_quantile",
        fixed_threshold: Optional[float] = None,
    ) -> pd.DataFrame:
        future_returns = cls.future_horizon_returns(portfolio_returns, horizon)
        if target_method == "fixed_threshold":
            if fixed_threshold is None or float(fixed_threshold) >= 0.0:
                raise ValueError("fixed_threshold must be provided as a negative value")
            threshold = pd.Series(float(fixed_threshold), index=portfolio_returns.index)
        else:
            threshold = cls.dynamic_tail_threshold(portfolio_returns, horizon, tail_quantile)

        labels = (future_returns < threshold).astype(float)
        label_frame = features.copy()
        label_frame["future_horizon_return"] = future_returns
        label_frame["tail_threshold"] = threshold
        label_frame["tail_event"] = labels
        return label_frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")

    @classmethod
    def build_training_frame(
        cls,
        price_df: pd.DataFrame,
        weights: np.ndarray,
        horizon: ForecastHorizon,
        tail_quantile: float = 0.05,
        target_method: TargetMethod = "dynamic_quantile",
        fixed_threshold: Optional[float] = None,
    ) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        prices = MLRiskEngine._normalize_price_frame(price_df)
        portfolio_returns = cls.portfolio_returns(prices, weights)
        features = MLRiskEngine.build_feature_frame(prices, weights)
        label_frame = cls.build_label_frame(
            features=features,
            portfolio_returns=portfolio_returns,
            horizon=horizon,
            tail_quantile=tail_quantile,
            target_method=target_method,
            fixed_threshold=fixed_threshold,
        )
        cls.validate_training_frame(label_frame)
        return features, portfolio_returns, label_frame

    @classmethod
    def validate_training_frame(cls, label_frame: pd.DataFrame) -> None:
        if len(label_frame) < cls.min_training_rows:
            raise ValueError("at least 120 complete training rows are required for crisis warning")
        positives = int(label_frame["tail_event"].sum())
        negatives = int(len(label_frame) - positives)
        if positives < cls.min_positive_events:
            raise ValueError("at least 10 positive tail events are required for crisis warning")
        if negatives <= 0:
            raise ValueError("both positive and negative tail-event classes are required")

        feature_values = label_frame[cls.feature_columns].to_numpy(dtype=float)
        if not np.isfinite(feature_values).all():
            raise ValueError("training features contain non-finite values")

    @staticmethod
    def warning_level(probability: float) -> RiskLevel:
        value = float(np.clip(probability, 0.0, 1.0))
        if value < 0.35:
            return "Low"
        if value < 0.60:
            return "Medium"
        if value < 0.80:
            return "High"
        return "Extreme"

    @staticmethod
    def target_definition(
        horizon: ForecastHorizon,
        tail_quantile: float,
        target_method: TargetMethod,
        fixed_threshold: Optional[float],
    ) -> str:
        if target_method == "fixed_threshold":
            threshold = float(fixed_threshold) if fixed_threshold is not None else 0.0
            return (
                f"Future {horizon}D portfolio log return below fixed "
                f"{threshold:.4f} threshold."
            )
        return (
            f"Future {horizon}D portfolio log return below trailing "
            f"{tail_quantile:.0%} historical {horizon}D return threshold."
        )

    @staticmethod
    def validate_feature_schema(feature_names: Sequence[str], expected_names: Sequence[str]) -> None:
        if list(feature_names) != list(expected_names):
            raise ValueError("feature schema does not match the crisis warning artifact")

    @staticmethod
    def _sigmoid(value: float) -> float:
        return float(1.0 / (1.0 + np.exp(-float(value))))

    @staticmethod
    def _coerce_shap_values(values: Any) -> np.ndarray:
        if isinstance(values, list):
            selected = values[-1]
        else:
            selected = values
        arr = np.asarray(selected, dtype=float)
        if arr.ndim == 3:
            arr = arr[:, :, -1]
        if arr.ndim == 2:
            arr = arr[0]
        return np.asarray(arr, dtype=float).reshape(-1)

    @staticmethod
    def _coerce_expected_value(value: Any) -> float:
        if isinstance(value, (list, tuple, np.ndarray)):
            arr = np.asarray(value, dtype=float).reshape(-1)
            if arr.size:
                return float(arr[-1])
        return float(value)

    @classmethod
    def shap_values(
        cls,
        artifact: CrisisWarningArtifact,
        latest_features: pd.DataFrame,
    ) -> tuple[np.ndarray, float, bool, list[str]]:
        warnings: list[str] = []
        feature_names = artifact.feature_names
        background = artifact.background_sample
        if not background.empty:
            background = background[feature_names]

        try:
            import shap

            if background.empty:
                raise ValueError("SHAP background sample is unavailable")
            explainer = shap.TreeExplainer(
                artifact.model,
                data=background,
                model_output="probability",
            )
            shap_raw = explainer.shap_values(latest_features[feature_names])
            shap_values = cls._coerce_shap_values(shap_raw)
            expected = cls._coerce_expected_value(explainer.expected_value)
            if shap_values.shape[0] != len(feature_names) or not np.isfinite(shap_values).all():
                raise ValueError("SHAP values have an invalid shape")
            return shap_values, float(np.clip(expected, 0.0, 1.0)), False, warnings
        except Exception as exc:
            warnings.append(f"SHAP explanation used native XGBoost contribution fallback: {exc}")

        try:
            xgb = import_xgboost()

            booster = artifact.model.get_booster()
            matrix = xgb.DMatrix(latest_features[feature_names], feature_names=feature_names)
            contribs = booster.predict(matrix, pred_contribs=True)
            row = np.asarray(contribs, dtype=float)[0]
            values = row[:-1]
            base_margin = float(row[-1])
            if values.shape[0] != len(feature_names) or not np.isfinite(values).all():
                raise ValueError("native contribution values have an invalid shape")
            return values, cls._sigmoid(base_margin), True, warnings
        except Exception as exc:
            warnings.append(f"Feature contribution explanation is unavailable: {exc}")
            return np.zeros(len(feature_names), dtype=float), 0.0, True, warnings

    @staticmethod
    def format_drivers(
        feature_names: Sequence[str],
        feature_values: Sequence[float],
        shap_values: Sequence[float],
        top_n: int,
    ) -> tuple[list[CrisisWarningDriver], list[CrisisWarningDriver]]:
        rows = []
        for name, value, shap_value in zip(feature_names, feature_values, shap_values):
            if not np.isfinite(float(value)) or not np.isfinite(float(shap_value)):
                continue
            rows.append((str(name), float(value), float(shap_value)))

        positive = sorted(
            (row for row in rows if row[2] > 0.0),
            key=lambda row: row[2],
            reverse=True,
        )[:top_n]
        negative = sorted(
            (row for row in rows if row[2] < 0.0),
            key=lambda row: row[2],
        )[:top_n]

        drivers = [
            CrisisWarningDriver(
                feature=name,
                feature_value=value,
                shap_value=shap_value,
                direction="increase_risk",
            )
            for name, value, shap_value in positive
        ]
        reducers = [
            CrisisWarningDriver(
                feature=name,
                feature_value=value,
                shap_value=shap_value,
                direction="decrease_risk",
            )
            for name, value, shap_value in negative
        ]
        return drivers, reducers

    @staticmethod
    def explanation(probability: float, level: RiskLevel, horizon: ForecastHorizon) -> str:
        return (
            f"The model estimates a {probability:.1%} probability that the portfolio enters "
            f"a {horizon}D tail-risk event. Warning level is {level}. This is a risk alert, "
            "not a return forecast or trading recommendation."
        )


class CrisisWarningArtifactStore:
    """Load and validate crisis warning artifacts from disk."""

    def __init__(
        self,
        artifact_root: Path | str = Path("artifacts/crisis_warning"),
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self.logger = logger or logging.getLogger(__name__)
        self._artifacts: dict[int, CrisisWarningArtifact] = {}
        self._errors: dict[int, str] = {}

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name} must contain a JSON object")
        return payload

    @staticmethod
    def _load_model(path: Path) -> Any:
        try:
            xgb = import_xgboost()
        except Exception as exc:
            raise RuntimeError("xgboost is required to load crisis warning artifacts") from exc
        model = xgb.XGBClassifier()
        model.load_model(str(path))
        return model

    def directory_for_horizon(self, horizon: ForecastHorizon) -> Path:
        return self.artifact_root / f"global_h{int(horizon)}"

    def load_horizon(self, horizon: ForecastHorizon) -> CrisisWarningArtifact:
        directory = self.directory_for_horizon(horizon)
        model_path = directory / "xgb_crisis_model.json"
        schema_path = directory / "feature_schema.json"
        metadata_path = directory / "training_metadata.json"
        background_path = directory / "shap_background_sample.csv"
        calibration_path = directory / "calibration.json"

        for required_path in (model_path, schema_path, metadata_path):
            if not required_path.exists():
                raise FileNotFoundError(f"missing crisis warning artifact file: {required_path}")

        model = self._load_model(model_path)
        schema = self._read_json(schema_path)
        metadata = self._read_json(metadata_path)
        feature_names = [str(name) for name in schema.get("feature_names", [])]
        CrisisWarningEngine.validate_feature_schema(feature_names, CrisisWarningEngine.feature_columns)
        if int(schema.get("horizon", horizon)) != int(horizon):
            raise ValueError("artifact horizon does not match its directory")

        warnings: list[str] = []
        if background_path.exists():
            background = pd.read_csv(background_path)
            missing = [name for name in feature_names if name not in background.columns]
            if missing:
                warnings.append("SHAP background sample is missing expected feature columns.")
                background = pd.DataFrame(columns=feature_names)
            else:
                background = background[feature_names].apply(pd.to_numeric, errors="coerce")
                background = background.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        else:
            warnings.append("SHAP background sample is unavailable.")
            background = pd.DataFrame(columns=feature_names)

        calibration = None
        if calibration_path.exists():
            calibration = CalibrationMapping.from_json(self._read_json(calibration_path))
            if calibration is None:
                warnings.append("Probability calibration artifact could not be read.")

        return CrisisWarningArtifact(
            horizon=horizon,
            directory=directory,
            model=model,
            feature_schema=schema,
            metadata=metadata,
            background_sample=background,
            calibration=calibration,
            load_warnings=warnings,
        )

    def load_available(self, horizons: Iterable[ForecastHorizon] = (1, 5)) -> None:
        self._artifacts.clear()
        self._errors.clear()
        for horizon in horizons:
            try:
                self._artifacts[int(horizon)] = self.load_horizon(horizon)
            except Exception as exc:
                self._errors[int(horizon)] = str(exc)
                self.logger.warning(
                    "crisis warning artifact unavailable horizon=%s error=%s",
                    horizon,
                    exc,
                )

    def get(self, horizon: ForecastHorizon) -> CrisisWarningArtifact:
        artifact = self._artifacts.get(int(horizon))
        if artifact is None:
            detail = self._errors.get(int(horizon), "artifact has not been loaded")
            raise CrisisWarningUnavailableError(detail)
        return artifact

    def ensure(self, horizon: ForecastHorizon) -> CrisisWarningArtifact:
        """Load a horizon artifact on demand and return it."""
        horizon_key = int(horizon)
        artifact = self._artifacts.get(horizon_key)
        if artifact is not None:
            return artifact
        try:
            artifact = self.load_horizon(horizon)
        except Exception as exc:
            self._errors[horizon_key] = str(exc)
            self.logger.warning(
                "crisis warning artifact unavailable horizon=%s error=%s",
                horizon,
                exc,
            )
            raise CrisisWarningUnavailableError(str(exc)) from exc
        self._artifacts[horizon_key] = artifact
        self._errors.pop(horizon_key, None)
        return artifact

    def is_ready(self, horizon: ForecastHorizon) -> bool:
        return int(horizon) in self._artifacts


class CrisisWarningService:
    """Orchestrate stateless crisis warning inference."""

    def __init__(
        self,
        store: Optional[CrisisWarningArtifactStore] = None,
        aligner: Optional[MarketAligner] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.store = store or CrisisWarningArtifactStore(logger=logger)
        self.aligner = aligner or MarketAligner()
        self.logger = logger or logging.getLogger(__name__)

    def load_artifacts(self) -> None:
        self.store.load_available()

    def _artifact_for_horizon(self, horizon: ForecastHorizon) -> CrisisWarningArtifact:
        try:
            return self.store.get(horizon)
        except CrisisWarningUnavailableError as exc:
            if str(exc) != "artifact has not been loaded":
                raise
        ensure = getattr(self.store, "ensure", None)
        if callable(ensure):
            return ensure(horizon)
        raise

    def evaluate(self, request: CrisisWarningRequest) -> CrisisWarningResult:
        self._artifact_for_horizon(request.horizon)
        fetcher = SmartFetcher(
            api_key=request.api_key,
            allow_sandbox_data=request.allow_sandbox_data,
        )
        risk_engine = RiskEngine(fetcher=fetcher, aligner=self.aligner)
        price_df = risk_engine._fetch_prices(
            request.tickers,
            request.start_date,
            request.end_date,
            market_mode=request.market,
        )
        return self.evaluate_from_prices(
            tickers=request.tickers,
            price_df=price_df,
            weights=request.weights,
            horizon=request.horizon,
            tail_quantile=request.tail_quantile,
            target_method=request.target_method,
            fixed_threshold=request.fixed_threshold,
            explanation_top_n=request.explanation_top_n,
            source=fetcher.last_source,
            source_detail=fetcher.last_source_detail,
            data_warnings=list(fetcher.data_warnings),
        )

    @staticmethod
    def _metadata_float(metadata: dict[str, Any], key: str, default: float = 0.0) -> float:
        try:
            value = float(metadata.get(key, default))
            if np.isfinite(value):
                return value
        except Exception:
            pass
        return default

    @staticmethod
    def _metadata_int(metadata: dict[str, Any], key: str, default: int = 0) -> int:
        try:
            return max(int(metadata.get(key, default)), 0)
        except Exception:
            return default

    @staticmethod
    def _clean_metrics(metrics: dict[str, Any]) -> dict[str, float]:
        clean: dict[str, float] = {}
        for key, value in metrics.items():
            try:
                numeric = float(value)
            except Exception:
                continue
            if np.isfinite(numeric):
                clean[str(key)] = numeric
        return clean

    def _diagnostics(
        self,
        artifact: CrisisWarningArtifact,
        latest_features: pd.DataFrame,
        shap_fallback_used: bool,
        warnings: Sequence[str],
    ) -> CrisisWarningDiagnostics:
        metadata = artifact.metadata
        metadata_warnings = [str(item) for item in metadata.get("warnings", []) or []]
        all_warnings = list(dict.fromkeys([*metadata_warnings, *(artifact.load_warnings or []), *warnings]))
        validation_metrics = self._clean_metrics(metadata.get("validation_metrics", {}) or {})
        model_health: CrisisModelHealth = "degraded" if all_warnings else "ok"
        if str(metadata.get("model_health", "")).lower() == "degraded":
            model_health = "degraded"

        asof = ""
        if not latest_features.empty:
            asof = pd.Timestamp(latest_features.index[-1]).date().isoformat()

        return CrisisWarningDiagnostics(
            model_health=model_health,
            asof_date=asof,
            training_start=str(metadata.get("training_start") or ""),
            training_end=str(metadata.get("training_end") or ""),
            n_observations=self._metadata_int(metadata, "n_observations"),
            n_training_rows=self._metadata_int(metadata, "n_training_rows"),
            positive_events=self._metadata_int(metadata, "positive_events"),
            positive_rate=self._metadata_float(metadata, "positive_rate"),
            validation_metrics=validation_metrics,
            validation_positive_events=self._metadata_int(
                validation_metrics,
                "validation_positive_events",
            ),
            probability_calibrated=artifact.calibration is not None,
            shap_fallback_used=bool(shap_fallback_used),
            feature_count=len(artifact.feature_names),
            warnings=all_warnings,
        )

    def evaluate_from_prices(
        self,
        tickers: Sequence[str],
        price_df: pd.DataFrame,
        weights: Sequence[float],
        horizon: ForecastHorizon = 5,
        tail_quantile: float = 0.05,
        target_method: TargetMethod = "dynamic_quantile",
        fixed_threshold: Optional[float] = None,
        explanation_top_n: int = 5,
        source: str = "unknown",
        source_detail: str = "unknown",
        data_warnings: Optional[Sequence[str]] = None,
    ) -> CrisisWarningResult:
        artifact = self._artifact_for_horizon(horizon)
        n_assets = len(tickers)
        normalized_weights = RiskEngine._normalize_weights(list(weights), n_assets)
        prices = MLRiskEngine._normalize_price_frame(price_df)
        features = MLRiskEngine.build_feature_frame(prices, normalized_weights)
        feature_names = artifact.feature_names
        CrisisWarningEngine.validate_feature_schema(feature_names, list(features.columns))

        latest_features = features.iloc[[-1]].replace([np.inf, -np.inf], np.nan)
        if latest_features.isna().any().any():
            raise ValueError("latest crisis warning feature row contains non-finite values")
        latest_features = latest_features[feature_names]

        raw_probability = float(artifact.model.predict_proba(latest_features)[0, 1])
        probability = (
            artifact.calibration.predict(raw_probability)
            if artifact.calibration is not None
            else raw_probability
        )
        probability = float(np.clip(probability, 0.0, 1.0))
        level = CrisisWarningEngine.warning_level(probability)

        shap_values, base_value, shap_fallback_used, shap_warnings = CrisisWarningEngine.shap_values(
            artifact,
            latest_features,
        )
        drivers, reducers = CrisisWarningEngine.format_drivers(
            feature_names=feature_names,
            feature_values=latest_features.iloc[0].to_numpy(dtype=float),
            shap_values=shap_values,
            top_n=int(explanation_top_n),
        )
        diagnostics = self._diagnostics(
            artifact=artifact,
            latest_features=latest_features,
            shap_fallback_used=shap_fallback_used,
            warnings=shap_warnings,
        )

        target_definition = str(artifact.metadata.get("target_definition") or "") or CrisisWarningEngine.target_definition(
            horizon=horizon,
            tail_quantile=tail_quantile,
            target_method=target_method,
            fixed_threshold=fixed_threshold,
        )

        return CrisisWarningResult(
            crisis_probability=probability,
            warning_level=level,
            model_name=artifact.model_name,
            model_version=artifact.model_version,
            horizon=horizon,
            target_definition=target_definition,
            base_value=float(np.clip(base_value, 0.0, 1.0)),
            top_risk_drivers=drivers,
            risk_reducers=reducers,
            explanation=CrisisWarningEngine.explanation(probability, level, horizon),
            diagnostics=diagnostics,
            source=source,
            source_detail=source_detail,
            data_warnings=list(data_warnings or []),
        )
