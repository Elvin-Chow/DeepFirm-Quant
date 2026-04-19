"""Shared exceptions for the data pipeline modules."""

from typing import Optional


class DataFetcherError(Exception):
    """Raised when a data fetch operation fails after all retries are exhausted."""

    def __init__(
        self,
        message: str,
        symbol: str,
        source: str,
        last_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.symbol = symbol
        self.source = source
        self.last_exception = last_exception


class AlignmentError(Exception):
    """Raised when market calendar alignment cannot be performed cleanly."""

    def __init__(
        self,
        message: str,
        market: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.market = market
