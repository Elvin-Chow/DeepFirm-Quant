"""Smart multi-source data fetcher with automatic failover."""

import logging
import os
import time
from datetime import date
from typing import Any, Callable, Dict, List, Literal, Optional

import akshare as ak
import numpy as np
import pandas as pd
import requests
import requests_cache
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from pydantic import BaseModel, Field, field_validator

from data_pipeline.exceptions import DataFetcherError

logger = logging.getLogger(__name__)


class FetchRequest(BaseModel):
    """Validated request for fetching financial data."""

    symbol: str = Field(..., min_length=1)
    source: Literal["us_equity", "hk_equity", "china_macro", "china_equity"]
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

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {pd.DataFrame: lambda df: df.to_dict(orient="records")},
    }


class SmartFetcher:
    """Fetch financial data from multiple sources with automatic failover."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_name: str = "cache/http_cache",
        cache_expire_hours: int = 24,
    ) -> None:
        self.api_key = api_key
        self.last_source = "unknown"
        self.cache_expire_hours = cache_expire_hours
        self._last_yf_call_time = 0.0

        cache_dir = os.path.dirname(cache_name)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)

        self._result_cache_dir = os.path.join(cache_dir, "fetcher_results")
        os.makedirs(self._result_cache_dir, exist_ok=True)

        self._session = requests_cache.CachedSession(
            cache_name,
            backend="sqlite",
            expire_after=cache_expire_hours * 3600,
        )
        self._macro_registry: Dict[str, Callable[..., pd.DataFrame]] = {
            "lpr": ak.macro_china_lpr,
            "shrzgm": ak.macro_china_shrzgm,
            "cpi": ak.macro_china_cpi,
        }

    def _result_cache_path(
        self,
        source: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> str:
        """Build a deterministic file path for a cached DataFrame."""
        safe_symbol = symbol.replace(".", "_").replace("/", "_")
        filename = f"{source}_{safe_symbol}_{start_date.isoformat()}_{end_date.isoformat()}.parquet"
        return os.path.join(self._result_cache_dir, filename)

    def _read_result_cache(
        self,
        source: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> Optional[pd.DataFrame]:
        """Read a cached DataFrame if it exists and is not stale."""
        path = self._result_cache_path(source, symbol, start_date, end_date)
        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        if time.time() - mtime > self.cache_expire_hours * 3600:
            return None
        try:
            return pd.read_parquet(path)
        except Exception:
            return None

    def _write_result_cache(
        self,
        df: pd.DataFrame,
        source: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> None:
        """Persist a DataFrame to the local result cache."""
        path = self._result_cache_path(source, symbol, start_date, end_date)
        df.to_parquet(path, index=False)

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

    def _fetch_yf(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Primary fetch via Yahoo Finance with per-instance rate limiting."""
        elapsed = time.time() - self._last_yf_call_time
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        yf_symbol = self._normalize_yf_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(start=start_date.isoformat(), end=end_date.isoformat())
        self._last_yf_call_time = time.time()
        df = df.reset_index()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
        return df

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

        resp = requests.get(url, params=params, headers=headers, timeout=30)
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
        """Final fallback: local cache or synthetic data."""
        for source in ("us_equity", "hk_equity"):
            cached = self._read_result_cache(source, symbol, start_date, end_date)
            if cached is not None:
                return cached

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
        market: Literal["us_equity", "hk_equity"],
    ) -> FetchResponse:
        """Try yfinance -> Tiingo -> sandbox in sequence."""
        # 1. Primary: yfinance
        try:
            df = self._fetch_yf(symbol, start_date, end_date)
            if not df.empty and "Close" in df.columns:
                self.last_source = "yfinance"
                self._write_result_cache(df, market, symbol, start_date, end_date)
                return FetchResponse(
                    symbol=symbol,
                    source=market,
                    records=len(df),
                    start_date=start_date,
                    end_date=end_date,
                    data=df,
                )
        except Exception as exc:
            logger.warning("yfinance failed for %s: %s", symbol, exc)

        # 2. Fallback: Tiingo (only for US equities)
        if market == "us_equity" and self.api_key:
            try:
                df = self._fetch_tiingo(symbol, start_date, end_date)
                if not df.empty and "Close" in df.columns:
                    self.last_source = "tiingo"
                    self._write_result_cache(df, market, symbol, start_date, end_date)
                    return FetchResponse(
                        symbol=symbol,
                        source=market,
                        records=len(df),
                        start_date=start_date,
                        end_date=end_date,
                        data=df,
                    )
            except Exception as exc:
                logger.warning("tiingo failed for %s: %s", symbol, exc)

        # 3. Final fallback: sandbox
        df = self._fetch_sandbox(symbol, start_date, end_date)
        self.last_source = "sandbox"
        return FetchResponse(
            symbol=symbol,
            source=market,
            records=len(df),
            start_date=start_date,
            end_date=end_date,
            data=df,
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

    def fetch_equity_batch(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch multiple equity prices with batch download and per-ticker failover."""
        cached_frames: Dict[str, pd.DataFrame] = {}
        missing_tickers: List[str] = []

        for ticker in tickers:
            for market in ("us_equity", "hk_equity"):
                cached = self._read_result_cache(market, ticker, start_date, end_date)
                if cached is not None:
                    cached_frames[ticker] = cached
                    break
            else:
                missing_tickers.append(ticker)

        if not missing_tickers:
            self.last_source = "cache"
            frames = []
            for ticker, df in cached_frames.items():
                sub = df.set_index("Date")[["Close"]].rename(columns={"Close": ticker})
                sub.index = pd.to_datetime(sub.index).tz_localize(None).normalize()
                frames.append(sub)
            combined = pd.concat(frames, axis=1)
            combined.columns = pd.MultiIndex.from_product([["Close"], combined.columns])
            return combined

        # Track the best source achieved in this batch so fallback does not downgrade it
        batch_best_source = None

        # Attempt a single yfinance batch download to minimize HTTP requests
        if missing_tickers:
            try:
                normalized = [self._normalize_yf_symbol(t) for t in missing_tickers]
                batch_df = yf.download(
                    normalized,
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                    progress=False,
                    auto_adjust=False,
                )
                if not batch_df.empty:
                    for ticker in missing_tickers:
                        norm = self._normalize_yf_symbol(ticker)
                        close_col = ("Close", norm)
                        if close_col not in batch_df.columns:
                            continue
                        close_series = batch_df[close_col].dropna()
                        if close_series.empty:
                            continue
                        df = pd.DataFrame({
                            "Date": pd.to_datetime(close_series.index).tz_localize(None).normalize(),
                            "Close": close_series.values,
                        })
                        market = "hk_equity" if ticker.upper().endswith(".HK") else "us_equity"
                        self._write_result_cache(df, market, ticker, start_date, end_date)
                        cached_frames[ticker] = df
                    batch_best_source = "yfinance"
                    self.last_source = "yfinance"
            except Exception as exc:
                logger.warning("yfinance batch download failed: %s", exc)

        # Fallback: per-ticker smart fetch for any remaining missing tickers
        series_list: List[pd.Series] = []
        for ticker in tickers:
            if ticker in cached_frames:
                df = cached_frames[ticker]
            else:
                market = "hk_equity" if ticker.upper().endswith(".HK") else "us_equity"
                response = self._smart_fetch(ticker, start_date, end_date, market)
                df = response.data

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

        # Restore the best source if a fallback pushed it down to sandbox
        if batch_best_source and batch_best_source != "sandbox" and self.last_source == "sandbox":
            self.last_source = batch_best_source

        aligned = pd.concat([s.to_frame() for s in series_list], axis=1)
        aligned.index = pd.to_datetime(aligned.index).tz_localize(None).normalize()
        aligned.columns = pd.MultiIndex.from_product([["Close"], aligned.columns])
        return aligned

    def fetch_china_equity(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> FetchResponse:
        """Fetch A-share historical prices via AKShare."""
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_str,
            end_date=end_str,
            adjust="qfq",
        )
        if df.empty:
            raise DataFetcherError(
                message="empty dataframe returned from AKShare",
                symbol=symbol,
                source="china_equity",
            )

        self.last_source = "akshare"
        return FetchResponse(
            symbol=symbol,
            source="china_equity",
            records=len(df),
            start_date=start_date,
            end_date=end_date,
            data=df,
        )

    def fetch_china_macro(
        self,
        indicator: str,
        start_date: date,
        end_date: date,
    ) -> FetchResponse:
        """Fetch China macroeconomic indicators via AKShare."""
        fetch_fn = self._macro_registry.get(indicator)
        if fetch_fn is None:
            raise DataFetcherError(
                message=f"unsupported macro indicator: {indicator}",
                symbol=indicator,
                source="china_macro",
            )

        df = fetch_fn()

        date_col = None
        for candidate in ("日期", "datetime", "time", "publish_date"):
            if candidate in df.columns:
                date_col = candidate
                break

        if date_col is None:
            return FetchResponse(
                symbol=indicator,
                source="china_macro",
                records=len(df),
                start_date=start_date,
                end_date=end_date,
                data=df,
            )

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        mask = (
            df[date_col] >= pd.Timestamp(start_date)
        ) & (df[date_col] <= pd.Timestamp(end_date))
        df = df.loc[mask].copy()

        self.last_source = "akshare"
        return FetchResponse(
            symbol=indicator,
            source="china_macro",
            records=len(df),
            start_date=start_date,
            end_date=end_date,
            data=df,
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
