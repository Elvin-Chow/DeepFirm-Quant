"""Backend orchestration services for portfolio analysis."""

import asyncio
import importlib
import logging
import os
import queue
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable, List, Optional, TypeVar, cast

import numpy as np
import pandas as pd
from pydantic import BaseModel

from backend.schemas import (
    AnalysisRunRequest,
    AnalysisRunResult,
    PortfolioOptimizeRequest,
    ReportLanguage,
    RiskReportAnomaly,
    RiskReportCrisisDriver,
    RiskReportCrisisWarning,
    RiskReportDecisionSummary,
    RiskReportMLForecast,
    RiskReportMethodologyNote,
    RiskReportMetric,
    RiskReportPortfolioOverview,
    RiskReportRegime,
    RiskReportRequest,
    RiskReportResult,
    RiskReportSection,
    RiskReportTraditionalRisk,
)
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
    "jp": ("^N225", "Nikkei 225"),
    "tw": ("^TWII", "TAIEX"),
}
DEFAULT_RISK_FREE_RATE = 0.02
RISK_FREE_TICKER = "^IRX"
RISK_FREE_NAME = "Risk-free"
DEFAULT_HK_RISK_FREE_RATE = 0.02
HK_RISK_FREE_SYMBOL = "HKMA_EFB_91D"
HK_RISK_FREE_NAME = "HKD 91D EFB"
HK_RISK_FREE_SOURCE_DETAIL = "HKMA 91-day Exchange Fund Bills yield"
HK_RISK_FREE_FALLBACK_DETAIL = "HKMA 91-day Exchange Fund Bills fallback (2.00% annualized)"
HKMA_EFBN_YIELD_DAILY_URL = (
    "https://api.hkma.gov.hk/public/market-data-and-statistics/"
    "monthly-statistical-bulletin/efbn/efbn-yield-daily"
)
DEFAULT_CN_RISK_FREE_RATE = 0.02
CN_RISK_FREE_SYMBOL = "CHINABOND_CGB_3M"
CN_RISK_FREE_NAME = "CNY 3M CGB"
CN_RISK_FREE_SOURCE_DETAIL = "ChinaBond 3-month government bond yield"
CN_RISK_FREE_FALLBACK_DETAIL = "ChinaBond 3-month government bond yield fallback (2.00% annualized)"
DEFAULT_JP_RISK_FREE_RATE = 0.0075
JP_RISK_FREE_SYMBOL = "TONA"
JP_RISK_FREE_NAME = "JPY RFR"
JP_RISK_FREE_SOURCE_DETAIL = "Tokyo Overnight Average Rate proxy fallback (0.75% annualized)"
DEFAULT_TW_RISK_FREE_RATE = 0.02
TW_RISK_FREE_SYMBOL = "CBC_DISCOUNT_RATE"
TW_RISK_FREE_NAME = "TWD policy rate"
TW_RISK_FREE_SOURCE_DETAIL = "Central Bank of the Republic of China discount rate fallback (2.00% annualized)"
RISK_FREE_PROXY_BY_MARKET: dict[MarketMode, tuple[str, str]] = {
    "us": (RISK_FREE_TICKER, RISK_FREE_NAME),
    "hk": (HK_RISK_FREE_SYMBOL, HK_RISK_FREE_NAME),
    "cn": (CN_RISK_FREE_SYMBOL, CN_RISK_FREE_NAME),
    "jp": (JP_RISK_FREE_SYMBOL, JP_RISK_FREE_NAME),
    "tw": (TW_RISK_FREE_SYMBOL, TW_RISK_FREE_NAME),
}
REPORT_CURRENCY_BY_MARKET: dict[MarketMode, str] = {
    "us": "USD",
    "hk": "HKD",
    "cn": "CNY",
    "jp": "JPY",
    "tw": "TWD",
}


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

    @staticmethod
    def parallel_analysis_enabled() -> bool:
        value = os.getenv("DFQ_ANALYSIS_PARALLEL", "").strip().lower()
        return value in {"1", "true", "yes", "on"}

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

    @staticmethod
    def normalize_annualized_rate(value: object, symbol: str) -> float:
        """Normalize a percent or decimal annualized rate into decimal form."""
        rate = float(value)
        if not np.isfinite(rate):
            raise ValueError(f"non-finite risk-free rate for {symbol}")
        if abs(rate) > 0.5:
            rate = rate / 100.0
        if rate <= -0.99:
            raise ValueError(f"risk-free rate is too negative for {symbol}")
        return rate

    @staticmethod
    def constant_risk_free_curve(
        portfolio_index: pd.DatetimeIndex,
        annualized_rate: float,
    ) -> tuple[list[float], list[str]]:
        """Build a daily cumulative risk-free curve aligned to portfolio dates."""
        if len(portfolio_index) < 2:
            return [], []
        daily_rate = np.power(1.0 + annualized_rate, 1.0 / 252.0) - 1.0
        daily_returns = np.full(len(portfolio_index) - 1, daily_rate, dtype=float)
        cumulative = np.cumprod(1.0 + daily_returns) - 1.0
        dates = portfolio_index[1:].strftime("%Y-%m-%d").tolist()
        return cumulative.tolist(), dates

    def fetch_hk_risk_free_rate(
        self,
        fetcher: SmartFetcher,
        asof: Optional[date] = None,
    ) -> float:
        """Fetch the latest HKD 91-day Exchange Fund Bills yield from HKMA."""
        end = asof if asof is not None else datetime.now().date()
        start = end - timedelta(days=21)
        session = getattr(fetcher, "_session", None)
        if session is None:
            raise DataFetcherError(
                message="HKMA session is unavailable",
                symbol=HK_RISK_FREE_SYMBOL,
                source="hkma",
            )

        response = session.get(
            HKMA_EFBN_YIELD_DAILY_URL,
            params={
                "from": start.isoformat(),
                "to": end.isoformat(),
                "pagesize": 100,
                "sortby": "end_of_day",
                "sortorder": "desc",
            },
            timeout=5,
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code == 429:
            raise DataFetcherError(
                message="HKMA risk-free API rate limited with HTTP 429",
                symbol=HK_RISK_FREE_SYMBOL,
                source="hkma",
            )
        if status_code >= 400:
            raise DataFetcherError(
                message=f"HKMA risk-free API returned HTTP {status_code}",
                symbol=HK_RISK_FREE_SYMBOL,
                source="hkma",
            )

        payload = response.json()
        records = payload.get("result", {}).get("records", [])
        if not isinstance(records, list) or not records:
            raise ValueError("HKMA risk-free response contains no records")

        rows: list[tuple[pd.Timestamp, float]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            record_date = pd.to_datetime(record.get("end_of_day"), errors="coerce")
            rate = pd.to_numeric(pd.Series([record.get("efb_91d")]), errors="coerce").iloc[0]
            if pd.isna(record_date) or pd.isna(rate):
                continue
            rows.append((record_date.normalize(), float(rate)))
        if not rows:
            raise ValueError("HKMA 91-day Exchange Fund Bills yield is empty")

        latest_rate = sorted(rows, key=lambda item: item[0])[-1][1]
        return self.normalize_annualized_rate(latest_rate, HK_RISK_FREE_SYMBOL)

    def fetch_cn_risk_free_rate(self, asof: Optional[date] = None) -> float:
        """Fetch the latest ChinaBond 3-month government bond yield."""
        end = asof if asof is not None else datetime.now().date()
        start = end - timedelta(days=21)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")
        df = self.call_provider_with_timeout(
            "akshare_cn_risk_free",
            SmartFetcher._akshare_timeout_seconds(),
            lambda: ak.bond_china_yield(start_date=start_str, end_date=end_str),
        )
        if df.empty or "3月" not in df.columns:
            raise ValueError("ChinaBond 3-month government bond yield is empty")

        normalized = df.copy()
        date_col = "日期" if "日期" in normalized.columns else normalized.columns[0]
        normalized[date_col] = pd.to_datetime(normalized[date_col], errors="coerce")
        normalized["3月"] = pd.to_numeric(normalized["3月"], errors="coerce")
        normalized = normalized.dropna(subset=[date_col, "3月"]).sort_values(date_col)
        if asof is not None:
            normalized = normalized[normalized[date_col] <= pd.Timestamp(asof)]
        if normalized.empty:
            raise ValueError("ChinaBond 3-month government bond yield has no valid observations")

        latest_rate = float(normalized["3月"].iloc[-1])
        return self.normalize_annualized_rate(latest_rate, CN_RISK_FREE_SYMBOL)

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

        if market == "hk":
            bench_resp = fetcher.fetch_hk_equity(
                symbol,
                start_date,
                end_date,
            )
        elif market == "jp":
            bench_resp = fetcher.fetch_jp_equity(
                symbol,
                start_date,
                end_date,
            )
        elif market == "tw":
            bench_resp = fetcher.fetch_tw_equity(
                symbol,
                start_date,
                end_date,
            )
        else:
            bench_resp = fetcher.fetch_us_equity(
                symbol,
                start_date,
                end_date,
            )
        return self.normalize_benchmark_prices(bench_resp.data, symbol)

    def attach_risk_benchmark(
        self,
        result: RiskEvaluationResult,
        request: RiskEvaluationRequest,
        price_df: pd.DataFrame,
    ) -> None:
        """Attach a non-blocking market benchmark comparison series to risk results."""
        if price_df.empty:
            return

        portfolio_index = pd.DatetimeIndex(price_df.index)
        if portfolio_index.tz is not None:
            portfolio_index = portfolio_index.tz_localize(None)
        portfolio_index = portfolio_index.normalize()
        if len(portfolio_index) < 2:
            result.data_warnings.append("Risk comparison series unavailable: portfolio has fewer than two price observations")
            return

        benchmark_symbol, benchmark_name = BENCHMARKS.get(request.market, BENCHMARKS["us"])
        benchmark_fetcher = self.make_fetcher(request.api_key, request.allow_sandbox_data)
        try:
            benchmark_df = self.fetch_benchmark_prices(
                benchmark_fetcher,
                benchmark_symbol,
                request.start_date,
                request.end_date,
                request.market,
            )
            benchmark_dates = pd.to_datetime(benchmark_df["Date"], errors="coerce")
            benchmark_close = pd.to_numeric(benchmark_df["Close"], errors="coerce")
            benchmark_series = pd.Series(
                benchmark_close.to_numpy(dtype=float),
                index=benchmark_dates.dt.tz_localize(None).dt.normalize(),
            ).sort_index()
            benchmark_series = benchmark_series.replace([np.inf, -np.inf], np.nan).dropna()
            benchmark_series = benchmark_series[benchmark_series > 0.0]
            if len(benchmark_series) < 2:
                raise ValueError("benchmark has fewer than two valid observations")

            aligned_close = benchmark_series.reindex(portfolio_index).ffill().bfill()
            aligned_close = aligned_close.replace([np.inf, -np.inf], np.nan).dropna()
            aligned_close = aligned_close[aligned_close > 0.0]
            if len(aligned_close) < 2:
                raise ValueError("benchmark does not overlap the portfolio window")

            benchmark_returns = np.log(aligned_close / aligned_close.shift(1))
            benchmark_returns = benchmark_returns.replace([np.inf, -np.inf], np.nan).dropna()
            benchmark_returns = benchmark_returns.reindex(portfolio_index[1:]).dropna()
            if benchmark_returns.empty:
                raise ValueError("benchmark return series is empty after alignment")

            cumulative = np.exp(np.cumsum(benchmark_returns.to_numpy(dtype=float))) - 1.0
            result.benchmark_symbol = benchmark_symbol
            result.benchmark_name = benchmark_name
            result.benchmark_cumulative_returns = cumulative.tolist()
            result.benchmark_performance_dates = benchmark_returns.index.strftime("%Y-%m-%d").tolist()
            result.benchmark_source = benchmark_fetcher.last_source
            result.benchmark_source_detail = benchmark_fetcher.last_source_detail

            warnings = list(result.data_warnings or [])
            for warning in benchmark_fetcher.data_warnings:
                if warning not in warnings:
                    warnings.append(warning)
            result.data_warnings = warnings
        except (DataFetcherError, ValueError, KeyError, TypeError) as exc:
            warning = f"{benchmark_name} benchmark unavailable: {exc}"
            if warning not in result.data_warnings:
                result.data_warnings.append(warning)

        risk_free_fetcher = self.make_fetcher(request.api_key, request.allow_sandbox_data)
        if request.market != "us":
            risk_free_rate, risk_free_source, risk_free_detail, risk_free_warnings = self.resolve_risk_free_rate(
                risk_free_fetcher,
                None,
                asof=request.end_date,
                market=request.market,
            )
            cumulative, dates = self.constant_risk_free_curve(portfolio_index, risk_free_rate)
            if dates:
                risk_free_symbol, risk_free_name = RISK_FREE_PROXY_BY_MARKET.get(
                    request.market,
                    (RISK_FREE_TICKER, RISK_FREE_NAME),
                )
                result.risk_free_symbol = risk_free_symbol
                result.risk_free_name = risk_free_name
                result.risk_free_cumulative_returns = cumulative
                result.risk_free_performance_dates = dates
                result.risk_free_source = risk_free_source
                result.risk_free_source_detail = risk_free_detail
            warnings = list(result.data_warnings or [])
            for warning in risk_free_warnings:
                if warning not in warnings:
                    warnings.append(warning)
            result.data_warnings = warnings
            return

        try:
            risk_free_response = risk_free_fetcher.fetch_us_equity(
                RISK_FREE_TICKER,
                request.start_date,
                request.end_date,
            )
            risk_free_df = self.normalize_benchmark_prices(risk_free_response.data, RISK_FREE_TICKER)
            risk_free_dates = pd.to_datetime(risk_free_df["Date"], errors="coerce")
            risk_free_rates = pd.to_numeric(risk_free_df["Close"], errors="coerce")
            risk_free_series = pd.Series(
                risk_free_rates.to_numpy(dtype=float),
                index=risk_free_dates.dt.tz_localize(None).dt.normalize(),
            ).sort_index()
            risk_free_series = risk_free_series.replace([np.inf, -np.inf], np.nan).dropna()
            if risk_free_series.empty:
                raise ValueError("risk-free series is empty")

            normalized_rates = risk_free_series.where(risk_free_series <= 0.5, risk_free_series / 100.0)
            normalized_rates = normalized_rates.clip(lower=-0.99)
            aligned_rates = normalized_rates.reindex(portfolio_index).ffill().bfill()
            aligned_rates = aligned_rates.replace([np.inf, -np.inf], np.nan).dropna()
            aligned_rates = aligned_rates.reindex(portfolio_index[1:]).dropna()
            if aligned_rates.empty:
                raise ValueError("risk-free series does not overlap the portfolio window")

            daily_returns = np.power(1.0 + aligned_rates.to_numpy(dtype=float), 1.0 / 252.0) - 1.0
            cumulative = np.cumprod(1.0 + daily_returns) - 1.0
            result.risk_free_symbol = RISK_FREE_TICKER
            result.risk_free_name = RISK_FREE_NAME
            result.risk_free_cumulative_returns = cumulative.tolist()
            result.risk_free_performance_dates = aligned_rates.index.strftime("%Y-%m-%d").tolist()
            result.risk_free_source = risk_free_fetcher.last_source
            result.risk_free_source_detail = risk_free_fetcher.last_source_detail

            warnings = list(result.data_warnings or [])
            for warning in risk_free_fetcher.data_warnings:
                if warning not in warnings:
                    warnings.append(warning)
            result.data_warnings = warnings
        except (DataFetcherError, ValueError, KeyError, TypeError) as exc:
            cumulative, dates = self.constant_risk_free_curve(portfolio_index, DEFAULT_RISK_FREE_RATE)
            if dates:
                result.risk_free_symbol = RISK_FREE_TICKER
                result.risk_free_name = RISK_FREE_NAME
                result.risk_free_cumulative_returns = cumulative
                result.risk_free_performance_dates = dates
                result.risk_free_source = "fallback"
                result.risk_free_source_detail = "Deterministic fallback (2.00% annualized)"
            warning = f"{RISK_FREE_NAME} proxy unavailable: {exc}; defaulted to 2.00% annualized."
            if warning not in result.data_warnings:
                result.data_warnings.append(warning)

    def resolve_risk_free_rate(
        self,
        fetcher: SmartFetcher,
        requested_rate: Optional[float],
        asof: Optional[date] = None,
        market: MarketMode = "us",
    ) -> tuple[float, str, str, list[str]]:
        """Return the risk-free rate, source label, and non-fatal warnings."""
        if requested_rate is not None:
            return float(requested_rate), "request", "Request override", []
        if market == "hk":
            try:
                return self.fetch_hk_risk_free_rate(fetcher, asof=asof), "hkma", HK_RISK_FREE_SOURCE_DETAIL, []
            except Exception as exc:
                return (
                    DEFAULT_HK_RISK_FREE_RATE,
                    "fallback",
                    HK_RISK_FREE_FALLBACK_DETAIL,
                    [f"Hong Kong risk-free rate was unavailable ({exc}); defaulted to 2.00% annualized."],
                )
        if market == "cn":
            try:
                return self.fetch_cn_risk_free_rate(asof=asof), "chinabond", CN_RISK_FREE_SOURCE_DETAIL, []
            except Exception as exc:
                return (
                    DEFAULT_CN_RISK_FREE_RATE,
                    "fallback",
                    CN_RISK_FREE_FALLBACK_DETAIL,
                    [f"China A-share risk-free rate was unavailable ({exc}); defaulted to 2.00% annualized."],
                )
        if market == "jp":
            return (
                DEFAULT_JP_RISK_FREE_RATE,
                "fallback",
                JP_RISK_FREE_SOURCE_DETAIL,
                ["Japan risk-free rate live source is unavailable; defaulted to 0.75% annualized."],
            )
        if market == "tw":
            return (
                DEFAULT_TW_RISK_FREE_RATE,
                "fallback",
                TW_RISK_FREE_SOURCE_DETAIL,
                ["Taiwan risk-free rate live source is unavailable; defaulted to 2.00% annualized."],
            )
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
            self.attach_risk_benchmark(result, risk_payload, price_df)
            self.attach_data_provenance(result, fetcher)
            return result

        def build_alpha() -> Optional[FactorRegressionResult]:
            if payload.market in {"cn", "jp", "tw"}:
                alpha_messages = {
                    "cn": "China A-share factor attribution is not supported yet.",
                    "jp": "Japan market factor attribution is not supported yet.",
                    "tw": "Taiwan market factor attribution is not supported yet.",
                }
                alpha_message = alpha_messages[payload.market]
                alpha_meta.update(
                    {
                        "status": "unavailable",
                        "message": alpha_message,
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

        if self.parallel_analysis_enabled():
            risk_result, alpha_result, anomaly_result, regime_result, ml_result, crisis_result = await asyncio.gather(
                asyncio.to_thread(self.timed_stage, timings, "risk", build_risk),
                asyncio.to_thread(self.timed_stage, timings, "alpha", build_alpha),
                asyncio.to_thread(self.timed_stage, timings, "anomaly", build_anomaly),
                asyncio.to_thread(self.timed_stage, timings, "regime", build_regime),
                asyncio.to_thread(self.timed_stage, timings, "ml_forecast", build_ml),
                asyncio.to_thread(self.timed_stage, timings, "crisis_warning", build_crisis_warning),
            )
        else:
            risk_result = self.timed_stage(timings, "risk", build_risk)
            alpha_result = self.timed_stage(timings, "alpha", build_alpha)
            anomaly_result = self.timed_stage(timings, "anomaly", build_anomaly)
            regime_result = self.timed_stage(timings, "regime", build_regime)
            ml_result = self.timed_stage(timings, "ml_forecast", build_ml)
            crisis_result = self.timed_stage(timings, "crisis_warning", build_crisis_warning)

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

    @staticmethod
    def _safe_report_float(value: object) -> Optional[float]:
        """Return a finite float or None for report serialization."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if np.isfinite(number) else None

    @classmethod
    def _safe_report_dict(cls, values: dict[str, object]) -> dict[str, float]:
        """Return finite numeric values from a mapping."""
        clean: dict[str, float] = {}
        for key, value in values.items():
            number = cls._safe_report_float(value)
            if number is not None:
                clean[str(key)] = number
        return clean

    @classmethod
    def _normalize_report_weights(cls, weights: list[float], n_assets: int) -> list[float]:
        """Return finite normalized weights for report display."""
        if n_assets <= 0:
            return []
        if len(weights) != n_assets:
            return (np.ones(n_assets, dtype=float) / n_assets).tolist()
        weights_arr = np.asarray(weights, dtype=float)
        if not np.isfinite(weights_arr).all() or (weights_arr < 0.0).any():
            return (np.ones(n_assets, dtype=float) / n_assets).tolist()
        total = float(weights_arr.sum())
        if total <= 1e-12:
            return (np.ones(n_assets, dtype=float) / n_assets).tolist()
        return (weights_arr / total).tolist()

    @staticmethod
    def _unique_strings(values: list[str]) -> list[str]:
        """Return stable unique non-empty strings."""
        seen: set[str] = set()
        clean: list[str] = []
        for value in values:
            text = str(value).strip()
            if text and text not in seen:
                clean.append(text)
                seen.add(text)
        return clean

    @staticmethod
    def _localized_text(language: ReportLanguage, en: str, zh: str, tc: str) -> str:
        """Return localized report prose."""
        if language == "zh":
            return zh
        if language == "tc":
            return tc
        return en

    @classmethod
    def _localized_na(cls, language: ReportLanguage) -> str:
        """Return a localized missing-value label."""
        return cls._localized_text(language, "n/a", "暂无", "暫無")

    @classmethod
    def _localized_market(cls, value: str, language: ReportLanguage) -> str:
        """Return a localized market label."""
        normalized = (value or "").strip().lower()
        labels = {
            "us": cls._localized_text(language, "US market", "美国市场", "美國市場"),
            "hk": cls._localized_text(language, "HK market", "香港市场", "香港市場"),
            "cn": cls._localized_text(language, "China A-share market", "中国 A 股市场", "中國 A 股市場"),
            "jp": cls._localized_text(language, "Japan market", "日本市场", "日本市場"),
            "tw": cls._localized_text(language, "Taiwan market", "台湾市场", "台灣市場"),
        }
        return labels.get(normalized, value.upper() if value else cls._localized_na(language))

    @classmethod
    def _localized_level(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return a localized risk or alert level."""
        normalized = (value or "").strip().lower().replace("_", " ").replace("-", " ")
        labels = {
            "low": cls._localized_text(language, "Low", "低", "低"),
            "medium": cls._localized_text(language, "Medium", "中等", "中等"),
            "moderate": cls._localized_text(language, "Moderate", "中等", "中等"),
            "high": cls._localized_text(language, "High", "高", "高"),
            "extreme": cls._localized_text(language, "Extreme", "极高", "極高"),
            "critical": cls._localized_text(language, "Critical", "极高", "極高"),
            "normal": cls._localized_text(language, "Normal", "正常", "正常"),
        }
        if not normalized:
            return cls._localized_na(language)
        return labels.get(normalized, value or cls._localized_na(language))

    @classmethod
    def _localized_regime(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return a localized regime label."""
        normalized = (value or "").strip().lower().replace("_", " ").replace("-", " ")
        labels = {
            "normal": cls._localized_text(language, "Normal", "正常", "正常"),
            "high volatility": cls._localized_text(language, "High Volatility", "高波动", "高波動"),
            "crisis": cls._localized_text(language, "Crisis", "危机", "危機"),
            "low volatility": cls._localized_text(language, "Low Volatility", "低波动", "低波動"),
            "stress": cls._localized_text(language, "Stress", "压力", "壓力"),
        }
        if not normalized:
            return cls._localized_na(language)
        return labels.get(normalized, value or cls._localized_na(language))

    @classmethod
    def _localized_decision_policy(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return a localized allocation policy label."""
        normalized = (value or "").strip().lower()
        labels = {
            "raw": cls._localized_text(language, "Raw model", "原始模型", "原始模型"),
            "balanced_blend": cls._localized_text(language, "Balanced blend", "平衡混合", "平衡混合"),
            "defensive_blend": cls._localized_text(language, "Defensive blend", "防守混合", "防守混合"),
        }
        if not normalized:
            return cls._localized_na(language)
        return labels.get(normalized, value or cls._localized_na(language))

    @classmethod
    def _localized_decision_impact(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return a localized anomaly decision impact label."""
        normalized = (value or "").strip().lower()
        labels = {
            "none": cls._localized_text(language, "None", "无", "無"),
            "tighten_constraints": cls._localized_text(language, "Tighten constraints", "收紧约束", "收緊約束"),
            "freeze_rebalance": cls._localized_text(language, "Freeze rebalance", "冻结调仓", "凍結調倉"),
            "force_oos_guard": cls._localized_text(language, "Force OOS guard", "强制启用样本外防守", "強制啟用樣本外防守"),
        }
        if not normalized:
            return cls._localized_na(language)
        return labels.get(normalized, value or cls._localized_na(language))

    @classmethod
    def _localized_model_health(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return a localized model health label."""
        normalized = (value or "").strip().lower()
        labels = {
            "ok": cls._localized_text(language, "Healthy", "正常", "正常"),
            "degraded": cls._localized_text(language, "Watch", "需关注", "需關注"),
            "fallback": cls._localized_text(language, "Fallback", "已降级", "已降級"),
            "unavailable": cls._localized_text(language, "Unavailable", "不可用", "不可用"),
        }
        if not normalized:
            return cls._localized_na(language)
        return labels.get(normalized, value or cls._localized_na(language))

    @classmethod
    def _localized_calibration_state(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return a localized probability calibration state."""
        normalized = (value or "").strip().lower()
        labels = {
            "calibrated": cls._localized_text(language, "Calibrated", "已校准", "已校準"),
            "raw": cls._localized_text(language, "Raw", "原始概率", "原始概率"),
        }
        if not normalized:
            return cls._localized_na(language)
        return labels.get(normalized, value or cls._localized_na(language))

    @classmethod
    def _localized_feature(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return a localized feature label for report prose."""
        raw = (value or "").strip()
        normalized = raw.lower()
        labels = {
            "rolling_volatility_20d": cls._localized_text(language, "20-day rolling volatility", "20 日滚动波动率", "20 日滾動波動率"),
            "correlation_mean_20d": cls._localized_text(language, "20-day average correlation", "20 日平均相关性", "20 日平均相關性"),
            "rolling_mean_return_20d": cls._localized_text(language, "20-day rolling average return", "20 日滚动平均收益", "20 日滾動平均收益"),
            "rolling_max_drawdown_60d": cls._localized_text(language, "60-day rolling max drawdown", "60 日滚动最大回撤", "60 日滾動最大回撤"),
            "downside_volatility_20d": cls._localized_text(language, "20-day downside volatility", "20 日下行波动率", "20 日下行波動率"),
            "portfolio_return_1d": cls._localized_text(language, "1-day portfolio return", "组合单日收益", "組合單日收益"),
            "portfolio_return_5d": cls._localized_text(language, "5-day portfolio return", "组合 5 日收益", "組合 5 日收益"),
            "volatility_20d": cls._localized_text(language, "20-day volatility", "20 日波动率", "20 日波動率"),
            "max_drawdown_60d": cls._localized_text(language, "60-day max drawdown", "60 日最大回撤", "60 日最大回撤"),
            "correlation_stress": cls._localized_text(language, "Correlation stress", "相关性压力", "相關性壓力"),
        }
        if not raw:
            return cls._localized_na(language)
        if normalized in labels:
            return labels[normalized]
        if language == "en":
            return raw.replace("_", " ")
        return raw

    @classmethod
    def _localized_reason(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return a localized anomaly reason where it is known."""
        raw = (value or "").strip()
        normalized = raw.lower()
        labels = {
            "no material anomaly signal": cls._localized_text(
                language,
                "No material anomaly signal",
                "未发现显著异常信号",
                "未發現顯著異常訊號",
            ),
            "missing or invalid price data": cls._localized_text(
                language,
                "Missing or invalid price data",
                "存在缺失或无效价格数据",
                "存在缺失或無效價格資料",
            ),
            "large negative return": cls._localized_text(
                language,
                "Large negative return",
                "组合出现较大负收益冲击",
                "組合出現較大負收益衝擊",
            ),
            "price jump": cls._localized_text(
                language,
                "Price jump",
                "价格跳变信号",
                "價格跳變訊號",
            ),
            "high volatility": cls._localized_text(
                language,
                "High volatility",
                "短期波动率偏高",
                "短期波動率偏高",
            ),
            "correlation spike": cls._localized_text(
                language,
                "Correlation spike",
                "相关性上升",
                "相關性上升",
            ),
        }
        if not raw:
            return cls._localized_na(language)
        return labels.get(normalized, raw)

    @classmethod
    def _localized_warning_text(cls, value: Optional[str], language: ReportLanguage) -> str:
        """Return localized text for known report warnings."""
        raw = (value or "").strip()
        if not raw:
            return cls._localized_na(language)
        known = {
            "China A-share factor attribution is not supported yet.": cls._localized_text(
                language,
                "China A-share factor attribution is not supported yet.",
                "中国 A 股因子归因暂未接入。",
                "中國 A 股因子歸因暫未接入。",
            ),
            "Japan market factor attribution is not supported yet.": cls._localized_text(
                language,
                "Japan market factor attribution is not supported yet.",
                "日本市场因子归因暂未接入。",
                "日本市場因子歸因暫未接入。",
            ),
            "Taiwan market factor attribution is not supported yet.": cls._localized_text(
                language,
                "Taiwan market factor attribution is not supported yet.",
                "台湾市场因子归因暂未接入。",
                "台灣市場因子歸因暫未接入。",
            ),
            "Alpha attribution is unavailable for this report.": cls._localized_text(
                language,
                "Alpha attribution is unavailable for this report.",
                "本报告未生成 Alpha 归因。",
                "本報告未生成 Alpha 歸因。",
            ),
            "Alpha attribution is unavailable for the selected market or sample window.": cls._localized_text(
                language,
                "Alpha attribution is unavailable for the selected market or sample window.",
                "所选市场或样本窗口下 Alpha 归因不可用。",
                "所選市場或樣本視窗下 Alpha 歸因不可用。",
            ),
            "real factors unavailable": cls._localized_text(
                language,
                "Real factors unavailable.",
                "真实因子数据不可用。",
                "真實因子資料不可用。",
            ),
        }
        return known.get(raw, raw)

    @classmethod
    def _default_report_title(cls, payload: RiskReportRequest) -> str:
        """Return a stable report title."""
        if payload.report_title and payload.report_title.strip():
            return payload.report_title.strip()
        return cls._localized_text(
            payload.language,
            "DeepFirm Quant Risk Report",
            "DeepFirm Quant 风险报告",
            "DeepFirm Quant 風險報告",
        )

    @classmethod
    def _diagnostics_summary(cls, diagnostics: object) -> dict[str, object]:
        """Flatten optional diagnostics into report-safe primitives."""
        if diagnostics is None:
            return {}
        fields = {
            "model_health": getattr(diagnostics, "model_health", None),
            "asof_date": getattr(diagnostics, "asof_date", None),
            "training_start": getattr(diagnostics, "training_start", None),
            "training_end": getattr(diagnostics, "training_end", None),
            "n_observations": getattr(diagnostics, "n_observations", None),
            "feature_count": getattr(diagnostics, "feature_count", None),
            "data_quality_score": getattr(diagnostics, "data_quality_score", None),
            "fallback_used": getattr(diagnostics, "fallback_used", None),
            "fallback_reason": getattr(diagnostics, "fallback_reason", None),
            "confidence": getattr(diagnostics, "confidence", None),
        }
        summary: dict[str, object] = {}
        for key, value in fields.items():
            if value is None:
                continue
            if isinstance(value, (float, int)):
                number = cls._safe_report_float(value)
                if number is not None:
                    summary[key] = number
            elif isinstance(value, (str, bool)):
                summary[key] = value
        warnings = getattr(diagnostics, "warnings", None)
        if warnings:
            summary["warnings"] = cls._unique_strings(list(warnings))
        return summary

    @classmethod
    def _crisis_driver(cls, driver: object) -> RiskReportCrisisDriver:
        """Map a crisis driver into a report-safe model."""
        return RiskReportCrisisDriver(
            feature=str(getattr(driver, "feature", "")),
            feature_value=cls._safe_report_float(getattr(driver, "feature_value", None)),
            shap_value=cls._safe_report_float(getattr(driver, "shap_value", None)),
            direction=str(getattr(driver, "direction", "")),
        )

    @staticmethod
    def _format_report_percent(value: Optional[float], signed: bool = False, missing: str = "n/a") -> str:
        """Format a report ratio as a percentage."""
        if value is None or not np.isfinite(value):
            return missing
        percent = float(value) * 100.0
        prefix = "+" if signed and percent > 0.0 else ""
        return f"{prefix}{percent:.2f}%"

    @staticmethod
    def _format_report_money(value: Optional[float], currency: str, missing: str = "n/a") -> str:
        """Format a report currency amount."""
        if value is None or not np.isfinite(value):
            return f"{currency} {missing}"
        return f"{currency} {float(value):,.0f}"

    @classmethod
    def _dominant_probability_label(cls, values: dict[str, float], language: ReportLanguage) -> str:
        """Return the largest probability label and value for narrative text."""
        if not values:
            return cls._localized_na(language)
        key, value = max(values.items(), key=lambda item: item[1])
        return f"{cls._localized_regime(key, language)} {value * 100.0:.1f}%"

    @classmethod
    def _build_executive_summary(
        cls,
        language: ReportLanguage,
        overview: RiskReportPortfolioOverview,
        traditional_risk: RiskReportTraditionalRisk,
        ml_report: Optional[RiskReportMLForecast],
        anomaly_report: Optional[RiskReportAnomaly],
        regime_report: Optional[RiskReportRegime],
        crisis_report: Optional[RiskReportCrisisWarning],
        decision_summary: RiskReportDecisionSummary,
        data_warnings: list[str],
    ) -> list[str]:
        """Build deterministic natural-language report interpretation."""
        missing = cls._localized_na(language)
        ticker_text = ", ".join(overview.tickers)
        market_text = cls._localized_market(overview.market, language)
        hist_es = cls._format_report_percent(traditional_risk.historical_es, missing=missing)
        mc_es = cls._format_report_percent(traditional_risk.monte_carlo_es, missing=missing)
        max_drawdown = cls._format_report_percent(traditional_risk.max_drawdown, missing=missing)
        absolute_loss = cls._format_report_money(
            traditional_risk.absolute_loss_monte_carlo,
            overview.currency,
            missing,
        )
        ml_level = cls._localized_level(ml_report.risk_level, language) if ml_report else missing
        regime_text = cls._localized_regime(regime_report.current_regime, language) if regime_report else missing
        anomaly_text = cls._localized_level(anomaly_report.alert_level, language) if anomaly_report else missing
        crisis_text = (
            cls._format_report_percent(crisis_report.crisis_probability, missing=missing)
            if crisis_report
            else missing
        )
        oos_excess = cls._format_report_percent(decision_summary.oos_excess_return, signed=True, missing=missing)
        model_score = (
            f"{decision_summary.model_score:.1f}"
            if decision_summary.model_score is not None and np.isfinite(decision_summary.model_score)
            else missing
        )
        model_grade = decision_summary.model_grade or missing
        warning_count = len(data_warnings)

        return [
            cls._localized_text(
                language,
                (
                    f"The report covers {len(overview.tickers)} assets ({ticker_text}) from "
                    f"{overview.start_date} to {overview.end_date}, using {overview.currency} basis for "
                    f"{overview.market.upper()} market exposure."
                ),
                (
                    f"本报告覆盖 {len(overview.tickers)} 个标的（{ticker_text}），样本区间为 "
                    f"{overview.start_date} 至 {overview.end_date}，采用 {overview.currency} 口径评估"
                    f"{market_text}组合。"
                ),
                (
                    f"本報告覆蓋 {len(overview.tickers)} 個標的（{ticker_text}），樣本區間為 "
                    f"{overview.start_date} 至 {overview.end_date}，採用 {overview.currency} 口徑評估"
                    f"{market_text}組合。"
                ),
            ),
            cls._localized_text(
                language,
                (
                    f"Tail-risk readings show historical ES at {hist_es} and Monte Carlo ES at {mc_es}. "
                    f"At the submitted capital and leverage, the Monte Carlo tail-loss estimate is about {absolute_loss}; "
                    f"the observed maximum drawdown is {max_drawdown}."
                ),
                (
                    f"尾部风险读数显示：历史 ES 为 {hist_es}，蒙特卡洛 ES 为 {mc_es}。"
                    f"结合提交的本金与杠杆，蒙特卡洛尾部亏损估计约为 {absolute_loss}；"
                    f"样本内最大回撤为 {max_drawdown}。"
                ),
                (
                    f"尾部風險讀數顯示：歷史 ES 為 {hist_es}，蒙地卡羅 ES 為 {mc_es}。"
                    f"結合提交的本金與槓桿，蒙地卡羅尾部虧損估計約為 {absolute_loss}；"
                    f"樣本內最大回撤為 {max_drawdown}。"
                ),
            ),
            cls._localized_text(
                language,
                (
                    f"Model context is {ml_level} for ML downside risk, {anomaly_text} for anomaly alert, "
                    f"{regime_text} for market regime, and {crisis_text} for crisis probability. "
                    f"OOS excess return is {oos_excess}, with model score {model_score} and grade "
                    f"{decision_summary.model_grade or 'n/a'}."
                ),
                (
                    f"模型上下文显示：机器学习下行风险等级为 {ml_level}，异常告警为 {anomaly_text}，"
                    f"市场状态为 {regime_text}，危机概率为 {crisis_text}。样本外超额收益为 "
                    f"{oos_excess}，模型评分为 {model_score}，评级为 {model_grade}。"
                ),
                (
                    f"模型上下文顯示：機器學習下行風險等級為 {ml_level}，異常警報為 {anomaly_text}，"
                    f"市場狀態為 {regime_text}，危機概率為 {crisis_text}。樣本外超額收益為 "
                    f"{oos_excess}，模型評分為 {model_score}，評級為 {model_grade}。"
                ),
            ),
            cls._localized_text(
                language,
                (
                    f"The report contains {warning_count} non-fatal data or methodology notices. "
                    "They should be reviewed before using the output in a risk committee discussion."
                ),
                (
                    f"本报告包含 {warning_count} 条非阻断数据或方法提示。进入风控会讨论前，"
                    "应先阅读这些提示以理解数据源、样本和可选模块限制。"
                ),
                (
                    f"本報告包含 {warning_count} 條非阻斷資料或方法提示。進入風控會討論前，"
                    "應先閱讀這些提示以理解資料源、樣本和可選模組限制。"
                ),
            ),
        ]

    @classmethod
    def _section_summary(cls, report: RiskReportResult, key: str) -> str:
        """Return a narrative summary for one report section."""
        language = report.language
        overview = report.portfolio_overview
        traditional = report.traditional_risk
        ml = report.ml_forecast
        anomaly = report.anomaly
        regime = report.regime
        crisis = report.crisis_warning
        decision = report.decision_summary
        missing = cls._localized_na(language)

        if key == "portfolio_overview":
            weights_text = ", ".join(
                f"{ticker} {weight * 100.0:.1f}%"
                for ticker, weight in zip(overview.tickers, overview.weights)
            )
            return cls._localized_text(
                language,
                f"The starting allocation is {weights_text}. Capital and leverage are used only to translate percentage tail risk into absolute loss.",
                f"初始配置为 {weights_text}。本金与杠杆仅用于把百分比尾部风险换算成绝对亏损口径。",
                f"初始配置為 {weights_text}。本金與槓桿僅用於把百分比尾部風險換算成絕對虧損口徑。",
            )
        if key == "executive_risk_summary":
            return " ".join(report.executive_summary[:2])
        if key == "traditional_risk":
            return cls._localized_text(
                language,
                (
                    f"Historical ES is {cls._format_report_percent(traditional.historical_es, missing=missing)}, while Monte Carlo ES is "
                    f"{cls._format_report_percent(traditional.monte_carlo_es, missing=missing)}. The gap between these two estimates helps identify "
                    "whether simulated distribution assumptions are producing a heavier or lighter tail than realized history."
                ),
                (
                    f"历史 ES 为 {cls._format_report_percent(traditional.historical_es, missing=missing)}，蒙特卡洛 ES 为 "
                    f"{cls._format_report_percent(traditional.monte_carlo_es, missing=missing)}。两者差异用于判断模拟分布假设相对真实历史尾部是更重还是更轻。"
                ),
                (
                    f"歷史 ES 為 {cls._format_report_percent(traditional.historical_es, missing=missing)}，蒙地卡羅 ES 為 "
                    f"{cls._format_report_percent(traditional.monte_carlo_es, missing=missing)}。兩者差異用於判斷模擬分布假設相對真實歷史尾部是更重還是更輕。"
                ),
            )
        if key == "ml_forecast" and ml is not None:
            feature_separator = ", " if language == "en" else "、"
            features = feature_separator.join(cls._localized_feature(feature, language) for feature in ml.top_features[:3]) or missing
            ml_level = cls._localized_level(ml.risk_level, language)
            return cls._localized_text(
                language,
                f"The ML layer classifies downside risk as {ml_level}, with top explanatory features led by {features}. Treat this as a model-based risk overlay rather than a return forecast.",
                f"机器学习层将下行风险识别为 {ml_level}，主要解释特征包括 {features}。该结果应视为模型化风险叠加信号，而不是收益预测。",
                f"機器學習層將下行風險識別為 {ml_level}，主要解釋特徵包括 {features}。該結果應視為模型化風險疊加訊號，而不是收益預測。",
            )
        if key == "anomaly" and anomaly is not None:
            reasons = "；".join(cls._localized_reason(reason, language) for reason in anomaly.main_reasons[:3]) or missing
            alert_level = cls._localized_level(anomaly.alert_level, language)
            decision_impact = cls._localized_decision_impact(anomaly.decision_impact, language)
            return cls._localized_text(
                language,
                f"The anomaly layer reports a {anomaly.alert_level} alert. Main reasons: {reasons}. Decision impact is {anomaly.decision_impact}.",
                f"异常检测层给出 {alert_level} 告警。主要原因：{reasons}。对决策约束的影响为 {decision_impact}。",
                f"異常偵測層給出 {alert_level} 警報。主要原因：{reasons}。對決策約束的影響為 {decision_impact}。",
            )
        if key == "regime" and regime is not None:
            dominant = cls._dominant_probability_label(regime.regime_probabilities, language)
            current_regime = cls._localized_regime(regime.current_regime, language)
            stress_level = cls._localized_level(regime.recommended_stress_level, language)
            return cls._localized_text(
                language,
                f"The regime detector places the portfolio in {regime.current_regime}, with dominant probability {dominant}. Stress level is {regime.recommended_stress_level}.",
                f"市场状态识别将组合归入 {current_regime}，最高状态概率为 {dominant}。建议压力等级为 {stress_level}。",
                f"市場狀態識別將組合歸入 {current_regime}，最高狀態概率為 {dominant}。建議壓力等級為 {stress_level}。",
            )
        if key == "crisis_warning" and crisis is not None:
            driver = cls._localized_feature(crisis.top_risk_drivers[0].feature, language) if crisis.top_risk_drivers else missing
            warning_level = cls._localized_level(crisis.warning_level, language)
            model_health = cls._localized_model_health(crisis.model_health, language)
            return cls._localized_text(
                language,
                f"Crisis probability is {cls._format_report_percent(crisis.crisis_probability, missing=missing)} at {crisis.warning_level} level. The leading risk driver is {driver}; model health is {crisis.model_health}.",
                f"危机概率为 {cls._format_report_percent(crisis.crisis_probability, missing=missing)}，预警等级为 {warning_level}。首要风险驱动为 {driver}；模型健康状态为 {model_health}。",
                f"危機概率為 {cls._format_report_percent(crisis.crisis_probability, missing=missing)}，預警等級為 {warning_level}。首要風險驅動為 {driver}；模型健康狀態為 {model_health}。",
            )
        if key == "decision_summary":
            policy = cls._localized_decision_policy(decision.decision_policy, language)
            benchmark = decision.benchmark_symbol or missing
            return cls._localized_text(
                language,
                (
                    f"The decision layer uses policy {decision.decision_policy}, benchmark {decision.benchmark_symbol or 'n/a'}, "
                    f"OOS excess return {cls._format_report_percent(decision.oos_excess_return, signed=True, missing=missing)}, and turnover "
                    f"{cls._format_report_percent(decision.turnover, missing=missing)}. This is a risk-control allocation output, not a transaction instruction."
                ),
                (
                    f"决策层采用 {policy} 策略，基准为 {benchmark}，"
                    f"样本外超额收益为 {cls._format_report_percent(decision.oos_excess_return, signed=True, missing=missing)}，换手率为 "
                    f"{cls._format_report_percent(decision.turnover, missing=missing)}。这属于风控配置输出，不是交易指令。"
                ),
                (
                    f"決策層採用 {policy} 策略，基準為 {benchmark}，"
                    f"樣本外超額收益為 {cls._format_report_percent(decision.oos_excess_return, signed=True, missing=missing)}，換手率為 "
                    f"{cls._format_report_percent(decision.turnover, missing=missing)}。這屬於風控配置輸出，不是交易指令。"
                ),
            )
        if key == "methodology_notes":
            return cls._localized_text(
                language,
                "Methodology notes explain model scope, fallback behavior, market-specific assumptions, and optional module limitations.",
                "方法说明用于解释模型适用范围、兜底行为、市场特定假设和可选模块限制。",
                "方法說明用於解釋模型適用範圍、兜底行為、市場特定假設和可選模組限制。",
            )
        if key == "disclaimer":
            return cls._localized_text(
                language,
                "The report is intended for risk monitoring and research review only.",
                "本报告仅用于风险监控与投研复核。",
                "本報告僅用於風險監控與投研覆核。",
            )
        return ""

    @classmethod
    def _collect_report_warnings(
        cls,
        analysis: AnalysisRunResult,
        extra_warnings: list[str],
    ) -> list[str]:
        """Collect non-fatal report warnings from every available module."""
        warnings: list[str] = []
        sources = [
            analysis.risk,
            analysis.optimization,
            analysis.anomaly,
            analysis.regime,
            analysis.ml_forecast,
            analysis.crisis_warning,
        ]
        for source in sources:
            if source is None:
                continue
            warnings.extend(list(getattr(source, "data_warnings", []) or []))
        warnings.extend(list(getattr(analysis.optimization, "methodology_warnings", []) or []))
        if analysis.alpha_status != "available":
            alpha_message = analysis.alpha_message or "Alpha attribution is unavailable for this report."
            warnings.append(alpha_message)
        if analysis.ml_forecast is None:
            warnings.append("ML forecast is unavailable; the report omits ML forecast metrics.")
        if analysis.anomaly is None:
            warnings.append("Anomaly detection is unavailable; the report omits anomaly metrics.")
        if analysis.regime is None:
            warnings.append("Market regime detection is unavailable; the report omits regime metrics.")
        if analysis.crisis_warning is None:
            warnings.append("Crisis warning is unavailable; the report omits crisis warning metrics.")
        warnings.extend(extra_warnings)
        return cls._unique_strings(warnings)

    @classmethod
    def _build_methodology_notes(
        cls,
        payload: RiskReportRequest,
        analysis: AnalysisRunResult,
        data_warnings: list[str],
    ) -> list[RiskReportMethodologyNote]:
        """Build methodology notes and non-fatal limitations."""
        language = payload.language
        notes: list[RiskReportMethodologyNote] = [
            RiskReportMethodologyNote(
                code="TAIL_RISK_METHODS",
                title=cls._localized_text(language, "Tail risk methods", "尾部风险方法", "尾部風險方法"),
                detail=cls._localized_text(
                    language,
                    "Traditional risk uses historical Expected Shortfall, Monte Carlo Expected Shortfall, volatility, drawdown, and correlation metrics.",
                    "传统风险部分使用历史预期尾部损失（ES）、蒙特卡洛预期尾部损失（ES）、波动率、回撤与相关性指标。",
                    "傳統風險部分使用歷史預期尾部損失（ES）、蒙地卡羅預期尾部損失（ES）、波動率、回撤與相關性指標。",
                ),
            ),
            RiskReportMethodologyNote(
                code="MODEL_OUTPUT_LIMITATION",
                title=cls._localized_text(language, "Model output limitation", "模型输出限制", "模型輸出限制"),
                detail=cls._localized_text(
                    language,
                    "Forecast, anomaly, regime, crisis, and OOS scores are risk-monitoring signals only and do not guarantee future accuracy.",
                    "预测、异常、状态、危机预警与样本外评分仅作为风控监测信号，不保证未来准确性。",
                    "預測、異常、狀態、危機預警與樣本外評分僅作為風控監測訊號，不保證未來準確性。",
                ),
                severity="limitation",
            ),
        ]

        if analysis.alpha_status != "available":
            notes.append(
                RiskReportMethodologyNote(
                    code="ALPHA_UNAVAILABLE",
                    title=cls._localized_text(language, "Alpha attribution unavailable", "Alpha 归因不可用", "Alpha 歸因不可用"),
                    detail=cls._localized_warning_text(
                        analysis.alpha_message or "Alpha attribution is unavailable for the selected market or sample window.",
                        language,
                    ),
                    severity="warning",
                )
            )

        if payload.market == "cn":
            notes.extend(
                [
                    RiskReportMethodologyNote(
                        code="CN_CURRENCY_BASIS",
                        title=cls._localized_text(language, "CNY basis", "人民币计价口径", "人民幣計價口徑"),
                        detail=cls._localized_text(
                            language,
                            "CN market report uses CNY valuation basis.",
                            "中国 A 股市场报告采用人民币（CNY）口径。",
                            "中國 A 股市場報告採用人民幣（CNY）口徑。",
                        ),
                    ),
                    RiskReportMethodologyNote(
                        code="CN_BENCHMARK",
                        title=cls._localized_text(language, "CSI300 benchmark", "沪深 300 基准", "滬深 300 基準"),
                        detail=cls._localized_text(
                            language,
                            "CN out-of-sample benchmark uses CSI300 (000300).",
                            "中国 A 股样本外评估基准使用沪深 300（CSI300，000300）。",
                            "中國 A 股樣本外評估基準使用滬深 300（CSI300，000300）。",
                        ),
                    ),
                    RiskReportMethodologyNote(
                        code="CN_FACTOR_ATTRIBUTION_UNAVAILABLE",
                        title=cls._localized_text(
                            language,
                            "China A-share factor attribution unavailable",
                            "A 股因子归因不可用",
                            "A 股因子歸因不可用",
                        ),
                        detail=cls._localized_text(
                            language,
                            "China A-share factor attribution unavailable.",
                            "当前尚未接入中国 A 股因子归因，报告不会使用 A 股 Alpha 归因结论。",
                            "目前尚未接入中國 A 股因子歸因，報告不會使用 A 股 Alpha 歸因結論。",
                        ),
                        severity="limitation",
                    ),
                ]
            )

        if payload.market == "jp":
            notes.extend(
                [
                    RiskReportMethodologyNote(
                        code="JP_CURRENCY_BASIS",
                        title=cls._localized_text(language, "JPY basis", "日元计价口径", "日圓計價口徑"),
                        detail=cls._localized_text(
                            language,
                            "JP market report uses JPY valuation basis.",
                            "日本市场报告采用日元（JPY）口径。",
                            "日本市場報告採用日圓（JPY）口徑。",
                        ),
                    ),
                    RiskReportMethodologyNote(
                        code="JP_BENCHMARK",
                        title=cls._localized_text(language, "Nikkei 225 benchmark", "日经 225 基准", "日經 225 基準"),
                        detail=cls._localized_text(
                            language,
                            "JP out-of-sample benchmark uses Nikkei 225 (^N225).",
                            "日本市场样本外评估基准使用日经 225（^N225）。",
                            "日本市場樣本外評估基準使用日經 225（^N225）。",
                        ),
                    ),
                    RiskReportMethodologyNote(
                        code="JP_FACTOR_ATTRIBUTION_UNAVAILABLE",
                        title=cls._localized_text(
                            language,
                            "Japan market factor attribution unavailable",
                            "日本市场因子归因不可用",
                            "日本市場因子歸因不可用",
                        ),
                        detail=cls._localized_text(
                            language,
                            "Japan market factor attribution unavailable.",
                            "当前尚未接入日本市场因子归因，报告不会使用日股 Alpha 归因结论。",
                            "目前尚未接入日本市場因子歸因，報告不會使用日股 Alpha 歸因結論。",
                        ),
                        severity="limitation",
                    ),
                ]
            )

        if payload.market == "tw":
            notes.extend(
                [
                    RiskReportMethodologyNote(
                        code="TW_CURRENCY_BASIS",
                        title=cls._localized_text(language, "TWD basis", "新台币计价口径", "新台幣計價口徑"),
                        detail=cls._localized_text(
                            language,
                            "TW market report uses TWD valuation basis.",
                            "台湾市场报告采用新台币（TWD）口径。",
                            "台灣市場報告採用新台幣（TWD）口徑。",
                        ),
                    ),
                    RiskReportMethodologyNote(
                        code="TW_BENCHMARK",
                        title=cls._localized_text(language, "TAIEX benchmark", "台湾加权指数基准", "台灣加權指數基準"),
                        detail=cls._localized_text(
                            language,
                            "TW out-of-sample benchmark uses TAIEX (^TWII).",
                            "台湾市场样本外评估基准使用台湾加权指数（TAIEX，^TWII）。",
                            "台灣市場樣本外評估基準使用台灣加權指數（TAIEX，^TWII）。",
                        ),
                    ),
                    RiskReportMethodologyNote(
                        code="TW_FACTOR_ATTRIBUTION_UNAVAILABLE",
                        title=cls._localized_text(
                            language,
                            "Taiwan market factor attribution unavailable",
                            "台湾市场因子归因不可用",
                            "台灣市場因子歸因不可用",
                        ),
                        detail=cls._localized_text(
                            language,
                            "Taiwan market factor attribution unavailable.",
                            "当前尚未接入台湾市场因子归因，报告不会使用台股 Alpha 归因结论。",
                            "目前尚未接入台灣市場因子歸因，報告不會使用台股 Alpha 歸因結論。",
                        ),
                        severity="limitation",
                    ),
                ]
            )

        warning_text = " ".join(data_warnings)
        if "inverse-volatility" in warning_text:
            notes.append(
                RiskReportMethodologyNote(
                    code="INVERSE_VOL_PRIOR_FALLBACK",
                    title=cls._localized_text(
                        language,
                        "Inverse-volatility prior fallback",
                        "逆波动率先验兜底",
                        "逆波動率先驗兜底",
                    ),
                    detail=cls._localized_text(
                        language,
                        "Market-cap prior was unavailable; inverse-volatility prior fallback was used where applicable.",
                        "市值先验不可用时，相关配置已使用逆波动率先验作为兜底。",
                        "市值先驗不可用時，相關配置已使用逆波動率先驗作為兜底。",
                    ),
                    severity="warning",
                )
            )

        if data_warnings:
            notes.append(
                RiskReportMethodologyNote(
                    code="DATA_WARNING_DISCLOSURE",
                    title=cls._localized_text(language, "Data warnings", "数据提示", "資料提示"),
                    detail=cls._localized_text(
                        language,
                        "Data provider fallbacks, stale cache, HTTP limits, sample insufficiency, or missing optional modules may affect report interpretation.",
                        "数据源兜底、缓存、HTTP 限流、样本不足或可选模块缺失都可能影响报告解读。",
                        "資料源兜底、快取、HTTP 限流、樣本不足或可選模組缺失都可能影響報告解讀。",
                    ),
                    severity="warning",
                )
            )
        return notes

    @classmethod
    def _report_disclaimers(cls, language: ReportLanguage) -> list[str]:
        """Return report disclaimers."""
        return [
            cls._localized_text(
                language,
                "This report is for risk monitoring and research support only; it is not investment advice or a transaction instruction.",
                "本报告仅用于风险监控与投研辅助，不构成投资建议或交易指令。",
                "本報告僅用於風險監控與投研輔助，不構成投資建議或交易指令。",
            ),
            cls._localized_text(
                language,
                "Model forecasts, crisis probabilities, OOS metrics, and allocation outputs are estimates and may be wrong.",
                "模型预测、危机概率、样本外指标与配置输出均为估计结果，可能出现误差。",
                "模型預測、危機概率、樣本外指標與配置輸出均為估計結果，可能出現誤差。",
            ),
            cls._localized_text(
                language,
                "Provider availability, rate limits, fallback data, market holidays, and short samples can materially change the analysis.",
                "数据源可用性、限流、兜底数据、市场假期和短样本可能显著影响分析结果。",
                "資料源可用性、限流、兜底資料、市場假期和短樣本可能顯著影響分析結果。",
            ),
        ]

    @classmethod
    def _report_sections(
        cls,
        payload: RiskReportRequest,
        report: RiskReportResult,
    ) -> list[RiskReportSection]:
        """Build report section metadata for client rendering."""
        language = payload.language
        requested = {section.strip() for section in (payload.include_sections or []) if section.strip()}

        def is_included(key: str) -> bool:
            return not requested or key in requested

        def title(en: str, zh: str, tc: str) -> str:
            return cls._localized_text(language, en, zh, tc)

        sections = [
            RiskReportSection(
                key="portfolio_overview",
                title=title("Portfolio Overview", "组合概览", "組合概覽"),
                summary=cls._section_summary(report, "portfolio_overview"),
                included=is_included("portfolio_overview"),
                metrics=[
                    RiskReportMetric(key="market", label=title("Market", "市场", "市場"), value=report.portfolio_overview.market),
                    RiskReportMetric(key="capital", label=title("Capital", "资本", "資本"), value=report.portfolio_overview.capital, unit=report.portfolio_overview.currency),
                    RiskReportMetric(key="leverage", label=title("Leverage", "杠杆", "槓桿"), value=report.portfolio_overview.leverage, unit="x"),
                ],
            ),
            RiskReportSection(
                key="executive_risk_summary",
                title=title("Executive Risk Summary", "执行摘要", "執行摘要"),
                summary=cls._section_summary(report, "executive_risk_summary"),
                included=is_included("executive_risk_summary"),
                metrics=[
                    RiskReportMetric(key="historical_es", label=title("Historical ES", "历史 ES", "歷史 ES"), value=report.traditional_risk.historical_es),
                    RiskReportMetric(key="monte_carlo_es", label=title("Monte Carlo ES", "蒙特卡洛 ES", "蒙地卡羅 ES"), value=report.traditional_risk.monte_carlo_es),
                    RiskReportMetric(key="ml_risk_level", label=title("ML risk level", "ML 风险等级", "ML 風險等級"), value=report.ml_forecast.risk_level if report.ml_forecast else None),
                    RiskReportMetric(key="crisis_probability", label=title("Crisis probability", "危机概率", "危機概率"), value=report.crisis_warning.crisis_probability if report.crisis_warning else None),
                    RiskReportMetric(key="model_score", label=title("Model score", "模型评分", "模型評分"), value=report.decision_summary.model_score),
                ],
            ),
            RiskReportSection(
                key="traditional_risk",
                title=title("Traditional Risk Metrics", "传统风险指标", "傳統風險指標"),
                summary=cls._section_summary(report, "traditional_risk"),
                included=is_included("traditional_risk"),
            ),
            RiskReportSection(
                key="ml_forecast",
                title=title("ML Risk Forecast", "ML 风险预测", "ML 風險預測"),
                summary=cls._section_summary(report, "ml_forecast"),
                included=is_included("ml_forecast") and report.ml_forecast is not None,
                warnings=[] if report.ml_forecast else [
                    title("ML forecast is unavailable.", "机器学习预测不可用。", "機器學習預測不可用。")
                ],
            ),
            RiskReportSection(
                key="anomaly",
                title=title("Anomaly Detection", "异常检测", "異常偵測"),
                summary=cls._section_summary(report, "anomaly"),
                included=is_included("anomaly") and report.anomaly is not None,
                warnings=[] if report.anomaly else [
                    title("Anomaly detection is unavailable.", "异常检测不可用。", "異常偵測不可用。")
                ],
            ),
            RiskReportSection(
                key="regime",
                title=title("Market Regime", "市场状态", "市場狀態"),
                summary=cls._section_summary(report, "regime"),
                included=is_included("regime") and report.regime is not None,
                warnings=[] if report.regime else [
                    title("Market regime detection is unavailable.", "市场状态识别不可用。", "市場狀態識別不可用。")
                ],
            ),
            RiskReportSection(
                key="crisis_warning",
                title=title("Explainable Crisis Warning", "可解释危机预警", "可解釋危機預警"),
                summary=cls._section_summary(report, "crisis_warning"),
                included=is_included("crisis_warning") and report.crisis_warning is not None,
                warnings=[] if report.crisis_warning else [
                    title("Crisis warning is unavailable.", "危机预警不可用。", "危機預警不可用。")
                ],
            ),
            RiskReportSection(
                key="decision_summary",
                title=title("Decision / OOS Summary", "决策 / 样本外摘要", "決策 / 樣本外摘要"),
                summary=cls._section_summary(report, "decision_summary"),
                included=is_included("decision_summary"),
            ),
            RiskReportSection(
                key="methodology_notes",
                title=title("Methodology Notes", "方法说明", "方法說明"),
                summary=cls._section_summary(report, "methodology_notes"),
                included=is_included("methodology_notes"),
            ),
            RiskReportSection(
                key="disclaimer",
                title=title("Disclaimer", "免责声明", "免責聲明"),
                summary=cls._section_summary(report, "disclaimer"),
                included=is_included("disclaimer"),
            ),
        ]
        return [section for section in sections if section.included]

    @classmethod
    def _build_report_result(
        cls,
        payload: RiskReportRequest,
        analysis: AnalysisRunResult,
        extra_warnings: list[str],
    ) -> RiskReportResult:
        """Map an analysis result into a structured report response."""
        risk = analysis.risk
        optimization = analysis.optimization
        data_warnings = cls._collect_report_warnings(analysis, extra_warnings)
        overview = RiskReportPortfolioOverview(
            tickers=list(payload.tickers),
            weights=cls._normalize_report_weights(list(payload.weights or []), len(payload.tickers)),
            market=payload.market,
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat(),
            capital=float(payload.capital),
            leverage=float(payload.leverage),
            currency=REPORT_CURRENCY_BY_MARKET.get(payload.market, "USD"),
        )
        traditional_risk = RiskReportTraditionalRisk(
            historical_es=cls._safe_report_float(risk.historical_es),
            monte_carlo_es=cls._safe_report_float(risk.monte_carlo_es),
            absolute_loss_historical=cls._safe_report_float(risk.absolute_loss_historical),
            absolute_loss_monte_carlo=cls._safe_report_float(risk.absolute_loss_monte_carlo),
            annualized_volatility=cls._safe_report_float(risk.annualized_volatility),
            max_drawdown=cls._safe_report_float(risk.max_drawdown),
            max_drawdown_date=risk.max_drawdown_date or "",
        )

        ml_report = None
        if analysis.ml_forecast is not None:
            ml_report = RiskReportMLForecast(
                ml_var=cls._safe_report_float(analysis.ml_forecast.ml_var),
                ml_es=cls._safe_report_float(analysis.ml_forecast.ml_es),
                risk_score=cls._safe_report_float(analysis.ml_forecast.risk_score),
                risk_level=analysis.ml_forecast.risk_level,
                top_features=list(analysis.ml_forecast.top_features or []),
                diagnostics_summary=cls._diagnostics_summary(analysis.ml_forecast.diagnostics),
            )

        anomaly_report = None
        if analysis.anomaly is not None:
            anomaly_report = RiskReportAnomaly(
                anomaly_score=cls._safe_report_float(analysis.anomaly.anomaly_score),
                alert_level=analysis.anomaly.alert_level,
                main_reasons=list(analysis.anomaly.main_reasons or []),
                decision_impact=analysis.anomaly.decision_impact,
            )

        regime_report = None
        if analysis.regime is not None:
            regime_report = RiskReportRegime(
                current_regime=analysis.regime.current_regime,
                smoothed_regime=analysis.regime.smoothed_regime,
                regime_probabilities=cls._safe_report_dict(analysis.regime.regime_probabilities),
                volatility_multiplier=cls._safe_report_float(analysis.regime.volatility_multiplier),
                correlation_multiplier=cls._safe_report_float(analysis.regime.correlation_multiplier),
                recommended_stress_level=analysis.regime.recommended_stress_level,
            )

        crisis_report = None
        if analysis.crisis_warning is not None:
            crisis_diagnostics = analysis.crisis_warning.diagnostics
            calibration_state = "calibrated" if crisis_diagnostics.probability_calibrated else "raw"
            crisis_report = RiskReportCrisisWarning(
                crisis_probability=cls._safe_report_float(analysis.crisis_warning.crisis_probability),
                warning_level=analysis.crisis_warning.warning_level,
                model_health=crisis_diagnostics.model_health,
                calibration_state=calibration_state,
                top_risk_drivers=[
                    cls._crisis_driver(driver)
                    for driver in list(analysis.crisis_warning.top_risk_drivers or [])
                ],
                risk_reducers=[
                    cls._crisis_driver(driver)
                    for driver in list(analysis.crisis_warning.risk_reducers or [])
                ],
            )

        decision_summary = RiskReportDecisionSummary(
            decision_policy=optimization.decision_policy,
            recommended_weights=cls._normalize_report_weights(
                list(optimization.recommended_weights or optimization.posterior_weights or []),
                len(payload.tickers),
            ),
            turnover=cls._safe_report_float(optimization.turnover),
            benchmark_symbol=optimization.benchmark_symbol,
            benchmark_name=optimization.benchmark_name,
            oos_excess_return=cls._safe_report_float(optimization.oos_excess_return),
            oos_optimized_sharpe=cls._safe_report_float(optimization.oos_optimized_sharpe),
            model_score=cls._safe_report_float(optimization.model_score),
            model_grade=optimization.model_grade,
        )
        executive_summary = cls._build_executive_summary(
            payload.language,
            overview,
            traditional_risk,
            ml_report,
            anomaly_report,
            regime_report,
            crisis_report,
            decision_summary,
            data_warnings,
        )

        report = RiskReportResult(
            report_title=cls._default_report_title(payload),
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            language=payload.language,
            portfolio_overview=overview,
            traditional_risk=traditional_risk,
            ml_forecast=ml_report,
            anomaly=anomaly_report,
            regime=regime_report,
            crisis_warning=crisis_report,
            decision_summary=decision_summary,
            executive_summary=executive_summary,
            methodology_notes=[],
            disclaimers=cls._report_disclaimers(payload.language),
            data_warnings=data_warnings,
        )
        report.methodology_notes = cls._build_methodology_notes(payload, analysis, data_warnings)
        report.sections = cls._report_sections(payload, report)
        return report

    async def generate_risk_report(self, payload: RiskReportRequest) -> RiskReportResult:
        """Run analysis and map it into a structured report."""
        extra_warnings: list[str] = []
        try:
            analysis = await self.run_analysis(payload)
        except ValueError as exc:
            if not payload.crisis_enabled:
                raise
            retry_payload = payload.model_copy(update={"crisis_enabled": False})
            analysis = await self.run_analysis(retry_payload)
            extra_warnings.append(
                f"Crisis warning is unavailable; report generated without crisis warning metrics. Reason: {exc}"
            )
        return self._build_report_result(payload, analysis, extra_warnings)

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
            (
                risk_free_rate,
                risk_free_rate_source,
                risk_free_rate_source_detail,
                risk_free_warnings,
            ) = self.resolve_risk_free_rate(
                fetcher,
                payload.risk_free_rate,
                asof=asof,
                market=payload.market,
            )
            if payload.market == "cn" and payload.risk_free_rate is None:
                risk_free_warnings = list(risk_free_warnings)
                risk_free_warnings.append("China A-share OOS benchmark uses CSI 300 Index (000300).")
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
