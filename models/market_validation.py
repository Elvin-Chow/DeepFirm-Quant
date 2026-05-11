"""Market input validation helpers."""

from typing import Iterable, Literal

MarketMode = Literal["us", "hk", "cn", "mixed"]


def is_hk_ticker(ticker: str) -> bool:
    """Return whether a ticker uses the Hong Kong suffix."""
    return str(ticker).strip().upper().endswith(".HK")


def has_hk_suffix(ticker: str) -> bool:
    """Return whether a ticker uses the Hong Kong suffix."""
    return is_hk_ticker(ticker)


def is_cn_ticker(ticker: str) -> bool:
    """Return whether a ticker uses the supported A-share format."""
    clean_ticker = str(ticker).strip()
    return clean_ticker.isdigit() and len(clean_ticker) == 6


def validate_market_tickers(tickers: Iterable[str], market: MarketMode) -> None:
    """Validate ticker suffixes against the selected market mode."""
    ticker_list = [str(ticker).strip() for ticker in tickers if str(ticker).strip()]

    if market == "mixed":
        cn_tickers = [ticker for ticker in ticker_list if is_cn_ticker(ticker)]
        if cn_tickers:
            raise ValueError(
                "Mixed market mode currently supports US and HK tickers only: "
                + ", ".join(cn_tickers)
            )
        return

    if market == "us":
        hk_tickers = [ticker for ticker in ticker_list if is_hk_ticker(ticker)]
        if hk_tickers:
            raise ValueError(
                "US market mode does not accept HK tickers: "
                + ", ".join(hk_tickers)
            )
        cn_tickers = [ticker for ticker in ticker_list if is_cn_ticker(ticker)]
        if cn_tickers:
            raise ValueError(
                "US market mode does not accept A-share tickers: "
                + ", ".join(cn_tickers)
            )
        return

    if market == "cn":
        non_cn_tickers = [ticker for ticker in ticker_list if not is_cn_ticker(ticker)]
        if non_cn_tickers:
            raise ValueError(
                "CN market mode only accepts 6-digit A-share tickers: "
                + ", ".join(non_cn_tickers)
            )
        return

    non_hk_tickers = [ticker for ticker in ticker_list if not is_hk_ticker(ticker)]
    if non_hk_tickers:
        raise ValueError(
            "HK market mode only accepts .HK tickers: "
            + ", ".join(non_hk_tickers)
        )
