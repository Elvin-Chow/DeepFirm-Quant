"""Risk computation engine for log returns and Expected Shortfall."""

from datetime import date
from typing import List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from data_pipeline import AlignmentError, DataFetcherError, MarketAligner, SmartFetcher
from models.market_validation import validate_market_tickers


class RiskEvaluationRequest(BaseModel):
    """Request payload for risk evaluation."""

    tickers: List[str] = Field(..., min_length=1)
    start_date: date
    end_date: date
    confidence_level: float = Field(default=0.99, ge=0.9, le=0.999)
    weights: List[float] = Field(default_factory=list)
    api_key: Optional[str] = Field(default=None, description="Tiingo API key for failover")
    mc_paths: int = Field(default=10_000, ge=1_000, le=50_000, description="Number of Monte Carlo simulation paths")
    capital: float = Field(default=1_000_000, gt=0, description="Total capital in base currency")
    leverage: float = Field(default=1.0, gt=0, description="Overall leverage multiplier")
    market: Literal["us", "hk", "mixed"] = Field(default="us", description="Market mode: us, hk, or mixed")

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, end_date: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        return end_date

    @model_validator(mode="after")
    def validate_market_contract(self) -> "RiskEvaluationRequest":
        validate_market_tickers(self.tickers, self.market)
        return self


class RiskEvaluationResult(BaseModel):
    """Result of a risk evaluation."""

    tickers: List[str]
    historical_es: float
    monte_carlo_es: float
    confidence_level: float
    sample_paths: List[List[float]] = Field(default_factory=list)
    correlation_matrix: List[List[float]] = Field(default_factory=list)
    source: str = Field(default="unknown", description="Data source used for prices")
    absolute_loss_historical: float = Field(default=0.0, description="Absolute loss based on historical ES")
    absolute_loss_monte_carlo: float = Field(default=0.0, description="Absolute loss based on Monte Carlo ES")
    cumulative_returns: List[float] = Field(default_factory=list, description="Daily cumulative return series")
    performance_dates: List[str] = Field(default_factory=list, description="Date labels for cumulative returns")
    annualized_volatility: float = Field(default=0.0, description="Annualized volatility")
    max_drawdown: float = Field(default=0.0, description="Maximum drawdown")
    max_drawdown_date: str = Field(default="", description="Date of maximum drawdown")


class RiskEngine:
    """Compute log returns, historical ES, and Monte Carlo ES."""

    def __init__(
        self,
        fetcher: SmartFetcher,
        aligner: MarketAligner,
    ) -> None:
        self.fetcher = fetcher
        self.aligner = aligner

    @staticmethod
    def compute_log_returns(price_df: pd.DataFrame) -> pd.DataFrame:
        """Convert a price DataFrame into log returns and drop leading NaNs."""
        log_returns = np.log(price_df / price_df.shift(1))
        return log_returns.dropna()

    @staticmethod
    def sanitize_returns(returns_df: pd.DataFrame) -> pd.DataFrame:
        """Return complete finite return rows suitable for numerical routines."""
        if returns_df.empty:
            raise ValueError("returns data is empty")

        cleaned = returns_df.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if cleaned.empty:
            raise ValueError("returns data contains no complete finite rows")
        return cleaned

    @staticmethod
    def split_returns(
        returns_df: pd.DataFrame,
        test_ratio: float,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split returns chronologically into in-sample and out-of-sample DataFrames."""
        returns_df = RiskEngine.sanitize_returns(returns_df)
        n_total = len(returns_df)
        n_test = max(1, int(n_total * test_ratio))
        n_train = n_total - n_test
        if n_train < 2:
            raise ValueError(
                "at least 3 complete finite return observations are required for OOS backtest"
            )
        train_df = returns_df.iloc[:n_train]
        test_df = returns_df.iloc[n_train:]
        if test_df.empty:
            raise ValueError("OOS test sample is empty")
        return train_df, test_df

    @staticmethod
    def _normalize_weights(weights: Optional[List[float]], n_assets: int) -> np.ndarray:
        """Return finite full-investment weights, falling back to equal weights."""
        if n_assets <= 0:
            raise ValueError("n_assets must be positive")

        equal_weights = np.ones(n_assets, dtype=float) / n_assets
        if weights is None or len(weights) != n_assets:
            return equal_weights

        weights_arr = np.asarray(weights, dtype=float)
        weight_sum = float(weights_arr.sum())
        if not np.isfinite(weights_arr).all() or abs(weight_sum) <= 1e-12:
            return equal_weights
        return weights_arr / weight_sum

    @staticmethod
    def historical_es(
        returns_df: pd.DataFrame,
        weights: np.ndarray,
        confidence_level: float = 0.99,
    ) -> float:
        """Calculate Expected Shortfall via historical simulation."""
        returns_df = RiskEngine.sanitize_returns(returns_df)
        portfolio_returns = returns_df.to_numpy() @ weights
        portfolio_returns = portfolio_returns[np.isfinite(portfolio_returns)]
        if portfolio_returns.size == 0:
            raise ValueError("portfolio returns contain no finite values")
        var_threshold = np.percentile(
            portfolio_returns,
            (1.0 - confidence_level) * 100.0,
        )
        tail_returns = portfolio_returns[portfolio_returns <= var_threshold]
        if tail_returns.size == 0:
            return float(var_threshold)
        return float(tail_returns.mean())

    @staticmethod
    def _ensure_psd(cov: np.ndarray) -> np.ndarray:
        """Ensure covariance matrix is positive semi-definite."""
        cov = np.asarray(cov, dtype=float)
        if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
            raise ValueError("covariance matrix must be square")
        if not np.isfinite(cov).all():
            raise ValueError("covariance matrix contains non-finite values")

        cov = (cov + cov.T) / 2.0
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        eigenvalues = np.maximum(eigenvalues, 1e-8)
        psd = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        return (psd + psd.T) / 2.0

    @staticmethod
    def prepare_optimization_inputs(
        returns_df: pd.DataFrame,
        n_assets: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Build finite prior returns and covariance inputs for optimization."""
        returns_df = RiskEngine.sanitize_returns(returns_df)
        if len(returns_df) < 2:
            raise ValueError(
                "at least 2 complete finite training observations are required for covariance estimation"
            )
        if returns_df.shape[1] != n_assets:
            raise ValueError("returns data asset count does not match tickers")

        mean_vector = np.nan_to_num(
            returns_df.mean().to_numpy(dtype=float),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        cov_matrix = np.nan_to_num(
            returns_df.cov().to_numpy(dtype=float),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        if mean_vector.shape != (n_assets,):
            raise ValueError("prior return vector has invalid shape")
        if cov_matrix.shape != (n_assets, n_assets):
            raise ValueError("covariance matrix has invalid shape")
        if not np.isfinite(mean_vector).all():
            raise ValueError("prior return vector contains non-finite values")

        cov_matrix = RiskEngine._ensure_psd(cov_matrix)
        return mean_vector, cov_matrix

    @staticmethod
    def _portfolio_return_moments(
        returns_df: pd.DataFrame,
        weights: np.ndarray,
    ) -> Tuple[float, float]:
        """Estimate daily portfolio log-return mean and standard deviation."""
        returns_df = RiskEngine.sanitize_returns(returns_df)

        mean_vector = np.nan_to_num(
            returns_df.mean().to_numpy(),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        cov_matrix = np.nan_to_num(
            returns_df.cov().to_numpy(),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        if not np.any(cov_matrix):
            return float(weights @ mean_vector), 0.0

        cov_matrix = RiskEngine._ensure_psd(cov_matrix)

        portfolio_mean = float(weights @ mean_vector)
        portfolio_variance = float(weights @ cov_matrix @ weights)
        portfolio_std = float(np.sqrt(max(portfolio_variance, 0.0)))
        return portfolio_mean, portfolio_std

    @staticmethod
    def monte_carlo_es(
        returns_df: pd.DataFrame,
        weights: np.ndarray,
        confidence_level: float = 0.99,
        n_simulations: int = 10_000,
        random_seed: int = 42,
    ) -> float:
        """Calculate Expected Shortfall via Monte Carlo simulation."""
        rng = np.random.default_rng(random_seed)
        portfolio_mean, portfolio_std = RiskEngine._portfolio_return_moments(
            returns_df,
            weights,
        )

        if portfolio_std <= 1e-12:
            portfolio_returns = np.full(n_simulations, portfolio_mean)
        else:
            portfolio_returns = rng.normal(
                loc=portfolio_mean,
                scale=portfolio_std,
                size=n_simulations,
            )

        var_threshold = np.percentile(
            portfolio_returns,
            (1.0 - confidence_level) * 100.0,
        )
        tail_returns = portfolio_returns[portfolio_returns <= var_threshold]
        if tail_returns.size == 0:
            return float(var_threshold)
        return float(tail_returns.mean())

    @staticmethod
    def generate_mc_paths(
        returns_df: pd.DataFrame,
        weights: np.ndarray,
        n_simulations: int = 10_000,
        random_seed: int = 42,
    ) -> np.ndarray:
        """Generate multi-day Monte Carlo portfolio price paths for visualization."""
        returns_df = RiskEngine.sanitize_returns(returns_df)
        rng = np.random.default_rng(random_seed)
        n_days = len(returns_df)
        n_sample_paths = min(100, n_simulations)
        portfolio_mean, portfolio_std = RiskEngine._portfolio_return_moments(
            returns_df,
            weights,
        )

        if portfolio_std <= 1e-12:
            portfolio_daily = np.full((n_sample_paths, n_days), portfolio_mean)
        else:
            portfolio_daily = rng.normal(
                loc=portfolio_mean,
                scale=portfolio_std,
                size=(n_sample_paths, n_days),
            )

        cum_returns = np.cumsum(portfolio_daily, axis=1)
        price_paths = 100.0 * np.exp(cum_returns)
        return price_paths

    @staticmethod
    def compute_performance_metrics(
        returns_df: pd.DataFrame,
        weights: np.ndarray,
    ) -> dict:
        """Compute cumulative returns, annualized volatility, and max drawdown."""
        returns_df = RiskEngine.sanitize_returns(returns_df)
        portfolio_returns = returns_df.to_numpy() @ weights
        cum_returns = np.cumprod(1.0 + portfolio_returns) - 1.0
        ann_vol = float(portfolio_returns.std() * np.sqrt(252))
        ann_return = float(portfolio_returns.mean() * 252)
        risk_free_rate = 0.02
        sharpe = (ann_return - risk_free_rate) / ann_vol if ann_vol > 1e-12 else 0.0

        cumulative = np.cumprod(1.0 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_dd_idx = int(np.argmin(drawdown))
        max_dd = float(drawdown[max_dd_idx])

        return {
            "cumulative_returns": cum_returns.tolist(),
            "dates": returns_df.index.strftime("%Y-%m-%d").tolist(),
            "annualized_volatility": ann_vol,
            "annualized_return": ann_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "max_drawdown_date": str(returns_df.index[max_dd_idx].date()),
        }

    @staticmethod
    def compute_information_ratio(
        strategy_returns: np.ndarray,
        benchmark_returns: np.ndarray,
    ) -> float:
        """Compute annualized Information Ratio from daily strategy and benchmark returns."""
        excess = strategy_returns - benchmark_returns
        if excess.std() < 1e-12:
            return 0.0
        return float(excess.mean() / excess.std() * np.sqrt(252))

    @staticmethod
    def calculate_model_score(metrics: dict) -> dict:
        """
        Compute a 0-100 comprehensive model score and letter grade.

        Risk control weight: 40%
        Return stability weight: 60% (average of profitability, alpha, stability, win rate, consistency)
        """
        sharpe = metrics.get("sharpe_ratio", 0.0)
        max_dd = metrics.get("max_drawdown", 0.0)
        ir = metrics.get("information_ratio", 0.0)
        ann_vol = metrics.get("annualized_volatility", 0.0)
        excess_return = metrics.get("excess_return", 0.0)
        bench_vol = metrics.get("benchmark_annualized_volatility", ann_vol)

        # 1. Profitability (Sharpe-based)
        if sharpe >= 2.0:
            profitability = 100.0
        elif sharpe >= 1.0:
            profitability = 70.0 + (sharpe - 1.0) * 30.0
        elif sharpe >= 0.0:
            profitability = 40.0 + sharpe * 30.0
        elif sharpe >= -1.0:
            profitability = 20.0 + (sharpe + 1.0) * 20.0
        else:
            profitability = max(0.0, 20.0 + (sharpe + 1.0) * 10.0)

        # 2. Risk Control (Max Drawdown-based)
        if max_dd >= -0.05:
            risk_control = 100.0
        elif max_dd >= -0.10:
            risk_control = 90.0 + (max_dd + 0.10) * 200.0
        elif max_dd >= -0.20:
            risk_control = 70.0 + (max_dd + 0.20) * 200.0
        elif max_dd >= -0.30:
            risk_control = 40.0 + (max_dd + 0.30) * 300.0
        else:
            risk_control = max(0.0, 40.0 + (max_dd + 0.30) * 100.0)

        # 3. Alpha Capability (IR-based)
        if ir >= 1.5:
            alpha_cap = 100.0
        elif ir >= 0.5:
            alpha_cap = 60.0 + (ir - 0.5) * 40.0
        elif ir >= 0.0:
            alpha_cap = 40.0 + ir * 40.0
        elif ir >= -0.5:
            alpha_cap = 20.0 + (ir + 0.5) * 40.0
        else:
            alpha_cap = max(0.0, 20.0 + (ir + 0.5) * 20.0)

        # 4. Stability (Volatility-based)
        if ann_vol <= 0.10:
            stability = 100.0
        elif ann_vol <= 0.20:
            stability = 80.0 + (0.20 - ann_vol) * 200.0
        elif ann_vol <= 0.30:
            stability = 60.0 + (0.30 - ann_vol) * 200.0
        elif ann_vol <= 0.40:
            stability = 40.0 + (0.40 - ann_vol) * 200.0
        else:
            stability = max(0.0, 40.0 - (ann_vol - 0.40) * 100.0)

        # 5. Win Rate (Excess return-based)
        win_rate = 100.0 if excess_return > 0 else max(0.0, 50.0 + excess_return * 500.0)

        # 6. Consistency (Vol ratio vs benchmark)
        if bench_vol > 1e-12:
            vol_ratio = ann_vol / bench_vol
        else:
            vol_ratio = 1.0

        if vol_ratio <= 0.8:
            consistency = 100.0
        elif vol_ratio <= 1.0:
            consistency = 80.0 + (1.0 - vol_ratio) * 100.0
        elif vol_ratio <= 1.2:
            consistency = 60.0 + (1.2 - vol_ratio) * 100.0
        elif vol_ratio <= 1.5:
            consistency = 40.0 + (1.5 - vol_ratio) * 66.67
        else:
            consistency = max(0.0, 40.0 - (vol_ratio - 1.5) * 20.0)

        return_stability = (profitability + alpha_cap + stability + win_rate + consistency) / 5.0
        total_score = risk_control * 0.40 + return_stability * 0.60
        total_score = round(float(total_score), 1)

        if total_score >= 90:
            grade = "S"
        elif total_score >= 75:
            grade = "A"
        elif total_score >= 60:
            grade = "B"
        elif total_score >= 40:
            grade = "C"
        else:
            grade = "D"

        return {
            "total_score": total_score,
            "grade": grade,
            "risk_control": round(float(risk_control), 1),
            "profitability": round(float(profitability), 1),
            "alpha_capability": round(float(alpha_cap), 1),
            "stability": round(float(stability), 1),
            "win_rate": round(float(win_rate), 1),
            "consistency": round(float(consistency), 1),
        }

    @staticmethod
    def _resolve_market(ticker: str) -> str:
        """Map ticker symbols to their primary exchange."""
        if ticker.upper().endswith(".HK"):
            return "HKEX"
        return "NYSE"

    def _fetch_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
        market_mode: str = "us",
    ) -> pd.DataFrame:
        """Fetch and align close prices for a list of tickers."""
        series_list: List[pd.Series] = []
        markets: List[str] = []

        # Try batch download first to minimize HTTP requests and avoid rate limits
        if len(tickers) > 1:
            try:
                batch_df = self.fetcher.fetch_equity_batch(
                    tickers, start_date, end_date
                )
            except DataFetcherError:
                batch_df = None

            if batch_df is not None and not batch_df.empty:
                for ticker in tickers:
                    if ticker not in batch_df.columns.get_level_values(1).unique():
                        continue
                    close_col = ("Close", ticker)
                    if close_col not in batch_df.columns:
                        continue
                    prices = pd.Series(
                        batch_df[close_col].values,
                        index=pd.to_datetime(batch_df.index.values),
                        name=ticker,
                    )
                    series_list.append(prices)
                    markets.append(self._resolve_market(ticker))

                if len(series_list) == len(tickers):
                    aligned = self.aligner.align_multiple(series_list, markets)
                    aligned.columns = tickers
                    if market_mode == "mixed":
                        for col in aligned.columns:
                            if self._resolve_market(str(col)) == "HKEX":
                                aligned[col] = aligned[col] / 7.8
                    return aligned

        # Fallback to per-ticker fetch; _fetch_yf enforces 2s rate limits
        for idx, ticker in enumerate(tickers):
            if idx > 0:
                import time
                time.sleep(0.5)

            market = self._resolve_market(ticker)
            if market == "HKEX":
                response = self.fetcher.fetch_hk_equity(ticker, start_date, end_date)
            else:
                response = self.fetcher.fetch_us_equity(ticker, start_date, end_date)

            df = response.data
            if "Close" not in df.columns:
                raise DataFetcherError(
                    message=f"missing Close column for {ticker}",
                    symbol=ticker,
                    source="risk_engine",
                )

            date_col = "Date" if "Date" in df.columns else df.columns[0]
            prices = pd.Series(
                df["Close"].values,
                index=pd.to_datetime(df[date_col].values),
                name=ticker,
            )
            series_list.append(prices)
            markets.append(market)

        aligned = self.aligner.align_multiple(series_list, markets)
        aligned.columns = tickers
        if market_mode == "mixed":
            for col in aligned.columns:
                if self._resolve_market(str(col)) == "HKEX":
                    aligned[col] = aligned[col] / 7.8
        return aligned

    def evaluate(self, request: RiskEvaluationRequest) -> RiskEvaluationResult:
        """Run the full risk evaluation pipeline."""
        price_df = self._fetch_prices(
            request.tickers,
            request.start_date,
            request.end_date,
            market_mode=request.market,
        )
        returns_df = self.compute_log_returns(price_df)
        returns_df = self.sanitize_returns(returns_df)

        n_assets = len(request.tickers)
        weights = self._normalize_weights(request.weights, n_assets)

        hist_es = self.historical_es(returns_df, weights, request.confidence_level)
        mc_es = self.monte_carlo_es(
            returns_df, weights, request.confidence_level, n_simulations=request.mc_paths
        )
        paths = self.generate_mc_paths(
            returns_df, weights, n_simulations=request.mc_paths
        )
        sample_paths = paths.tolist()

        corr_matrix = returns_df.corr().to_numpy()
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0, posinf=0.0, neginf=0.0)
        np.fill_diagonal(corr_matrix, 1.0)

        abs_loss_hist = request.capital * request.leverage * abs(hist_es)
        abs_loss_mc = request.capital * request.leverage * abs(mc_es)

        perf = self.compute_performance_metrics(returns_df, weights)

        return RiskEvaluationResult(
            tickers=request.tickers,
            historical_es=hist_es,
            monte_carlo_es=mc_es,
            confidence_level=request.confidence_level,
            sample_paths=sample_paths,
            correlation_matrix=corr_matrix.tolist(),
            source=self.fetcher.last_source,
            absolute_loss_historical=abs_loss_hist,
            absolute_loss_monte_carlo=abs_loss_mc,
            cumulative_returns=perf["cumulative_returns"],
            performance_dates=perf["dates"],
            annualized_volatility=perf["annualized_volatility"],
            max_drawdown=perf["max_drawdown"],
            max_drawdown_date=perf["max_drawdown_date"],
        )
