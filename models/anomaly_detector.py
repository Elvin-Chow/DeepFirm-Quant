"""Machine-learning risk anomaly detection for portfolio market states."""

from datetime import date
from typing import List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator
from sklearn.ensemble import IsolationForest

from data_pipeline import DataQuality, MarketAligner, SmartFetcher
from models.market_validation import MarketMode
from models.ml_diagnostics import MLModelDiagnostics, diagnostics_from_frame
from models.request_validation import (
    normalize_tickers,
    validate_common_portfolio_contract,
)
from models.risk_engine import RiskEngine


AlertLevel = Literal["Low", "Medium", "High", "Extreme"]
AnomalyReasonCode = Literal[
    "DATA_QUALITY_RISK",
    "LARGE_NEGATIVE_RETURN",
    "ASSET_PRICE_JUMP",
    "HIGH_ROLLING_VOLATILITY",
    "CORRELATION_SPIKE",
    "MODEL_ANOMALY_SIGNAL",
    "NO_MATERIAL_SIGNAL",
]
AnomalyReasonCategory = Literal["data_quality", "market", "model"]
DecisionImpact = Literal["none", "tighten_constraints", "freeze_rebalance", "force_oos_guard"]


class RiskAnomalyReason(BaseModel):
    """Structured reason for a portfolio anomaly signal."""

    code: AnomalyReasonCode
    category: AnomalyReasonCategory
    severity: AlertLevel
    message: str


class RiskAnomalyRequest(BaseModel):
    """Request payload for risk anomaly detection."""

    tickers: List[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
    weights: List[float] = Field(default_factory=list)
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
    def validate_market_contract(self) -> "RiskAnomalyRequest":
        validate_common_portfolio_contract(self.tickers, self.market, self.weights)
        return self


class RiskAnomalyResult(BaseModel):
    """Result of a risk anomaly detection run."""

    anomaly_score: float = Field(ge=0.0, le=1.0)
    is_anomaly: bool
    alert_level: AlertLevel
    main_reasons: List[str] = Field(default_factory=list)
    reason_codes: List[AnomalyReasonCode] = Field(default_factory=list)
    structured_reasons: List[RiskAnomalyReason] = Field(default_factory=list)
    decision_impact: DecisionImpact = Field(default="none")
    source: str = Field(default="unknown", description="Data source used for prices")
    source_detail: str = Field(default="unknown", description="Detailed price data provenance")
    data_warnings: List[str] = Field(default_factory=list, description="Non-fatal data quality warnings")
    data_quality: DataQuality = Field(default_factory=DataQuality, description="Unified data quality provenance")
    diagnostics: Optional[MLModelDiagnostics] = Field(default=None)


class RiskAnomalyDetector:
    """Detect abnormal portfolio risk states using engineered features and Isolation Forest."""

    model_version = "anomaly-2026-05-09"
    PRICE_FORWARD_FILL_LIMIT = 1
    feature_columns = [
        "daily_return",
        "absolute_daily_return",
        "rolling_volatility_5d",
        "rolling_volatility_20d",
        "drawdown_20d",
        "correlation_mean_20d",
        "correlation_change_20d",
        "missing_data_ratio",
        "price_jump_score",
    ]

    def __init__(
        self,
        fetcher: Optional[SmartFetcher] = None,
        aligner: Optional[MarketAligner] = None,
    ) -> None:
        self.fetcher = fetcher
        self.aligner = aligner
        self.risk_engine = (
            RiskEngine(fetcher=fetcher, aligner=aligner) if fetcher is not None and aligner is not None else None
        )

    @staticmethod
    def _normalize_price_frame(price_df: pd.DataFrame) -> pd.DataFrame:
        """Return numeric prices sorted by normalized date."""
        if price_df.empty:
            raise ValueError("price data is empty")

        prices = price_df.copy()
        idx = pd.to_datetime(prices.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        prices.index = idx.normalize()
        prices = prices.sort_index()
        return prices.apply(pd.to_numeric, errors="coerce")

    @classmethod
    def _price_coverage_warning(
        cls,
        total_rows: int,
        total_cells: int,
        observed_cells: int,
        filled_cells: int,
        retained_rows: int,
    ) -> str:
        if total_rows <= 0 or total_cells <= 0:
            return ""
        if observed_cells == total_cells and filled_cells == 0 and retained_rows == total_rows:
            return ""

        observed_ratio = observed_cells / total_cells
        retained_ratio = retained_rows / total_rows
        return (
            f"Anomaly price coverage warning: observed {observed_cells}/"
            f"{total_cells} price cells ({observed_ratio:.1%}), forward-filled "
            f"{filled_cells} with limit {cls.PRICE_FORWARD_FILL_LIMIT}, retained "
            f"{retained_rows}/{total_rows} dates ({retained_ratio:.1%}) after "
            "residual gaps."
        )

    @staticmethod
    def _rolling_correlation_mean(returns_df: pd.DataFrame) -> pd.Series:
        """Compute mean pairwise rolling correlation across assets."""
        if returns_df.shape[1] < 2:
            return pd.Series(0.0, index=returns_df.index)

        filled_returns = returns_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        values: List[float] = []
        for end_idx in range(len(filled_returns)):
            window = filled_returns.iloc[max(0, end_idx - 19) : end_idx + 1]
            if len(window) < 3:
                values.append(0.0)
                continue

            corr = window.corr().replace([np.inf, -np.inf], np.nan).to_numpy()
            upper = corr[np.triu_indices(corr.shape[0], k=1)]
            upper = upper[np.isfinite(upper)]
            values.append(float(upper.mean()) if upper.size else 0.0)

        return pd.Series(values, index=returns_df.index)

    @classmethod
    def build_feature_frame(
        cls,
        price_df: pd.DataFrame,
        weights: np.ndarray,
    ) -> pd.DataFrame:
        """Build daily anomaly features from price history and portfolio weights."""
        prices = cls._normalize_price_frame(price_df)
        if prices.shape[1] != len(weights):
            raise ValueError("price data asset count does not match weights")

        finite_mask = pd.DataFrame(
            np.isfinite(prices.to_numpy(dtype=float)),
            index=prices.index,
            columns=prices.columns,
        )
        invalid_mask = prices.isna() | ~finite_mask | (prices <= 0.0)
        missing_ratio = invalid_mask.mean(axis=1)

        masked_prices = prices.mask(invalid_mask)
        observed_cells = int(masked_prices.notna().sum().sum())
        clean_prices = masked_prices.ffill(limit=cls.PRICE_FORWARD_FILL_LIMIT)
        filled_cells = int((clean_prices.notna() & masked_prices.isna()).sum().sum())
        residual_rows = clean_prices.isna().any(axis=1) | (clean_prices <= 0.0).any(axis=1)
        retained_rows = int((~residual_rows).sum())
        coverage_warnings = [
            warning
            for warning in [
                cls._price_coverage_warning(
                    len(prices),
                    prices.size,
                    observed_cells,
                    filled_cells,
                    retained_rows,
                )
            ]
            if warning
        ]
        clean_prices = clean_prices.loc[~residual_rows]
        missing_ratio = missing_ratio.reindex(clean_prices.index)
        if clean_prices.isna().any().any() or (clean_prices <= 0.0).any().any():
            raise ValueError("price data contains no usable positive finite values")

        asset_returns = np.log(clean_prices / clean_prices.shift(1))
        asset_returns = asset_returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        asset_returns = asset_returns.iloc[1:]
        if len(asset_returns) < 10:
            raise ValueError("at least 10 return observations are required for anomaly detection")

        portfolio_returns = pd.Series(
            asset_returns.to_numpy(dtype=float) @ weights,
            index=asset_returns.index,
            name="daily_return",
        )
        portfolio_growth = np.exp(portfolio_returns.cumsum())
        running_max_20d = portfolio_growth.rolling(window=20, min_periods=1).max()
        drawdown_20d = portfolio_growth / running_max_20d - 1.0

        correlation_mean = cls._rolling_correlation_mean(asset_returns)
        prior_corr_mean = correlation_mean.rolling(window=20, min_periods=3).mean().shift(1)
        correlation_change = (correlation_mean - prior_corr_mean).fillna(0.0)

        features = pd.DataFrame(
            {
                "daily_return": portfolio_returns,
                "absolute_daily_return": portfolio_returns.abs(),
                "rolling_volatility_5d": portfolio_returns.rolling(window=5, min_periods=2).std(),
                "rolling_volatility_20d": portfolio_returns.rolling(window=20, min_periods=2).std(),
                "drawdown_20d": drawdown_20d,
                "correlation_mean_20d": correlation_mean,
                "correlation_change_20d": correlation_change,
                "missing_data_ratio": missing_ratio.reindex(asset_returns.index).fillna(0.0),
                "price_jump_score": asset_returns.abs().max(axis=1),
            },
            index=asset_returns.index,
        )
        features = features.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        result = features[cls.feature_columns].astype(float)
        if coverage_warnings:
            result.attrs["coverage_warnings"] = coverage_warnings
        return result

    @staticmethod
    def _safe_quantile(history: pd.Series, q: float, fallback: float) -> float:
        values = history.replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            return fallback
        result = float(values.quantile(q))
        return result if np.isfinite(result) else fallback

    @classmethod
    def _rule_floor(cls, features: pd.DataFrame, n_assets: int) -> Tuple[float, List[str]]:
        """Return deterministic rule score floors and plain-English reasons."""
        current = features.iloc[-1]
        history = features.iloc[:-1]
        score_floor = 0.0
        reasons: List[str] = []

        missing_ratio = float(current["missing_data_ratio"])
        if missing_ratio > 0.0:
            reasons.append("Missing or invalid price data")
            score_floor = max(score_floor, 0.75 if missing_ratio >= 0.25 else 0.60)

        latest_return = float(current["daily_return"])
        return_limit = max(
            0.04,
            cls._safe_quantile(history["absolute_daily_return"], 0.99, 0.04) * 1.25,
        )
        if latest_return <= -return_limit:
            reasons.append("Large negative return")
            score_floor = max(score_floor, 0.90 if latest_return <= -0.10 else 0.75)

        latest_jump = float(current["price_jump_score"])
        jump_limit = max(
            0.06,
            cls._safe_quantile(history["price_jump_score"], 0.99, 0.06) * 1.25,
        )
        if latest_jump >= jump_limit:
            reasons.append("Asset price jump")
            score_floor = max(score_floor, 0.90 if latest_jump >= 0.12 else 0.75)

        vol_5d = float(current["rolling_volatility_5d"])
        vol_20d = float(current["rolling_volatility_20d"])
        vol_limit = max(
            0.02,
            cls._safe_quantile(history["rolling_volatility_5d"], 0.95, 0.02) * 1.20,
        )
        if vol_5d >= vol_limit and (vol_20d <= 1e-12 or vol_5d >= vol_20d * 1.25):
            reasons.append("High rolling volatility")
            score_floor = max(score_floor, 0.75 if vol_5d >= 0.04 else 0.60)

        if n_assets > 1:
            corr_mean = float(current["correlation_mean_20d"])
            corr_change = float(current["correlation_change_20d"])
            corr_baseline = cls._safe_quantile(history["correlation_mean_20d"], 0.50, 0.0)
            if corr_mean >= 0.75 and (corr_change >= 0.10 or corr_mean - corr_baseline >= 0.20):
                reasons.append("Correlation spike")
                score_floor = max(score_floor, 0.75)

        return score_floor, reasons

    @staticmethod
    def _alert_level(score: float) -> AlertLevel:
        if score >= 0.90:
            return "Extreme"
        if score >= 0.75:
            return "High"
        if score >= 0.60:
            return "Medium"
        return "Low"

    @staticmethod
    def _adaptive_contamination(features: pd.DataFrame) -> float:
        """Select a conservative anomaly share from sample length and recent volatility."""
        n_rows = len(features)
        if n_rows < 60:
            base = 0.08
        elif n_rows < 160:
            base = 0.06
        else:
            base = 0.04

        recent_vol = float(features["rolling_volatility_20d"].tail(20).mean())
        historical_vol = float(features["rolling_volatility_20d"].mean())
        if historical_vol > 1e-12 and recent_vol > historical_vol * 1.8:
            base += 0.015
        return float(np.clip(base, 0.02, 0.10))

    @classmethod
    def _model_score(cls, features: pd.DataFrame) -> Tuple[float, bool]:
        """Compute Isolation Forest score and latest-row prediction."""
        model = IsolationForest(
            n_estimators=128,
            contamination=cls._adaptive_contamination(features),
            random_state=42,
        )
        model.fit(features)

        latest = features.iloc[[-1]]
        is_model_anomaly = bool(model.predict(latest)[0] == -1)

        raw_abnormality = -model.score_samples(features)
        latest_raw = float(raw_abnormality[-1])
        percentile_score = float(np.mean(raw_abnormality <= latest_raw))

        if is_model_anomaly:
            return max(0.75, percentile_score), True
        return min(0.59, percentile_score * 0.59), False

    @staticmethod
    def _reason_code(reason: str) -> AnomalyReasonCode:
        mapping: dict[str, AnomalyReasonCode] = {
            "Missing or invalid price data": "DATA_QUALITY_RISK",
            "Large negative return": "LARGE_NEGATIVE_RETURN",
            "Asset price jump": "ASSET_PRICE_JUMP",
            "High rolling volatility": "HIGH_ROLLING_VOLATILITY",
            "Correlation spike": "CORRELATION_SPIKE",
            "Machine learning anomaly signal": "MODEL_ANOMALY_SIGNAL",
            "No material anomaly signal": "NO_MATERIAL_SIGNAL",
        }
        return mapping.get(reason, "MODEL_ANOMALY_SIGNAL")

    @staticmethod
    def _reason_category(code: AnomalyReasonCode) -> AnomalyReasonCategory:
        if code == "DATA_QUALITY_RISK":
            return "data_quality"
        if code in {"MODEL_ANOMALY_SIGNAL", "NO_MATERIAL_SIGNAL"}:
            return "model"
        return "market"

    @classmethod
    def _structured_reasons(
        cls,
        reasons: List[str],
        alert_level: AlertLevel,
    ) -> List[RiskAnomalyReason]:
        structured: List[RiskAnomalyReason] = []
        for reason in reasons:
            code = cls._reason_code(reason)
            structured.append(
                RiskAnomalyReason(
                    code=code,
                    category=cls._reason_category(code),
                    severity=alert_level,
                    message=reason,
                )
            )
        return structured

    @staticmethod
    def _decision_impact(
        score: float,
        alert_level: AlertLevel,
        reason_codes: List[AnomalyReasonCode],
    ) -> DecisionImpact:
        if "DATA_QUALITY_RISK" in reason_codes and score >= 0.75:
            return "freeze_rebalance"
        if alert_level == "Extreme":
            return "force_oos_guard"
        if alert_level in {"Medium", "High"}:
            return "tighten_constraints"
        return "none"

    def evaluate_from_prices(
        self,
        tickers: List[str],
        price_df: pd.DataFrame,
        weights: List[float],
        source: str = "unknown",
    ) -> RiskAnomalyResult:
        """Evaluate anomaly state from an already aligned price DataFrame."""
        n_assets = len(tickers)
        normalized_weights = RiskEngine._normalize_weights(weights, n_assets)
        features = self.build_feature_frame(price_df, normalized_weights)
        coverage_warnings = list(features.attrs.get("coverage_warnings", []) or [])

        model_score, model_anomaly = self._model_score(features)
        rule_score, reasons = self._rule_floor(features, n_assets)
        score = round(float(np.clip(max(model_score, rule_score), 0.0, 1.0)), 4)

        if model_anomaly and "Machine learning anomaly signal" not in reasons:
            reasons.append("Machine learning anomaly signal")
        if not reasons:
            reasons.append("No material anomaly signal")

        alert_level = self._alert_level(score)
        structured = self._structured_reasons(reasons[:5], alert_level)
        reason_codes = [item.code for item in structured]
        diagnostics = diagnostics_from_frame(
            model_name="IsolationForest",
            model_version=self.model_version,
            price_df=price_df,
            feature_count=len(self.feature_columns),
            n_observations=len(features),
            calibration_metrics={
                "anomaly_score": score,
                "contamination": self._adaptive_contamination(features),
            },
            warnings=[
                *coverage_warnings,
                *([] if score < 0.60 else ["Anomaly signal affects allocation controls."]),
            ],
            confidence=float(np.clip(0.50 + score * 0.50, 0.0, 1.0)),
        )
        return RiskAnomalyResult(
            anomaly_score=score,
            is_anomaly=bool(score >= 0.75 or model_anomaly),
            alert_level=alert_level,
            main_reasons=reasons[:5],
            reason_codes=reason_codes,
            structured_reasons=structured,
            decision_impact=self._decision_impact(score, alert_level, reason_codes),
            source=source,
            data_warnings=coverage_warnings,
            diagnostics=diagnostics,
        )

    def evaluate(self, request: RiskAnomalyRequest) -> RiskAnomalyResult:
        """Run the full anomaly detection pipeline."""
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
            source=self.fetcher.last_source,
        )
