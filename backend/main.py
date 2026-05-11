"""FastAPI backend for the DeepFirm Quant engine."""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.schemas import AlphaAnalysisRequest, AnalysisRunRequest, AnalysisRunResult, PortfolioOptimizeRequest
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
analysis_service = PortfolioAnalysisService(logger=logger)
aligner = analysis_service.aligner
factor_analyzer = analysis_service.factor_analyzer
bl_optimizer = analysis_service.optimizer
allocation_policy_engine = analysis_service.allocation_policy_engine
crisis_warning_service = analysis_service.crisis_warning_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events."""
    crisis_warning_service.load_artifacts()
    yield


app = FastAPI(
    title="DeepFirm Quant",
    description="Industrial-grade quant risk and decision engine",
    version="3.5.0",
    lifespan=lifespan,
)

origins_env = os.getenv("ALLOW_ORIGINS")
if origins_env:
    allow_origins = [o.strip() for o in origins_env.split(",")]
else:
    allow_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health probe endpoint."""
    return {"status": "ok"}


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
        result = engine.evaluate(payload)
        _attach_data_provenance(result, fetcher)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/risk/anomaly", response_model=RiskAnomalyResult)
async def detect_risk_anomaly(payload: RiskAnomalyRequest) -> RiskAnomalyResult:
    """Detect abnormal portfolio risk states using engineered market features."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        detector = RiskAnomalyDetector(fetcher=fetcher, aligner=aligner)
        result = detector.evaluate(payload)
        _attach_data_provenance(result, fetcher)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/risk/regime", response_model=MarketRegimeResult)
async def detect_market_regime(payload: MarketRegimeRequest) -> MarketRegimeResult:
    """Detect the current portfolio market regime using engineered market features."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        detector = MarketRegimeDetector(fetcher=fetcher, aligner=aligner)
        result = detector.evaluate(payload)
        _attach_data_provenance(result, fetcher)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/risk/ml-forecast", response_model=MLRiskForecastResult)
async def forecast_ml_risk(payload: MLRiskForecastRequest) -> MLRiskForecastResult:
    """Forecast portfolio downside risk using an ML enhancement model."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        engine = MLRiskEngine(fetcher=fetcher, aligner=aligner)
        result = engine.evaluate(payload)
        _attach_data_provenance(result, fetcher)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/risk/crisis-warning", response_model=CrisisWarningResult)
async def crisis_warning(payload: CrisisWarningRequest) -> CrisisWarningResult:
    """Estimate explainable tail-risk event probability from offline artifacts."""
    try:
        return crisis_warning_service.evaluate(payload)
    except CrisisWarningUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        price_df = engine._fetch_prices(
            payload.tickers, payload.start_date, payload.end_date, market_mode=payload.market
        )
        result = _run_alpha_from_prices(
            payload.start_date,
            payload.end_date,
            price_df,
            fetcher,
        )
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/analysis/run", response_model=AnalysisRunResult)
async def run_analysis(payload: AnalysisRunRequest) -> AnalysisRunResult:
    """Run the complete analysis workflow from one request."""
    try:
        return await analysis_service.run_analysis(payload)
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        logger.warning("analysis run failed error=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("analysis run crashed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/portfolio/optimize", response_model=OptimizationResult)
async def optimize_portfolio(payload: PortfolioOptimizeRequest) -> OptimizationResult:
    """Optimize portfolio weights using Black-Litterman and mean-variance."""
    try:
        fetcher = _make_fetcher(payload.api_key, payload.allow_sandbox_data)
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)
        price_df = engine._fetch_prices(
            payload.tickers, payload.start_date, payload.end_date, market_mode=payload.market
        )
        portfolio_source = fetcher.last_source
        portfolio_source_detail = fetcher.last_source_detail
        return _optimize_portfolio_from_prices(
            payload,
            fetcher,
            price_df,
            portfolio_source=portfolio_source,
            portfolio_source_detail=portfolio_source_detail,
        )
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
