"""Market regime detection for portfolio-level risk context."""

from datetime import date
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from data_pipeline import MarketAligner, SmartFetcher
from models.ml_diagnostics import MLModelDiagnostics, diagnostics_from_frame
from models.request_validation import (
    normalize_tickers,
    validate_common_portfolio_contract,
)
from models.risk_engine import RiskEngine


RegimeName = Literal["Normal", "High Volatility", "Crisis"]
RegimeModelType = Literal["kmeans", "gaussian_mixture"]
StressLevel = Literal["Normal", "High", "Extreme"]


class MarketRegimeRequest(BaseModel):
    """Request payload for market regime detection."""

    tickers: List[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
    weights: List[float] = Field(default_factory=list)
    api_key: Optional[str] = Field(default=None, description="Tiingo API key for failover")
    allow_sandbox_data: bool = Field(default=False, description="Allow synthetic demo price fallback")
    market: Literal["us", "hk", "mixed"] = Field(default="us", description="Market mode")
    model_type: RegimeModelType = Field(default="kmeans", description="Regime clustering model")

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
    def validate_market_contract(self) -> "MarketRegimeRequest":
        validate_common_portfolio_contract(self.tickers, self.market, self.weights)
        return self


class MarketRegimeResult(BaseModel):
    """Result of a market regime detection run."""

    current_regime: RegimeName
    smoothed_regime: RegimeName = Field(default="Normal")
    regime_probabilities: Dict[str, float]
    transition_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    persistence_days: int = Field(default=0, ge=0)
    volatility_multiplier: float
    correlation_multiplier: float
    recommended_stress_level: StressLevel
    source: str = Field(default="unknown", description="Data source used for prices")
    source_detail: str = Field(default="unknown", description="Detailed price data provenance")
    data_warnings: List[str] = Field(default_factory=list, description="Non-fatal data quality warnings")
    diagnostics: Optional[MLModelDiagnostics] = Field(default=None)


class MarketRegimeDetector:
    """Classify the current portfolio market state using unsupervised features."""

    model_version = "regime-2026-05-09"
    feature_columns = [
        "market_return_5d",
        "market_return_20d",
        "rolling_volatility_20d",
        "rolling_volatility_60d",
        "rolling_drawdown_20d",
        "rolling_drawdown_60d",
        "average_correlation_20d",
        "max_correlation_20d",
        "downside_volatility_20d",
    ]

    regimes: Tuple[RegimeName, RegimeName, RegimeName] = (
        "Normal",
        "High Volatility",
        "Crisis",
    )
    min_return_observations = 60
    n_regimes = 3

    regime_parameters: Dict[str, Tuple[float, float, StressLevel]] = {
        "Normal": (1.0, 1.0, "Normal"),
        "High Volatility": (1.5, 1.2, "High"),
        "Crisis": (2.0, 1.5, "Extreme"),
    }

    def __init__(
        self,
        fetcher: Optional[SmartFetcher] = None,
        aligner: Optional[MarketAligner] = None,
    ) -> None:
        self.fetcher = fetcher
        self.aligner = aligner
        self.risk_engine = (
            RiskEngine(fetcher=fetcher, aligner=aligner)
            if fetcher is not None and aligner is not None
            else None
        )

    @staticmethod
    def _normalize_price_frame(price_df: pd.DataFrame) -> pd.DataFrame:
        """Return positive finite prices sorted by normalized date."""
        if price_df.empty:
            raise ValueError("price data is empty")

        prices = price_df.copy()
        idx = pd.to_datetime(prices.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        prices.index = idx.normalize()
        prices = prices.sort_index()
        prices = prices.apply(pd.to_numeric, errors="coerce")

        values = prices.to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("price data contains non-finite values")
        if (values <= 0.0).any():
            raise ValueError("price data contains non-positive values")

        return prices

    @staticmethod
    def _normalize_requested_weights(weights: List[float], n_assets: int) -> np.ndarray:
        """Return explicit finite non-negative full-investment weights."""
        if n_assets <= 0:
            raise ValueError("n_assets must be positive")
        if not weights:
            return np.ones(n_assets, dtype=float) / n_assets
        if len(weights) != n_assets:
            raise ValueError("weights length does not match asset count")

        weights_arr = np.asarray(weights, dtype=float)
        if not np.isfinite(weights_arr).all():
            raise ValueError("weights contain non-finite values")
        if (weights_arr < 0.0).any():
            raise ValueError("weights must be non-negative")

        weight_sum = float(weights_arr.sum())
        if weight_sum <= 1e-12:
            raise ValueError("weights must contain at least one positive allocation")
        return weights_arr / weight_sum

    @staticmethod
    def _rolling_correlation_features(returns_df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Compute rolling average and maximum pairwise correlation."""
        if returns_df.shape[1] < 2:
            zeros = pd.Series(0.0, index=returns_df.index)
            return zeros, zeros

        filled_returns = returns_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        average_values: List[float] = []
        max_values: List[float] = []

        for end_idx in range(len(filled_returns)):
            window = filled_returns.iloc[max(0, end_idx - 19): end_idx + 1]
            if len(window) < 3:
                average_values.append(0.0)
                max_values.append(0.0)
                continue

            corr = window.corr().replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
            upper = corr[np.triu_indices(corr.shape[0], k=1)]
            upper = upper[np.isfinite(upper)]
            if upper.size == 0:
                average_values.append(0.0)
                max_values.append(0.0)
            else:
                average_values.append(float(upper.mean()))
                max_values.append(float(upper.max()))

        return (
            pd.Series(average_values, index=returns_df.index),
            pd.Series(max_values, index=returns_df.index),
        )

    @staticmethod
    def _downside_std(values: np.ndarray) -> float:
        negative = values[values < 0.0]
        if negative.size < 2:
            return 0.0
        return float(negative.std(ddof=1))

    @classmethod
    def build_feature_frame(
        cls,
        price_df: pd.DataFrame,
        weights: np.ndarray,
    ) -> pd.DataFrame:
        """Build regime classification features from price history and portfolio weights."""
        prices = cls._normalize_price_frame(price_df)
        if prices.shape[1] != len(weights):
            raise ValueError("price data asset count does not match weights")

        asset_returns = RiskEngine.compute_log_returns(prices)
        asset_returns = RiskEngine.sanitize_returns(asset_returns)
        if len(asset_returns) < cls.min_return_observations:
            raise ValueError(
                "at least 60 complete finite return observations are required for regime detection"
            )

        portfolio_returns = pd.Series(
            asset_returns.to_numpy(dtype=float) @ weights,
            index=asset_returns.index,
            name="portfolio_return",
        )
        portfolio_growth = np.exp(portfolio_returns.cumsum())

        rolling_peak_20d = portfolio_growth.rolling(window=20, min_periods=5).max()
        rolling_peak_60d = portfolio_growth.rolling(window=60, min_periods=20).max()
        average_corr_20d, max_corr_20d = cls._rolling_correlation_features(asset_returns)

        features = pd.DataFrame(
            {
                "market_return_5d": portfolio_returns.rolling(window=5, min_periods=5).sum(),
                "market_return_20d": portfolio_returns.rolling(window=20, min_periods=20).sum(),
                "rolling_volatility_20d": portfolio_returns.rolling(window=20, min_periods=10).std(),
                "rolling_volatility_60d": portfolio_returns.rolling(window=60, min_periods=20).std(),
                "rolling_drawdown_20d": portfolio_growth / rolling_peak_20d - 1.0,
                "rolling_drawdown_60d": portfolio_growth / rolling_peak_60d - 1.0,
                "average_correlation_20d": average_corr_20d,
                "max_correlation_20d": max_corr_20d,
                "downside_volatility_20d": portfolio_returns.rolling(
                    window=20,
                    min_periods=5,
                ).apply(cls._downside_std, raw=True),
            },
            index=asset_returns.index,
        )

        features = features.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        features = features[cls.feature_columns].astype(float)
        if not np.isfinite(features.to_numpy(dtype=float)).all():
            raise ValueError("regime features contain non-finite values")
        if len(features) < cls.n_regimes:
            raise ValueError("at least 3 feature rows are required for regime detection")
        return features

    @staticmethod
    def _scale_0_1(series: pd.Series) -> pd.Series:
        values = series.astype(float)
        min_val = float(values.min())
        max_val = float(values.max())
        span = max_val - min_val
        if span <= 1e-12:
            return pd.Series(0.0, index=values.index)
        return (values - min_val) / span

    @classmethod
    def _stress_scores(cls, features: pd.DataFrame) -> pd.Series:
        """Compute relative stress scores used only for cluster ordering."""
        components = pd.DataFrame(
            {
                "loss_5d": np.maximum(-features["market_return_5d"], 0.0),
                "loss_20d": np.maximum(-features["market_return_20d"], 0.0),
                "volatility_20d": features["rolling_volatility_20d"],
                "volatility_60d": features["rolling_volatility_60d"],
                "drawdown_20d": np.maximum(-features["rolling_drawdown_20d"], 0.0),
                "drawdown_60d": np.maximum(-features["rolling_drawdown_60d"], 0.0),
                "average_correlation": np.maximum(features["average_correlation_20d"], 0.0),
                "max_correlation": np.maximum(features["max_correlation_20d"], 0.0),
                "downside_volatility": features["downside_volatility_20d"],
            },
            index=features.index,
        )
        scaled = components.apply(cls._scale_0_1, axis=0)
        weights = np.array([0.10, 0.15, 0.16, 0.14, 0.14, 0.15, 0.06, 0.04, 0.06])
        return pd.Series(scaled.to_numpy(dtype=float) @ weights, index=features.index)

    @classmethod
    def _map_labels_to_regimes(
        cls,
        labels: np.ndarray,
        features: pd.DataFrame,
    ) -> Optional[Dict[int, RegimeName]]:
        labels = np.asarray(labels, dtype=int)
        unique_labels = np.unique(labels)
        if unique_labels.size != cls.n_regimes:
            return None

        stress_scores = cls._stress_scores(features)
        cluster_scores = {
            int(label): float(stress_scores.iloc[np.flatnonzero(labels == label)].mean())
            for label in unique_labels
        }
        score_values = np.array(list(cluster_scores.values()), dtype=float)
        if not np.isfinite(score_values).all() or score_values.max() - score_values.min() <= 1e-8:
            return None

        ordered_labels = sorted(cluster_scores, key=cluster_scores.get)
        return {
            ordered_labels[0]: "Normal",
            ordered_labels[1]: "High Volatility",
            ordered_labels[2]: "Crisis",
        }

    @classmethod
    def _normalize_probabilities(cls, probabilities: Dict[str, float]) -> Dict[str, float]:
        clean = {
            regime: max(float(probabilities.get(regime, 0.0)), 0.0)
            for regime in cls.regimes
        }
        total = float(sum(clean.values()))
        if total <= 1e-12:
            return {"Normal": 1.0, "High Volatility": 0.0, "Crisis": 0.0}
        return {regime: clean[regime] / total for regime in cls.regimes}

    @staticmethod
    def _softmax_negative_distances(distances: np.ndarray) -> np.ndarray:
        finite_distances = np.asarray(distances, dtype=float)
        if not np.isfinite(finite_distances).all():
            raise ValueError("cluster distances contain non-finite values")
        logits = -finite_distances
        logits = logits - float(logits.max())
        exp_values = np.exp(logits)
        total = float(exp_values.sum())
        if total <= 1e-12:
            return np.ones_like(exp_values) / len(exp_values)
        return exp_values / total

    @classmethod
    def _fallback_result(cls, source: str) -> MarketRegimeResult:
        vol_multiplier, corr_multiplier, stress_level = cls.regime_parameters["Normal"]
        return MarketRegimeResult(
            current_regime="Normal",
            smoothed_regime="Normal",
            regime_probabilities={"Normal": 1.0, "High Volatility": 0.0, "Crisis": 0.0},
            transition_confidence=1.0,
            persistence_days=0,
            volatility_multiplier=vol_multiplier,
            correlation_multiplier=corr_multiplier,
            recommended_stress_level=stress_level,
            source=source,
            diagnostics=MLModelDiagnostics(
                model_name="RegimeFallback",
                model_version=cls.model_version,
                model_health="fallback",
                fallback_used=True,
                fallback_reason="Regime clusters were not distinct enough.",
                confidence=0.35,
            ),
        )

    @classmethod
    def _parameters_for_regime(cls, regime: RegimeName) -> Tuple[float, float, StressLevel]:
        return cls.regime_parameters[regime]

    @classmethod
    def _regime_sequence(
        cls,
        labels: np.ndarray,
        label_to_regime: Dict[int, RegimeName],
    ) -> List[RegimeName]:
        return [label_to_regime[int(label)] for label in labels if int(label) in label_to_regime]

    @classmethod
    def _persistence_days(cls, sequence: List[RegimeName], current_regime: RegimeName) -> int:
        count = 0
        for regime in reversed(sequence):
            if regime != current_regime:
                break
            count += 1
        return count

    @classmethod
    def _smoothed_regime(
        cls,
        sequence: List[RegimeName],
        current_regime: RegimeName,
        probabilities: Dict[str, float],
    ) -> RegimeName:
        if len(sequence) < 5:
            return current_regime
        persistence = cls._persistence_days(sequence, current_regime)
        latest_probability = float(probabilities.get(current_regime, 0.0))
        recent = sequence[-5:]
        recent_counts = {regime: recent.count(regime) for regime in cls.regimes}
        recent_majority = max(recent_counts, key=recent_counts.get)
        if (
            persistence < 3
            and recent_majority != current_regime
            and latest_probability < 0.55
        ):
            return recent_majority
        return current_regime

    @staticmethod
    def _transition_confidence(probabilities: Dict[str, float]) -> float:
        values = sorted(
            [float(value) for value in probabilities.values() if np.isfinite(float(value))],
            reverse=True,
        )
        if not values:
            return 0.0
        if len(values) == 1:
            return float(np.clip(values[0], 0.0, 1.0))
        return float(np.clip(values[0] - values[1], 0.0, 1.0))

    @classmethod
    def _classify_features(
        cls,
        features: pd.DataFrame,
        model_type: RegimeModelType,
        source: str,
    ) -> MarketRegimeResult:
        feature_values = features.to_numpy(dtype=float)
        distinct_rows = np.unique(np.round(feature_values, decimals=12), axis=0)
        if distinct_rows.shape[0] < cls.n_regimes:
            return cls._fallback_result(source)

        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(feature_values)
        latest_scaled = scaled_features[[-1]]

        labels: np.ndarray
        if model_type == "gaussian_mixture":
            model = GaussianMixture(n_components=cls.n_regimes, random_state=42)
            labels = model.fit_predict(scaled_features)
            label_to_regime = cls._map_labels_to_regimes(labels, features)
            if label_to_regime is None:
                return cls._fallback_result(source)

            latest_component = int(model.predict(latest_scaled)[0])
            raw_probabilities = model.predict_proba(latest_scaled)[0]
            regime_probabilities: Dict[str, float] = {regime: 0.0 for regime in cls.regimes}
            for component_idx, probability in enumerate(raw_probabilities):
                regime = label_to_regime.get(component_idx)
                if regime is not None:
                    regime_probabilities[regime] += float(probability)
            current_regime = label_to_regime[latest_component]
        else:
            model = KMeans(n_clusters=cls.n_regimes, n_init=10, random_state=42)
            labels = model.fit_predict(scaled_features)
            label_to_regime = cls._map_labels_to_regimes(labels, features)
            if label_to_regime is None:
                return cls._fallback_result(source)

            latest_label = int(model.predict(latest_scaled)[0])
            distances = np.linalg.norm(model.cluster_centers_ - latest_scaled, axis=1)
            raw_probabilities = cls._softmax_negative_distances(distances)
            regime_probabilities = {regime: 0.0 for regime in cls.regimes}
            for label, probability in enumerate(raw_probabilities):
                regime = label_to_regime.get(label)
                if regime is not None:
                    regime_probabilities[regime] += float(probability)
            current_regime = label_to_regime[latest_label]

        normalized_probabilities = cls._normalize_probabilities(regime_probabilities)
        sequence = cls._regime_sequence(labels, label_to_regime)
        persistence_days = cls._persistence_days(sequence, current_regime)
        smoothed_regime = cls._smoothed_regime(
            sequence,
            current_regime,
            normalized_probabilities,
        )
        vol_multiplier, corr_multiplier, stress_level = cls._parameters_for_regime(smoothed_regime)
        transition_confidence = cls._transition_confidence(normalized_probabilities)
        warnings: List[str] = []
        if smoothed_regime != current_regime:
            warnings.append("Current regime was smoothed because the transition signal was unstable.")
        if transition_confidence < 0.15:
            warnings.append("Regime transition confidence is low.")
        diagnostics = diagnostics_from_frame(
            model_name="GaussianMixture" if model_type == "gaussian_mixture" else "KMeans",
            model_version=cls.model_version,
            price_df=features,
            feature_count=len(cls.feature_columns),
            n_observations=len(features),
            calibration_metrics={
                "transition_confidence": transition_confidence,
                "persistence_days": float(persistence_days),
            },
            warnings=warnings,
            confidence=float(np.clip(0.50 + transition_confidence * 0.50, 0.0, 1.0)),
            positive_required=False,
        )
        return MarketRegimeResult(
            current_regime=current_regime,
            smoothed_regime=smoothed_regime,
            regime_probabilities=normalized_probabilities,
            transition_confidence=transition_confidence,
            persistence_days=persistence_days,
            volatility_multiplier=vol_multiplier,
            correlation_multiplier=corr_multiplier,
            recommended_stress_level=stress_level,
            source=source,
            diagnostics=diagnostics,
        )

    def evaluate_from_prices(
        self,
        tickers: List[str],
        price_df: pd.DataFrame,
        weights: List[float],
        model_type: RegimeModelType = "kmeans",
        source: str = "unknown",
    ) -> MarketRegimeResult:
        """Evaluate the current market regime from an already aligned price DataFrame."""
        normalized_weights = self._normalize_requested_weights(weights, len(tickers))
        features = self.build_feature_frame(price_df, normalized_weights)
        return self._classify_features(features, model_type=model_type, source=source)

    def evaluate(self, request: MarketRegimeRequest) -> MarketRegimeResult:
        """Run the full market regime detection pipeline."""
        if self.risk_engine is None or self.fetcher is None:
            raise ValueError("fetcher and aligner are required for request evaluation")

        price_df = self.risk_engine._fetch_prices(
            request.tickers,
            request.start_date,
            request.end_date,
            market_mode=request.market,
        )
        return self.evaluate_from_prices(
            tickers=request.tickers,
            price_df=price_df,
            weights=request.weights,
            model_type=request.model_type,
            source=self.fetcher.last_source,
        )
