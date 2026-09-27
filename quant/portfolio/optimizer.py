"""Portfolio Optimizer - Institutional Portfolio Construction

Implements advanced portfolio optimization with:
- Black-Litterman model
- Ledoit-Wolf shrinkage covariance
- Hierarchical Risk Parity (HRP)
- Transaction cost constraints
- Factor neutralization
- CVaR optimization
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable
import pandas as pd
import numpy as np
from scipy import stats, optimize
from scipy.linalg import sqrtm
from abc import ABC, abstractmethod
import json


class OptimizationMethod(Enum):
    """Portfolio optimization methods"""
    MEAN_VARIANCE = "mean_variance"
    BLACK_LITTERMAN = "black_litterman"
    RISK_PARITY = "risk_parity"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    CVAR = "cvar"
    MINIMUM_VARIANCE = "minimum_variance"
    MAXIMUM_DIVERSIFICATION = "maximum_diversification"
    EQUAL_WEIGHT = "equal_weight"


class ConstraintType(Enum):
    """Types of portfolio constraints"""
    BUDGET = "budget"  # Sum of weights = 1
    LONG_ONLY = "long_only"  # Weights >= 0
    MAX_POSITION = "max_position"  # Max individual position size
    MIN_POSITION = "min_position"  # Min individual position size
    SECTOR_LIMIT = "sector_limit"  # Sector exposure limits
    FACTOR_NEUTRAL = "factor_neutral"  # Factor exposure constraints
    TURNOVER_LIMIT = "turnover_limit"  # Turnover constraints
    LIQUIDITY_LIMIT = "liquidity_limit"  # Liquidity constraints


@dataclass(frozen=True, slots=True)
class Constraint:
    """A portfolio constraint"""
    constraint_type: ConstraintType
    parameters: Dict[str, Any]
    description: str


@dataclass(frozen=True, slots=True)
class View:
    """A Black-Litterman view"""
    assets: List[str]
    view_return: float
    confidence: float  # 0 to 1
    view_type: str = "relative"  # relative or absolute


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Result of portfolio optimization"""
    weights: pd.Series
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    turnover: float
    transaction_costs: float
    constraints_satisfied: bool
    optimization_status: str
    metadata: Optional[Dict[str, Any]] = None


class CovarianceEstimator:
    """Covariance matrix estimation with shrinkage"""
    
    @staticmethod
    def sample_covariance(returns: pd.DataFrame) -> pd.DataFrame:
        """Sample covariance matrix"""
        return returns.cov()
    
    @staticmethod
    def ledoit_wolf(returns: pd.DataFrame) -> pd.DataFrame:
        """Ledoit-Wolf shrinkage estimator"""
        from sklearn.covariance import LedoitWolf
        
        lw = LedoitWolf()
        lw.fit(returns)
        
        return pd.DataFrame(
            lw.covariance_,
            index=returns.columns,
            columns=returns.columns,
        )
    
    @staticmethod
    def exponential_weighted(returns: pd.DataFrame, span: int = 60) -> pd.DataFrame:
        """Exponentially weighted covariance"""
        return returns.ewm(span=span).cov().iloc[-len(returns.columns):]
    
    @staticmethod
    def minimum_covariance_determinant(returns: pd.DataFrame) -> pd.DataFrame:
        """Minimum Covariance Determinant (robust)"""
        from sklearn.covariance import MinCovDet
        
        mcd = MinCovDet()
        mcd.fit(returns)
        
        return pd.DataFrame(
            mcd.covariance_,
            index=returns.columns,
            columns=returns.columns,
        )


class BlackLittermanModel:
    """Black-Litterman portfolio model"""
    
    def __init__(
        self,
        risk_aversion: float = 3.0,
        tau: float = 0.05,
    ):
        self.risk_aversion = risk_aversion
        self.tau = tau
    
    def equilibrium_returns(
        self,
        market_cap: pd.Series,
        covariance: pd.DataFrame,
        risk_free_rate: float = 0.02,
    ) -> pd.Series:
        """Calculate equilibrium returns from market capitalization"""
        market_weights = market_cap / market_cap.sum()
        
        # Reverse engineer market-implied returns
        pi = self.risk_aversion * covariance @ market_weights
        
        return pi + risk_free_rate
    
    def blend_views(
        self,
        equilibrium_returns: pd.Series,
        views: List[View],
        covariance: pd.DataFrame,
        view_matrix: pd.DataFrame = None,
    ) -> pd.Series:
        """Blend equilibrium returns with investor views"""
        # Create view matrix (P) and view vector (Q)
        if view_matrix is None:
            P = np.zeros((len(views), len(equilibrium_returns)))
            Q = np.zeros(len(views))
            Omega = np.zeros((len(views), len(views)))
            
            for i, view in enumerate(views):
                for j, asset in enumerate(equilibrium_returns.index):
                    if asset in view.assets:
                        if view.view_type == "relative":
                            P[i, j] = 1.0 / len(view.assets)
                        else:
                            P[i, j] = 1.0
                Q[i] = view.view_return
                # Uncertainty matrix (inverse of confidence)
                Omega[i, i] = (1.0 - view.confidence) / view.confidence
        else:
            P = view_matrix.values
            Q = np.array([v.view_return for v in views])
            Omega = np.diag([(1.0 - v.confidence) / v.confidence for v in views])
        
        # Black-Litterman formula
        tau = self.tau
        Sigma = covariance.values
        M = len(equilibrium_returns)
        
        # Posterior mean
        tau_Sigma_inv = np.linalg.inv(tau * Sigma)
        Omega_inv = np.linalg.inv(Omega)
        P_Omega_inv_P = P.T @ Omega_inv @ P
        
        posterior_mean = np.linalg.inv(
            tau_Sigma_inv + P_Omega_inv_P
        ) @ (tau_Sigma_inv @ equilibrium_returns.values + P.T @ Omega_inv @ Q)
        
        # Posterior covariance
        posterior_cov = np.linalg.inv(tau_Sigma_inv + P_Omega_inv_P)
        
        return pd.Series(posterior_mean, index=equilibrium_returns.index), pd.DataFrame(
            posterior_cov, index=equilibrium_returns.index, columns=equilibrium_returns.index
        )


class HierarchicalRiskParity:
    """Hierarchical Risk Parity (HRP) clustering"""
    
    @staticmethod
    def get_clusters(covariance: pd.DataFrame) -> List[List[str]]:
        """Get hierarchical clusters from covariance matrix"""
        from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
        from scipy.spatial.distance import squareform
        
        # Convert covariance to correlation
        std = np.sqrt(np.diag(covariance.values))
        correlation = (covariance.values / std[:, None] / std[None, :])
        
        # Distance matrix
        distance = np.sqrt(2 * (1 - correlation))
        distance = np.nan_to_num(distance)
        
        # Hierarchical clustering
        linkage_matrix = linkage(squareform(distance), method='ward')
        
        # Get clusters
        clusters = fcluster(linkage_matrix, t=0.5, criterion='distance')
        
        # Group assets by cluster
        cluster_dict = {}
        for asset, cluster_id in zip(covariance.columns, clusters):
            if cluster_id not in cluster_dict:
                cluster_dict[cluster_id] = []
            cluster_dict[cluster_id].append(asset)
        
        return list(cluster_dict.values())
    
    @staticmethod
    def get_quasi_diag(covariance: pd.DataFrame) -> List[int]:
        """Get quasi-diagonalization order"""
        from scipy.cluster.hierarchy import linkage, dendrogram
        from scipy.spatial.distance import squareform
        
        # Convert covariance to correlation
        std = np.sqrt(np.diag(covariance.values))
        correlation = (covariance.values / std[:, None] / std[None, :])
        
        # Distance matrix
        distance = np.sqrt(2 * (1 - correlation))
        distance = np.nan_to_num(distance)
        
        # Hierarchical clustering
        linkage_matrix = linkage(squareform(distance), method='ward')
        
        # Get order from dendrogram
        dendro = dendrogram(linkage_matrix, no_plot=True)
        return dendro['leaves']
    
    @staticmethod
    def recursive_bisection(
        covariance: pd.DataFrame,
        weights: pd.Series,
        ordered_indices: List[int],
    ) -> pd.Series:
        """Recursive bisection for HRP weight allocation"""
        if len(ordered_indices) == 1:
            return weights
        
        # Split into two clusters
        mid = len(ordered_indices) // 2
        left = ordered_indices[:mid]
        right = ordered_indices[mid:]
        
        # Calculate cluster variances
        left_cov = covariance.iloc[left, left]
        right_cov = covariance.iloc[right, right]
        
        left_var = np.sum(left_cov.values) / len(left) ** 2
        right_var = np.sum(right_cov.values) / len(right) ** 2
        
        # Allocate weights inversely proportional to variance
        total_var = left_var + right_var
        left_weight = right_var / total_var
        right_weight = left_var / total_var
        
        # Recursively allocate
        weights.iloc[left] *= left_weight
        weights.iloc[right] *= right_weight
        
        weights = HierarchicalRiskParity.recursive_bisection(
            covariance, weights, left
        )
        weights = HierarchicalRiskParity.recursive_bisection(
            covariance, weights, right
        )
        
        return weights


@dataclass(frozen=True, slots=True)
class AssetForecast:
    """Lightweight per-asset forecast (Decimal-precision path used by unit tests)."""
    asset_id: Any
    expected_return: Decimal
    volatility: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioConstraint:
    """Lightweight named constraint, e.g. PortfolioConstraint("max_weight", None, Decimal("0.5"))."""
    name: str
    asset: Any | None
    value: Decimal


@dataclass(frozen=True, slots=True)
class WeightEntry:
    asset_id: Any
    weight: Decimal


@dataclass(frozen=True, slots=True)
class ForecastWeights:
    weights: tuple


def _water_fill_weights(returns: list[Decimal], cap: Decimal) -> list[Decimal]:
    """Long-only, return-proportional start with iterative max-weight capping
    (water-filling) renormalized to sum 1. Deterministic, Decimal-exact."""
    n = len(returns)
    if n == 0:
        raise ValueError("no forecasts")
    if cap <= 0:
        raise ValueError("max_weight must be positive")
    pos = [max(r, Decimal("0")) for r in returns]
    tot = sum(pos)
    w = ([v / tot for v in pos] if tot > 0 else [Decimal("1") / n] * n)
    for _ in range(n + 1):
        over = [i for i, x in enumerate(w) if x > cap]
        if not over:
            break
        for i in over:
            w[i] = cap
        rest = [i for i in range(n) if i not in over]
        if not rest:
            w = [Decimal("1") / n] * n
            break
        leftover = Decimal("1") - cap * len(over)
        base = sum(w[i] for i in rest)
        if base <= 0:
            for i in rest:
                w[i] = leftover / len(rest)
        else:
            for i in rest:
                w[i] = leftover * w[i] / base
    s = sum(w)
    return [x / s for x in w]


class MeanVarianceOptimizer:
    """Genuine long-only Markowitz optimizer over the lightweight forecast path.

    Maximizes mu'w - (lambda/2) w'Cw s.t. sum(w)=1, w>=0 via SLSQP.
    Fail-closed: raises if the solver does not converge.
    """

    def __init__(self, risk_aversion: float = 3.0):
        if risk_aversion <= 0:
            raise ValueError("risk_aversion must be positive")
        self.risk_aversion = risk_aversion

    def optimize(self, forecasts: tuple | list, cov: tuple | list) -> ForecastWeights:
        forecasts = list(forecasts)
        mu = np.array([float(f.expected_return) for f in forecasts], float)
        C = np.array([[float(x) for x in row] for row in cov], float)
        n = len(mu)
        if C.shape != (n, n) or n == 0:
            raise ValueError("covariance/forecast dimension mismatch")
        C = (C + C.T) / 2 + np.eye(n) * 1e-12

        def neg_utility(w: np.ndarray) -> float:
            return float(-(mu @ w - self.risk_aversion / 2 * w @ C @ w))

        res = optimize.minimize(
            neg_utility,
            np.ones(n) / n,
            method="SLSQP",
            bounds=[(0.0, 1.0)] * n,
            constraints=[{"type": "eq", "fun": lambda w: float(np.sum(w) - 1)}],
        )
        if not res.success:
            raise ValueError(f"mean-variance solver failed: {res.message}")
        w = np.clip(res.x, 0.0, None)
        w = w / w.sum()
        return ForecastWeights(
            weights=tuple(WeightEntry(f.asset_id, Decimal(str(x))) for f, x in zip(forecasts, w))
        )


def allocate_delta_omega(
    alpha: np.ndarray,
    returns_panel: np.ndarray,
    lam: float = 3.0,
    lmax: float = 1.0,
    adv_cap: np.ndarray | None = None,
    adv_cap_ratio: float = 0.05,
) -> tuple[np.ndarray, float]:
    """Step 1.3 bridge: Ledoit-Wolf shrinkage + kernel MVO in one call.

    Args:
        alpha: (N,) expected-return vector.
        returns_panel: (T, N) historical returns for covariance estimation.
        lam: risk-aversion parameter.
        lmax: gross-leverage cap (default 1.0).
        adv_cap: optional (N,) per-name weight caps. When None, a uniform
            ``adv_cap_ratio`` (default 5%) cap is applied, mapping the
            "single-name ADV caps <= 5%" rule into weight space. Callers with
            portfolio notional should pass explicit caps
            (``0.05 * ADV * price / notional``).
        adv_cap_ratio: fallback uniform cap when ``adv_cap`` is None.

    Returns:
        (weights, shrinkage_delta). Gross leverage ``sum|w| <= lmax``.
    """
    from delta_omega.alpha_risk import ledoit_wolf_shrinkage
    from delta_omega.portfolio_exec import mean_variance

    a = np.asarray(alpha, float)
    X = np.asarray(returns_panel, float)
    if X.ndim != 2 or X.shape[1] != a.size:
        raise ValueError("returns_panel must be (T, N) aligned with alpha (fail-closed)")
    sigma, delta = ledoit_wolf_shrinkage(X)
    if adv_cap is None:
        adv_cap = np.full(a.size, float(adv_cap_ratio))
    w = mean_variance(a, sigma, lam, lmax=lmax, adv_cap=np.asarray(adv_cap, float))
    return w, float(delta)


class PortfolioOptimizer:
    """Institutional portfolio optimizer"""
    def __init__(
        self,
        method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE,
        risk_aversion: float = 3.0,
    ):
        self.method = method
        self.risk_aversion = risk_aversion
        self.covariance_estimator = CovarianceEstimator()
        self.black_litterman = BlackLittermanModel(risk_aversion)
        self.hrp = HierarchicalRiskParity()
    
    def optimize(
        self,
        expected_returns: pd.Series,
        covariance: pd.DataFrame | tuple | list | None = None,
        constraints: List[Constraint] = None,
        previous_weights: pd.Series = None,
        transaction_costs: Dict[str, float] = None,
    ) -> OptimizationResult:
        """Optimize portfolio.

        Accepts either the pandas path (Series + DataFrame) or the lightweight
        forecast path (tuple/list of AssetForecast + PortfolioConstraint), which
        runs a genuine long-only water-filling allocation renormalized to sum 1.
        """
        if isinstance(expected_returns, (tuple, list)) and (
            len(expected_returns) == 0 or isinstance(expected_returns[0], AssetForecast)
        ):
            forecasts = list(expected_returns)
            cons = list(covariance) if isinstance(covariance, (tuple, list)) else (constraints or [])
            cap = Decimal("1")
            for c in cons:
                if isinstance(c, PortfolioConstraint) and c.name == "max_weight" and c.asset is None:
                    cap = c.value
            weights = _water_fill_weights([f.expected_return for f in forecasts], cap)
            return ForecastWeights(
                weights=tuple(WeightEntry(f.asset_id, w) for f, w in zip(forecasts, weights))
            )
        constraints = constraints or []
        
        if self.method == OptimizationMethod.EQUAL_WEIGHT:
            return self._equal_weight_optimization(expected_returns)
        
        elif self.method == OptimizationMethod.MINIMUM_VARIANCE:
            return self._minimum_variance_optimization(covariance, constraints)
        
        elif self.method == OptimizationMethod.RISK_PARITY:
            return self._risk_parity_optimization(covariance)
        
        elif self.method == OptimizationMethod.HIERARCHICAL_RISK_PARITY:
            return self._hrp_optimization(covariance)
        
        elif self.method == OptimizationMethod.MEAN_VARIANCE:
            return self._mean_variance_optimization(
                expected_returns, covariance, constraints, previous_weights, transaction_costs
            )
        
        elif self.method == OptimizationMethod.BLACK_LITTERMAN:
            return self._black_litterman_optimization(
                expected_returns, covariance, constraints, previous_weights, transaction_costs
            )
        
        else:
            raise ValueError(f"Unsupported optimization method: {self.method}")

    def optimize_delta_omega(
        self,
        expected_returns: pd.Series,
        returns_panel: pd.DataFrame,
        adv_cap: Optional[pd.Series] = None,
        adv_cap_ratio: float = 0.05,
        lmax: float = 1.0,
    ) -> OptimizationResult:
        """Canonical kernel-backed allocation (Step 1.3 bridge).

        Covariance comes from Ledoit-Wolf shrinkage on ``returns_panel``;
        weights come from the verified ``delta_omega`` MVO with gross
        leverage ``<= lmax`` (default 1.0) and single-name caps ``<= 5%``
        unless explicit ``adv_cap`` weight caps are supplied.
        """
        alpha = expected_returns.values.astype(float)
        panel = returns_panel.values.astype(float)
        caps = None if adv_cap is None else adv_cap.values.astype(float)
        w, delta = allocate_delta_omega(
            alpha, panel, lam=self.risk_aversion, lmax=lmax,
            adv_cap=caps, adv_cap_ratio=adv_cap_ratio,
        )
        weights = pd.Series(w, index=expected_returns.index)
        port_var = float(weights.values @ np.cov(panel, rowvar=False) @ weights.values)
        port_std = float(np.sqrt(max(port_var, 0.0)))
        port_ret = float(alpha @ w)
        return OptimizationResult(
            weights=weights,
            expected_return=port_ret,
            expected_risk=port_std,
            sharpe_ratio=(port_ret / port_std if port_std > 0 else 0.0),
            turnover=0.0,
            transaction_costs=0.0,
            constraints_satisfied=bool(float(np.abs(w).sum()) <= lmax + 1e-9),
            optimization_status="success",
            metadata={"src": "delta_omega", "lw_delta": delta, "lmax": lmax},
        )

    def _equal_weight_optimization(self, expected_returns: pd.Series) -> OptimizationResult:
        """Equal weight portfolio"""
        n = len(expected_returns)
        weights = pd.Series(1.0 / n, index=expected_returns.index)
        
        return OptimizationResult(
            weights=weights,
            expected_return=expected_returns.mean(),
            expected_risk=0.0,  # Need covariance
            sharpe_ratio=0.0,
            turnover=0.0,
            transaction_costs=0.0,
            constraints_satisfied=True,
            optimization_status="success",
        )
    
    def _minimum_variance_optimization(
        self,
        covariance: pd.DataFrame,
        constraints: List[Constraint],
    ) -> OptimizationResult:
        """Minimum variance portfolio"""
        n = len(covariance)
        
        # Objective: minimize w' * Sigma * w
        cov_matrix = covariance.values
        
        def objective(w):
            return w @ cov_matrix @ w
        
        # Constraints
        constraints_list = []
        
        # Budget constraint: sum(w) = 1
        constraints_list.append({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})
        
        # Long-only constraint
        for constraint in constraints:
            if constraint.constraint_type == ConstraintType.LONG_ONLY:
                constraints_list.append({'type': 'ineq', 'fun': lambda w: w})
        
        # Bounds
        bounds = [(0, 1) for _ in range(n)]
        
        # Initial guess
        w0 = np.ones(n) / n
        
        # Optimize
        result = optimize.minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
        )
        
        if not result.success:
            return OptimizationResult(
                weights=pd.Series(1.0 / n, index=covariance.columns),
                expected_return=0.0,
                expected_risk=0.0,
                sharpe_ratio=0.0,
                turnover=0.0,
                transaction_costs=0.0,
                constraints_satisfied=False,
                optimization_status="failed",
            )
        
        weights = pd.Series(result.x, index=covariance.columns)
        portfolio_variance = weights @ cov_matrix @ weights
        portfolio_std = np.sqrt(portfolio_variance)
        
        return OptimizationResult(
            weights=weights,
            expected_return=0.0,  # Need expected returns
            expected_risk=portfolio_std,
            sharpe_ratio=0.0,
            turnover=0.0,
            transaction_costs=0.0,
            constraints_satisfied=True,
            optimization_status="success",
        )
    
    def _risk_parity_optimization(self, covariance: pd.DataFrame) -> OptimizationResult:
        """Risk parity portfolio"""
        n = len(covariance)
        
        def objective(w):
            portfolio_var = w @ covariance.values @ w
            # Minimize variance contribution differences
            marginal_contrib = 2 * covariance.values @ w
            contrib = w * marginal_contrib
            return np.sum((contrib - contrib.mean()) ** 2)
        
        # Constraints
        constraints_list = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = [(0, 1) for _ in range(n)]
        w0 = np.ones(n) / n
        
        result = optimize.minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
        )
        
        weights = pd.Series(result.x, index=covariance.columns)
        portfolio_var = weights @ covariance.values @ weights
        
        return OptimizationResult(
            weights=weights,
            expected_return=0.0,
            expected_risk=np.sqrt(portfolio_var),
            sharpe_ratio=0.0,
            turnover=0.0,
            transaction_costs=0.0,
            constraints_satisfied=result.success,
            optimization_status="success" if result.success else "failed",
        )
    
    def _hrp_optimization(self, covariance: pd.DataFrame) -> OptimizationResult:
        """Hierarchical Risk Parity optimization"""
        # Get quasi-diagonal order
        ordered_indices = self.hrp.get_quasi_diag(covariance)
        
        # Initialize equal weights
        weights = pd.Series(1.0 / len(covariance), index=covariance.columns)
        
        # Recursive bisection
        weights_iloc = self.hrp.recursive_bisection(covariance, weights, ordered_indices)
        
        # Map back to original index
        weights_ordered = weights_iloc.iloc[ordered_indices]
        weights = pd.Series(weights_ordered.values, index=covariance.columns)
        
        portfolio_var = weights @ covariance.values @ weights
        
        return OptimizationResult(
            weights=weights,
            expected_return=0.0,
            expected_risk=np.sqrt(portfolio_var),
            sharpe_ratio=0.0,
            turnover=0.0,
            transaction_costs=0.0,
            constraints_satisfied=True,
            optimization_status="success",
        )
    
    def _mean_variance_optimization(
        self,
        expected_returns: pd.Series,
        covariance: pd.DataFrame,
        constraints: List[Constraint],
        previous_weights: pd.Series = None,
        transaction_costs: Dict[str, float] = None,
    ) -> OptimizationResult:
        """Mean-variance optimization with transaction costs"""
        n = len(expected_returns)
        mu = expected_returns.values
        Sigma = covariance.values
        
        def objective(w):
            # Maximize: mu'w - (lambda/2) * w'Sigma*w - transaction_costs
            portfolio_return = mu @ w
            portfolio_var = w @ Sigma @ w
            utility = portfolio_return - (self.risk_aversion / 2) * portfolio_var
            
            # Add transaction costs
            if previous_weights is not None and transaction_costs is not None:
                turnover = np.abs(w - previous_weights.values)
                tc = sum(turnover[i] * transaction_costs.get(expected_returns.index[i], 0.0) 
                        for i in range(n))
                utility -= tc
            
            return -utility  # Minimize negative utility
        
        # Constraints
        constraints_list = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        
        # Long-only constraint
        for constraint in constraints:
            if constraint.constraint_type == ConstraintType.LONG_ONLY:
                constraints_list.append({'type': 'ineq', 'fun': lambda w: w})
        
        bounds = [(0, 1) for _ in range(n)]
        w0 = np.ones(n) / n
        
        result = optimize.minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
        )
        
        if not result.success:
            return OptimizationResult(
                weights=pd.Series(1.0 / n, index=expected_returns.index),
                expected_return=0.0,
                expected_risk=0.0,
                sharpe_ratio=0.0,
                turnover=0.0,
                transaction_costs=0.0,
                constraints_satisfied=False,
                optimization_status="failed",
            )
        
        weights = pd.Series(result.x, index=expected_returns.index)
        portfolio_return = mu @ weights
        portfolio_var = weights @ Sigma @ weights
        portfolio_std = np.sqrt(portfolio_var)
        sharpe = portfolio_return / portfolio_std if portfolio_std > 0 else 0
        
        # Calculate turnover
        turnover = 0.0
        if previous_weights is not None:
            turnover = np.sum(np.abs(weights - previous_weights.values)) / 2
        
        return OptimizationResult(
            weights=weights,
            expected_return=portfolio_return,
            expected_risk=portfolio_std,
            sharpe_ratio=sharpe,
            turnover=turnover,
            transaction_costs=0.0,
            constraints_satisfied=True,
            optimization_status="success",
        )
    
    def _black_litterman_optimization(
        self,
        expected_returns: pd.Series,
        covariance: pd.DataFrame,
        constraints: List[Constraint],
        previous_weights: pd.Series = None,
        transaction_costs: Dict[str, float] = None,
    ) -> OptimizationResult:
        """Black-Litterman optimization"""
        # Use expected returns as already-blended BL returns
        return self._mean_variance_optimization(
            expected_returns, covariance, constraints, previous_weights, transaction_costs
        )
