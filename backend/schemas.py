"""API request and response schemas for the FastAPI backend."""

import math
from datetime import date
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from models import (
    AllocationMode,
    CrisisWarningResult,
    FactorRegressionResult,
    MarketRegimeResult,
    MLRiskForecastResult,
    OptimizationResult,
    RiskAnomalyResult,
    RiskEvaluationResult,
    ViewSpec,
)
from models.market_validation import MarketMode
from models.request_validation import (
    normalize_tickers,
    validate_common_portfolio_contract,
    validate_view_assets,
)


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
    risk_free_rate: Optional[float] = Field(default=None, description="Annualized risk-free rate for Sharpe; if None, resolved from the selected market proxy")
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
    crisis_enabled: bool = Field(default=True)
    crisis_horizon: Literal[1, 5] = Field(default=5)


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
    crisis_warning: Optional[CrisisWarningResult] = Field(default=None)


MarketSessionStatus = Literal["open", "lunch_break", "closed", "unknown"]
MarketIndexStatus = Literal["ok", "unavailable"]


class MarketSnapshotTrendPoint(BaseModel):
    """One intraday price point for a market snapshot chart."""

    timestamp: str
    price: float


class MarketSnapshotIndex(BaseModel):
    """Display contract for one market index quote."""

    symbol: str
    name: str
    name_zh: str
    name_tc: str
    price: Optional[float] = Field(default=None)
    change: Optional[float] = Field(default=None)
    change_percent: Optional[float] = Field(default=None)
    asof_date: Optional[str] = Field(default=None)
    source: str = Field(default="")
    source_detail: str = Field(default="")
    status: MarketIndexStatus = Field(default="ok")
    warning: str = Field(default="")
    trend: List[MarketSnapshotTrendPoint] = Field(default_factory=list)


class MarketSnapshotResult(BaseModel):
    """Response for the landing-page market snapshot."""

    market: MarketMode
    session_status: MarketSessionStatus
    timezone: str
    local_time: str
    updated_at: str
    indices: List[MarketSnapshotIndex] = Field(default_factory=list)
    source: str = Field(default="")
    source_detail: str = Field(default="")
    data_warnings: List[str] = Field(default_factory=list)


ReportLanguage = Literal["en", "zh", "tc"]
ReportSeverity = Literal["info", "warning", "limitation"]
MetricValue = Union[str, float, int, bool, List[str], None]


class RiskReportRequest(AnalysisRunRequest):
    """Request for a structured risk report."""

    language: ReportLanguage = Field(default="zh")
    include_sections: Optional[List[str]] = Field(default=None)
    report_title: Optional[str] = Field(default=None)


class RiskReportMetric(BaseModel):
    """Display-ready metric for report sections."""

    key: str
    label: str
    value: MetricValue = None
    unit: str = Field(default="")
    severity: ReportSeverity = Field(default="info")
    description: str = Field(default="")


class RiskReportSection(BaseModel):
    """Structured report section metadata."""

    key: str
    title: str
    summary: str = Field(default="")
    metrics: List[RiskReportMetric] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    included: bool = Field(default=True)


class RiskReportMethodologyNote(BaseModel):
    """Methodology, limitation, or data note attached to the report."""

    code: str
    title: str
    detail: str
    severity: ReportSeverity = Field(default="info")


class RiskReportPortfolioOverview(BaseModel):
    """Portfolio identity and run configuration for a report."""

    tickers: List[str]
    weights: List[float]
    market: MarketMode
    start_date: str
    end_date: str
    capital: float
    leverage: float
    currency: str


class RiskReportTraditionalRisk(BaseModel):
    """Traditional risk metrics for a report."""

    historical_es: Optional[float] = None
    monte_carlo_es: Optional[float] = None
    absolute_loss_historical: Optional[float] = None
    absolute_loss_monte_carlo: Optional[float] = None
    annualized_volatility: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_date: str = Field(default="")


class RiskReportMLForecast(BaseModel):
    """ML downside forecast summary for a report."""

    ml_var: Optional[float] = None
    ml_es: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: str = Field(default="")
    top_features: List[str] = Field(default_factory=list)
    diagnostics_summary: Dict[str, MetricValue] = Field(default_factory=dict)


class RiskReportAnomaly(BaseModel):
    """Risk anomaly summary for a report."""

    anomaly_score: Optional[float] = None
    alert_level: str = Field(default="")
    main_reasons: List[str] = Field(default_factory=list)
    decision_impact: str = Field(default="")


class RiskReportRegime(BaseModel):
    """Market regime summary for a report."""

    current_regime: str = Field(default="")
    smoothed_regime: str = Field(default="")
    regime_probabilities: Dict[str, float] = Field(default_factory=dict)
    volatility_multiplier: Optional[float] = None
    correlation_multiplier: Optional[float] = None
    recommended_stress_level: str = Field(default="")


class RiskReportCrisisDriver(BaseModel):
    """One crisis warning driver for report display."""

    feature: str
    feature_value: Optional[float] = None
    shap_value: Optional[float] = None
    direction: str


class RiskReportCrisisWarning(BaseModel):
    """Explainable crisis warning summary for a report."""

    crisis_probability: Optional[float] = None
    warning_level: str = Field(default="")
    model_health: str = Field(default="")
    calibration_state: str = Field(default="")
    top_risk_drivers: List[RiskReportCrisisDriver] = Field(default_factory=list)
    risk_reducers: List[RiskReportCrisisDriver] = Field(default_factory=list)


class RiskReportDecisionSummary(BaseModel):
    """Decision and OOS summary for a report."""

    decision_policy: str = Field(default="")
    recommended_weights: List[float] = Field(default_factory=list)
    turnover: Optional[float] = None
    benchmark_symbol: str = Field(default="")
    benchmark_name: str = Field(default="")
    oos_excess_return: Optional[float] = None
    oos_optimized_sharpe: Optional[float] = None
    model_score: Optional[float] = None
    model_grade: str = Field(default="")


class RiskReportResult(BaseModel):
    """Structured response for a risk report."""

    report_title: str
    generated_at: str
    language: ReportLanguage
    portfolio_overview: RiskReportPortfolioOverview
    traditional_risk: RiskReportTraditionalRisk
    ml_forecast: Optional[RiskReportMLForecast] = None
    anomaly: Optional[RiskReportAnomaly] = None
    regime: Optional[RiskReportRegime] = None
    crisis_warning: Optional[RiskReportCrisisWarning] = None
    decision_summary: RiskReportDecisionSummary
    executive_summary: List[str] = Field(default_factory=list)
    sections: List[RiskReportSection] = Field(default_factory=list)
    methodology_notes: List[RiskReportMethodologyNote] = Field(default_factory=list)
    disclaimers: List[str] = Field(default_factory=list)
    data_warnings: List[str] = Field(default_factory=list)
