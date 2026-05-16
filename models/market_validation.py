"""Market input validation helpers."""

from typing import Iterable, Literal

MarketMode = Literal["us", "hk", "cn", "jp", "tw"]


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


def is_jp_ticker(ticker: str) -> bool:
    """Return whether a ticker uses the Japan exchange suffix."""
    return str(ticker).strip().upper().endswith(".T")


def is_tw_ticker(ticker: str) -> bool:
    """Return whether a ticker uses a supported Taiwan exchange suffix."""
    normalized = str(ticker).strip().upper()
    return normalized.endswith(".TW") or normalized.endswith(".TWO")


def validate_market_tickers(tickers: Iterable[str], market: MarketMode) -> None:
    """Validate ticker suffixes against the selected market mode."""
    ticker_list = [str(ticker).strip() for ticker in tickers if str(ticker).strip()]

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
        jp_tickers = [ticker for ticker in ticker_list if is_jp_ticker(ticker)]
        if jp_tickers:
            raise ValueError(
                "US market mode does not accept Japan tickers: "
                + ", ".join(jp_tickers)
            )
        tw_tickers = [ticker for ticker in ticker_list if is_tw_ticker(ticker)]
        if tw_tickers:
            raise ValueError(
                "US market mode does not accept Taiwan tickers: "
                + ", ".join(tw_tickers)
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

    if market == "jp":
        non_jp_tickers = [ticker for ticker in ticker_list if not is_jp_ticker(ticker)]
        if non_jp_tickers:
            raise ValueError(
                "Japan market mode only accepts .T tickers: "
                + ", ".join(non_jp_tickers)
            )
        return

    if market == "tw":
        non_tw_tickers = [ticker for ticker in ticker_list if not is_tw_ticker(ticker)]
        if non_tw_tickers:
            raise ValueError(
                "Taiwan market mode only accepts .TW or .TWO tickers: "
                + ", ".join(non_tw_tickers)
            )
        return

    non_hk_tickers = [ticker for ticker in ticker_list if not is_hk_ticker(ticker)]
    if non_hk_tickers:
        raise ValueError(
            "HK market mode only accepts .HK tickers: "
            + ", ".join(non_hk_tickers)
        )
