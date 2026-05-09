"""Adaptive allocation parameter policy for portfolio optimization."""

from typing import List, Literal, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from models.anomaly_detector import RiskAnomalyDetector, RiskAnomalyResult
from models.ml_risk_engine import MLRiskEngine, MLRiskForecastResult
from models.regime_detector import MarketRegimeDetector, MarketRegimeResult
from models.risk_engine import RiskEngine


AllocationMode = Literal["smart", "professional"]


class AllocationPolicyResult(BaseModel):
    """Effective allocation controls used by the optimizer."""

    mode: AllocationMode
    max_weight: float = Field(gt=0.0, le=1.0)
    min_weight: float = Field(ge=0.0, le=0.20)
    turnover_penalty: float = Field(ge=0.0, le=20.0)
    concentration_penalty: float = Field(ge=0.0, le=20.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)
    risk_level: str = Field(default="")
    regime: str = Field(default="")
    anomaly_level: str = Field(default="")
    anomaly_impact: str = Field(default="")
    annualized_volatility: float = Field(default=0.0)
    max_drawdown: float = Field(default=0.0)
    average_correlation: float = Field(default=0.0)
    ml_asof: str = Field(default="", description="Date of the ML forecast observation window (YYYY-MM-DD)")
    ml_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    regime_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    anomaly_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AllocationPolicyEngine:
    """Derive optimizer controls from portfolio risk state."""

    default_max_weight = 0.40
    default_min_weight = 0.02
    default_turnover_penalty = 0.005
    default_concentration_penalty = 0.005

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return float(min(max(value, low), high))

    @staticmethod
    def _average_pairwise_correlation(returns_df: pd.DataFrame) -> float:
        if returns_df.shape[1] < 2:
            return 0.0
        corr = returns_df.corr().replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
        upper = corr[np.triu_indices(corr.shape[0], k=1)]
        upper = upper[np.isfinite(upper)]
        if upper.size == 0:
            return 0.0
        return float(upper.mean())

    @staticmethod
    def _fallback(
        mode: AllocationMode,
        max_weight: float,
        min_weight: float,
        turnover_penalty: float,
        concentration_penalty: float,
        reason: str,
    ) -> AllocationPolicyResult:
        return AllocationPolicyResult(
            mode=mode,
            max_weight=max_weight,
            min_weight=min_weight,
            turnover_penalty=turnover_penalty,
            concentration_penalty=concentration_penalty,
            confidence=0.35,
            reasons=[reason],
        )

    @classmethod
    def resolve_from_prices(
        cls,
        tickers: List[str],
        price_df: pd.DataFrame,
        weights: List[float],
        mode: AllocationMode,
        requested_max_weight: float,
        requested_min_weight: float,
        requested_turnover_penalty: float,
        requested_concentration_penalty: float,
        asof_date: Optional[str] = None,
        ml_result: Optional[MLRiskForecastResult] = None,
        regime_result: Optional[MarketRegimeResult] = None,
        anomaly_result: Optional[RiskAnomalyResult] = None,
    ) -> AllocationPolicyResult:
        """Resolve effective optimizer controls for the current request."""
        if mode == "professional":
            return AllocationPolicyResult(
                mode="professional",
                max_weight=requested_max_weight,
                min_weight=requested_min_weight,
                turnover_penalty=requested_turnover_penalty,
                concentration_penalty=requested_concentration_penalty,
                confidence=1.0,
                reasons=["Professional mode uses manual allocation controls."],
            )

        n_assets = len(tickers)
        if n_assets <= 0:
            return cls._fallback(
                "smart",
                cls.default_max_weight,
                cls.default_min_weight,
                cls.default_turnover_penalty,
                cls.default_concentration_penalty,
                "No assets were available for adaptive allocation controls.",
            )

        try:
            returns_df = RiskEngine.sanitize_returns(
                RiskEngine.compute_log_returns(price_df)
            )
            normalized_weights = RiskEngine._normalize_weights(weights, n_assets)
            perf = RiskEngine.compute_performance_metrics(returns_df, normalized_weights)
            ann_vol = float(perf["annualized_volatility"])
            max_drawdown = float(perf["max_drawdown"])
            avg_corr = cls._average_pairwise_correlation(returns_df)
        except ValueError:
            return cls._fallback(
                "smart",
                cls.default_max_weight,
                cls.default_min_weight,
                cls.default_turnover_penalty,
                cls.default_concentration_penalty,
                "Adaptive controls used defaults because the risk sample was incomplete.",
            )

        reasons: List[str] = []
        confidence_parts = [0.45]

        volatility_score = cls._clamp(ann_vol / 0.35, 0.0, 1.0)
        drawdown_score = cls._clamp(abs(max_drawdown) / 0.30, 0.0, 1.0)
        correlation_score = cls._clamp((avg_corr - 0.20) / 0.60, 0.0, 1.0)
        concentration_score = cls._clamp(
            float(np.sum(normalized_weights ** 2)) * n_assets - 1.0,
            0.0,
            1.0,
        )

        ml_score = 0.0
        risk_level = ""
        ml_confidence = 0.0
        try:
            if ml_result is None:
                ml_result = MLRiskEngine().evaluate_from_prices(
                    tickers=tickers,
                    price_df=price_df,
                    weights=normalized_weights.tolist(),
                    horizon=5,
                    confidence_level=0.95,
                    source="allocation_policy",
                )
            ml_confidence = (
                ml_result.diagnostics.confidence if ml_result.diagnostics else 0.65
            )
            ml_score = cls._clamp(
                (ml_result.risk_score / 100.0) * max(ml_confidence, 0.35),
                0.0,
                1.0,
            )
            risk_level = ml_result.risk_level
            confidence_parts.append(0.20)
            if ml_result.diagnostics and ml_result.diagnostics.fallback_used:
                reasons.append("ML downside forecast used fallback risk estimation.")
            if risk_level in {"High", "Extreme"}:
                reasons.append(f"ML downside forecast is {risk_level.lower()}.")
        except ValueError:
            reasons.append("ML downside forecast was skipped because the sample was too short.")

        regime_score = 0.0
        regime = ""
        regime_confidence = 0.0
        try:
            if regime_result is None:
                regime_result = MarketRegimeDetector().evaluate_from_prices(
                    tickers=tickers,
                    price_df=price_df,
                    weights=normalized_weights.tolist(),
                    model_type="kmeans",
                    source="allocation_policy",
                )
            regime = regime_result.smoothed_regime or regime_result.current_regime
            regime_confidence = (
                regime_result.diagnostics.confidence if regime_result.diagnostics else 0.65
            )
            regime_score = {
                "Normal": 0.15,
                "High Volatility": 0.65,
                "Crisis": 0.90,
            }.get(regime, 0.0) * max(regime_confidence, 0.35)
            confidence_parts.append(0.15)
            if regime != "Normal":
                reasons.append(f"Market regime is {regime.lower()}.")
        except ValueError:
            reasons.append("Market regime signal was skipped because the sample was too short.")

        anomaly_score = 0.0
        anomaly_level = ""
        anomaly_impact = ""
        anomaly_confidence = 0.0
        try:
            if anomaly_result is None:
                anomaly_result = RiskAnomalyDetector().evaluate_from_prices(
                    tickers=tickers,
                    price_df=price_df,
                    weights=normalized_weights.tolist(),
                    source="allocation_policy",
                )
            anomaly_confidence = (
                anomaly_result.diagnostics.confidence if anomaly_result.diagnostics else 0.65
            )
            impact_boost = {
                "none": 0.0,
                "tighten_constraints": 0.10,
                "freeze_rebalance": 0.20,
                "force_oos_guard": 0.25,
            }.get(anomaly_result.decision_impact, 0.0)
            anomaly_score = cls._clamp(
                anomaly_result.anomaly_score * max(anomaly_confidence, 0.35) + impact_boost,
                0.0,
                1.0,
            )
            anomaly_level = anomaly_result.alert_level
            anomaly_impact = anomaly_result.decision_impact
            confidence_parts.append(0.15)
            if anomaly_level in {"Medium", "High", "Extreme"}:
                reasons.append(f"Anomaly alert level is {anomaly_level.lower()}.")
        except ValueError:
            reasons.append("Anomaly signal was skipped because the sample was too short.")

        stress_score = cls._clamp(
            0.24 * volatility_score
            + 0.20 * drawdown_score
            + 0.16 * correlation_score
            + 0.16 * ml_score
            + 0.16 * regime_score
            + 0.08 * anomaly_score,
            0.0,
            1.0,
        )

        if ann_vol >= 0.25:
            reasons.append("Realized volatility is elevated.")
        if max_drawdown <= -0.15:
            reasons.append("Recent drawdown is material.")
        if avg_corr >= 0.65:
            reasons.append("Asset correlations are reducing diversification.")
        if concentration_score >= 0.35:
            reasons.append("Current allocation is already concentrated.")
        if not reasons:
            reasons.append("Risk state is stable enough for balanced allocation controls.")

        feasible_cap = 1.0 / n_assets
        if n_assets == 1:
            max_weight = 1.0
        elif n_assets == 2:
            max_weight = cls._clamp(
                0.78 - 0.20 * stress_score - 0.05 * concentration_score,
                feasible_cap,
                0.85,
            )
            reasons.append("Two-asset portfolio keeps enough max-weight room for relative signals.")
        else:
            max_weight = cls._clamp(
                0.55 - 0.25 * stress_score - 0.05 * concentration_score,
                feasible_cap,
                1.0,
            )
        min_weight = cls._clamp(
            0.01 + 0.035 * stress_score,
            0.0,
            min(0.20, 0.5 / n_assets),
        )
        turnover_penalty = cls._clamp(
            0.003 + 0.030 * stress_score + 0.010 * drawdown_score,
            0.0,
            0.05,
        )
        concentration_penalty = cls._clamp(
            0.004 + 0.035 * stress_score + 0.010 * correlation_score,
            0.0,
            0.05,
        )
        confidence = cls._clamp(sum(confidence_parts), 0.0, 0.95)

        return AllocationPolicyResult(
            mode="smart",
            max_weight=round(max_weight, 4),
            min_weight=round(min_weight, 4),
            turnover_penalty=round(turnover_penalty, 4),
            concentration_penalty=round(concentration_penalty, 4),
            confidence=round(confidence, 4),
            reasons=reasons[:6],
            risk_level=risk_level,
            regime=regime,
            anomaly_level=anomaly_level,
            anomaly_impact=anomaly_impact,
            annualized_volatility=round(ann_vol, 6),
            max_drawdown=round(max_drawdown, 6),
            average_correlation=round(avg_corr, 6),
            ml_asof=asof_date or "",
            ml_confidence=round(ml_confidence, 4),
            regime_confidence=round(regime_confidence, 4),
            anomaly_confidence=round(anomaly_confidence, 4),
        )
