"""Smart multi-source data fetcher with automatic failover."""

import logging
import importlib
import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import requests_cache
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from data_pipeline.exceptions import DataFetcherError
from data_pipeline.provenance import DataQuality

logger = logging.getLogger(__name__)


def _akshare_module():
    return importlib.import_module("akshare")


class _LazyAkShare:
    def __getattr__(self, name: str):
        return getattr(_akshare_module(), name)


ak = _LazyAkShare()


class FetchRequest(BaseModel):
    """Validated request for fetching financial data."""

    symbol: str = Field(..., min_length=1)
    source: Literal[
        "us_equity",
        "hk_equity",
        "jp_equity",
        "tw_equity",
        "china_macro",
        "china_equity",
    ]
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, end_date: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        return end_date


class FetchResponse(BaseModel):
    """Structured response containing fetched market data."""

    symbol: str
    source: str
    records: int
    start_date: date
    end_date: date
    data: pd.DataFrame
    data_quality: DataQuality = Field(default_factory=DataQuality)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_serializer("data")
    def serialize_data(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        return data.to_dict(orient="records")


@dataclass(frozen=True)
class _CacheReadResult:
    """Internal cache read result with separate stale and partial flags."""

    data: pd.DataFrame
    is_stale: bool
    is_partial: bool
    provider: str
    coverage_ratio: float
    asof_date: Optional[str]


class SmartFetcher:
    """Fetch financial data from multiple sources with automatic failover."""

    _yf_lock = threading.RLock()
    _yf_last_call_time = 0.0
    _yf_cooldown_until = 0.0
    _yahoo_chart_cooldown_until = 0.0
    _china_akshare_cooldown_until = 0.0
    _yf_min_interval_seconds = 0.6
    _yf_cooldown_seconds = 15.0
    _yahoo_chart_cooldown_seconds = 15.0
    _china_akshare_cooldown_seconds = 90.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_name: str = "cache/http_cache",
        cache_expire_hours: int = 24,
        allow_sandbox_data: bool = False,
    ) -> None:
        self.api_key = api_key
        self.last_source = "unknown"
        self.last_source_detail = "unknown"
        self.data_warnings: List[str] = []
        self.last_data_quality = DataQuality()
        self._provider_chain: List[str] = []
        self.allow_sandbox_data = allow_sandbox_data
        self.cache_expire_hours = cache_expire_hours
        self.cache_enabled = os.getenv("DFQ_DISABLE_CACHE", "").lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._bypass_cache_reads = False
        self._result_cache_dir: Optional[str] = None
        self._session: requests.Session = requests.Session()

        if self.cache_enabled:
            cache_dir = os.path.dirname(cache_name)
            try:
                if cache_dir and not os.path.exists(cache_dir):
                    os.makedirs(cache_dir, exist_ok=True)

                self._result_cache_dir = os.path.join(cache_dir, "fetcher_results")
                os.makedirs(self._result_cache_dir, exist_ok=True)

                self._session = requests_cache.CachedSession(
                    cache_name,
                    backend="sqlite",
                    expire_after=cache_expire_hours * 3600,
                )
            except Exception as exc:
                logger.warning("local fetch cache disabled: %s", exc)
                self.cache_enabled = False
                self._result_cache_dir = None
                self._session = requests.Session()

        self._macro_registry: Dict[str, str] = {
            "lpr": "macro_china_lpr",
            "shrzgm": "macro_china_shrzgm",
            "cpi": "macro_china_cpi",
        }

    def disable_cache(self) -> None:
        """Bypass cache reads and cached HTTP responses for this request."""
        self._bypass_cache_reads = True
        self._session = requests.Session()

    def _result_cache_path(
        self,
        source: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> str:
        """Build a deterministic file path for a cached DataFrame."""
        if self._result_cache_dir is None:
            raise RuntimeError("result cache is disabled")
        safe_symbol = symbol.replace(".", "_").replace("/", "_")
        filename = f"{source}_{safe_symbol}_{start_date.isoformat()}_{end_date.isoformat()}.parquet"
        return os.path.join(self._result_cache_dir, filename)

    def _price_cache_path(self, source: str, symbol: str) -> str:
        """Build the symbol-level price cache path."""
        if self._result_cache_dir is None:
            raise RuntimeError("result cache is disabled")
        safe_symbol = symbol.replace(".", "_").replace("/", "_")
        filename = f"{source}_{safe_symbol}_prices.parquet"
        return os.path.join(self._result_cache_dir, filename)

    @staticmethod
    def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
        """Return a cache-safe price frame with normalized dates and close prices."""
        if df.empty:
            return df.copy()

        normalized = df.copy()
        if "Date" not in normalized.columns and "日期" in normalized.columns:
            normalized = normalized.rename(columns={"日期": "Date"})
        if "Date" not in normalized.columns:
            normalized = normalized.reset_index()
            if "Date" not in normalized.columns:
                normalized = normalized.rename(columns={normalized.columns[0]: "Date"})

        normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce")
        normalized["Date"] = normalized["Date"].dt.tz_localize(None).dt.normalize()

        if "Close" not in normalized.columns and "收盘" in normalized.columns:
            normalized["Close"] = normalized["收盘"]
        if "Close" not in normalized.columns and "Adj Close" in normalized.columns:
            normalized["Close"] = normalized["Adj Close"]
        if "Close" not in normalized.columns:
            return pd.DataFrame(columns=["Date", "Close"])

        normalized["Close"] = pd.to_numeric(normalized["Close"], errors="coerce")
        normalized = normalized.dropna(subset=["Date", "Close"])
        normalized = normalized.sort_values("Date")
        normalized = normalized.drop_duplicates(subset=["Date"], keep="last")
        return normalized.reset_index(drop=True)

    @staticmethod
    def _cache_storage_frame(df: pd.DataFrame) -> pd.DataFrame:
        """Return the canonical columns stored in price caches."""
        normalized = SmartFetcher._normalize_price_frame(df)
        if normalized.empty:
            return normalized
        return normalized[["Date", "Close"]].copy()

    @staticmethod
    def _provider_metadata_frame(df: pd.DataFrame) -> pd.DataFrame:
        """Return date-aligned provider metadata from a cached frame."""
        normalized = SmartFetcher._normalize_price_frame(df)
        if normalized.empty or "__provider" not in normalized.columns:
            return pd.DataFrame(columns=["Date", "__provider"])
        provider_frame = normalized[["Date", "__provider"]].copy()
        provider_frame["__provider"] = provider_frame["__provider"].fillna("unknown").astype(str)
        return provider_frame.drop_duplicates(subset=["Date"], keep="last")

    @staticmethod
    def _expected_cache_bounds(start_date: date, end_date: date) -> Tuple[pd.Timestamp, pd.Timestamp]:
        """Return tolerant business-day bounds for cache coverage checks."""
        business_days = pd.date_range(start_date, end_date, freq="B")
        if len(business_days) == 0:
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
        else:
            start_ts = pd.Timestamp(business_days.min())
            end_ts = pd.Timestamp(business_days.max())
        return start_ts, end_ts

    def _slice_cached_prices(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
        allow_partial: bool,
        require_exact_end: bool = False,
    ) -> Optional[Tuple[pd.DataFrame, bool, float]]:
        """Return cached prices when they cover the requested window."""
        normalized = self._normalize_price_frame(df)
        if normalized.empty:
            return None

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        filtered = normalized[
            (normalized["Date"] >= start_ts) & (normalized["Date"] <= end_ts)
        ].copy()
        if len(filtered) < 2:
            return None

        expected_start, expected_end = self._expected_cache_bounds(start_date, end_date)
        first_date = pd.Timestamp(filtered["Date"].min())
        last_date = pd.Timestamp(filtered["Date"].max())
        expected_rows = max(2, len(pd.date_range(start_date, end_date, freq="B")))
        coverage_ratio = float(np.clip(len(filtered) / expected_rows, 0.0, 1.0))
        complete_tolerance = pd.Timedelta(days=0 if require_exact_end or allow_partial else 3)
        covers_start = first_date <= expected_start + complete_tolerance
        covers_end = last_date >= expected_end - complete_tolerance
        has_full_coverage = covers_start and covers_end
        if has_full_coverage:
            return filtered.reset_index(drop=True), False, coverage_ratio

        enough_rows = len(filtered) >= max(2, int(expected_rows * 0.60))
        if allow_partial and covers_start and enough_rows:
            return filtered.reset_index(drop=True), True, coverage_ratio
        return None

    def _read_price_cache(
        self,
        source: str,
        symbol: str,
        start_date: date,
        end_date: date,
        allow_stale: bool = False,
        allow_partial: bool = False,
    ) -> Optional[_CacheReadResult]:
        """Read symbol-level or legacy exact-window cache data."""
        if self._bypass_cache_reads or not self.cache_enabled or self._result_cache_dir is None:
            return None

        paths = [
            self._price_cache_path(source, symbol),
            self._result_cache_path(source, symbol, start_date, end_date),
        ]
        require_exact_end = source == "us_equity" and not allow_stale and not allow_partial
        for path in paths:
            if not os.path.exists(path):
                continue
            try:
                mtime = os.path.getmtime(path)
                is_expired = time.time() - mtime > self.cache_expire_hours * 3600
                if is_expired and not allow_stale:
                    continue
                cached_df = pd.read_parquet(path)
                sliced = self._slice_cached_prices(
                    cached_df,
                    start_date,
                    end_date,
                    allow_partial=allow_partial,
                    require_exact_end=require_exact_end,
                )
                if sliced is None:
                    continue
                result_df, is_partial, coverage_ratio = sliced
                provider = self._providers_from_frame(result_df)
                provider_columns = [
                    column for column in result_df.columns
                    if str(column).startswith("__provider")
                ]
                result_df = result_df.drop(columns=provider_columns, errors="ignore")
                return _CacheReadResult(
                    data=result_df,
                    is_stale=bool(is_expired),
                    is_partial=bool(is_partial),
                    provider=provider,
                    coverage_ratio=coverage_ratio,
                    asof_date=self._asof_date_from_frame(result_df),
                )
            except Exception as exc:
                logger.warning("price cache read skipped for %s: %s", symbol, exc)
        return None

    def _read_result_cache(
        self,
        source: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> Optional[pd.DataFrame]:
        """Read a cached DataFrame if it exists and is not stale."""
        cached = self._read_price_cache(source, symbol, start_date, end_date)
        if cached is None:
            return None
        return cached.data

    def _write_result_cache(
        self,
        df: pd.DataFrame,
        source: str,
        symbol: str,
        start_date: date,
        end_date: date,
        provider: str = "unknown",
    ) -> None:
        """Persist a DataFrame to the local result cache."""
        if not self.cache_enabled or self._result_cache_dir is None:
            return
        try:
            normalized = self._cache_storage_frame(df)
            if normalized.empty:
                return
            normalized["__provider"] = provider

            symbol_path = self._price_cache_path(source, symbol)
            if os.path.exists(symbol_path):
                try:
                    existing_raw = pd.read_parquet(symbol_path)
                    existing = self._cache_storage_frame(existing_raw)
                    provider_map = self._provider_metadata_frame(existing_raw)
                    if not provider_map.empty:
                        existing = existing.merge(provider_map, on="Date", how="left")
                    if "__provider" not in existing.columns:
                        existing["__provider"] = "unknown"
                    normalized = pd.concat([existing, normalized], ignore_index=True)
                except Exception as exc:
                    logger.warning("price cache merge skipped for %s: %s", symbol, exc)
            normalized = normalized.sort_values("Date")
            normalized = normalized.drop_duplicates(subset=["Date"], keep="last")
            normalized.to_parquet(symbol_path, index=False)

            exact_path = self._result_cache_path(source, symbol, start_date, end_date)
            normalized.to_parquet(exact_path, index=False)
        except Exception as exc:
            logger.warning("result cache write skipped for %s: %s", symbol, exc)

    @staticmethod
    def _calendar_for_source(source: str) -> str:
        """Return the exchange calendar label for a fetcher source."""
        return {
            "us_equity": "NYSE",
            "hk_equity": "HKEX",
            "jp_equity": "JPX",
            "tw_equity": "XTAI",
            "china_equity": "SSE",
            "china_macro": "SSE",
        }.get(source, "unknown")

    @staticmethod
    def _provider_values(provider: str) -> List[str]:
        """Return clean provider labels from a cache metadata value."""
        if not provider or provider == "unknown":
            return []
        providers: List[str] = []
        for item in str(provider).replace("|", ",").split(","):
            text = item.strip()
            if text and text not in providers:
                providers.append(text)
        return providers

    @staticmethod
    def _providers_from_frame(df: pd.DataFrame) -> str:
        """Return provider metadata from a cached result slice."""
        provider_columns = [
            column for column in df.columns
            if str(column).startswith("__provider")
        ]
        providers: List[str] = []
        for column in provider_columns:
            for value in df[column].dropna().astype(str).tolist():
                text = value.strip()
                if text and text != "unknown" and text not in providers:
                    providers.append(text)
        if not providers:
            return "unknown"
        return ",".join(sorted(providers))

    @staticmethod
    def _asof_date_from_frame(df: pd.DataFrame) -> Optional[str]:
        """Return the latest normalized date in a price frame."""
        normalized = SmartFetcher._normalize_price_frame(df)
        if normalized.empty:
            return None
        latest = pd.to_datetime(normalized["Date"], errors="coerce").dropna()
        if latest.empty:
            return None
        return pd.Timestamp(latest.max()).strftime("%Y-%m-%d")

    @staticmethod
    def _coverage_ratio_from_frame(
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> float:
        """Estimate business-day coverage for a fetched price frame."""
        expected_days = pd.date_range(start_date, end_date, freq="B")
        if len(expected_days) == 0:
            return 1.0

        normalized = SmartFetcher._normalize_price_frame(df)
        if normalized.empty:
            return 0.0
        observed_days = pd.DatetimeIndex(
            pd.to_datetime(normalized["Date"], errors="coerce").dropna()
        ).normalize()
        covered_days = observed_days.intersection(expected_days)
        return float(np.clip(len(covered_days) / len(expected_days), 0.0, 1.0))

    def _append_provider_chain(self, providers: List[str]) -> List[str]:
        """Append providers to the request-level provider chain once."""
        for provider in providers:
            text = str(provider).strip()
            if text and text not in self._provider_chain:
                self._provider_chain.append(text)
        return list(self._provider_chain)

    def _live_cache_status(self) -> str:
        """Return cache status when a live provider supplied the data."""
        if self._bypass_cache_reads:
            return "bypassed"
        if not self.cache_enabled:
            return "disabled"
        return "miss"

    @staticmethod
    def _cache_status(is_stale: bool, is_partial: bool) -> str:
        """Return a cache status label from cache freshness and coverage."""
        if is_stale and is_partial:
            return "stale_partial"
        if is_stale:
            return "stale_cache"
        if is_partial:
            return "partial"
        return "hit"

    def _mark_data_quality(
        self,
        source: str,
        start_date: date,
        end_date: date,
        df: Optional[pd.DataFrame] = None,
        cache_status: str = "unknown",
        is_stale: bool = False,
        is_partial: bool = False,
        provider_chain: Optional[List[str]] = None,
        coverage_ratio: Optional[float] = None,
        asof_date: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ) -> DataQuality:
        """Store the latest request-level data quality metadata."""
        if provider_chain:
            self._append_provider_chain(provider_chain)
        elif self.last_source and self.last_source != "unknown":
            self._append_provider_chain([self.last_source])

        if df is not None:
            asof_date = asof_date or self._asof_date_from_frame(df)
            coverage_ratio = (
                self._coverage_ratio_from_frame(df, start_date, end_date)
                if coverage_ratio is None
                else coverage_ratio
            )
        if coverage_ratio is None:
            coverage_ratio = self.last_data_quality.coverage_ratio

        merged_warnings: List[str] = []
        for warning in [*self.data_warnings, *(warnings or [])]:
            if warning and warning not in merged_warnings:
                merged_warnings.append(warning)

        self.last_data_quality = DataQuality(
            asof_date=asof_date,
            coverage_ratio=float(np.clip(coverage_ratio, 0.0, 1.0)),
            calendar=self._calendar_for_source(source),
            cache_status=cache_status,
            is_stale=is_stale,
            is_partial=is_partial,
            provider_chain=list(self._provider_chain),
            warnings=merged_warnings,
        )
        return self.last_data_quality

    def _mark_source(self, source: str, detail: str) -> None:
        """Store the most recent data source metadata."""
        self.last_source = source
        self.last_source_detail = detail

    def _append_warning(self, message: str) -> None:
        """Append a warning once while preserving insertion order."""
        if message not in self.data_warnings:
            self.data_warnings.append(message)

    @classmethod
    def is_china_akshare_cooling_down(cls) -> bool:
        """Return whether recent AKShare A-share failures should be bypassed."""
        return time.time() < cls._china_akshare_cooldown_until

    @classmethod
    def _register_china_akshare_failure(cls) -> None:
        """Bypass AKShare A-share calls briefly after provider failures."""
        cls._china_akshare_cooldown_until = (
            time.time() + cls._china_akshare_cooldown_seconds
        )

    @staticmethod
    def _akshare_timeout_seconds() -> float:
        """Return the AKShare request timeout used for A-share fetches."""
        try:
            return max(1.0, float(os.getenv("DFQ_AKSHARE_TIMEOUT_SECONDS", "3")))
        except ValueError:
            return 3.0

    @staticmethod
    def _yahoo_chart_timeout_seconds() -> float:
        """Return the Yahoo chart request timeout used for equity fetches."""
        try:
            return max(1.0, float(os.getenv("DFQ_YAHOO_CHART_TIMEOUT_SECONDS", "8")))
        except ValueError:
            return 8.0

    @staticmethod
    def _yfinance_timeout_seconds() -> float:
        """Return the yfinance request timeout used for equity fetches."""
        try:
            return max(1.0, float(os.getenv("DFQ_YFINANCE_TIMEOUT_SECONDS", "8")))
        except ValueError:
            return 8.0

    @staticmethod
    def _akshare_attempts() -> int:
        """Return the configured AKShare attempt count for A-share fetches."""
        try:
            return max(1, int(os.getenv("DFQ_AKSHARE_ATTEMPTS", "1")))
        except ValueError:
            return 1

    @staticmethod
    def _market_for_ticker(ticker: str) -> Literal["us_equity", "hk_equity", "jp_equity", "tw_equity"]:
        """Resolve the fetcher market source for a listed ticker."""
        normalized = ticker.upper()
        if normalized.endswith(".HK"):
            return "hk_equity"
        if normalized.endswith(".T"):
            return "jp_equity"
        if normalized.endswith(".TW") or normalized.endswith(".TWO"):
            return "tw_equity"
        return "us_equity"

    @staticmethod
    def _normalize_cn_yahoo_symbol(symbol: str) -> str:
        """Normalize an A-share symbol for Yahoo Finance fallback."""
        clean_symbol = str(symbol).strip()
        if clean_symbol.startswith(("0", "2", "3")):
            return f"{clean_symbol}.SZ"
        if clean_symbol.startswith(("4", "8")):
            return f"{clean_symbol}.BJ"
        return f"{clean_symbol}.SS"

    @staticmethod
    def _cache_detail(is_stale: bool, is_partial: bool, provider: str) -> Tuple[str, str]:
        """Return normalized cache source and detail labels."""
        clean_provider = provider if provider and provider != "unknown" else "yfinance"
        if is_stale:
            source = "stale_cache"
        elif is_partial:
            source = "partial_cache"
        else:
            source = "cache"

        if is_stale and is_partial:
            prefix = "stale partial cache"
        elif is_stale:
            prefix = "stale cache"
        elif is_partial:
            prefix = "partial cache"
        else:
            prefix = "cache"
        return source, f"{prefix} ({clean_provider})"

    def _cache_response(
        self,
        market: Literal["us_equity", "hk_equity", "jp_equity", "tw_equity"],
        symbol: str,
        start_date: date,
        end_date: date,
        allow_stale: bool = False,
        allow_partial: bool = False,
    ) -> Optional[FetchResponse]:
        """Return a cache-backed fetch response when available."""
        cached = self._read_price_cache(
            market,
            symbol,
            start_date,
            end_date,
            allow_stale=allow_stale,
            allow_partial=allow_partial,
        )
        if cached is None:
            return None

        df = cached.data
        provider = cached.provider
        source, detail = self._cache_detail(
            cached.is_stale,
            cached.is_partial,
            provider,
        )
        self._mark_source(source, detail)
        if cached.is_stale or cached.is_partial:
            qualifier = "stale cached" if cached.is_stale else "partial cached"
            self._append_warning(
                f"{symbol}: using {qualifier} prices because live data is temporarily unavailable or incomplete"
            )
        quality = self._mark_data_quality(
            market,
            start_date,
            end_date,
            df=df,
            cache_status=self._cache_status(cached.is_stale, cached.is_partial),
            is_stale=cached.is_stale,
            is_partial=cached.is_partial,
            provider_chain=self._provider_values(provider),
            coverage_ratio=cached.coverage_ratio,
            asof_date=cached.asof_date,
        )
        return FetchResponse(
            symbol=symbol,
            source=market,
            records=len(df),
            start_date=start_date,
            end_date=end_date,
            data=df,
            data_quality=quality,
        )

    @classmethod
    def _respect_yf_rate_limit(cls) -> None:
        """Apply process-wide yfinance cooldown and minimum spacing."""
        now = time.time()
        if now < cls._yf_cooldown_until:
            remaining = int(cls._yf_cooldown_until - now)
            raise DataFetcherError(
                message=f"yfinance is cooling down after rate limiting; retry in about {remaining} seconds",
                symbol="batch",
                source="yfinance",
            )
        elapsed = now - cls._yf_last_call_time
        if elapsed < cls._yf_min_interval_seconds:
            time.sleep(cls._yf_min_interval_seconds - elapsed)

    @classmethod
    def _respect_yahoo_spacing(cls) -> None:
        """Apply lightweight spacing for direct Yahoo chart requests."""
        now = time.time()
        if now < cls._yahoo_chart_cooldown_until:
            remaining = int(cls._yahoo_chart_cooldown_until - now)
            raise DataFetcherError(
                message=f"Yahoo Finance is cooling down after rate limiting; retry in about {remaining} seconds",
                symbol="batch",
                source="yahoo_chart",
            )
        elapsed = now - cls._yf_last_call_time
        if elapsed < cls._yf_min_interval_seconds:
            time.sleep(cls._yf_min_interval_seconds - elapsed)

    @classmethod
    def _is_rate_limit_error(cls, exc: Exception) -> bool:
        """Return whether an exception represents provider-side throttling."""
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        message = str(exc).lower()
        return (
            isinstance(exc, YFRateLimitError)
            or status_code == 429
            or "too many requests" in message
            or "rate limit" in message
            or "429" in message
        )

    @classmethod
    def _register_yf_failure(cls, exc: Exception) -> None:
        """Open a short cooldown after yfinance rate limiting."""
        if cls._is_rate_limit_error(exc):
            cls._yf_cooldown_until = time.time() + cls._yf_cooldown_seconds

    @classmethod
    def _register_yahoo_chart_failure(cls, exc: Exception) -> None:
        """Open a short cooldown after direct Yahoo chart throttling."""
        if cls._is_rate_limit_error(exc):
            cls._yahoo_chart_cooldown_until = (
                time.time() + cls._yahoo_chart_cooldown_seconds
            )

    @staticmethod
    def _format_error(source: str, exc: Exception) -> str:
        """Format a provider error for diagnostics."""
        return f"{source}: {exc}"

    @staticmethod
    def _unix_timestamp(day: date, end_of_day: bool = False) -> int:
        """Convert a date into a UTC timestamp for Yahoo chart API calls."""
        clock = datetime_time(23, 59, 59) if end_of_day else datetime_time(0, 0, 0)
        return int(datetime.combine(day, clock, tzinfo=timezone.utc).timestamp())

    @staticmethod
    def _normalize_yf_symbol(symbol: str) -> str:
        """Normalize symbol for Yahoo Finance compatibility."""
        if symbol.upper().endswith(".HK"):
            prefix = symbol[:-3]
            # Yahoo Finance expects 4-digit HK codes; strip exactly one leading zero from 5-digit codes
            if len(prefix) == 5 and prefix.startswith("0"):
                prefix = prefix[1:]
            return prefix + ".HK"
        return symbol

    def _fetch_yahoo_chart(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch daily prices from Yahoo chart API without the yfinance cookie flow."""
        yf_symbol = self._normalize_yf_symbol(symbol)
        params = {
            "period1": self._unix_timestamp(start_date),
            "period2": self._unix_timestamp(end_date, end_of_day=True),
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "close",
        }
        provider_errors: List[str] = []
        for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
            url = f"https://{host}/v8/finance/chart/{yf_symbol}"
            try:
                response = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self._yahoo_chart_timeout_seconds(),
                )
                response.raise_for_status()
                payload = response.json()
                chart = payload.get("chart", {})
                error = chart.get("error")
                if error:
                    raise DataFetcherError(
                        message=str(error.get("description") or error),
                        symbol=symbol,
                        source="yahoo_chart",
                    )
                results = chart.get("result") or []
                if not results:
                    raise DataFetcherError(
                        message="empty Yahoo chart response",
                        symbol=symbol,
                        source="yahoo_chart",
                    )
                result = results[0]
                timestamps = result.get("timestamp") or []
                quote = (result.get("indicators", {}).get("quote") or [{}])[0]
                adjclose = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
                closes = adjclose or quote.get("close") or []
                if not timestamps or not closes:
                    raise DataFetcherError(
                        message="Yahoo chart response missing close prices",
                        symbol=symbol,
                        source="yahoo_chart",
                    )
                df = pd.DataFrame(
                    {
                        "Date": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None).normalize(),
                        "Close": closes,
                    }
                )
                df = self._normalize_price_frame(df)
                if df.empty:
                    raise DataFetcherError(
                        message="Yahoo chart response contained no finite close prices",
                        symbol=symbol,
                        source="yahoo_chart",
                    )
                return df
            except Exception as exc:
                provider_errors.append(f"{host}: {exc}")

        raise DataFetcherError(
            message="; ".join(provider_errors) or "Yahoo chart response failed",
            symbol=symbol,
            source="yahoo_chart",
        )

    def _fetch_yf(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        market: Literal["us_equity", "hk_equity", "jp_equity", "tw_equity"],
    ) -> FetchResponse:
        """Primary fetch via Yahoo Finance with process-wide rate limiting."""
        with self._yf_lock:
            cached = self._cache_response(market, symbol, start_date, end_date)
            if cached is not None:
                return cached

            try:
                self._respect_yahoo_spacing()
                df = self._fetch_yahoo_chart(symbol, start_date, end_date)
                SmartFetcher._yf_last_call_time = time.time()
                self._write_result_cache(df, market, symbol, start_date, end_date, provider="yahoo_chart")
                self._mark_source("yahoo_chart", "Yahoo Finance chart API")
                quality = self._mark_data_quality(
                    market,
                    start_date,
                    end_date,
                    df=df,
                    cache_status=self._live_cache_status(),
                    provider_chain=["yahoo_chart"],
                )
                return FetchResponse(
                    symbol=symbol,
                    source=market,
                    records=len(df),
                    start_date=start_date,
                    end_date=end_date,
                    data=df,
                    data_quality=quality,
                )
            except Exception as chart_exc:
                self._register_yahoo_chart_failure(chart_exc)
                self._append_provider_chain(["yahoo_chart"])
                logger.warning("Yahoo chart API failed for %s: %s", symbol, chart_exc)

            self._respect_yf_rate_limit()
            yf_symbol = self._normalize_yf_symbol(symbol)
            try:
                ticker = yf.Ticker(yf_symbol)
                df = ticker.history(
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                    timeout=self._yfinance_timeout_seconds(),
                )
                SmartFetcher._yf_last_call_time = time.time()
            except Exception as exc:
                self._register_yf_failure(exc)
                self._append_provider_chain(["yfinance"])
                raise DataFetcherError(
                    message=f"yfinance failed for {symbol}: {exc}",
                    symbol=symbol,
                    source="yfinance",
                    last_exception=exc,
                ) from exc

            df = self._normalize_price_frame(df)
            if df.empty or "Close" not in df.columns:
                raise DataFetcherError(
                    message=f"yfinance returned no usable close prices for {symbol}",
                    symbol=symbol,
                    source="yfinance",
                )

            self._write_result_cache(df, market, symbol, start_date, end_date, provider="yfinance")
            self._mark_source("yfinance", "yfinance")
            quality = self._mark_data_quality(
                market,
                start_date,
                end_date,
                df=df,
                cache_status=self._live_cache_status(),
                provider_chain=["yfinance"],
            )
            return FetchResponse(
                symbol=symbol,
                source=market,
                records=len(df),
                start_date=start_date,
                end_date=end_date,
                data=df,
                data_quality=quality,
            )

    def _fetch_tiingo(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Fallback fetch via Tiingo REST API."""
        if not self.api_key:
            raise DataFetcherError(
                message="Tiingo API key not provided",
                symbol=symbol,
                source="tiingo",
            )

        url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices"
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "format": "json",
        }
        headers = {"Authorization": f"Token {self.api_key}"}

        resp = self._session.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            raise DataFetcherError(
                message="empty Tiingo response",
                symbol=symbol,
                source="tiingo",
            )

        df = pd.DataFrame(data)

        # Normalize date column
        if "date" in df.columns:
            df["Date"] = pd.to_datetime(df["date"]).dt.normalize()
        elif "Date" not in df.columns:
            df["Date"] = pd.to_datetime(df.index)

        # Normalize price column: prefer adjusted close
        if "adjClose" in df.columns:
            df["Close"] = df["adjClose"]
            df["Adj Close"] = df["adjClose"]
        elif "close" in df.columns:
            df["Close"] = df["close"]

        if "Close" not in df.columns:
            raise DataFetcherError(
                message="missing Close column in Tiingo response",
                symbol=symbol,
                source="tiingo",
            )

        return df

    def _fetch_sandbox(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Generate deterministic demo price data."""
        rng = np.random.default_rng(abs(hash(symbol)) % (2 ** 32))
        trading_days = pd.date_range(start_date, end_date, freq="B")
        drift = 0.0002
        vol = 0.015
        returns = rng.normal(drift, vol, len(trading_days))
        prices = 100.0 * np.exp(np.cumsum(returns))

        df = pd.DataFrame(
            {
                "Date": pd.to_datetime(trading_days),
                "Close": prices,
            }
        )
        return df

    def _smart_fetch(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        market: Literal["us_equity", "hk_equity", "jp_equity", "tw_equity"],
    ) -> FetchResponse:
        """Try cache -> yfinance -> Tiingo -> stale cache -> optional sandbox."""
        cached = self._cache_response(market, symbol, start_date, end_date)
        if cached is not None:
            return cached

        provider_errors: List[str] = []

        try:
            return self._fetch_yf(symbol, start_date, end_date, market)
        except DataFetcherError as exc:
            provider_errors.append(self._format_error("yfinance", exc))
            logger.warning("yfinance failed for %s: %s", symbol, exc)
        except Exception as exc:
            provider_errors.append(self._format_error("yfinance", exc))
            logger.warning("yfinance failed for %s: %s", symbol, exc)

        if market == "us_equity" and self.api_key:
            try:
                df = self._fetch_tiingo(symbol, start_date, end_date)
                if not df.empty and "Close" in df.columns:
                    df = self._normalize_price_frame(df)
                    self._write_result_cache(
                        df,
                        market,
                        symbol,
                        start_date,
                        end_date,
                        provider="tiingo",
                    )
                    self._mark_source("tiingo", "tiingo")
                    quality = self._mark_data_quality(
                        market,
                        start_date,
                        end_date,
                        df=df,
                        cache_status=self._live_cache_status(),
                        provider_chain=["tiingo"],
                    )
                    return FetchResponse(
                        symbol=symbol,
                        source=market,
                        records=len(df),
                        start_date=start_date,
                        end_date=end_date,
                        data=df,
                        data_quality=quality,
                    )
            except Exception as exc:
                provider_errors.append(self._format_error("tiingo", exc))
                self._append_provider_chain(["tiingo"])
                logger.warning("tiingo failed for %s: %s", symbol, exc)

        stale_cached = self._cache_response(
            market,
            symbol,
            start_date,
            end_date,
            allow_stale=True,
            allow_partial=True,
        )
        if stale_cached is not None:
            return stale_cached

        if not self.allow_sandbox_data:
            details = "; ".join(provider_errors) if provider_errors else "no live provider returned data"
            raise DataFetcherError(
                message=(
                    f"Unable to fetch real price data for {symbol}. {details}. "
                    "Enable Demo Fallback only for sandbox demonstrations."
                ),
                symbol=symbol,
                source="smart_fetcher",
            )

        df = self._fetch_sandbox(symbol, start_date, end_date)
        self._mark_source("sandbox", "sandbox demo")
        self._append_warning(f"{symbol}: using sandbox demo prices")
        quality = self._mark_data_quality(
            market,
            start_date,
            end_date,
            df=df,
            cache_status=self._live_cache_status(),
            provider_chain=["sandbox"],
        )
        return FetchResponse(
            symbol=symbol,
            source=market,
            records=len(df),
            start_date=start_date,
            end_date=end_date,
            data=df,
            data_quality=quality,
        )

    def fetch_us_equity(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> FetchResponse:
        """Fetch US equity historical prices with failover."""
        return self._smart_fetch(symbol, start_date, end_date, "us_equity")

    def fetch_hk_equity(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> FetchResponse:
        """Fetch Hong Kong equity historical prices with failover."""
        return self._smart_fetch(symbol, start_date, end_date, "hk_equity")

    def fetch_jp_equity(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> FetchResponse:
        """Fetch Japan equity historical prices with failover."""
        return self._smart_fetch(symbol, start_date, end_date, "jp_equity")

    def fetch_tw_equity(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> FetchResponse:
        """Fetch Taiwan equity historical prices with failover."""
        return self._smart_fetch(symbol, start_date, end_date, "tw_equity")

    @staticmethod
    def _extract_yf_close_series(batch_df: pd.DataFrame, yf_symbol: str) -> Optional[pd.Series]:
        """Extract one close series from a yfinance batch response."""
        if batch_df.empty:
            return None
        if isinstance(batch_df.columns, pd.MultiIndex):
            candidates = [("Close", yf_symbol), (yf_symbol, "Close")]
            for close_col in candidates:
                if close_col in batch_df.columns:
                    close_series = batch_df[close_col].dropna()
                    return close_series if not close_series.empty else None
            return None
        if "Close" in batch_df.columns:
            close_series = batch_df["Close"].dropna()
            return close_series if not close_series.empty else None
        return None

    def _fetch_yf_batch(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
        cached_frames: Dict[str, pd.DataFrame],
        source_labels: Dict[str, str],
    ) -> None:
        """Fetch missing tickers in one yfinance call under the global lock."""
        with self._yf_lock:
            still_missing: List[str] = []
            for ticker in tickers:
                market = self._market_for_ticker(ticker)
                cached = self._read_price_cache(market, ticker, start_date, end_date)
                if cached is None:
                    still_missing.append(ticker)
                    continue
                cached_frames[ticker] = cached.data
                source_labels[ticker] = (
                    "stale_partial_cache"
                    if cached.is_stale and cached.is_partial
                    else self._cache_detail(cached.is_stale, cached.is_partial, cached.provider)[0]
                )
                self._append_provider_chain(self._provider_values(cached.provider))

            if not still_missing:
                return

            chart_missing: List[str] = []
            for ticker in still_missing:
                market = self._market_for_ticker(ticker)
                try:
                    self._respect_yahoo_spacing()
                    df = self._fetch_yahoo_chart(ticker, start_date, end_date)
                    SmartFetcher._yf_last_call_time = time.time()
                    self._write_result_cache(
                        df,
                        market,
                        ticker,
                        start_date,
                        end_date,
                        provider="yahoo_chart",
                    )
                    cached_frames[ticker] = df
                    source_labels[ticker] = "yahoo_chart"
                    self._append_provider_chain(["yahoo_chart"])
                except Exception as exc:
                    self._register_yahoo_chart_failure(exc)
                    self._append_provider_chain(["yahoo_chart"])
                    logger.warning("Yahoo chart API failed for %s: %s", ticker, exc)
                    chart_missing.append(ticker)

            if not chart_missing:
                return

            self._respect_yf_rate_limit()
            normalized_symbols = [self._normalize_yf_symbol(ticker) for ticker in chart_missing]
            try:
                batch_df = yf.download(
                    normalized_symbols,
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                    progress=False,
                    auto_adjust=False,
                    group_by="column",
                    threads=False,
                    timeout=self._yfinance_timeout_seconds(),
                )
                SmartFetcher._yf_last_call_time = time.time()
            except Exception as exc:
                self._register_yf_failure(exc)
                self._append_provider_chain(["yfinance"])
                raise DataFetcherError(
                    message=f"yfinance batch download failed: {exc}",
                    symbol=",".join(chart_missing),
                    source="yfinance",
                    last_exception=exc,
                ) from exc

            if batch_df.empty:
                raise DataFetcherError(
                    message="yfinance batch download returned no data",
                    symbol=",".join(chart_missing),
                    source="yfinance",
                )

            for ticker, yf_symbol in zip(chart_missing, normalized_symbols):
                close_series = self._extract_yf_close_series(batch_df, yf_symbol)
                if close_series is None:
                    continue
                df = pd.DataFrame(
                    {
                        "Date": pd.to_datetime(close_series.index).tz_localize(None).normalize(),
                        "Close": close_series.values,
                    }
                )
                market = self._market_for_ticker(ticker)
                self._write_result_cache(
                    df,
                    market,
                    ticker,
                    start_date,
                    end_date,
                    provider="yfinance",
                )
                cached_frames[ticker] = df
                source_labels[ticker] = "yfinance"
                self._append_provider_chain(["yfinance"])

    @staticmethod
    def _coverage_ratio_from_index(
        index: pd.Index,
        start_date: date,
        end_date: date,
    ) -> float:
        """Estimate business-day coverage from an aligned price index."""
        expected_days = pd.date_range(start_date, end_date, freq="B")
        if len(expected_days) == 0:
            return 1.0
        observed_days = pd.DatetimeIndex(pd.to_datetime(index, errors="coerce")).dropna()
        observed_days = observed_days.tz_localize(None).normalize()
        covered_days = observed_days.intersection(expected_days)
        return float(np.clip(len(covered_days) / len(expected_days), 0.0, 1.0))

    def _mark_batch_source(
        self,
        source_labels: Dict[str, str],
        market_source: str,
        start_date: date,
        end_date: date,
        aligned: pd.DataFrame,
    ) -> None:
        """Summarize per-ticker sources into response-level source metadata."""
        if not source_labels:
            self._mark_source("unknown", "unknown")
            self._mark_data_quality(market_source, start_date, end_date)
            return
        unique_sources = sorted(set(source_labels.values()))
        if len(unique_sources) == 1:
            source = "stale_cache" if unique_sources[0] == "stale_partial_cache" else unique_sources[0]
            detail = self._cache_detail(
                unique_sources[0] in {"stale_cache", "stale_partial_cache"},
                unique_sources[0] in {"partial_cache", "stale_partial_cache"},
                ",".join(self._provider_chain) or "yfinance",
            )[1] if unique_sources[0] in {
                "cache",
                "stale_cache",
                "partial_cache",
                "stale_partial_cache",
            } else source
            self._mark_source(source, detail)
        else:
            self._mark_source("mixed", ", ".join(unique_sources))

        is_stale = any(source in {"stale_cache", "stale_partial_cache"} for source in unique_sources)
        is_partial = any(source in {"partial_cache", "stale_partial_cache"} for source in unique_sources)
        cache_status = (
            self._cache_status(is_stale, is_partial)
            if len(unique_sources) == 1 and unique_sources[0] in {
                "cache",
                "stale_cache",
                "partial_cache",
                "stale_partial_cache",
            }
            else "mixed"
        )
        asof_date = None
        if not aligned.empty:
            asof_date = pd.Timestamp(pd.to_datetime(aligned.index).max()).strftime("%Y-%m-%d")
        self._mark_data_quality(
            market_source,
            start_date,
            end_date,
            cache_status=cache_status,
            is_stale=is_stale,
            is_partial=is_partial,
            coverage_ratio=self._coverage_ratio_from_index(aligned.index, start_date, end_date),
            asof_date=asof_date,
        )

    def fetch_equity_batch(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch multiple equity prices with batch download and per-ticker failover."""
        cached_frames: Dict[str, pd.DataFrame] = {}
        source_labels: Dict[str, str] = {}
        missing_tickers: List[str] = []

        for ticker in tickers:
            market = self._market_for_ticker(ticker)
            cached = self._read_price_cache(market, ticker, start_date, end_date)
            if cached is not None:
                cached_frames[ticker] = cached.data
                source_labels[ticker] = (
                    "stale_partial_cache"
                    if cached.is_stale and cached.is_partial
                    else self._cache_detail(cached.is_stale, cached.is_partial, cached.provider)[0]
                )
                self._append_provider_chain(self._provider_values(cached.provider))
                if cached.is_stale or cached.is_partial:
                    qualifier = "stale cached" if cached.is_stale else "partial cached"
                    self._append_warning(
                        f"{ticker}: using {qualifier} prices because live data is temporarily unavailable or incomplete"
                    )
            else:
                missing_tickers.append(ticker)

        if not missing_tickers:
            frames = []
            for ticker, df in cached_frames.items():
                sub = df.set_index("Date")[["Close"]].rename(columns={"Close": ticker})
                sub.index = pd.to_datetime(sub.index).tz_localize(None).normalize()
                frames.append(sub)
            combined = pd.concat(frames, axis=1)
            combined.columns = pd.MultiIndex.from_product([["Close"], combined.columns])
            market_source = self._market_for_ticker(tickers[0]) if tickers else "us_equity"
            self._mark_batch_source(source_labels, market_source, start_date, end_date, combined)
            return combined

        if missing_tickers:
            try:
                self._fetch_yf_batch(
                    missing_tickers,
                    start_date,
                    end_date,
                    cached_frames,
                    source_labels,
                )
            except DataFetcherError as exc:
                logger.warning("yfinance batch download failed: %s", exc)
            except Exception as exc:
                logger.warning("yfinance batch download failed: %s", exc)

        series_list: List[pd.Series] = []
        for ticker in tickers:
            if ticker in cached_frames:
                df = cached_frames[ticker]
            else:
                market = self._market_for_ticker(ticker)
                response = self._smart_fetch(ticker, start_date, end_date, market)
                df = response.data
                source_labels[ticker] = self.last_source

            if "Close" not in df.columns:
                raise DataFetcherError(
                    message=f"missing Close column for {ticker}",
                    symbol=ticker,
                    source="smart_fetcher",
                )

            date_col = "Date" if "Date" in df.columns else df.columns[0]
            prices = pd.Series(
                df["Close"].values,
                index=pd.to_datetime(df[date_col].values),
                name=ticker,
            )
            series_list.append(prices)

        aligned = pd.concat([s.to_frame() for s in series_list], axis=1)
        aligned.index = pd.to_datetime(aligned.index).tz_localize(None).normalize()
        aligned.columns = pd.MultiIndex.from_product([["Close"], aligned.columns])
        market_source = self._market_for_ticker(tickers[0]) if tickers else "us_equity"
        self._mark_batch_source(source_labels, market_source, start_date, end_date, aligned)
        return aligned

    def fetch_china_equity(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> FetchResponse:
        """Fetch A-share historical prices via AKShare."""
        cached = self._read_price_cache("china_equity", symbol, start_date, end_date)
        if cached is not None:
            df = cached.data
            cache_provider = cached.provider if cached.provider and cached.provider != "unknown" else "akshare"
            source, detail = self._cache_detail(
                cached.is_stale,
                cached.is_partial,
                cache_provider,
            )
            self._mark_source(source, detail)
            if cached.is_stale or cached.is_partial:
                qualifier = "stale cached" if cached.is_stale else "partial cached"
                self._append_warning(
                    f"{symbol}: using {qualifier} prices because live data is temporarily unavailable or incomplete"
                )
            quality = self._mark_data_quality(
                "china_equity",
                start_date,
                end_date,
                df=df,
                cache_status=self._cache_status(cached.is_stale, cached.is_partial),
                is_stale=cached.is_stale,
                is_partial=cached.is_partial,
                provider_chain=self._provider_values(cache_provider),
                coverage_ratio=cached.coverage_ratio,
                asof_date=cached.asof_date,
            )
            return FetchResponse(
                symbol=symbol,
                source="china_equity",
                records=len(df),
                start_date=start_date,
                end_date=end_date,
                data=df,
                data_quality=quality,
            )

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        provider_errors: List[str] = []

        if self.is_china_akshare_cooling_down():
            provider_errors.append("akshare: skipped during provider cooldown")
        else:
            for attempt in range(self._akshare_attempts()):
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=symbol,
                        period="daily",
                        start_date=start_str,
                        end_date=end_str,
                        adjust="qfq",
                        timeout=self._akshare_timeout_seconds(),
                    )
                    if df.empty:
                        raise DataFetcherError(
                            message="empty dataframe returned from AKShare",
                            symbol=symbol,
                            source="china_equity",
                        )
                    self._write_result_cache(
                        df,
                        "china_equity",
                        symbol,
                        start_date,
                        end_date,
                        provider="akshare",
                    )
                    self._mark_source("akshare", "AKShare A-share daily qfq")
                    quality = self._mark_data_quality(
                        "china_equity",
                        start_date,
                        end_date,
                        df=df,
                        cache_status=self._live_cache_status(),
                        provider_chain=["akshare"],
                    )
                    return FetchResponse(
                        symbol=symbol,
                        source="china_equity",
                        records=len(df),
                        start_date=start_date,
                        end_date=end_date,
                        data=df,
                        data_quality=quality,
                    )
                except Exception as exc:
                    self._register_china_akshare_failure()
                    provider_errors.append(self._format_error("akshare", exc))
                    self._append_provider_chain(["akshare"])
                    logger.warning("AKShare A-share fetch failed for %s: %s", symbol, exc)
                    if attempt < self._akshare_attempts() - 1:
                        time.sleep(0.5)

        try:
            yahoo_symbol = self._normalize_cn_yahoo_symbol(symbol)
            df = self._fetch_yahoo_chart(yahoo_symbol, start_date, end_date)
            if df.empty or "Close" not in df.columns:
                raise DataFetcherError(
                    message="Yahoo Finance fallback returned no usable close prices",
                    symbol=symbol,
                    source="yahoo_chart",
                )
            self._write_result_cache(
                df,
                "china_equity",
                symbol,
                start_date,
                end_date,
                provider="yahoo_chart_cn",
            )
            self._mark_source("yahoo_chart", "Yahoo Finance chart API (A-share fallback)")
            self._append_warning(
                f"{symbol}: AKShare A-share data was unavailable; using Yahoo Finance fallback"
            )
            quality = self._mark_data_quality(
                "china_equity",
                start_date,
                end_date,
                df=df,
                cache_status=self._live_cache_status(),
                provider_chain=["yahoo_chart_cn"],
            )
            return FetchResponse(
                symbol=symbol,
                source="china_equity",
                records=len(df),
                start_date=start_date,
                end_date=end_date,
                data=df,
                data_quality=quality,
            )
        except Exception as exc:
            provider_errors.append(self._format_error("yahoo_chart", exc))
            self._append_provider_chain(["yahoo_chart_cn"])
            logger.warning("Yahoo A-share fallback failed for %s: %s", symbol, exc)

        stale_cached = self._read_price_cache(
            "china_equity",
            symbol,
            start_date,
            end_date,
            allow_stale=True,
            allow_partial=True,
        )
        if stale_cached is not None:
            df = stale_cached.data
            cache_provider = (
                stale_cached.provider
                if stale_cached.provider and stale_cached.provider != "unknown"
                else "akshare"
            )
            source, detail = self._cache_detail(
                stale_cached.is_stale,
                stale_cached.is_partial,
                cache_provider,
            )
            self._mark_source(source, detail)
            qualifier = "stale cached" if stale_cached.is_stale else "partial cached"
            self._append_warning(
                f"{symbol}: using {qualifier} prices because live data is temporarily unavailable or incomplete"
            )
            quality = self._mark_data_quality(
                "china_equity",
                start_date,
                end_date,
                df=df,
                cache_status=self._cache_status(stale_cached.is_stale, stale_cached.is_partial),
                is_stale=stale_cached.is_stale,
                is_partial=stale_cached.is_partial,
                provider_chain=self._provider_values(cache_provider),
                coverage_ratio=stale_cached.coverage_ratio,
                asof_date=stale_cached.asof_date,
            )
            return FetchResponse(
                symbol=symbol,
                source="china_equity",
                records=len(df),
                start_date=start_date,
                end_date=end_date,
                data=df,
                data_quality=quality,
            )

        if self.allow_sandbox_data:
            df = self._fetch_sandbox(symbol, start_date, end_date)
            self._mark_source("sandbox", "sandbox demo")
            self._append_warning(f"{symbol}: using sandbox demo prices")
            quality = self._mark_data_quality(
                "china_equity",
                start_date,
                end_date,
                df=df,
                cache_status=self._live_cache_status(),
                provider_chain=["sandbox"],
            )
            return FetchResponse(
                symbol=symbol,
                source="china_equity",
                records=len(df),
                start_date=start_date,
                end_date=end_date,
                data=df,
                data_quality=quality,
            )

        details = "; ".join(provider_errors) if provider_errors else "no live provider returned data"
        raise DataFetcherError(
            message=(
                f"Unable to fetch real A-share price data for {symbol}. {details}. "
                "Enable Demo Fallback only for sandbox demonstrations."
            ),
            symbol=symbol,
            source="china_equity",
        )

    def fetch_china_macro(
        self,
        indicator: str,
        start_date: date,
        end_date: date,
    ) -> FetchResponse:
        """Fetch China macroeconomic indicators via AKShare."""
        fetch_name = self._macro_registry.get(indicator)
        if fetch_name is None:
            raise DataFetcherError(
                message=f"unsupported macro indicator: {indicator}",
                symbol=indicator,
                source="china_macro",
            )

        fetch_fn = getattr(_akshare_module(), fetch_name)
        df = fetch_fn()

        date_col = None
        for candidate in ("日期", "datetime", "time", "publish_date"):
            if candidate in df.columns:
                date_col = candidate
                break

        if date_col is None:
            self._mark_source("akshare", "AKShare China macro")
            quality = self._mark_data_quality(
                "china_macro",
                start_date,
                end_date,
                df=df,
                cache_status=self._live_cache_status(),
                provider_chain=["akshare"],
            )
            return FetchResponse(
                symbol=indicator,
                source="china_macro",
                records=len(df),
                start_date=start_date,
                end_date=end_date,
                data=df,
                data_quality=quality,
            )

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        mask = (
            df[date_col] >= pd.Timestamp(start_date)
        ) & (df[date_col] <= pd.Timestamp(end_date))
        df = df.loc[mask].copy()

        self._mark_source("akshare", "AKShare China macro")
        quality = self._mark_data_quality(
            "china_macro",
            start_date,
            end_date,
            df=df,
            cache_status=self._live_cache_status(),
            provider_chain=["akshare"],
        )
        return FetchResponse(
            symbol=indicator,
            source="china_macro",
            records=len(df),
            start_date=start_date,
            end_date=end_date,
            data=df,
            data_quality=quality,
        )

    def fetch(self, request: FetchRequest) -> FetchResponse:
        """Unified routing entry point."""
        if request.source == "us_equity":
            return self.fetch_us_equity(
                request.symbol, request.start_date, request.end_date
            )
        if request.source == "hk_equity":
            return self.fetch_hk_equity(
                request.symbol, request.start_date, request.end_date
            )
        if request.source == "jp_equity":
            return self.fetch_jp_equity(
                request.symbol, request.start_date, request.end_date
            )
        if request.source == "tw_equity":
            return self.fetch_tw_equity(
                request.symbol, request.start_date, request.end_date
            )
        if request.source == "china_equity":
            return self.fetch_china_equity(
                request.symbol, request.start_date, request.end_date
            )
        if request.source == "china_macro":
            return self.fetch_china_macro(
                request.symbol, request.start_date, request.end_date
            )

        raise DataFetcherError(
            message=f"unsupported source: {request.source}",
            symbol=request.symbol,
            source=request.source,
        )
