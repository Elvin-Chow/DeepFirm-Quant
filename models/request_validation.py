"""Shared request validation helpers for portfolio analysis contracts."""

import math
from typing import Iterable, Sequence

from models.market_validation import MarketMode, validate_market_tickers


def normalize_tickers(tickers: Iterable[str]) -> list[str]:
    """Return stripped ticker symbols and reject empty or duplicated inputs."""
    ticker_list = [str(ticker).strip() for ticker in tickers]
    ticker_list = [ticker for ticker in ticker_list if ticker]
    if not ticker_list:
        raise ValueError("at least one ticker is required")

    seen: set[str] = set()
    duplicates: list[str] = []
    for ticker in ticker_list:
        key = ticker.upper()
        if key in seen and ticker not in duplicates:
            duplicates.append(ticker)
        seen.add(key)
    if duplicates:
        raise ValueError("duplicate tickers are not allowed: " + ", ".join(duplicates))
    return ticker_list


def validate_common_portfolio_contract(
    tickers: Sequence[str],
    market: MarketMode,
    weights: Sequence[float] | None = None,
) -> None:
    """Validate shared market and weight constraints for API request models."""
    validate_market_tickers(tickers, market)
    if weights is None or len(weights) == 0:
        return
    if len(weights) != len(tickers):
        raise ValueError("weights length must match tickers length")

    clean_weights = []
    for weight in weights:
        value = float(weight)
        if not math.isfinite(value):
            raise ValueError("weights must contain only finite values")
        if value < 0.0:
            raise ValueError("weights must be non-negative")
        clean_weights.append(value)
    if sum(clean_weights) <= 1e-12:
        raise ValueError("weights must sum to a positive value")


def validate_view_assets(tickers: Sequence[str], views: Sequence[object]) -> None:
    """Validate Black-Litterman view assets against the submitted ticker universe."""
    ticker_set = {ticker.upper() for ticker in tickers}
    unknown: list[str] = []
    for view in views:
        for asset in getattr(view, "assets", []) or []:
            if str(asset).upper() not in ticker_set and asset not in unknown:
                unknown.append(str(asset))
        for asset in getattr(view, "relative_assets", []) or []:
            if str(asset).upper() not in ticker_set and asset not in unknown:
                unknown.append(str(asset))
    if unknown:
        raise ValueError("view assets must exist in tickers: " + ", ".join(unknown))
