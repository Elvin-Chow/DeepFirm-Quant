"""Backend orchestration services for portfolio analysis."""

import asyncio
import importlib
import logging
import queue
import threading
import time
from datetime import date, datetime, timedelta
from typing import Callable, List, Optional, TypeVar, cast

import numpy as np
import pandas as pd
from pydantic import BaseModel

from backend.schemas import AnalysisRunRequest, AnalysisRunResult, PortfolioOptimizeRequest
from data_pipeline import MarketAligner, SmartFetcher
from data_pipeline.exceptions import DataFetcherError
from models.market_validation import MarketMode
from models import (
    AllocationPolicyEngine,
    BayesianOptimizer,
    CrisisWarningResult,
    CrisisWarningService,
    CrisisWarningUnavailableError,
    FactorAnalyzer,
    FactorRegressionResult,
    MarketRegimeDetector,
    MarketRegimeResult,
    MLRiskEngine,
    MLRiskForecastResult,
    OptimizationResult,
    RiskAnomalyDetector,
    RiskAnomalyResult,
    RiskEngine,
    RiskEvaluationRequest,
    RiskEvaluationResult,
)

T = TypeVar("T")


def _akshare_module():
    return importlib.import_module("akshare")


class _LazyAkShare:
    def __getattr__(self, name: str):
        return getattr(_akshare_module(), name)


ak = _LazyAkShare()


BENCHMARKS: dict[MarketMode, tuple[str, str]] = {
    "us": ("SPY", "SPDR S&P 500 ETF Trust"),
    "hk": ("^HSI", "Hang Seng Index"),
    "cn": ("000300", "CSI 300 Index"),
    "mixed": ("ACWI", "iShares MSCI ACWI ETF"),
}
DEFAULT_RISK_FREE_RATE = 0.02
RISK_FREE_TICKER = "^IRX"


class PortfolioAnalysisService:
    """Coordinate data fetching, analytics modules, and optimization results."""

    def __init__(
        self,
        aligner: Optional[MarketAligner] = None,
        factor_analyzer: Optional[FactorAnalyzer] = None,
        optimizer: Optional[BayesianOptimizer] = None,
        allocation_policy_engine: Optional[AllocationPolicyEngine] = None,
        crisis_warning_service: Optional[CrisisWarningService] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.aligner = aligner or MarketAligner()
        self.factor_analyzer = factor_analyzer or FactorAnalyzer()
        self.optimizer = optimizer or BayesianOptimizer()
        self.allocation_policy_engine = allocation_policy_engine or AllocationPolicyEngine()
        self.crisis_warning_service = crisis_warning_service or CrisisWarningService(
            aligner=self.aligner,
            logger=logger,
        )
        self.logger = logger or logging.getLogger(__name__)

    @staticmethod
    def make_fetcher(api_key: Optional[str], allow_sandbox_data: bool) -> SmartFetcher:
        """Create a fetcher with the request's data fallback policy."""
        return SmartFetcher(api_key=api_key, allow_sandbox_data=allow_sandbox_data)

    @staticmethod
    def attach_data_provenance(result: BaseModel, fetcher: SmartFetcher) -> None:
        """Attach price data provenance fields to a response model."""
        setattr(result, "source", fetcher.last_source)
        setattr(result, "source_detail", fetcher.last_source_detail)
        existing_warnings = list(getattr(result, "data_warnings", []) or [])
        merged_warnings = existing_warnings.copy()
        for warning in fetcher.data_warnings:
            if warning not in merged_warnings:
                merged_warnings.append(warning)
        setattr(result, "data_warnings", merged_warnings)

    @staticmethod
    def timed_stage(timings: dict[str, float], name: str, fn: Callable[[], T]) -> T:
        """Run one analysis stage and record elapsed seconds."""
        started = time.perf_counter()
        try:
            return fn()
        finally:
            timings[name] = round(time.perf_counter() - started, 4)

    def run_alpha_from_prices(
        self,
        start_date: date,
        end_date: date,
        price_df: pd.DataFrame,
        fetcher: SmartFetcher,
    ) -> FactorRegressionResult:
        """Run factor attribution using only real factor observations."""
        returns_df = RiskEngine.compute_log_returns(price_df)
        portfolio_returns = returns_df.mean(axis=1)
        factors_df = self.factor_analyzer.fetch_kf_french_factors(
            start_date,
            end_date,
            allow_truncated=True,
        )
        result = self.factor_analyzer.regress_portfolio(portfolio_returns, factors_df)
        self.attach_data_provenance(result, fetcher)
        return result

    @staticmethod
    def normalize_benchmark_prices(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Normalize benchmark prices into Date and Close columns."""
        if df.empty:
            raise DataFetcherError(
                message=f"empty benchmark dataframe for {symbol}",
                symbol=symbol,
                source="benchmark",
            )

        if "Date" in df.columns:
            date_col = "Date"
        elif "日期" in df.columns:
            date_col = "日期"
        else:
            date_col = df.columns[0]

        if "Close" in df.columns:
            close_col = "Close"
        elif "收盘" in df.columns:
            close_col = "收盘"
        else:
            raise DataFetcherError(
                message=f"missing benchmark close column for {symbol}",
                symbol=symbol,
                source="benchmark",
            )

        dates = pd.to_datetime(df[date_col], errors="coerce")
        close = pd.to_numeric(df[close_col], errors="coerce")
        if dates.isna().any():
            raise ValueError(f"unparseable benchmark dates for {symbol}")
        close_values = close.to_numpy(dtype=float)
        if not np.isfinite(close_values).all():
            raise ValueError(f"non-finite benchmark close prices for {symbol}")
        if (close_values <= 0.0).any():
            raise ValueError(f"non-positive benchmark close prices for {symbol}")

        normalized = pd.DataFrame({"Date": dates.dt.tz_localize(None).dt.normalize(), "Close": close_values})
        normalized = normalized.sort_values("Date")
        normalized = normalized.drop_duplicates(subset=["Date"], keep="last")
        if len(normalized) < 2:
            raise ValueError(f"at least two valid benchmark prices are required for {symbol}")
        return normalized.reset_index(drop=True)

    @staticmethod
    def normalize_cn_benchmark_yahoo_symbol(symbol: str) -> str:
        """Normalize a China benchmark symbol for Yahoo Finance fallback."""
        if symbol == "000300":
            return "000300.SS"
        return SmartFetcher._normalize_cn_yahoo_symbol(symbol)

    @staticmethod
    def call_provider_with_timeout(
        provider_name: str,
        timeout_seconds: float,
        provider_call: Callable[[], pd.DataFrame],
    ) -> pd.DataFrame:
        """Run a blocking provider call with a bounded wait."""
        result_queue: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

        def run_provider() -> None:
            try:
                result_queue.put((True, provider_call()))
            except Exception as exc:
                result_queue.put((False, exc))

        worker = threading.Thread(
            target=run_provider,
            name=f"{provider_name}-fetch",
            daemon=True,
        )
        worker.start()
        worker.join(timeout_seconds)
        if worker.is_alive():
            raise TimeoutError(f"{provider_name} timed out after {timeout_seconds:.1f}s")

        succeeded, value = result_queue.get_nowait()
        if succeeded:
            return cast(pd.DataFrame, value)
        if isinstance(value, BaseException):
            raise value
        raise RuntimeError(f"{provider_name} failed without an exception")

    def fetch_benchmark_prices(
        self,
        fetcher: SmartFetcher,
        symbol: str,
        start_date: date,
        end_date: date,
        market: MarketMode,
    ) -> pd.DataFrame:
        """Fetch benchmark prices for the selected market mode."""
        if market == "cn":
            provider_errors: list[str] = []
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            if fetcher.is_china_akshare_cooling_down():
                provider_errors.append("akshare: skipped during provider cooldown")
            else:
                try:
                    df = self.call_provider_with_timeout(
                        "akshare_cn_benchmark",
                        SmartFetcher._akshare_timeout_seconds(),
                        lambda: ak.index_zh_a_hist(
                            symbol=symbol,
                            period="daily",
                            start_date=start_str,
                            end_date=end_str,
                        ),
                    )
                    fetcher._mark_source("akshare", "AKShare CSI 300 index daily")
                    return self.normalize_benchmark_prices(df, symbol)
                except Exception as exc:
                    fetcher._register_china_akshare_failure()
                    provider_errors.append(f"akshare: {exc}")
                    self.logger.warning("AKShare China benchmark fetch failed for %s: %s", symbol, exc)

            try:
                yahoo_symbol = self.normalize_cn_benchmark_yahoo_symbol(symbol)
                df = fetcher._fetch_yahoo_chart(yahoo_symbol, start_date, end_date)
                fetcher._mark_source("yahoo_chart", "Yahoo Finance chart API (CSI 300 fallback)")
                fetcher._append_warning(
                    f"{symbol}: AKShare benchmark data was unavailable; using Yahoo Finance fallback"
                )
                return self.normalize_benchmark_prices(df, symbol)
            except Exception as exc:
                provider_errors.append(f"yahoo_chart: {exc}")
                self.logger.warning("Yahoo China benchmark fallback failed for %s: %s", symbol, exc)

            if fetcher.allow_sandbox_data:
                df = fetcher._fetch_sandbox(symbol, start_date, end_date)
                fetcher._mark_source("sandbox", "sandbox demo")
                fetcher._append_warning(f"{symbol}: using sandbox demo benchmark prices")
                return self.normalize_benchmark_prices(df, symbol)

            raise DataFetcherError(
                message=(
                    f"Unable to fetch real China benchmark data for {symbol}. "
                    + "; ".join(provider_errors)
                ),
                symbol=symbol,
                source="benchmark",
            )

        bench_resp = fetcher.fetch_us_equity(
            symbol,
            start_date,
            end_date,
        )
        return self.normalize_benchmark_prices(bench_resp.data, symbol)

    def resolve_risk_free_rate(
        self,
        fetcher: SmartFetcher,
        requested_rate: Optional[float],
        asof: Optional[date] = None,
    ) -> tuple[float, str, str, list[str]]:
        """Return the risk-free rate, source label, and non-fatal warnings."""
        if requested_rate is not None:
            return float(requested_rate), "request", "Request override", []
        try:
            end = asof if asof is not None else datetime.now().date()
            start = end - timedelta(days=7)
            resp = fetcher.fetch_us_equity(RISK_FREE_TICKER, start, end)
            latest = float(resp.data["Close"].iloc[-1])
            if latest > 0.5:
                latest = latest / 100.0
            return latest, RISK_FREE_TICKER, "US 13-week Treasury bill proxy", []
        except Exception:
            return (
                DEFAULT_RISK_FREE_RATE,
                "fallback",
                "Deterministic fallback (2.00% annualized)",
                ["Risk-free rate was unavailable; defaulted to 2.00% annualized."],
            )

    @staticmethod
    def fetch_market_caps(
        tickers: List[str],
        cov_matrix: Optional[np.ndarray] = None,
        asof: Optional[date] = None,
        market: MarketMode = "us",
    ) -> Optional[List[float]]:
        """Fetch market capitalization or use a non-leaking inverse-volatility proxy."""
        if market == "cn":
            return None

        if (
            asof is not None
            and asof < datetime.now().date()
            and cov_matrix is not None
        ):
            try:
                cov = np.asarray(cov_matrix, dtype=float)
                if cov.ndim == 2 and cov.shape[0] == cov.shape[1] == len(tickers):
                    inv_vol = 1.0 / np.sqrt(np.diag(cov) + 1e-8)
                    inv_vol_sum = float(inv_vol.sum())
                    if inv_vol_sum > 1e-12:
                        return (inv_vol / inv_vol_sum).tolist()
            except Exception:
                pass
            return None

        try:
            import time as time_module

            import yfinance as yf

            caps = []
            for ticker in tickers:
                try:
                    info = yf.Ticker(ticker).info
                    cap = float(info.get("marketCap", 0.0))
                    caps.append(cap)
                except Exception:
                    caps.append(0.0)
                time_module.sleep(0.3)
            if all(c <= 1e-12 for c in caps):
                return None
            return caps
        except Exception:
            return None

    @staticmethod
    def score_oos_metrics(
        metrics: dict,
        strategy_daily: np.ndarray,
        benchmark_daily: np.ndarray,
        benchmark_metrics: dict,
    ) -> dict:
        """Score OOS performance against the selected benchmark."""
        ir = RiskEngine.compute_information_ratio(strategy_daily, benchmark_daily)
        excess_return = (
            metrics["cumulative_returns"][-1]
            - benchmark_metrics["cumulative_returns"][-1]
        )
        score = RiskEngine.calculate_model_score(
            {
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "information_ratio": ir,
                "annualized_volatility": metrics["annualized_volatility"],
                "excess_return": excess_return,
                "benchmark_annualized_volatility": benchmark_metrics["annualized_volatility"],
                "expected_shortfall": metrics.get("expected_shortfall", 0.0),
            },
            strategy_daily=strategy_daily,
            benchmark_daily=benchmark_daily,
        )
        return {
            "information_ratio": ir,
            "excess_return": excess_return,
            "score": score,
        }

    @staticmethod
    def select_oos_guard_weights(
        prior_weights: np.ndarray,
        raw_weights: np.ndarray,
        prior_metrics: dict,
        raw_metrics: dict,
        prior_score: float,
        raw_score: float,
        enabled: bool,
        raw_excess_return: Optional[float] = None,
        raw_information_ratio: Optional[float] = None,
        ml_risk_level: str = "",
        regime: str = "",
        anomaly_impact: str = "",
    ) -> tuple[np.ndarray, str]:
        """Select final recommendation weights from raw and prior OOS evidence."""
        if not enabled:
            return raw_weights.copy(), "raw"
        if np.allclose(prior_weights, raw_weights, atol=1e-10, rtol=1e-10):
            return raw_weights.copy(), "raw"

        raw_cum_return = raw_metrics["cumulative_returns"][-1]
        prior_cum_return = prior_metrics["cumulative_returns"][-1]
        prior_not_worse = (
            prior_score >= raw_score - 1.0
            and prior_cum_return >= raw_cum_return - 0.001
        )
        prior_clearly_better = (
            prior_score >= raw_score + 5.0
            and prior_cum_return >= raw_cum_return + 0.01
        )

        force_context = (
            anomaly_impact in {"force_oos_guard", "freeze_rebalance"}
            or regime == "Crisis"
            or ml_risk_level == "Extreme"
        )
        tight_context = (
            force_context
            or anomaly_impact == "tighten_constraints"
            or regime == "High Volatility"
            or ml_risk_level == "High"
        )
        if force_context and raw_score < 65.0 and prior_not_worse:
            return prior_weights * 0.40 + raw_weights * 0.60, "defensive_blend"
        if (
            tight_context
            and raw_information_ratio is not None
            and raw_information_ratio < 0.15
            and raw_score < 62.0
            and prior_not_worse
        ):
            return prior_weights * 0.50 + raw_weights * 0.50, "balanced_blend"

        if raw_excess_return is not None:
            if (
                raw_excess_return < -0.015
                and raw_score < 50.0
                and prior_clearly_better
            ):
                return prior_weights * 0.40 + raw_weights * 0.60, "defensive_blend"
            if (
                raw_information_ratio is not None
                and raw_excess_return < -0.005
                and raw_information_ratio < 0.0
                and raw_score < 60.0
                and prior_not_worse
            ):
                return prior_weights * 0.50 + raw_weights * 0.50, "balanced_blend"

        if raw_score < prior_score - 5.0 and raw_cum_return < prior_cum_return - 0.01:
            return prior_weights * 0.40 + raw_weights * 0.60, "defensive_blend"
        if raw_score < prior_score - 1.0 and raw_cum_return < prior_cum_return - 0.003:
            return prior_weights * 0.50 + raw_weights * 0.50, "balanced_blend"
        return raw_weights.copy(), "raw"

    async def run_analysis(self, payload: AnalysisRunRequest) -> AnalysisRunResult:
        """Run the complete analysis workflow from one request."""
        timings: dict[str, float] = {}
        analysis_started = time.perf_counter()
        fetcher = self.make_fetcher(payload.api_key, payload.allow_sandbox_data)
        engine = RiskEngine(fetcher=fetcher, aligner=self.aligner)
        price_df = self.timed_stage(
            timings,
            "prices",
            lambda: engine._fetch_prices(
                payload.tickers,
                payload.start_date,
                payload.end_date,
                market_mode=payload.market,
            ),
        )
        portfolio_source = fetcher.last_source
        portfolio_source_detail = fetcher.last_source_detail
        alpha_meta = {
            "status": "unavailable",
            "message": "Alpha attribution was not run.",
            "factor_available_through": None,
            "effective_start": None,
            "effective_end": None,
        }

        risk_payload = RiskEvaluationRequest(
            tickers=payload.tickers,
            start_date=payload.start_date,
            end_date=payload.end_date,
            confidence_level=payload.confidence_level,
            weights=payload.weights,
            api_key=payload.api_key,
            allow_sandbox_data=payload.allow_sandbox_data,
            mc_paths=payload.mc_paths,
            capital=payload.capital,
            leverage=payload.leverage,
            market=payload.market,
        )

        def build_risk() -> RiskEvaluationResult:
            result = engine.evaluate_from_prices(risk_payload, price_df)
            self.attach_data_provenance(result, fetcher)
            return result

        def build_alpha() -> Optional[FactorRegressionResult]:
            if payload.market == "cn":
                alpha_meta.update(
                    {
                        "status": "unavailable",
                        "message": "China A-share factor attribution is not supported yet.",
                        "factor_available_through": None,
                        "effective_start": None,
                        "effective_end": None,
                    }
                )
                return None

            try:
                result = self.run_alpha_from_prices(
                    payload.start_date,
                    payload.end_date,
                    price_df,
                    fetcher,
                )
                alpha_meta.update(
                    {
                        "status": result.alpha_status,
                        "message": "",
                        "factor_available_through": result.factor_available_through or None,
                        "effective_start": result.alpha_effective_start or None,
                        "effective_end": result.alpha_effective_end or None,
                    }
                )
                return result
            except (DataFetcherError, ValueError) as exc:
                alpha_meta.update(
                    {
                        "status": "unavailable",
                        "message": str(exc),
                        "factor_available_through": None,
                        "effective_start": None,
                        "effective_end": None,
                    }
                )
                self.logger.warning(
                    "alpha attribution unavailable tickers=%s start=%s end=%s error=%s",
                    ",".join(payload.tickers),
                    payload.start_date.isoformat(),
                    payload.end_date.isoformat(),
                    exc,
                )
                return None

        def build_anomaly() -> Optional[RiskAnomalyResult]:
            try:
                result = RiskAnomalyDetector().evaluate_from_prices(
                    tickers=payload.tickers,
                    price_df=price_df,
                    weights=payload.weights,
                    source=portfolio_source,
                )
                self.attach_data_provenance(result, fetcher)
                return result
            except ValueError:
                return None

        def build_regime() -> Optional[MarketRegimeResult]:
            try:
                result = MarketRegimeDetector().evaluate_from_prices(
                    tickers=payload.tickers,
                    price_df=price_df,
                    weights=payload.weights,
                    model_type=payload.regime_model_type,
                    source=portfolio_source,
                )
                self.attach_data_provenance(result, fetcher)
                return result
            except ValueError:
                return None

        def build_ml() -> Optional[MLRiskForecastResult]:
            try:
                result = MLRiskEngine().evaluate_from_prices(
                    tickers=payload.tickers,
                    price_df=price_df,
                    weights=payload.weights,
                    horizon=payload.ml_horizon,
                    confidence_level=payload.ml_confidence_level,
                    source=portfolio_source,
                )
                self.attach_data_provenance(result, fetcher)
                return result
            except ValueError:
                return None

        def build_crisis_warning() -> Optional[CrisisWarningResult]:
            if not payload.crisis_enabled:
                return None
            try:
                return self.crisis_warning_service.evaluate_from_prices(
                    tickers=payload.tickers,
                    price_df=price_df,
                    weights=payload.weights,
                    horizon=payload.crisis_horizon,
                    source=portfolio_source,
                    source_detail=portfolio_source_detail,
                    data_warnings=list(fetcher.data_warnings),
                )
            except CrisisWarningUnavailableError as exc:
                self.logger.error(
                    "crisis warning unavailable tickers=%s horizon=%s error=%s",
                    ",".join(payload.tickers),
                    payload.crisis_horizon,
                    exc,
                )
                raise ValueError(f"Crisis warning artifact is unavailable: {exc}") from exc
            except ValueError as exc:
                self.logger.error(
                    "crisis warning failed tickers=%s horizon=%s error=%s",
                    ",".join(payload.tickers),
                    payload.crisis_horizon,
                    exc,
                )
                raise

        risk_result, alpha_result, anomaly_result, regime_result, ml_result, crisis_result = await asyncio.gather(
            asyncio.to_thread(self.timed_stage, timings, "risk", build_risk),
            asyncio.to_thread(self.timed_stage, timings, "alpha", build_alpha),
            asyncio.to_thread(self.timed_stage, timings, "anomaly", build_anomaly),
            asyncio.to_thread(self.timed_stage, timings, "regime", build_regime),
            asyncio.to_thread(self.timed_stage, timings, "ml_forecast", build_ml),
            asyncio.to_thread(self.timed_stage, timings, "crisis_warning", build_crisis_warning),
        )

        opt_payload = PortfolioOptimizeRequest(
            tickers=payload.tickers,
            start_date=payload.start_date,
            end_date=payload.end_date,
            views=payload.views,
            risk_aversion=payload.risk_aversion,
            weights=payload.weights,
            max_weight=payload.max_weight,
            min_weight=payload.min_weight,
            turnover_penalty=payload.turnover_penalty,
            concentration_penalty=payload.concentration_penalty,
            oos_guard_enabled=payload.oos_guard_enabled,
            allocation_mode=payload.allocation_mode,
            api_key=payload.api_key,
            allow_sandbox_data=payload.allow_sandbox_data,
            backtest_enabled=payload.backtest_enabled,
            test_ratio=payload.test_ratio,
            market=payload.market,
            risk_free_rate=payload.risk_free_rate,
            use_market_cap_prior=payload.use_market_cap_prior,
        )
        optimization_result = await asyncio.to_thread(
            self.timed_stage,
            timings,
            "optimization",
            lambda: self.optimize_portfolio_from_prices(
                opt_payload,
                fetcher,
                price_df,
                portfolio_source=portfolio_source,
                portfolio_source_detail=portfolio_source_detail,
                ml_result=ml_result,
                regime_result=regime_result,
                anomaly_result=anomaly_result,
            ),
        )
        timings["total"] = round(time.perf_counter() - analysis_started, 4)
        self.logger.info(
            "analysis run completed tickers=%s start=%s end=%s timings=%s",
            ",".join(payload.tickers),
            payload.start_date.isoformat(),
            payload.end_date.isoformat(),
            timings,
        )

        return AnalysisRunResult(
            risk=risk_result,
            alpha=alpha_result,
            alpha_status=alpha_meta["status"],
            alpha_message=alpha_meta["message"],
            factor_available_through=alpha_meta["factor_available_through"],
            alpha_effective_start=alpha_meta["effective_start"],
            alpha_effective_end=alpha_meta["effective_end"],
            optimization=optimization_result,
            anomaly=anomaly_result,
            regime=regime_result,
            ml_forecast=ml_result,
            crisis_warning=crisis_result,
        )

    def optimize_portfolio_from_prices(
        self,
        payload: PortfolioOptimizeRequest,
        fetcher: SmartFetcher,
        price_df: pd.DataFrame,
        portfolio_source: Optional[str] = None,
        portfolio_source_detail: Optional[str] = None,
        ml_result: Optional[MLRiskForecastResult] = None,
        regime_result: Optional[MarketRegimeResult] = None,
        anomaly_result: Optional[RiskAnomalyResult] = None,
    ) -> OptimizationResult:
        """Build an optimization result from aligned price data."""
        portfolio_source = portfolio_source or fetcher.last_source
        portfolio_source_detail = portfolio_source_detail or fetcher.last_source_detail
        returns_df = RiskEngine.compute_log_returns(price_df)

        n_assets = len(payload.tickers)

        if payload.backtest_enabled:
            train_df, test_df = RiskEngine.split_returns(returns_df, payload.test_ratio)
            asof = train_df.index[-1].date()
            initial_prior_returns, initial_cov_matrix = RiskEngine.prepare_optimization_inputs(
                train_df, n_assets,
            )
        else:
            asof = None
            train_df = None
            test_df = None
            initial_prior_returns, initial_cov_matrix = RiskEngine.prepare_optimization_inputs(
                returns_df, n_assets,
            )

        policy_price_df = price_df
        policy_asof: str | None = None
        if train_df is not None:
            policy_price_df = price_df.loc[:train_df.index[-1]]
            policy_asof = train_df.index[-1].strftime("%Y-%m-%d")
        allocation_policy = self.allocation_policy_engine.resolve_from_prices(
            tickers=payload.tickers,
            price_df=policy_price_df,
            weights=payload.weights,
            mode=payload.allocation_mode,
            requested_max_weight=payload.max_weight,
            requested_min_weight=payload.min_weight,
            requested_turnover_penalty=payload.turnover_penalty,
            requested_concentration_penalty=payload.concentration_penalty,
            asof_date=policy_asof,
            ml_result=ml_result,
            regime_result=regime_result,
            anomaly_result=anomaly_result,
        )
        max_weight = allocation_policy.max_weight
        min_weight = allocation_policy.min_weight
        turnover_penalty = allocation_policy.turnover_penalty
        concentration_penalty = allocation_policy.concentration_penalty

        risk_free_rate = 0.0
        risk_free_rate_source = ""
        risk_free_rate_source_detail = ""
        methodology_warnings: list[str] = []
        if payload.backtest_enabled:
            if payload.market == "cn" and payload.risk_free_rate is None:
                risk_free_rate = DEFAULT_RISK_FREE_RATE
                risk_free_rate_source = "fallback"
                risk_free_rate_source_detail = "China A-share policy fallback (2.00% annualized)"
                risk_free_warnings = [
                    "China A-share risk-free rate is unavailable; defaulted to 2.00% annualized.",
                    "China A-share OOS benchmark uses CSI 300 Index (000300).",
                ]
            else:
                (
                    risk_free_rate,
                    risk_free_rate_source,
                    risk_free_rate_source_detail,
                    risk_free_warnings,
                ) = self.resolve_risk_free_rate(
                    fetcher,
                    payload.risk_free_rate,
                    asof=asof,
                )
            methodology_warnings.extend(risk_free_warnings)

        regularization_boost = 1.0
        if payload.backtest_enabled and train_df is not None:
            regularization_boost = 252.0 / max(len(train_df), 30.0)
        effective_turnover_penalty = turnover_penalty * regularization_boost
        effective_concentration_penalty = concentration_penalty * regularization_boost

        market_caps: Optional[List[float]] = None
        if payload.use_market_cap_prior:
            market_caps = self.fetch_market_caps(
                payload.tickers,
                cov_matrix=initial_cov_matrix,
                asof=asof,
                market=payload.market,
            )
            if market_caps is None:
                if payload.market == "cn":
                    methodology_warnings.append(
                        "China A-share market-cap prior is unavailable; optimizer used inverse-volatility equilibrium."
                    )
                else:
                    methodology_warnings.append(
                        "Market-cap prior was unavailable; optimizer used inverse-volatility equilibrium."
                    )

        if not payload.backtest_enabled:
            result = self.optimizer.optimize_with_views(
                tickers=payload.tickers,
                prior_returns=initial_prior_returns,
                cov_matrix=initial_cov_matrix,
                views=payload.views,
                risk_aversion=payload.risk_aversion,
                weights=payload.weights,
                max_weight=max_weight,
                min_weight=min_weight,
                turnover_penalty=effective_turnover_penalty,
                concentration_penalty=effective_concentration_penalty,
                market_caps=market_caps,
                n_observations=len(returns_df),
            )
            result.allocation_policy = allocation_policy
            result.risk_free_rate = risk_free_rate
            result.risk_free_rate_source = risk_free_rate_source
            result.risk_free_rate_source_detail = risk_free_rate_source_detail
            result.methodology_warnings = methodology_warnings
            self.attach_data_provenance(result, fetcher)
            result.source = portfolio_source
            result.source_detail = portfolio_source_detail
            return result

        benchmark_symbol, benchmark_name = BENCHMARKS.get(payload.market, BENCHMARKS["us"])

        bench_df = self.fetch_benchmark_prices(
            fetcher,
            benchmark_symbol,
            payload.start_date,
            payload.end_date,
            payload.market,
        )
        benchmark_source = fetcher.last_source
        benchmark_source_detail = fetcher.last_source_detail
        bench_prices = bench_df.set_index("Date")["Close"]
        bench_prices.index = pd.to_datetime(bench_prices.index).tz_localize(None).normalize()
        bench_returns = np.log(bench_prices / bench_prices.shift(1)).dropna()

        common_idx = test_df.index.intersection(bench_returns.index)
        if len(common_idx) < 5:
            bench_aligned = bench_returns.reindex(test_df.index, method="ffill").dropna()
            common_idx = bench_aligned.index
            bench_returns_aligned = bench_aligned
        else:
            bench_returns_aligned = bench_returns.loc[common_idx]
        test_df = test_df.loc[common_idx]
        if test_df.empty or bench_returns_aligned.empty:
            raise ValueError("benchmark and test returns share no overlapping dates")

        rebalance_days = 21
        chunks_raw: List[np.ndarray] = []
        chunks_prior: List[np.ndarray] = []
        last_sub_result: Optional[OptimizationResult] = None
        cursor = 0
        while cursor < len(test_df):
            rolling_train = pd.concat(
                [train_df, test_df.iloc[:cursor]]
            ).tail(max(252, len(train_df)))
            roll_pi, roll_cov = RiskEngine.prepare_optimization_inputs(
                rolling_train, n_assets,
            )
            roll_asof = rolling_train.index[-1].date()
            roll_caps: Optional[List[float]] = None
            if payload.use_market_cap_prior:
                roll_caps = self.fetch_market_caps(
                    payload.tickers,
                    cov_matrix=roll_cov,
                    asof=roll_asof,
                    market=payload.market,
                )

            sub_result = self.optimizer.optimize_with_views(
                tickers=payload.tickers,
                prior_returns=roll_pi,
                cov_matrix=roll_cov,
                views=payload.views,
                risk_aversion=payload.risk_aversion,
                weights=payload.weights,
                max_weight=max_weight,
                min_weight=min_weight,
                turnover_penalty=effective_turnover_penalty,
                concentration_penalty=effective_concentration_penalty,
                market_caps=roll_caps,
                n_observations=len(rolling_train),
            )

            seg = test_df.iloc[cursor:cursor + rebalance_days]
            seg_prior_w = np.asarray(sub_result.prior_weights, dtype=float)
            seg_raw_w = np.asarray(sub_result.raw_posterior_weights, dtype=float)
            chunks_prior.append(seg.to_numpy() @ seg_prior_w)
            chunks_raw.append(seg.to_numpy() @ seg_raw_w)
            last_sub_result = sub_result
            cursor += rebalance_days

        if last_sub_result is None:
            raise RuntimeError("walk-forward produced no optimization sub-results")
        result = last_sub_result

        prior_daily = np.concatenate(chunks_prior)
        raw_daily = np.concatenate(chunks_raw)
        prior_weights = np.asarray(result.prior_weights, dtype=float)
        raw_posterior_weights = np.asarray(result.raw_posterior_weights, dtype=float)

        bench_metrics = RiskEngine.compute_performance_metrics(
            pd.DataFrame({"benchmark": bench_returns_aligned}, index=common_idx),
            np.array([1.0]),
            risk_free_rate=risk_free_rate,
        )
        benchmark_daily = bench_returns_aligned.to_numpy()

        prior_metrics = RiskEngine.compute_performance_metrics(
            pd.DataFrame({"strategy": prior_daily}, index=common_idx),
            np.array([1.0]),
            risk_free_rate=risk_free_rate,
        )
        raw_metrics = RiskEngine.compute_performance_metrics(
            pd.DataFrame({"strategy": raw_daily}, index=common_idx),
            np.array([1.0]),
            risk_free_rate=risk_free_rate,
        )

        prior_scored = self.score_oos_metrics(
            prior_metrics, prior_daily, benchmark_daily, bench_metrics,
        )
        raw_scored = self.score_oos_metrics(
            raw_metrics, raw_daily, benchmark_daily, bench_metrics,
        )
        raw_score = raw_scored["score"]["total_score"]
        prior_score = prior_scored["score"]["total_score"]

        decision_weights, decision_policy = self.select_oos_guard_weights(
            prior_weights,
            raw_posterior_weights,
            prior_metrics,
            raw_metrics,
            prior_score,
            raw_score,
            payload.oos_guard_enabled,
            raw_excess_return=raw_scored["excess_return"],
            raw_information_ratio=raw_scored["information_ratio"],
            ml_risk_level=allocation_policy.risk_level,
            regime=allocation_policy.regime,
            anomaly_impact=allocation_policy.anomaly_impact,
        )
        decision_weights = decision_weights / float(decision_weights.sum())

        if decision_policy == "defensive_blend":
            strategy_daily = 0.40 * prior_daily + 0.60 * raw_daily
        elif decision_policy == "balanced_blend":
            strategy_daily = 0.50 * prior_daily + 0.50 * raw_daily
        else:
            strategy_daily = raw_daily.copy()

        opt_metrics = RiskEngine.compute_performance_metrics(
            pd.DataFrame({"strategy": strategy_daily}, index=common_idx),
            np.array([1.0]),
            risk_free_rate=risk_free_rate,
        )
        opt_scored = self.score_oos_metrics(
            opt_metrics, strategy_daily, benchmark_daily, bench_metrics,
        )
        oos_warnings: List[str] = []
        if opt_scored["excess_return"] < 0.0:
            oos_warnings.append(
                "Out-of-sample results underperformed the selected benchmark; "
                "the recommendation does not support aggressive rebalancing."
            )

        result.posterior_weights = decision_weights.tolist()
        result.recommended_weights = decision_weights.tolist()
        result.decision_policy = decision_policy
        result.allocation_policy = allocation_policy
        result.turnover = float(np.abs(decision_weights - prior_weights).sum())
        result.backtest_enabled = True
        result.benchmark_symbol = benchmark_symbol
        result.benchmark_name = benchmark_name
        result.benchmark_source = benchmark_source
        result.benchmark_source_detail = benchmark_source_detail
        result.risk_free_rate = risk_free_rate
        result.risk_free_rate_source = risk_free_rate_source
        result.risk_free_rate_source_detail = risk_free_rate_source_detail
        result.methodology_warnings = methodology_warnings
        result.oos_dates = opt_metrics["dates"]
        result.oos_optimized_cum_returns = opt_metrics["cumulative_returns"]
        result.oos_benchmark_cum_returns = bench_metrics["cumulative_returns"]
        result.oos_prior_cum_returns = prior_metrics["cumulative_returns"]
        result.oos_optimized_ann_vol = opt_metrics["annualized_volatility"]
        result.oos_benchmark_ann_vol = bench_metrics["annualized_volatility"]
        result.oos_prior_ann_vol = prior_metrics["annualized_volatility"]
        result.oos_optimized_max_drawdown = opt_metrics["max_drawdown"]
        result.oos_benchmark_max_drawdown = bench_metrics["max_drawdown"]
        result.oos_prior_max_drawdown = prior_metrics["max_drawdown"]
        result.oos_excess_return = opt_scored["excess_return"]
        result.oos_optimized_sharpe = opt_metrics["sharpe_ratio"]
        result.oos_benchmark_sharpe = bench_metrics["sharpe_ratio"]
        result.oos_prior_sharpe = prior_metrics["sharpe_ratio"]
        result.oos_optimized_ir = opt_scored["information_ratio"]

        score_result = opt_scored["score"]
        result.model_score = score_result["total_score"]
        result.model_grade = score_result["grade"]
        result.model_score_risk_control = score_result["risk_control"]
        result.model_score_profitability = score_result["profitability"]
        result.model_score_alpha = score_result["alpha_capability"]
        result.model_score_stability = score_result["stability"]
        result.model_score_win_rate = score_result["win_rate"]

        self.attach_data_provenance(result, fetcher)
        result.source = portfolio_source
        result.source_detail = portfolio_source_detail
        result.data_warnings = [*result.data_warnings, *methodology_warnings, *oos_warnings]
        return result
