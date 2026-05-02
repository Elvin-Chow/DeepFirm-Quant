"""Market input validation helpers."""

from typing import Iterable, Literal

MarketMode = Literal["us", "hk", "mixed"]


def has_hk_suffix(ticker: str) -> bool:
    """Return whether a ticker uses the Hong Kong suffix."""
    return ticker.upper().endswith(".HK")


def validate_market_tickers(tickers: Iterable[str], market: MarketMode) -> None:
    """Validate ticker suffixes against the selected market mode."""
    ticker_list = [str(ticker).strip() for ticker in tickers if str(ticker).strip()]

    if market == "mixed":
        return

    if market == "us":
        hk_tickers = [ticker for ticker in ticker_list if has_hk_suffix(ticker)]
        if hk_tickers:
            raise ValueError(
                "US market mode does not accept HK tickers: "
                + ", ".join(hk_tickers)
            )
        return

    non_hk_tickers = [ticker for ticker in ticker_list if not has_hk_suffix(ticker)]
    if non_hk_tickers:
        raise ValueError(
            "HK market mode only accepts .HK tickers: "
            + ", ".join(non_hk_tickers)
        )
