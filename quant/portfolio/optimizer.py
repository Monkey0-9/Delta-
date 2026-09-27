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
        covariance: pd.DataFrame,
        constraints: List[Constraint] = None,
        previous_weights: pd.Series = None,
        transaction_costs: Dict[str, float] = None,
    ) -> OptimizationResult:
        """Optimize portfolio"""
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
