"""Market-calendar-aware time series alignment with strict inner join."""

from datetime import date
from typing import List, Literal

import pandas as pd
import pandas_market_calendars as mcal
from pydantic import BaseModel, Field, field_validator

from data_pipeline.exceptions import AlignmentError


class AlignmentRequest(BaseModel):
    """Request to align two time series on common trading days."""

    left: pd.Series = Field(...)
    right: pd.Series = Field(...)
    left_market: Literal["NYSE", "HKEX", "SSE"]
    right_market: Literal["NYSE", "HKEX", "SSE"]

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("left", "right")
    @classmethod
    def validate_series(cls, series: pd.Series) -> pd.Series:
        if not isinstance(series.index, pd.DatetimeIndex):
            raise ValueError("input must have a DatetimeIndex")
        if series.empty:
            raise ValueError("input series must not be empty")
        return series


class AlignmentResponse(BaseModel):
    """Result of aligning two time series."""

    left_aligned: pd.Series
    right_aligned: pd.Series
    common_days: List[str]
    dropped_days_left: int
    dropped_days_right: int

    model_config = {"arbitrary_types_allowed": True}


class MarketAligner:
    """Align financial time series using official exchange calendars."""

    def __init__(self) -> None:
        self._supported_markets = {"NYSE", "HKEX", "SSE"}

    def _normalize_index(self, series: pd.Series) -> pd.Series:
        """Strip timezone and truncate to date-level precision."""
        series = series.copy()
        idx = series.index
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        idx = idx.normalize()
        series.index = idx
        return series

    def _get_trading_days(
        self,
        market: str,
        start_date: date,
        end_date: date,
    ) -> pd.DatetimeIndex:
        """Retrieve valid trading days for a given market."""
        if market not in self._supported_markets:
            raise AlignmentError(
                message=f"unsupported market: {market}",
                market=market,
            )
        calendar = mcal.get_calendar(market)
        trading_days = calendar.valid_days(start_date=start_date, end_date=end_date)
        return trading_days.tz_localize(None)

    def align_pair(self, request: AlignmentRequest) -> AlignmentResponse:
        """Align two series on the intersection of their market trading calendars."""
        left = self._normalize_index(request.left)
        right = self._normalize_index(request.right)

        left_start = left.index.min().date()
        left_end = left.index.max().date()
        right_start = right.index.min().date()
        right_end = right.index.max().date()

        left_trading_days = self._get_trading_days(
            request.left_market, left_start, left_end
        )
        right_trading_days = self._get_trading_days(
            request.right_market, right_start, right_end
        )

        left_valid = left.index.intersection(left_trading_days)
        right_valid = right.index.intersection(right_trading_days)
        common_days = left_valid.intersection(right_valid)

        if len(common_days) == 0:
            raise AlignmentError(
                message="no overlapping trading days between the two markets",
                market=f"{request.left_market} vs {request.right_market}",
            )

        left_aligned = left.loc[common_days]
        right_aligned = right.loc[common_days]

        if left_aligned.isna().any():
            left_aligned = left_aligned.ffill().bfill()
        if right_aligned.isna().any():
            right_aligned = right_aligned.ffill().bfill()

        if left_aligned.isna().any() or right_aligned.isna().any():
            raise AlignmentError(
                message="NaN values detected after alignment; data source may be incomplete",
                market=f"{request.left_market} vs {request.right_market}",
            )

        return AlignmentResponse(
            left_aligned=left_aligned,
            right_aligned=right_aligned,
            common_days=common_days.strftime("%Y-%m-%d").tolist(),
            dropped_days_left=len(left) - len(left_aligned),
            dropped_days_right=len(right) - len(right_aligned),
        )

    def align_multiple(
        self,
        series_list: List[pd.Series],
        markets: List[str],
    ) -> pd.DataFrame:
        """Align multiple series on the common trading days across all markets."""
        if len(series_list) != len(markets):
            raise AlignmentError(
                message="series_list and markets must have the same length",
            )
        if len(series_list) == 0:
            raise AlignmentError(message="empty input: series_list is empty")

        all_valid_days: List[pd.DatetimeIndex] = []
        for series, market in zip(series_list, markets):
            series = self._normalize_index(series)
            series_start = series.index.min().date()
            series_end = series.index.max().date()
            trading_days = self._get_trading_days(market, series_start, series_end)
            valid_days = series.index.intersection(trading_days)
            if len(valid_days) == 0:
                raise AlignmentError(
                    message=f"no valid trading days for {market} after filtering",
                    market=market,
                )
            all_valid_days.append(valid_days)

        common_days = all_valid_days[0]
        for vd in all_valid_days[1:]:
            common_days = common_days.intersection(vd)

        if len(common_days) == 0:
            raise AlignmentError(
                message="no common trading days across all markets",
            )

        aligned_frames: List[pd.DataFrame] = []
        for series in series_list:
            series = self._normalize_index(series)
            aligned = series.loc[common_days]
            if aligned.isna().any():
                aligned = aligned.ffill().bfill()
            if aligned.isna().any():
                raise AlignmentError(
                    message="NaN values detected in final multi-market alignment",
                )
            aligned_frames.append(aligned.to_frame())

        result = pd.concat(aligned_frames, axis=1)

        if result.isna().any().any():
            raise AlignmentError(
                message="NaN values detected in final multi-market alignment",
            )

        return result
