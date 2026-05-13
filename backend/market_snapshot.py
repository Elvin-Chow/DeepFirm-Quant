"""Landing-page market snapshot orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import math
from typing import Dict, Iterable, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from backend.schemas import MarketSnapshotIndex, MarketSnapshotResult, MarketSessionStatus
from data_pipeline import SmartFetcher
from models.market_validation import MarketMode


@dataclass(frozen=True)
class IndexConfig:
    symbol: str
    name: str
    name_zh: str
    name_tc: str


INDEX_CONFIGS: Dict[MarketMode, Tuple[IndexConfig, ...]] = {
    "us": (
        IndexConfig("^GSPC", "S&P 500", "标普 500", "標普 500"),
        IndexConfig("^IXIC", "Nasdaq Composite", "纳斯达克综合指数", "納斯達克綜合指數"),
        IndexConfig("^DJI", "Dow Jones Industrial Average", "道琼斯工业平均指数", "道瓊斯工業平均指數"),
    ),
    "hk": (
        IndexConfig("^HSI", "Hang Seng Index", "恒生指数", "恆生指數"),
        IndexConfig("HSTECH.HK", "Hang Seng TECH Index", "恒生科技指数", "恆生科技指數"),
        IndexConfig("^HSCE", "Hang Seng China Enterprises Index", "国企指数", "國企指數"),
    ),
    "cn": (
        IndexConfig("000001.SS", "Shanghai Composite", "上证指数", "上證指數"),
        IndexConfig("399001.SZ", "Shenzhen Component", "深证成指", "深證成指"),
        IndexConfig("000300.SS", "CSI 300", "沪深 300", "滬深 300"),
    ),
    "mixed": (
        IndexConfig("^GSPC", "S&P 500", "标普 500", "標普 500"),
        IndexConfig("^IXIC", "Nasdaq Composite", "纳斯达克综合指数", "納斯達克綜合指數"),
        IndexConfig("^HSI", "Hang Seng Index", "恒生指数", "恆生指數"),
        IndexConfig("HSTECH.HK", "Hang Seng TECH Index", "恒生科技指数", "恆生科技指數"),
    ),
}

SESSION_WINDOWS: Dict[str, Tuple[str, Tuple[Tuple[time, time], ...]]] = {
    "us": ("America/New_York", ((time(9, 30), time(16, 0)),)),
    "hk": ("Asia/Hong_Kong", ((time(9, 30), time(12, 0)), (time(13, 0), time(16, 0)))),
    "cn": ("Asia/Shanghai", ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0)))),
}


def _round_optional(value: float | None, digits: int = 4) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _utc_stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _regular_session_status(
    market: str,
    now_utc: datetime,
) -> tuple[MarketSessionStatus, str, str]:
    timezone_name, windows = SESSION_WINDOWS[market]
    local_now = now_utc.astimezone(ZoneInfo(timezone_name))
    local_clock = local_now.time()

    if local_now.weekday() >= 5:
        return "closed", timezone_name, local_now.isoformat(timespec="minutes")

    for start, end in windows:
        if start <= local_clock < end:
            return "open", timezone_name, local_now.isoformat(timespec="minutes")

    if len(windows) > 1 and windows[0][1] <= local_clock < windows[-1][0]:
        return "lunch_break", timezone_name, local_now.isoformat(timespec="minutes")

    return "closed", timezone_name, local_now.isoformat(timespec="minutes")


def _mixed_session_status(now_utc: datetime) -> tuple[MarketSessionStatus, str, str]:
    hk_status, _, hk_time = _regular_session_status("hk", now_utc)
    us_status, _, us_time = _regular_session_status("us", now_utc)
    if "open" in {hk_status, us_status}:
        status: MarketSessionStatus = "open"
    elif "lunch_break" in {hk_status, us_status}:
        status = "lunch_break"
    else:
        status = "closed"
    return status, "Asia/Hong_Kong + America/New_York", f"HK {hk_time} / NY {us_time}"


def _session_status(
    market: MarketMode,
    now_utc: datetime,
) -> tuple[MarketSessionStatus, str, str]:
    if market == "mixed":
        return _mixed_session_status(now_utc)
    return _regular_session_status(market, now_utc)


def _normalize_quote_frame(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=["Date", "Close"])

    frame = data.copy()
    if "Date" not in frame.columns:
        frame = frame.reset_index()
        if "Date" not in frame.columns:
            frame = frame.rename(columns={frame.columns[0]: "Date"})

    if "Close" not in frame.columns and "Adj Close" in frame.columns:
        frame["Close"] = frame["Adj Close"]
    if "Close" not in frame.columns:
        return pd.DataFrame(columns=["Date", "Close"])

    normalized = frame[["Date", "Close"]].copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce")
    normalized["Close"] = pd.to_numeric(normalized["Close"], errors="coerce")
    normalized = normalized.dropna(subset=["Date", "Close"])
    normalized = normalized.sort_values("Date")
    normalized = normalized.drop_duplicates(subset=["Date"], keep="last")
    return normalized.reset_index(drop=True)


def _build_unavailable_index(config: IndexConfig, warning: str) -> MarketSnapshotIndex:
    return MarketSnapshotIndex(
        symbol=config.symbol,
        name=config.name,
        name_zh=config.name_zh,
        name_tc=config.name_tc,
        status="unavailable",
        source="unavailable",
        source_detail="unavailable",
        warning=warning,
    )


def _fetch_yahoo_chart_meta(
    config: IndexConfig,
    fetcher: SmartFetcher,
    start_date,
    end_date,
) -> dict:
    session = getattr(fetcher, "_session", requests.Session())
    normalize_symbol = getattr(fetcher, "_normalize_yf_symbol", lambda symbol: symbol)
    yf_symbol = normalize_symbol(config.symbol)
    params = {
        "period1": SmartFetcher._unix_timestamp(start_date),
        "period2": SmartFetcher._unix_timestamp(end_date, end_of_day=True),
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

    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{yf_symbol}"
        try:
            response = session.get(url, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            payload = response.json()
            results = payload.get("chart", {}).get("result") or []
            if not results:
                continue
            meta = results[0].get("meta") or {}
            if meta:
                return meta
        except Exception as exc:
            SmartFetcher._register_yahoo_chart_failure(exc)
            continue
    return {}


def _meta_number(meta: dict, key: str) -> float | None:
    value = meta.get(key)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _meta_previous_price(meta: dict) -> float | None:
    for key in ("regularMarketPreviousClose", "previousClose", "chartPreviousClose"):
        value = _meta_number(meta, key)
        if value is not None:
            return value
    return None


def _meta_quote_time(meta: dict) -> str | None:
    value = _meta_number(meta, "regularMarketTime")
    if value is None:
        return None
    try:
        timestamp = datetime.fromtimestamp(value, timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None

    timezone_name = meta.get("exchangeTimezoneName")
    if isinstance(timezone_name, str) and timezone_name:
        try:
            timestamp = timestamp.astimezone(ZoneInfo(timezone_name))
        except Exception:
            timestamp = timestamp.astimezone(timezone.utc)
    return timestamp.strftime("%Y-%m-%d %H:%M")


def _build_index_snapshot(
    config: IndexConfig,
    fetcher: SmartFetcher,
    start_date,
    end_date,
    force_refresh: bool = False,
) -> MarketSnapshotIndex:
    try:
        response = fetcher.fetch_us_equity(config.symbol, start_date, end_date)
        frame = _normalize_quote_frame(response.data)
        if frame.empty:
            return _build_unavailable_index(config, "No usable close prices returned.")

        latest = frame.iloc[-1]
        latest_price = float(latest["Close"])
        previous_price = None
        quote_time = None
        meta: dict = {}
        if len(frame) >= 2:
            previous_price = float(frame.iloc[-2]["Close"])
        if force_refresh or len(frame) < 2:
            meta = _fetch_yahoo_chart_meta(config, fetcher, start_date, end_date)
            meta_price = _meta_number(meta, "regularMarketPrice")
            meta_previous = _meta_previous_price(meta)
            if meta_price is not None:
                latest_price = meta_price
            if previous_price is None and meta_previous is not None:
                previous_price = meta_previous
            quote_time = _meta_quote_time(meta)

        change = None
        change_percent = None
        if previous_price is not None and math.isfinite(previous_price) and previous_price > 0.0:
            if change is None:
                change = latest_price - previous_price
            if change_percent is None:
                change_percent = change / previous_price * 100.0

        source = getattr(fetcher, "last_source", "unknown")
        source_detail = getattr(fetcher, "last_source_detail", "unknown")
        if force_refresh and meta:
            source = "yahoo_chart"
            source_detail = "Yahoo Finance chart metadata"

        return MarketSnapshotIndex(
            symbol=config.symbol,
            name=config.name,
            name_zh=config.name_zh,
            name_tc=config.name_tc,
            price=_round_optional(latest_price, 2),
            change=_round_optional(change, 2),
            change_percent=_round_optional(change_percent, 2),
            asof_date=quote_time or pd.Timestamp(latest["Date"]).strftime("%Y-%m-%d"),
            source=source,
            source_detail=source_detail,
            status="ok",
        )
    except Exception as exc:
        return _build_unavailable_index(config, str(exc))


def _source_summary(indices: Iterable[MarketSnapshotIndex]) -> tuple[str, str]:
    sources = [(item.source, item.source_detail) for item in indices if item.source]
    available_sources = [source for source in sources if source[0] != "unavailable"]
    if not available_sources:
        return "unavailable", "unavailable"
    unique_sources = sorted({source for source, _ in available_sources})
    unique_details = sorted({detail for _, detail in available_sources if detail})
    source = unique_sources[0] if len(unique_sources) == 1 else "mixed"
    detail = unique_details[0] if len(unique_details) == 1 else "mixed providers"
    return source, detail


def build_market_snapshot(
    market: MarketMode,
    fetcher: SmartFetcher,
    now_utc: datetime | None = None,
    force_refresh: bool = False,
) -> MarketSnapshotResult:
    current_utc = now_utc or datetime.now(timezone.utc)
    current_utc = current_utc.astimezone(timezone.utc)
    end_date = current_utc.date()
    start_date = end_date - timedelta(days=14)
    session_status, timezone_name, local_time = _session_status(market, current_utc)

    indices = [
        _build_index_snapshot(config, fetcher, start_date, end_date, force_refresh=force_refresh)
        for config in INDEX_CONFIGS[market]
    ]
    source, source_detail = _source_summary(indices)
    warnings = list(dict.fromkeys(getattr(fetcher, "data_warnings", [])))

    return MarketSnapshotResult(
        market=market,
        session_status=session_status,
        timezone=timezone_name,
        local_time=local_time,
        updated_at=_utc_stamp(current_utc),
        indices=indices,
        source=source,
        source_detail=source_detail,
        data_warnings=warnings,
    )
