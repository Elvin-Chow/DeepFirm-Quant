"""FastAPI backend for the DeepFirm Quant engine."""

import asyncio
import logging
import os
from typing import Callable, Optional, TypeVar

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.cors import configured_origin_regex, configured_origins
from backend.schemas import (
    AlphaAnalysisRequest,
    AnalysisRunRequest,
    AnalysisRunResult,
    MarketSnapshotResult,
    PortfolioOptimizeRequest,
    RiskReportRequest,
    RiskReportResult,
)
from backend.market_snapshot import build_market_snapshot
from backend.services import PortfolioAnalysisService
from data_pipeline import AlignmentError, DataFetcherError, SmartFetcher
from models import (
    CrisisWarningRequest,
    CrisisWarningResult,
    CrisisWarningUnavailableError,
    FactorRegressionResult,
    MarketRegimeDetector,
    MarketRegimeRequest,
    MarketRegimeResult,
    MLRiskEngine,
    MLRiskForecastRequest,
    MLRiskForecastResult,
    OptimizationResult,
    RiskAnomalyDetector,
    RiskAnomalyRequest,
    RiskAnomalyResult,
    RiskEngine,
    RiskEvaluationRequest,
    RiskEvaluationResult,
)


logger = logging.getLogger(__name__)
T = TypeVar("T")
analysis_service = PortfolioAnalysisService(logger=logger)
aligner = analysis_service.aligner
factor_analyzer = analysis_service.factor_analyzer
bl_optimizer = analysis_service.optimizer
allocation_policy_engine = analysis_service.allocation_policy_engine
crisis_warning_service = analysis_service.crisis_warning_service


app = FastAPI(
    title="DeepFirm Quant",
    description="Industrial-grade quant risk and decision engine",
    version="3.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(),
    allow_origin_regex=configured_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _timeout_seconds(env_name: str, default: float) -> float:
    try:
        value = float(os.getenv(env_name, str(default)))
    except ValueError:
        return default
    return max(1.0, value)


def _analysis_timeout_seconds() -> float:
    return _timeout_seconds("DFQ_ANALYSIS_TIMEOUT_SECONDS", 180.0)


def _request_timeout_seconds() -> float:
    return _timeout_seconds("DFQ_REQUEST_TIMEOUT_SECONDS", 90.0)


def _snapshot_timeout_seconds() -> float:
    return _timeout_seconds("DFQ_SNAPSHOT_TIMEOUT_SECONDS", 30.0)


async def _run_blocking_operation(
    operation_name: str,
    operation: Callable[[], T],
    timeout_seconds: float,
) -> T:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(operation),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        logger.warning(
            "%s timed out after %.1fs",
            operation_name,
            timeout_seconds,
        )
        raise HTTPException(
            status_code=504,
            detail=(
                f"{operation_name} timed out after {timeout_seconds:.0f} seconds. "
                "Please retry shortly; upstream market data providers may be slow or rate limited."
            ),
        ) from exc


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health probe endpoint."""
    return {"status": "ok"}


@app.get("/api/v1/market/snapshot", response_model=MarketSnapshotResult)
async def get_market_snapshot(market: str = "us", force_refresh: bool = False) -> MarketSnapshotResult:
    """Return a compact market status and index snapshot for the landing page."""
    if market not in {"us", "hk", "cn", "mixed"}:
        raise HTTPException(status_code=400, detail=f"unsupported market: {market}")

    fetcher = _make_fetcher(api_key=None, allow_sandbox_data=False)
    if force_refresh:
        fetcher.disable_cache()
    return await _run_blocking_operation(
        "market snapshot",
        lambda: build_market_snapshot(market, fetcher, force_refresh=force_refresh),
        _snapshot_timeout_seconds(),
    )


def _make_fetcher(api_key: Optional[str], allow_sandbox_data: bool) -> SmartFetcher:
    """Create a fetcher with the request's data fallback policy."""
    return analysis_service.make_fetcher(api_key, allow_sandbox_data)


def _attach_data_provenance(result: BaseModel, fetcher: SmartFetcher) -> None:
    """Attach price data provenance fields to a response model."""
    analysis_service.attach_data_provenance(result, fetcher)


def _run_alpha_from_prices(
    start_date,
    end_date,
    price_df: pd.DataFrame,
    fetcher: SmartFetcher,
) -> FactorRegressionResult:
    """Run factor attribution using only real factor observations."""
    return analysis_service.run_alpha_from_prices(start_date, end_date, price_df, fetcher)


def _optimize_portfolio_from_prices(
    payload: PortfolioOptimizeRequest,
    fetcher: SmartFetcher,
    price_df: pd.DataFrame,
    **kwargs,
) -> OptimizationResult:
    """Build an optimization result from aligned price data."""
    return analysis_service.optimize_portfolio_from_prices(payload, fetcher, price_df, **kwargs)


_select_oos_guard_weights = PortfolioAnalysisService.select_oos_guard_weights


@app.post("/api/v1/risk/evaluate", response_model=RiskEvaluationResult)
async def evaluate_risk(payload: RiskEvaluationRequest) -> RiskEvaluationResult:
    """Evaluate portfolio risk using historical and Monte Carlo ES."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)
        result = await _run_blocking_operation(
            "risk evaluation",
            lambda: engine.evaluate(payload),
            _request_timeout_seconds(),
        )
        _attach_data_provenance(result, fetcher)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/risk/anomaly", response_model=RiskAnomalyResult)
async def detect_risk_anomaly(payload: RiskAnomalyRequest) -> RiskAnomalyResult:
    """Detect abnormal portfolio risk states using engineered market features."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        detector = RiskAnomalyDetector(fetcher=fetcher, aligner=aligner)
        result = await _run_blocking_operation(
            "risk anomaly detection",
            lambda: detector.evaluate(payload),
            _request_timeout_seconds(),
        )
        _attach_data_provenance(result, fetcher)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/risk/regime", response_model=MarketRegimeResult)
async def detect_market_regime(payload: MarketRegimeRequest) -> MarketRegimeResult:
    """Detect the current portfolio market regime using engineered market features."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        detector = MarketRegimeDetector(fetcher=fetcher, aligner=aligner)
        result = await _run_blocking_operation(
            "market regime detection",
            lambda: detector.evaluate(payload),
            _request_timeout_seconds(),
        )
        _attach_data_provenance(result, fetcher)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/risk/ml-forecast", response_model=MLRiskForecastResult)
async def forecast_ml_risk(payload: MLRiskForecastRequest) -> MLRiskForecastResult:
    """Forecast portfolio downside risk using an ML enhancement model."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        engine = MLRiskEngine(fetcher=fetcher, aligner=aligner)
        result = await _run_blocking_operation(
            "ML risk forecast",
            lambda: engine.evaluate(payload),
            _request_timeout_seconds(),
        )
        _attach_data_provenance(result, fetcher)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/risk/crisis-warning", response_model=CrisisWarningResult)
async def crisis_warning(payload: CrisisWarningRequest) -> CrisisWarningResult:
    """Estimate explainable tail-risk event probability from offline artifacts."""
    try:
        return await _run_blocking_operation(
            "crisis warning",
            lambda: crisis_warning_service.evaluate(payload),
            _request_timeout_seconds(),
        )
    except CrisisWarningUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/alpha/fama-french", response_model=FactorRegressionResult)
async def fama_french_alpha(payload: AlphaAnalysisRequest) -> FactorRegressionResult:
    """Run Fama-French factor attribution on an equal-weighted portfolio."""
    try:
        if payload.market == "cn":
            raise ValueError("China A-share factor attribution is not supported yet.")
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)
        price_df = await _run_blocking_operation(
            "alpha price fetch",
            lambda: engine._fetch_prices(
                payload.tickers,
                payload.start_date,
                payload.end_date,
                market_mode=payload.market,
            ),
            _request_timeout_seconds(),
        )
        result = await _run_blocking_operation(
            "alpha attribution",
            lambda: _run_alpha_from_prices(
                payload.start_date,
                payload.end_date,
                price_df,
                fetcher,
            ),
            _request_timeout_seconds(),
        )
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/analysis/run", response_model=AnalysisRunResult)
async def run_analysis(payload: AnalysisRunRequest) -> AnalysisRunResult:
    """Run the complete analysis workflow from one request."""
    try:
        return await _run_blocking_operation(
            "analysis run",
            lambda: asyncio.run(analysis_service.run_analysis(payload)),
            _analysis_timeout_seconds(),
        )
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        logger.warning("analysis run failed error=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("analysis run crashed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/risk/report", response_model=RiskReportResult)
async def generate_risk_report(payload: RiskReportRequest) -> RiskReportResult:
    """Generate a structured risk report from the full analysis workflow."""
    try:
        return await _run_blocking_operation(
            "risk report generation",
            lambda: asyncio.run(analysis_service.generate_risk_report(payload)),
            _analysis_timeout_seconds(),
        )
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        logger.warning("risk report generation failed error=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("risk report generation crashed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/portfolio/optimize", response_model=OptimizationResult)
async def optimize_portfolio(payload: PortfolioOptimizeRequest) -> OptimizationResult:
    """Optimize portfolio weights using Black-Litterman and mean-variance."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)
        price_df = await _run_blocking_operation(
            "portfolio price fetch",
            lambda: engine._fetch_prices(
                payload.tickers,
                payload.start_date,
                payload.end_date,
                market_mode=payload.market,
            ),
            _request_timeout_seconds(),
        )
        portfolio_source = fetcher.last_source
        portfolio_source_detail = fetcher.last_source_detail
        return await _run_blocking_operation(
            "portfolio optimization",
            lambda: _optimize_portfolio_from_prices(
                payload,
                fetcher,
                price_df,
                portfolio_source=portfolio_source,
                portfolio_source_detail=portfolio_source_detail,
            ),
            _request_timeout_seconds(),
        )
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
