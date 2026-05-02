"""FastAPI backend for the DeepFirm Quant engine."""

import os
from contextlib import asynccontextmanager
from datetime import date
from typing import AsyncGenerator, List, Literal, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator

from data_pipeline import AlignmentError, DataFetcherError, MarketAligner, SmartFetcher
from models import (
    BayesianOptimizer,
    FactorAnalyzer,
    FactorRegressionResult,
    OptimizationResult,
    RiskEngine,
    RiskEvaluationRequest,
    RiskEvaluationResult,
    ViewSpec,
)
from models.market_validation import validate_market_tickers


class AlphaAnalysisRequest(BaseModel):
    """Request for Fama-French alpha attribution."""

    tickers: List[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
    api_key: Optional[str] = Field(default=None, description="Tiingo API key for failover")
    market: Literal["us", "hk", "mixed"] = Field(default="us", description="Market mode")

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, end_date: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        return end_date

    @model_validator(mode="after")
    def validate_market_contract(self) -> "AlphaAnalysisRequest":
        validate_market_tickers(self.tickers, self.market)
        return self


class PortfolioOptimizeRequest(BaseModel):
    """Request for Black-Litterman portfolio optimization."""

    tickers: List[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
    views: List[ViewSpec] = Field(default_factory=list)
    risk_aversion: float = Field(default=2.5, gt=0.0)
    weights: List[float] = Field(default_factory=list)
    max_weight: float = Field(default=0.40, gt=0.0, le=1.0)
    api_key: Optional[str] = Field(default=None, description="Tiingo API key for failover")
    backtest_enabled: bool = Field(default=False, description="Enable out-of-sample backtest")
    test_ratio: float = Field(default=0.20, ge=0.10, le=0.30, description="Fraction of data to hold out for testing")
    market: Literal["us", "hk", "mixed"] = Field(default="us", description="Market mode")

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, end_date: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        return end_date

    @model_validator(mode="after")
    def validate_market_contract(self) -> "PortfolioOptimizeRequest":
        validate_market_tickers(self.tickers, self.market)
        return self


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events."""
    yield


app = FastAPI(
    title="DeepFirm Quant",
    description="Industrial-grade quant risk and decision engine",
    version="1.1.0",
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

aligner = MarketAligner()
factor_analyzer = FactorAnalyzer()
bl_optimizer = BayesianOptimizer()


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health probe endpoint."""
    return {"status": "ok"}


@app.post("/api/v1/risk/evaluate", response_model=RiskEvaluationResult)
async def evaluate_risk(payload: RiskEvaluationRequest) -> RiskEvaluationResult:
    """Evaluate portfolio risk using historical and Monte Carlo ES."""
    try:
        fetcher = SmartFetcher(api_key=payload.api_key)
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)
        result = engine.evaluate(payload)
        result.source = fetcher.last_source
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/alpha/fama-french", response_model=FactorRegressionResult)
async def fama_french_alpha(payload: AlphaAnalysisRequest) -> FactorRegressionResult:
    """Run Fama-French three-factor attribution on an equal-weighted portfolio."""
    try:
        fetcher = SmartFetcher(api_key=payload.api_key)
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)
        price_df = engine._fetch_prices(
            payload.tickers, payload.start_date, payload.end_date, market_mode=payload.market
        )
        returns_df = RiskEngine.compute_log_returns(price_df)
        portfolio_returns = returns_df.mean(axis=1)
        factors_df = factor_analyzer.fetch_kf_french_factors(
            payload.start_date, payload.end_date
        )
        result = factor_analyzer.regress_portfolio(portfolio_returns, factors_df)
        result.source = fetcher.last_source
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/v1/portfolio/optimize", response_model=OptimizationResult)
async def optimize_portfolio(payload: PortfolioOptimizeRequest) -> OptimizationResult:
    """Optimize portfolio weights using Black-Litterman and mean-variance."""
    try:
        fetcher = SmartFetcher(api_key=payload.api_key)
        engine = RiskEngine(fetcher=fetcher, aligner=aligner)
        price_df = engine._fetch_prices(
            payload.tickers, payload.start_date, payload.end_date, market_mode=payload.market
        )
        returns_df = RiskEngine.compute_log_returns(price_df)

        if payload.backtest_enabled:
            train_df, test_df = RiskEngine.split_returns(returns_df, payload.test_ratio)
            prior_returns, cov_matrix = RiskEngine.prepare_optimization_inputs(
                train_df,
                len(payload.tickers),
            )
        else:
            prior_returns, cov_matrix = RiskEngine.prepare_optimization_inputs(
                returns_df,
                len(payload.tickers),
            )

        result = bl_optimizer.optimize_with_views(
            tickers=payload.tickers,
            prior_returns=prior_returns,
            cov_matrix=cov_matrix,
            views=payload.views,
            risk_aversion=payload.risk_aversion,
            weights=payload.weights,
            max_weight=payload.max_weight,
        )
        portfolio_source = fetcher.last_source

        if payload.backtest_enabled:
            posterior_weights = np.asarray(result.posterior_weights)
            BENCHMARK_MAP = {"us": "SPY", "hk": "^HSI", "mixed": "VT"}
            benchmark_ticker = BENCHMARK_MAP.get(payload.market, "SPY")

            bench_resp = fetcher.fetch_us_equity(benchmark_ticker, payload.start_date, payload.end_date)
            bench_prices = bench_resp.data.set_index("Date")["Close"]
            bench_prices.index = pd.to_datetime(bench_prices.index).tz_localize(None).normalize()
            bench_returns = np.log(bench_prices / bench_prices.shift(1)).dropna()
            bench_returns = bench_returns.reindex(test_df.index).fillna(0.0)

            opt_metrics = RiskEngine.compute_performance_metrics(test_df, posterior_weights)
            bench_metrics = RiskEngine.compute_performance_metrics(
                pd.DataFrame({"benchmark": bench_returns}, index=test_df.index),
                np.array([1.0]),
            )
            result.backtest_enabled = True
            result.oos_dates = opt_metrics["dates"]
            result.oos_optimized_cum_returns = opt_metrics["cumulative_returns"]
            result.oos_benchmark_cum_returns = bench_metrics["cumulative_returns"]
            result.oos_optimized_ann_vol = opt_metrics["annualized_volatility"]
            result.oos_benchmark_ann_vol = bench_metrics["annualized_volatility"]
            result.oos_optimized_max_drawdown = opt_metrics["max_drawdown"]
            result.oos_benchmark_max_drawdown = bench_metrics["max_drawdown"]
            result.oos_excess_return = opt_metrics["cumulative_returns"][-1] - bench_metrics["cumulative_returns"][-1]
            result.oos_optimized_sharpe = opt_metrics["sharpe_ratio"]
            result.oos_benchmark_sharpe = bench_metrics["sharpe_ratio"]

            strategy_daily = test_df.to_numpy() @ posterior_weights
            benchmark_daily = bench_returns.to_numpy()
            result.oos_optimized_ir = RiskEngine.compute_information_ratio(strategy_daily, benchmark_daily)

            score_result = RiskEngine.calculate_model_score({
                "sharpe_ratio": opt_metrics["sharpe_ratio"],
                "max_drawdown": opt_metrics["max_drawdown"],
                "information_ratio": result.oos_optimized_ir,
                "annualized_volatility": opt_metrics["annualized_volatility"],
                "excess_return": result.oos_excess_return,
                "benchmark_annualized_volatility": bench_metrics["annualized_volatility"],
            })
            result.model_score = score_result["total_score"]
            result.model_grade = score_result["grade"]
            result.model_score_risk_control = score_result["risk_control"]
            result.model_score_profitability = score_result["profitability"]
            result.model_score_alpha = score_result["alpha_capability"]
            result.model_score_stability = score_result["stability"]
            result.model_score_win_rate = score_result["win_rate"]
            result.model_score_consistency = score_result["consistency"]

        result.source = portfolio_source
    except (DataFetcherError, AlignmentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result
