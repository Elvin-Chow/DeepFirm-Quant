"""API request and response schemas for the FastAPI backend."""

import math
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from models import (
    AllocationMode,
    FactorRegressionResult,
    MarketRegimeResult,
    MLRiskForecastResult,
    OptimizationResult,
    RiskAnomalyResult,
    RiskEvaluationResult,
    ViewSpec,
)
from models.request_validation import (
    normalize_tickers,
    validate_common_portfolio_contract,
    validate_view_assets,
)

MarketMode = Literal["us", "hk", "mixed"]


class MarketRequestBase(BaseModel):
    """Shared market request contract."""

    tickers: List[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
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
    def validate_market_contract(self) -> "MarketRequestBase":
        validate_common_portfolio_contract(self.tickers, self.market)
        return self


class WeightedMarketRequestBase(MarketRequestBase):
    """Shared weighted portfolio request contract."""

    weights: List[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_weighted_market_contract(self) -> "WeightedMarketRequestBase":
        validate_common_portfolio_contract(self.tickers, self.market, self.weights)
        return self


class AlphaAnalysisRequest(MarketRequestBase):
    """Request for Fama-French alpha attribution."""


class PortfolioOptimizeRequest(WeightedMarketRequestBase):
    """Request for Black-Litterman portfolio optimization."""

    views: List[ViewSpec] = Field(default_factory=list)
    risk_aversion: float = Field(default=2.5, gt=0.0)
    max_weight: float = Field(default=0.40, gt=0.0, le=1.0)
    min_weight: float = Field(default=0.02, ge=0.0, le=0.20)
    turnover_penalty: float = Field(default=0.005, ge=0.0, le=20.0)
    concentration_penalty: float = Field(default=0.005, ge=0.0, le=20.0)
    oos_guard_enabled: bool = Field(default=False)
    allocation_mode: AllocationMode = Field(default="professional")
    backtest_enabled: bool = Field(default=False, description="Enable out-of-sample backtest")
    test_ratio: float = Field(default=0.20, ge=0.10, le=0.30, description="Fraction of data to hold out for testing")
    risk_free_rate: Optional[float] = Field(default=None, description="Annualized risk-free rate for Sharpe; if None, fetched dynamically from ^IRX")
    use_market_cap_prior: bool = Field(default=True, description="Use market-cap implied equilibrium prior for Black-Litterman")

    @field_validator("risk_free_rate")
    @classmethod
    def validate_risk_free_rate(cls, risk_free_rate: Optional[float]) -> Optional[float]:
        if risk_free_rate is not None and not math.isfinite(float(risk_free_rate)):
            raise ValueError("risk_free_rate must be finite")
        return risk_free_rate

    @model_validator(mode="after")
    def validate_view_contract(self) -> "PortfolioOptimizeRequest":
        validate_view_assets(self.tickers, self.views)
        return self


class AnalysisRunRequest(PortfolioOptimizeRequest):
    """Request for the full analysis workflow."""

    confidence_level: float = Field(default=0.99, ge=0.9, le=0.999)
    mc_paths: int = Field(default=10_000, ge=1_000, le=50_000)
    capital: float = Field(default=1_000_000, gt=0)
    leverage: float = Field(default=1.0, gt=0)
    ml_horizon: Literal[1, 5] = Field(default=5)
    ml_confidence_level: float = Field(default=0.95, ge=0.90, le=0.99)
    regime_model_type: Literal["kmeans", "gaussian_mixture"] = Field(default="kmeans")


class AnalysisRunResult(BaseModel):
    """Response for the full analysis workflow."""

    risk: RiskEvaluationResult
    alpha: Optional[FactorRegressionResult] = Field(default=None)
    alpha_status: Literal["available", "truncated", "unavailable"] = Field(default="unavailable")
    alpha_message: str = Field(default="")
    factor_available_through: Optional[str] = Field(default=None)
    alpha_effective_start: Optional[str] = Field(default=None)
    alpha_effective_end: Optional[str] = Field(default=None)
    optimization: OptimizationResult
    anomaly: Optional[RiskAnomalyResult] = Field(default=None)
    regime: Optional[MarketRegimeResult] = Field(default=None)
    ml_forecast: Optional[MLRiskForecastResult] = Field(default=None)
