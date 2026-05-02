"""Black-Litterman Bayesian portfolio optimizer with mean-variance optimization."""

from typing import List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import minimize


class ViewSpec(BaseModel):
    """A single investor view for the Black-Litterman model."""

    assets: List[str] = Field(..., min_length=1)
    relative_assets: Optional[List[str]] = Field(default=None)
    expected_return: float
    confidence: float = Field(default=0.5, gt=0.0, le=1.0)


class OptimizationResult(BaseModel):
    """Result of a Black-Litterman portfolio optimization."""

    tickers: List[str]
    prior_returns: List[float]
    prior_weights: List[float]
    posterior_returns: List[float]
    posterior_weights: List[float]
    risk_aversion: float
    source: str = Field(default="unknown", description="Data source used for prices")
    backtest_enabled: bool = Field(default=False)
    oos_dates: List[str] = Field(default_factory=list)
    oos_optimized_cum_returns: List[float] = Field(default_factory=list)
    oos_benchmark_cum_returns: List[float] = Field(default_factory=list)
    oos_optimized_ann_vol: float = Field(default=0.0)
    oos_benchmark_ann_vol: float = Field(default=0.0)
    oos_optimized_max_drawdown: float = Field(default=0.0)
    oos_benchmark_max_drawdown: float = Field(default=0.0)
    oos_excess_return: float = Field(default=0.0)
    oos_optimized_sharpe: float = Field(default=0.0)
    oos_benchmark_sharpe: float = Field(default=0.0)
    oos_optimized_ir: float = Field(default=0.0)
    model_score: float = Field(default=0.0)
    model_grade: str = Field(default="")
    model_score_risk_control: float = Field(default=0.0)
    model_score_profitability: float = Field(default=0.0)
    model_score_alpha: float = Field(default=0.0)
    model_score_stability: float = Field(default=0.0)
    model_score_win_rate: float = Field(default=0.0)
    model_score_consistency: float = Field(default=0.0)


class BayesianOptimizer:
    """Black-Litterman posterior inference and mean-variance optimization."""

    @staticmethod
    def _build_view_matrices(
        tickers: List[str],
        views: List[ViewSpec],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Translate human-readable views into P, Q, and confidence arrays."""
        n_assets = len(tickers)
        ticker_to_idx = {t: i for i, t in enumerate(tickers)}
        k = len(views)

        valid_views = []
        for view in views:
            valid_assets = [a for a in view.assets if a in ticker_to_idx]
            valid_rel = [a for a in (view.relative_assets or []) if a in ticker_to_idx]
            if valid_assets:
                valid_views.append(
                    ViewSpec(
                        assets=valid_assets,
                        relative_assets=valid_rel if valid_rel else None,
                        expected_return=view.expected_return,
                        confidence=view.confidence,
                    )
                )

        k = len(valid_views)
        P = np.zeros((k, n_assets))
        Q = np.zeros(k)
        confidences = np.zeros(k)

        for i, view in enumerate(valid_views):
            for asset in view.assets:
                idx = ticker_to_idx[asset]
                P[i, idx] += 1.0
            if view.relative_assets:
                for rel_asset in view.relative_assets:
                    idx = ticker_to_idx[rel_asset]
                    P[i, idx] -= 1.0
            Q[i] = view.expected_return
            confidences[i] = view.confidence

        assert P.shape == (k, n_assets), f"P shape mismatch: {P.shape} != ({k}, {n_assets})"
        assert Q.shape == (k,), f"Q shape mismatch: {Q.shape} != ({k},)"
        assert confidences.shape == (k,), f"confidences shape mismatch: {confidences.shape}"
        return P, Q, confidences

    @staticmethod
    def _build_omega(
        P: np.ndarray,
        cov_matrix: np.ndarray,
        confidences: np.ndarray,
    ) -> np.ndarray:
        """Construct the uncertainty diagonal matrix Omega from view confidences."""
        k = P.shape[0]
        var_views = np.diag(P @ cov_matrix @ P.T)
        omega_diag = (1.0 / confidences - 1.0) * var_views
        omega_diag = np.maximum(omega_diag, 1e-8)
        return np.diag(omega_diag)

    @staticmethod
    def _ensure_vector(v: np.ndarray, name: str = "vector") -> np.ndarray:
        """Ensure a 1D array is a column vector."""
        arr = np.asarray(v)
        if arr.ndim == 1:
            return arr.reshape(-1, 1)
        if arr.ndim == 2 and arr.shape[1] == 1:
            return arr
        raise ValueError(f"{name} must be 1-dimensional, got shape {arr.shape}")

    @staticmethod
    def black_litterman(
        prior_returns: np.ndarray,
        cov_matrix: np.ndarray,
        tau: float,
        P: np.ndarray,
        Q: np.ndarray,
        omega: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute posterior expected returns and covariance via Black-Litterman."""
        Pi = BayesianOptimizer._ensure_vector(prior_returns, "prior_returns")
        n_assets = Pi.shape[0]
        Sigma = np.asarray(cov_matrix)
        assert Sigma.shape == (n_assets, n_assets), (
            f"cov_matrix shape {Sigma.shape} incompatible with {n_assets} assets"
        )

        P_mat = np.asarray(P)
        Q_vec = BayesianOptimizer._ensure_vector(Q, "Q")
        k = P_mat.shape[0]
        assert P_mat.shape == (k, n_assets), (
            f"P shape {P_mat.shape} incompatible with ({k}, {n_assets})"
        )
        assert Q_vec.shape == (k, 1), f"Q shape {Q_vec.shape} incompatible with ({k}, 1)"

        if omega is None:
            omega = np.diag(np.ones(k) * 1e-4)
        else:
            omega = np.asarray(omega)
            assert omega.shape == (k, k), f"omega shape {omega.shape} incompatible with ({k}, {k})"

        tau_Sigma = tau * Sigma
        middle = P_mat @ tau_Sigma @ P_mat.T + omega

        diff = Q_vec - P_mat @ Pi
        solved = np.linalg.solve(middle, diff)
        Pi_post = Pi + tau_Sigma @ P_mat.T @ solved

        cov_solved = np.linalg.solve(middle, P_mat @ tau_Sigma)
        Sigma_post = Sigma + tau_Sigma - tau_Sigma @ P_mat.T @ cov_solved

        assert Pi_post.shape == (n_assets, 1), f"posterior returns shape mismatch: {Pi_post.shape}"
        assert Sigma_post.shape == (n_assets, n_assets), (
            f"posterior covariance shape mismatch: {Sigma_post.shape}"
        )
        return Pi_post.flatten(), Sigma_post

    @staticmethod
    def optimize_weights(
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        risk_aversion: float = 2.5,
        max_weight: float = 0.40,
    ) -> np.ndarray:
        """Solve mean-variance optimization with long-only, full-investment, and max-weight constraints."""
        n = len(expected_returns)
        mu = np.asarray(expected_returns)
        Sigma = np.asarray(cov_matrix)
        assert Sigma.shape == (n, n), f"cov_matrix shape {Sigma.shape} incompatible with {n} assets"

        def objective(w: np.ndarray) -> float:
            return float(-w @ mu + (risk_aversion / 2.0) * w @ Sigma @ w)

        effective_max = max(float(max_weight), 1.0 / n)
        x0 = np.ones(n) / n
        bounds = [(0.0, effective_max) for _ in range(n)]
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 1000},
        )

        if not result.success:
            raise RuntimeError(f"optimization failed: {result.message}")

        weights = result.x
        weights = np.clip(weights, 0.0, effective_max)
        weight_sum = float(np.sum(weights))
        if not np.isfinite(weights).all() or abs(weight_sum) <= 1e-12:
            raise RuntimeError("optimization produced invalid weights")
        weights /= weight_sum
        return weights

    @staticmethod
    def _normalize_prior_weights(
        weights: Optional[List[float]],
        n_assets: int,
        max_weight: float,
    ) -> Optional[np.ndarray]:
        """Return normalized user weights, or None when they are not usable."""
        if weights is None or len(weights) != n_assets:
            return None

        weights_arr = np.asarray(weights, dtype=float)
        if not np.isfinite(weights_arr).all():
            return None

        weights_arr = np.clip(weights_arr, 0.0, float(max_weight))
        weight_sum = float(weights_arr.sum())
        if abs(weight_sum) <= 1e-12:
            return None
        return weights_arr / weight_sum

    def optimize_with_views(
        self,
        tickers: List[str],
        prior_returns: np.ndarray,
        cov_matrix: np.ndarray,
        views: List[ViewSpec],
        tau: float = 0.025,
        risk_aversion: float = 2.5,
        weights: Optional[List[float]] = None,
        max_weight: float = 0.40,
    ) -> OptimizationResult:
        """Run full Black-Litterman pipeline: views -> posterior -> optimized weights."""
        n_assets = len(tickers)
        prior_returns_arr = np.asarray(prior_returns)
        cov_arr = np.asarray(cov_matrix)
        assert prior_returns_arr.shape == (n_assets,), (
            f"prior_returns shape {prior_returns_arr.shape} != ({n_assets},)"
        )
        assert cov_arr.shape == (n_assets, n_assets), (
            f"cov_matrix shape {cov_arr.shape} != ({n_assets}, {n_assets})"
        )

        P, Q, confidences = self._build_view_matrices(tickers, views)
        omega = self._build_omega(P, cov_arr, confidences)

        posterior_returns, posterior_cov = self.black_litterman(
            prior_returns_arr,
            cov_arr,
            tau,
            P,
            Q,
            omega,
        )

        prior_weights = self._normalize_prior_weights(weights, n_assets, max_weight)
        if prior_weights is None:
            prior_weights = self.optimize_weights(prior_returns_arr, cov_arr, risk_aversion, max_weight)
        posterior_weights = self.optimize_weights(posterior_returns, posterior_cov, risk_aversion, max_weight)

        assert prior_weights.shape == (n_assets,), (
            f"prior_weights shape mismatch: {prior_weights.shape}"
        )
        assert posterior_weights.shape == (n_assets,), (
            f"posterior_weights shape mismatch: {posterior_weights.shape}"
        )
        assert abs(np.sum(prior_weights) - 1.0) < 1e-6, "prior_weights do not sum to 1"
        assert abs(np.sum(posterior_weights) - 1.0) < 1e-6, "posterior_weights do not sum to 1"

        return OptimizationResult(
            tickers=tickers,
            prior_returns=prior_returns_arr.tolist(),
            prior_weights=prior_weights.tolist(),
            posterior_returns=posterior_returns.tolist(),
            posterior_weights=posterior_weights.tolist(),
            risk_aversion=risk_aversion,
        )
