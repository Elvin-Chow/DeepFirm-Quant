"""ML risk forecasting engine for portfolio downside risk."""

from datetime import date
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator
from sklearn.ensemble import GradientBoostingRegressor

from data_pipeline import MarketAligner, SmartFetcher
from models.market_validation import MarketMode
from models.ml_diagnostics import MLModelDiagnostics, diagnostics_from_frame
from models.request_validation import (
    normalize_tickers,
    validate_common_portfolio_contract,
)
from models.risk_engine import RiskEngine


RiskLevel = Literal["Low", "Medium", "High", "Extreme"]
ForecastHorizon = Literal[1, 5]


class MLRiskForecastRequest(BaseModel):
    """Request payload for portfolio ML risk forecasting."""

    tickers: List[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
    weights: List[float] = Field(default_factory=list)
    horizon: ForecastHorizon = Field(default=5, description="Forecast horizon in trading days")
    confidence_level: float = Field(default=0.95, ge=0.90, le=0.99)
    api_key: Optional[str] = Field(default=None, description="Tiingo API key for failover")
    allow_sandbox_data: bool = Field(default=False, description="Allow synthetic demo price fallback")
    market: MarketMode = Field(default="us", description="Market mode")

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
    def validate_market_contract(self) -> "MLRiskForecastRequest":
        validate_common_portfolio_contract(self.tickers, self.market, self.weights)
        return self


class MLRiskForecastResult(BaseModel):
    """Result of a portfolio ML risk forecast."""

    ml_var: float
    ml_es: float
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    model_name: str
    horizon: ForecastHorizon
    confidence_level: float
    top_features: List[str] = Field(default_factory=list)
    source: str = Field(default="unknown", description="Data source used for prices")
    source_detail: str = Field(default="unknown", description="Detailed price data provenance")
    data_warnings: List[str] = Field(default_factory=list, description="Non-fatal data quality warnings")
    diagnostics: Optional[MLModelDiagnostics] = Field(default=None)


class MLRiskEngine:
    """Forecast portfolio downside risk from engineered market features."""

    model_version = "ml-risk-2026-05-09"
    feature_columns = [
        "portfolio_return_1d",
        "portfolio_return_5d",
        "rolling_volatility_5d",
        "rolling_volatility_20d",
        "rolling_volatility_60d",
        "rolling_mean_return_5d",
        "rolling_mean_return_20d",
        "rolling_max_drawdown_20d",
        "rolling_max_drawdown_60d",
        "downside_volatility_20d",
        "skewness_20d",
        "kurtosis_20d",
        "correlation_mean_20d",
        "correlation_max_20d",
    ]
    min_return_observations = 80
    min_training_observations = 50

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
    def _downside_std(values: np.ndarray) -> float:
        negative = values[values < 0.0]
        if negative.size < 2:
            return 0.0
        return float(negative.std(ddof=1))

    @staticmethod
    def _rolling_drawdown(portfolio_growth: pd.Series, window: int, min_periods: int) -> pd.Series:
        rolling_peak = portfolio_growth.rolling(window=window, min_periods=min_periods).max()
        drawdown = portfolio_growth / rolling_peak - 1.0
        return drawdown.rolling(window=window, min_periods=min_periods).min()

    @staticmethod
    def _rolling_correlation_features(returns_df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Compute rolling mean and maximum pairwise correlation."""
        if returns_df.shape[1] < 2:
            zeros = pd.Series(0.0, index=returns_df.index)
            return zeros, zeros

        filled_returns = returns_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        mean_values: List[float] = []
        max_values: List[float] = []

        for end_idx in range(len(filled_returns)):
            window = filled_returns.iloc[max(0, end_idx - 19): end_idx + 1]
            if len(window) < 3:
                mean_values.append(0.0)
                max_values.append(0.0)
                continue

            corr = window.corr().replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
            upper = corr[np.triu_indices(corr.shape[0], k=1)]
            upper = upper[np.isfinite(upper)]
            if upper.size == 0:
                mean_values.append(0.0)
                max_values.append(0.0)
            else:
                mean_values.append(float(upper.mean()))
                max_values.append(float(upper.max()))

        return (
            pd.Series(mean_values, index=returns_df.index),
            pd.Series(max_values, index=returns_df.index),
        )

    @classmethod
    def build_feature_frame(
        cls,
        price_df: pd.DataFrame,
        weights: np.ndarray,
    ) -> pd.DataFrame:
        """Build point-in-time features from aligned price history."""
        prices = cls._normalize_price_frame(price_df)
        if prices.shape[1] != len(weights):
            raise ValueError("price data asset count does not match weights")

        asset_returns = RiskEngine.compute_log_returns(prices)
        asset_returns = RiskEngine.sanitize_returns(asset_returns)
        if len(asset_returns) < cls.min_return_observations:
            raise ValueError(
                "at least 80 complete finite return observations are required for ML risk forecasting"
            )

        portfolio_returns = pd.Series(
            asset_returns.to_numpy(dtype=float) @ weights,
            index=asset_returns.index,
            name="portfolio_return",
        )
        portfolio_growth = np.exp(portfolio_returns.cumsum())
        corr_mean_20d, corr_max_20d = cls._rolling_correlation_features(asset_returns)

        features = pd.DataFrame(
            {
                "portfolio_return_1d": portfolio_returns,
                "portfolio_return_5d": portfolio_returns.rolling(window=5, min_periods=5).sum(),
                "rolling_volatility_5d": portfolio_returns.rolling(window=5, min_periods=5).std(),
                "rolling_volatility_20d": portfolio_returns.rolling(window=20, min_periods=10).std(),
                "rolling_volatility_60d": portfolio_returns.rolling(window=60, min_periods=20).std(),
                "rolling_mean_return_5d": portfolio_returns.rolling(window=5, min_periods=5).mean(),
                "rolling_mean_return_20d": portfolio_returns.rolling(window=20, min_periods=10).mean(),
                "rolling_max_drawdown_20d": cls._rolling_drawdown(portfolio_growth, 20, 10),
                "rolling_max_drawdown_60d": cls._rolling_drawdown(portfolio_growth, 60, 20),
                "downside_volatility_20d": portfolio_returns.rolling(
                    window=20,
                    min_periods=10,
                ).apply(cls._downside_std, raw=True),
                "skewness_20d": portfolio_returns.rolling(window=20, min_periods=10).skew(),
                "kurtosis_20d": portfolio_returns.rolling(window=20, min_periods=10).kurt(),
                "correlation_mean_20d": corr_mean_20d,
                "correlation_max_20d": corr_max_20d,
            },
            index=asset_returns.index,
        )
        features = features.replace([np.inf, -np.inf], np.nan)
        features[["skewness_20d", "kurtosis_20d"]] = features[
            ["skewness_20d", "kurtosis_20d"]
        ].fillna(0.0)
        return features[cls.feature_columns].astype(float)

    @staticmethod
    def _future_loss(portfolio_returns: pd.Series, horizon: ForecastHorizon) -> pd.Series:
        future_return = portfolio_returns.shift(-1).rolling(
            window=int(horizon),
            min_periods=int(horizon),
        ).sum()
        if horizon > 1:
            future_return = future_return.shift(-(int(horizon) - 1))
        return -future_return

    @classmethod
    def _training_frame(
        cls,
        features: pd.DataFrame,
        portfolio_returns: pd.Series,
        horizon: ForecastHorizon,
    ) -> pd.DataFrame:
        target = cls._future_loss(portfolio_returns, horizon)
        training = features.copy()
        training["future_loss"] = target
        training = training.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if len(training) < cls.min_training_observations:
            raise ValueError(
                "at least 50 complete training observations are required for ML risk forecasting"
            )
        return training

    @staticmethod
    def _make_model(confidence_level: float) -> GradientBoostingRegressor:
        return GradientBoostingRegressor(
            loss="quantile",
            alpha=confidence_level,
            n_estimators=160,
            learning_rate=0.05,
            max_depth=3,
            min_samples_leaf=5,
            random_state=42,
        )

    @staticmethod
    def _tail_excess(losses: pd.Series, confidence_level: float) -> float:
        clean_losses = losses.replace([np.inf, -np.inf], np.nan).dropna()
        if clean_losses.empty:
            return 0.0

        threshold = float(clean_losses.quantile(confidence_level))
        tail_losses = clean_losses[clean_losses >= threshold]
        if tail_losses.empty:
            return 0.0

        tail_mean = float(tail_losses.mean())
        return max(tail_mean - threshold, 0.0)

    @staticmethod
    def _historical_es(losses: pd.Series, confidence_level: float) -> float:
        clean_losses = losses.replace([np.inf, -np.inf], np.nan).dropna()
        if clean_losses.empty:
            return 0.0

        threshold = float(clean_losses.quantile(confidence_level))
        tail_losses = clean_losses[clean_losses >= threshold]
        if tail_losses.empty:
            return max(threshold, 0.0)
        return max(float(tail_losses.mean()), threshold, 0.0)

    @staticmethod
    def _risk_score(es_loss: float, reference_loss: Optional[float] = None) -> Tuple[int, RiskLevel]:
        reference_scale = 0.0
        if reference_loss is not None and np.isfinite(reference_loss) and reference_loss > 0.0:
            reference_scale = float(reference_loss) * 1.25
        score_scale = max(0.06, reference_scale)
        score = int(round(float(np.clip(es_loss / score_scale * 100.0, 0.0, 100.0))))
        if score <= 30:
            level: RiskLevel = "Low"
        elif score <= 60:
            level = "Medium"
        elif score <= 85:
            level = "High"
        else:
            level = "Extreme"
        return score, level

    @classmethod
    def _top_features(cls, model: GradientBoostingRegressor) -> List[str]:
        importances = np.asarray(model.feature_importances_, dtype=float)
        if importances.shape != (len(cls.feature_columns),) or not np.isfinite(importances).all():
            return cls.feature_columns[:5]

        ordered_indices = np.argsort(importances)[::-1]
        selected = [
            cls.feature_columns[idx]
            for idx in ordered_indices
            if float(importances[idx]) > 0.0
        ]
        if not selected:
            selected = [cls.feature_columns[idx] for idx in ordered_indices]
        return selected[:5]

    @staticmethod
    def _quantile_loss(y_true: np.ndarray, y_pred: np.ndarray, alpha: float) -> float:
        residual = y_true - y_pred
        loss = np.maximum(alpha * residual, (alpha - 1.0) * residual)
        return float(np.mean(loss)) if loss.size else 0.0

    @classmethod
    def _calibration_metrics(
        cls,
        training: pd.DataFrame,
        confidence_level: float,
    ) -> Dict[str, float]:
        """Estimate out-of-window quantile calibration on the latest validation slice."""
        if len(training) < cls.min_training_observations + 10:
            model = cls._make_model(confidence_level)
            model.fit(training[cls.feature_columns], training["future_loss"])
            predictions = np.asarray(
                model.predict(training[cls.feature_columns]),
                dtype=float,
            )
            actual = training["future_loss"].to_numpy(dtype=float)
        else:
            split_idx = max(
                cls.min_training_observations,
                int(len(training) * 0.70),
            )
            split_idx = min(split_idx, len(training) - 10)
            train_part = training.iloc[:split_idx]
            validation_part = training.iloc[split_idx:]
            model = cls._make_model(confidence_level)
            model.fit(train_part[cls.feature_columns], train_part["future_loss"])
            predictions = np.asarray(
                model.predict(validation_part[cls.feature_columns]),
                dtype=float,
            )
            actual = validation_part["future_loss"].to_numpy(dtype=float)

        finite_mask = np.isfinite(predictions) & np.isfinite(actual)
        if not finite_mask.any():
            return {}
        predictions = np.maximum(predictions[finite_mask], 0.0)
        actual = np.maximum(actual[finite_mask], 0.0)
        breach_rate = float(np.mean(actual > predictions))
        expected_breach_rate = float(1.0 - confidence_level)
        calibration_error = abs(breach_rate - expected_breach_rate)
        return {
            "validation_observations": float(len(actual)),
            "breach_rate": breach_rate,
            "expected_breach_rate": expected_breach_rate,
            "calibration_error": calibration_error,
            "pinball_loss": cls._quantile_loss(actual, predictions, confidence_level),
        }

    @classmethod
    def _fallback_forecast(
        cls,
        tickers: List[str],
        price_df: pd.DataFrame,
        weights: List[float],
        horizon: ForecastHorizon,
        confidence_level: float,
        source: str,
        reason: str,
    ) -> MLRiskForecastResult:
        n_assets = len(tickers)
        normalized_weights = RiskEngine._normalize_weights(weights, n_assets)
        prices = cls._normalize_price_frame(price_df)
        asset_returns = RiskEngine.compute_log_returns(prices)
        try:
            asset_returns = RiskEngine.sanitize_returns(asset_returns)
        except ValueError:
            asset_returns = pd.DataFrame(index=prices.index, columns=prices.columns).dropna()

        if asset_returns.empty:
            var_loss = 0.0
            es_loss = 0.0
            n_observations = 0
        else:
            portfolio_returns = pd.Series(
                asset_returns.to_numpy(dtype=float) @ normalized_weights,
                index=asset_returns.index,
                name="portfolio_return",
            )
            horizon_returns = portfolio_returns.rolling(
                window=int(horizon),
                min_periods=1,
            ).sum()
            losses = (-horizon_returns).replace([np.inf, -np.inf], np.nan).dropna()
            if losses.empty:
                var_loss = 0.0
                es_loss = 0.0
            else:
                var_loss = max(float(losses.quantile(confidence_level)), 0.0)
                tail = losses[losses >= var_loss]
                es_loss = max(float(tail.mean()) if not tail.empty else var_loss, var_loss)
            n_observations = len(asset_returns)

        reference_loss = cls._historical_es(losses, confidence_level)
        score, level = cls._risk_score(es_loss, reference_loss=reference_loss)
        diagnostics = diagnostics_from_frame(
            model_name="HistoricalFallback",
            model_version=cls.model_version,
            price_df=prices,
            feature_count=0,
            n_observations=n_observations,
            calibration_metrics={
                "breach_rate": 0.0,
                "expected_breach_rate": float(1.0 - confidence_level),
                "calibration_error": float(1.0 - confidence_level),
            },
            warnings=[reason],
            fallback_used=True,
            fallback_reason=reason,
            confidence=0.35 if n_observations else 0.0,
        )
        return MLRiskForecastResult(
            ml_var=-var_loss,
            ml_es=-es_loss,
            risk_score=score,
            risk_level=level,
            model_name="HistoricalFallback",
            horizon=horizon,
            confidence_level=confidence_level,
            top_features=[],
            source=source,
            diagnostics=diagnostics,
        )

    def evaluate_from_prices(
        self,
        tickers: List[str],
        price_df: pd.DataFrame,
        weights: List[float],
        horizon: ForecastHorizon = 5,
        confidence_level: float = 0.95,
        source: str = "unknown",
        allow_fallback: bool = True,
    ) -> MLRiskForecastResult:
        """Forecast portfolio VaR and ES from already aligned prices."""
        n_assets = len(tickers)
        normalized_weights = RiskEngine._normalize_weights(weights, n_assets)
        prices = self._normalize_price_frame(price_df)
        asset_returns = RiskEngine.compute_log_returns(prices)
        asset_returns = RiskEngine.sanitize_returns(asset_returns)
        portfolio_returns = pd.Series(
            asset_returns.to_numpy(dtype=float) @ normalized_weights,
            index=asset_returns.index,
            name="portfolio_return",
        )

        try:
            features = self.build_feature_frame(prices, normalized_weights)
            training = self._training_frame(features, portfolio_returns, horizon)
        except ValueError as exc:
            if allow_fallback and "at least" in str(exc):
                return self._fallback_forecast(
                    tickers=tickers,
                    price_df=prices,
                    weights=normalized_weights.tolist(),
                    horizon=horizon,
                    confidence_level=confidence_level,
                    source=source,
                    reason=str(exc),
                )
            raise
        latest_features = features.iloc[[-1]].replace([np.inf, -np.inf], np.nan)
        if latest_features.isna().any().any():
            raise ValueError("latest ML feature row contains non-finite values")

        model = self._make_model(confidence_level)
        model.fit(training[self.feature_columns], training["future_loss"])
        calibration = self._calibration_metrics(training, confidence_level)

        predicted_loss = float(model.predict(latest_features[self.feature_columns])[0])
        var_loss = max(predicted_loss, 0.0)
        es_loss = var_loss + self._tail_excess(training["future_loss"], confidence_level)
        es_loss = max(es_loss, var_loss)
        reference_loss = self._historical_es(training["future_loss"], confidence_level)
        score, level = self._risk_score(es_loss, reference_loss=reference_loss)
        calibration_error = calibration.get("calibration_error", 0.0)
        warnings: List[str] = []
        if calibration_error > 0.10:
            warnings.append("ML risk calibration error is elevated.")
        confidence = float(np.clip(1.0 - calibration_error * 2.0, 0.30, 1.0))
        diagnostics = diagnostics_from_frame(
            model_name="GradientBoostingRegressor",
            model_version=self.model_version,
            price_df=prices,
            feature_count=len(self.feature_columns),
            n_observations=len(training),
            calibration_metrics=calibration,
            warnings=warnings,
            confidence=confidence,
        )

        return MLRiskForecastResult(
            ml_var=-var_loss,
            ml_es=-es_loss,
            risk_score=score,
            risk_level=level,
            model_name="GradientBoostingRegressor",
            horizon=horizon,
            confidence_level=confidence_level,
            top_features=self._top_features(model),
            source=source,
            diagnostics=diagnostics,
        )

    def evaluate(self, request: MLRiskForecastRequest) -> MLRiskForecastResult:
        """Run the full ML risk forecasting pipeline."""
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
            horizon=request.horizon,
            confidence_level=request.confidence_level,
            source=self.fetcher.last_source,
        )
