"""Fama-French factor attribution engine."""

import io
import os
import time
import warnings
import zipfile
from datetime import date
from typing import Literal, Optional

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
from pydantic import BaseModel, Field

from data_pipeline.exceptions import DataFetcherError
from data_pipeline.provenance import DataQuality


class FactorRegressionResult(BaseModel):
    """Output of a Fama-French factor OLS regression."""

    alpha: float = Field(..., description="intercept (daily excess return)")
    beta_mkt: float
    beta_smb: float
    beta_hml: float
    beta_rmw: float = 0.0
    beta_cma: float = 0.0
    t_stat_alpha: float
    t_stat_mkt: float
    t_stat_smb: float
    t_stat_hml: float
    t_stat_rmw: float = 0.0
    t_stat_cma: float = 0.0
    p_value_alpha: float
    p_value_mkt: float
    p_value_smb: float
    p_value_hml: float
    p_value_rmw: float = 1.0
    p_value_cma: float = 1.0
    r_squared: float
    adj_r_squared: float
    n_observations: int
    source: str = Field(default="unknown", description="Data source used for prices")
    source_detail: str = Field(default="unknown", description="Detailed price data provenance")
    data_warnings: list[str] = Field(default_factory=list, description="Non-fatal data quality warnings")
    data_quality: DataQuality = Field(default_factory=DataQuality, description="Unified data quality provenance")
    factor_source: str = Field(default="unknown", description="Data source used for factors")
    factor_is_synthetic: bool = Field(default=False, description="Whether factor data is synthetic")
    alpha_status: Literal["available", "truncated"] = Field(default="available")
    alpha_sample_quality: Literal["standard", "low"] = Field(default="standard")
    factor_available_through: str = Field(default="")
    alpha_effective_start: str = Field(default="")
    alpha_effective_end: str = Field(default="")


class FactorAnalyzer:
    """Fetch Fama-French factors and run portfolio attribution regressions."""

    _KF_URL = (
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
        "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
    )
    _FACTOR_COLUMNS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
    _REQUIRED_COLUMNS = [*_FACTOR_COLUMNS, "RF"]
    _MIN_REGRESSION_OBSERVATIONS = 60
    _LOW_SAMPLE_OBSERVATIONS = 252

    def __init__(
        self,
        cache_path: Optional[str] = "cache/kf_french_factors.parquet",
        request_timeout: Optional[float] = None,
        request_attempts: int = 2,
    ) -> None:
        self._factor_cache: Optional[pd.DataFrame] = None
        env_cache_path = os.getenv("DFQ_FACTOR_CACHE_PATH")
        self._factor_cache_path = env_cache_path if env_cache_path is not None else cache_path
        self._request_timeout = (
            request_timeout
            if request_timeout is not None
            else float(os.getenv("DFQ_FACTOR_TIMEOUT_SECONDS", "8"))
        )
        self._request_attempts = max(
            1,
            int(os.getenv("DFQ_FACTOR_ATTEMPTS", str(request_attempts))),
        )
        self._disk_cache_enabled = (
            bool(self._factor_cache_path)
            and os.getenv("DFQ_DISABLE_CACHE", "").lower()
            not in {"1", "true", "yes", "on"}
        )

    @staticmethod
    def _mark_factor_source(
        factors_df: pd.DataFrame,
        factor_source: str,
        factor_is_synthetic: bool,
        requested_start: Optional[date] = None,
        requested_end: Optional[date] = None,
        factor_available_through: Optional[pd.Timestamp] = None,
        alpha_status: str = "available",
    ) -> pd.DataFrame:
        """Attach factor provenance metadata to a DataFrame."""
        factors_df.attrs["factor_source"] = factor_source
        factors_df.attrs["factor_is_synthetic"] = factor_is_synthetic
        if requested_start is not None:
            factors_df.attrs["requested_start"] = requested_start.isoformat()
        if requested_end is not None:
            factors_df.attrs["requested_end"] = requested_end.isoformat()
        if factor_available_through is not None:
            factors_df.attrs["factor_available_through"] = pd.Timestamp(
                factor_available_through
            ).strftime("%Y-%m-%d")
        if not factors_df.empty:
            factors_df.attrs["alpha_effective_start"] = pd.Timestamp(
                factors_df.index.min()
            ).strftime("%Y-%m-%d")
            factors_df.attrs["alpha_effective_end"] = pd.Timestamp(
                factors_df.index.max()
            ).strftime("%Y-%m-%d")
        factors_df.attrs["alpha_status"] = alpha_status
        return factors_df

    @staticmethod
    def _synthetic_factors_enabled() -> bool:
        """Return whether explicit test-mode synthetic factors are enabled."""
        return os.getenv("DFQ_ALLOW_SYNTHETIC_FACTORS", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _factor_unavailable(
        self,
        message: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Raise for unavailable real factors unless test-mode fallback is enabled."""
        if self._synthetic_factors_enabled():
            warnings.warn(f"{message}; using synthetic factors because test mode is enabled")
            return self._generate_synthetic_factors(start_date, end_date)
        raise DataFetcherError(
            message=message,
            symbol="fama_french_factors",
            source="kenneth_french",
        )

    def _generate_synthetic_factors(
        self,
        start_date: date,
        end_date: date,
        random_seed: int = 42,
    ) -> pd.DataFrame:
        """Generate synthetic daily factors for testing when network fails."""
        rng = np.random.default_rng(random_seed)
        trading_days = pd.date_range(start_date, end_date, freq="B")

        mkt_rf = rng.normal(0.0003, 0.01, len(trading_days))
        smb = rng.normal(0.0001, 0.008, len(trading_days))
        hml = rng.normal(0.0001, 0.008, len(trading_days))
        rmw = rng.normal(0.0001, 0.006, len(trading_days))
        cma = rng.normal(0.0001, 0.006, len(trading_days))
        rf = rng.normal(0.0001, 0.0001, len(trading_days))
        rf = np.clip(rf, 0.0, None)

        df = pd.DataFrame(
            {
                "Mkt-RF": mkt_rf,
                "SMB": smb,
                "HML": hml,
                "RMW": rmw,
                "CMA": cma,
                "RF": rf,
            },
            index=pd.DatetimeIndex(trading_days, name="Date"),
        )
        return self._mark_factor_source(df, "synthetic", True)

    def _slice_factor_cache(
        self,
        factors_df: pd.DataFrame,
        start_date: date,
        end_date: date,
        allow_truncated: bool = True,
    ) -> Optional[pd.DataFrame]:
        """Return real factor rows, truncating the requested end date when needed."""
        if factors_df.empty:
            return None
        df = factors_df.copy()
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df[~df.index.isna()].sort_index()
        if any(col not in df.columns for col in self._REQUIRED_COLUMNS):
            return None

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        sliced = df.loc[(df.index >= start_ts) & (df.index <= end_ts)].copy()
        if sliced.empty:
            return None

        business_days = pd.date_range(start_date, end_date, freq="B")
        expected_start = pd.Timestamp(business_days.min()) if len(business_days) else start_ts
        expected_end = pd.Timestamp(business_days.max()) if len(business_days) else end_ts
        covers_start = pd.Timestamp(sliced.index.min()) <= expected_start + pd.Timedelta(days=7)
        covers_end = pd.Timestamp(sliced.index.max()) >= expected_end - pd.Timedelta(days=7)
        if not covers_start:
            return None
        if not covers_end and not allow_truncated:
            return None
        factor_available_through = pd.Timestamp(df.index.max())
        return self._mark_factor_source(
            sliced,
            "kenneth_french",
            False,
            requested_start=start_date,
            requested_end=end_date,
            factor_available_through=factor_available_through,
            alpha_status="available" if covers_end else "truncated",
        )

    def _read_disk_factor_cache(
        self,
        start_date: date,
        end_date: date,
        allow_truncated: bool = True,
    ) -> Optional[pd.DataFrame]:
        """Read cached Kenneth French factors from disk when available."""
        if not self._disk_cache_enabled or self._factor_cache_path is None:
            return None
        if not os.path.exists(self._factor_cache_path):
            return None
        try:
            cached = pd.read_parquet(self._factor_cache_path)
            if "Date" in cached.columns:
                cached["Date"] = pd.to_datetime(cached["Date"], errors="coerce")
                cached = cached.dropna(subset=["Date"]).set_index("Date")
            self._factor_cache = cached.copy()
            return self._slice_factor_cache(
                cached,
                start_date,
                end_date,
                allow_truncated=allow_truncated,
            )
        except Exception as exc:
            warnings.warn(f"failed to read cached Kenneth French factors ({exc})")
            return None

    def _write_disk_factor_cache(self, factors_df: pd.DataFrame) -> None:
        """Persist parsed Kenneth French factors for future runs."""
        if not self._disk_cache_enabled or self._factor_cache_path is None:
            return
        try:
            cache_dir = os.path.dirname(self._factor_cache_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            output = factors_df.copy()
            output.index = pd.to_datetime(output.index)
            output.index.name = "Date"
            output.reset_index().to_parquet(self._factor_cache_path, index=False)
        except Exception as exc:
            warnings.warn(f"failed to write cached Kenneth French factors ({exc})")

    def _parse_kf_response(self, content: bytes, start_date: date, end_date: date) -> pd.DataFrame:
        """Parse the Kenneth French daily five-factor zip payload."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                with zf.open(csv_name) as f:
                    raw_lines = [line.decode("utf-8") for line in f.readlines()]
        except Exception as exc:
            return self._factor_unavailable(
                f"failed to extract Kenneth French CSV ({exc})",
                start_date,
                end_date,
            )

        header_line = None
        for i, line in enumerate(raw_lines):
            stripped = line.strip()
            if "Mkt-RF" in stripped and "SMB" in stripped and "HML" in stripped:
                header_line = i
                break

        if header_line is None:
            return self._factor_unavailable(
                "could not locate Kenneth French CSV header",
                start_date,
                end_date,
            )

        footer_lines = 0
        for line in reversed(raw_lines):
            if line.strip() == "" or "Copyright" in line or "Disclaimer" in line:
                footer_lines += 1
            else:
                break

        data_lines = raw_lines[header_line : len(raw_lines) - footer_lines or None]
        df = pd.read_csv(io.StringIO("".join(data_lines)))
        df.columns = df.columns.str.strip()

        date_col = "Date"
        if date_col not in df.columns:
            for col in df.columns:
                if col.lower().startswith("unnamed"):
                    date_col = col
                    break

        df = df.rename(columns={date_col: "Date"})
        df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["Date"]).set_index("Date")

        missing_cols = [col for col in self._REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            return self._factor_unavailable(
                "Kenneth French factor file is missing required columns",
                start_date,
                end_date,
            )

        for col in self._REQUIRED_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0

        df = df[self._REQUIRED_COLUMNS]
        df = self._mark_factor_source(df, "kenneth_french", False)
        self._factor_cache = df.copy()
        self._write_disk_factor_cache(df)
        sliced = self._slice_factor_cache(df, start_date, end_date)
        if sliced is None:
            return self._factor_unavailable(
                "Kenneth French data does not overlap the requested analysis window",
                start_date,
                end_date,
            )
        return sliced

    def fetch_kf_french_factors(
        self,
        start_date: date,
        end_date: date,
        allow_truncated: bool = True,
    ) -> pd.DataFrame:
        """Download or cache Kenneth French daily five-factor data."""
        if self._factor_cache is not None:
            cached = self._slice_factor_cache(
                self._factor_cache,
                start_date,
                end_date,
                allow_truncated=allow_truncated,
            )
            if cached is not None:
                return cached

        disk_cached = self._read_disk_factor_cache(
            start_date,
            end_date,
            allow_truncated=allow_truncated,
        )
        if disk_cached is not None:
            return disk_cached

        last_exc: Optional[Exception] = None
        for attempt in range(self._request_attempts):
            try:
                response = requests.get(self._KF_URL, timeout=self._request_timeout)
                response.raise_for_status()
                break
            except Exception as exc:
                last_exc = exc
                if attempt < self._request_attempts - 1:
                    time.sleep(2 ** attempt)
        else:
            disk_cached = self._read_disk_factor_cache(
                start_date,
                end_date,
                allow_truncated=allow_truncated,
            )
            if disk_cached is not None:
                return disk_cached
            return self._factor_unavailable(
                f"failed to fetch Kenneth French data after {self._request_attempts} attempts ({last_exc})",
                start_date,
                end_date,
            )
        return self._parse_kf_response(response.content, start_date, end_date)

    def regress_portfolio(
        self,
        portfolio_returns: pd.Series,
        factors_df: pd.DataFrame,
    ) -> FactorRegressionResult:
        """Run OLS regression of portfolio excess returns on Fama-French factors."""
        portfolio_returns = portfolio_returns.copy()
        portfolio_returns.index = pd.to_datetime(portfolio_returns.index)
        factors_df = factors_df.copy()

        common_dates = portfolio_returns.index.intersection(factors_df.index)
        if len(common_dates) < self._MIN_REGRESSION_OBSERVATIONS:
            raise DataFetcherError(
                message=(
                    "insufficient overlapping dates between portfolio returns and real factors; "
                    f"required at least {self._MIN_REGRESSION_OBSERVATIONS}, got {len(common_dates)}"
                ),
                symbol="portfolio",
                source="factor_models",
            )

        pf = portfolio_returns.loc[common_dates]
        fac = factors_df.loc[common_dates]
        for col in self._REQUIRED_COLUMNS:
            if col not in fac.columns:
                fac[col] = 0.0
        excess_returns = pf - fac["RF"]

        X = fac[self._FACTOR_COLUMNS].reset_index(drop=True)
        X = sm.add_constant(X)
        y = excess_returns.reset_index(drop=True)

        model = sm.OLS(y, X).fit()
        params = model.params
        tvalues = model.tvalues
        pvalues = model.pvalues

        factor_source = str(factors_df.attrs.get("factor_source", "unknown"))
        factor_is_synthetic = bool(factors_df.attrs.get("factor_is_synthetic", False))
        factor_available_through = str(
            factors_df.attrs.get(
                "factor_available_through",
                pd.Timestamp(factors_df.index.max()).strftime("%Y-%m-%d"),
            )
        )
        requested_end = str(factors_df.attrs.get("requested_end", ""))
        alpha_effective_start = pd.Timestamp(common_dates.min()).strftime("%Y-%m-%d")
        alpha_effective_end = pd.Timestamp(common_dates.max()).strftime("%Y-%m-%d")
        raw_status = str(factors_df.attrs.get("alpha_status", "available"))
        alpha_status = (
            "truncated"
            if raw_status == "truncated" or (requested_end and alpha_effective_end < requested_end)
            else "available"
        )
        alpha_sample_quality = (
            "low"
            if len(common_dates) < self._LOW_SAMPLE_OBSERVATIONS
            else "standard"
        )
        data_warnings: list[str] = []
        if alpha_status == "truncated":
            data_warnings.append(
                f"Factor data is available through {factor_available_through}; alpha attribution was truncated to real factor coverage."
            )
        if alpha_sample_quality == "low":
            data_warnings.append(
                f"Alpha attribution uses {len(common_dates)} observations; interpret coefficients cautiously."
            )

        return FactorRegressionResult(
            alpha=params.get("const", 0.0),
            beta_mkt=params.get("Mkt-RF", 0.0),
            beta_smb=params.get("SMB", 0.0),
            beta_hml=params.get("HML", 0.0),
            beta_rmw=params.get("RMW", 0.0),
            beta_cma=params.get("CMA", 0.0),
            t_stat_alpha=tvalues.get("const", 0.0),
            t_stat_mkt=tvalues.get("Mkt-RF", 0.0),
            t_stat_smb=tvalues.get("SMB", 0.0),
            t_stat_hml=tvalues.get("HML", 0.0),
            t_stat_rmw=tvalues.get("RMW", 0.0),
            t_stat_cma=tvalues.get("CMA", 0.0),
            p_value_alpha=pvalues.get("const", 1.0),
            p_value_mkt=pvalues.get("Mkt-RF", 1.0),
            p_value_smb=pvalues.get("SMB", 1.0),
            p_value_hml=pvalues.get("HML", 1.0),
            p_value_rmw=pvalues.get("RMW", 1.0),
            p_value_cma=pvalues.get("CMA", 1.0),
            r_squared=model.rsquared,
            adj_r_squared=model.rsquared_adj,
            n_observations=int(model.nobs),
            data_warnings=data_warnings,
            factor_source=factor_source,
            factor_is_synthetic=factor_is_synthetic,
            alpha_status=alpha_status,
            alpha_sample_quality=alpha_sample_quality,
            factor_available_through=factor_available_through,
            alpha_effective_start=alpha_effective_start,
            alpha_effective_end=alpha_effective_end,
        )
