"""
Risk engine with Kelly sizing, VaR, CVaR calculations
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class VaRResult:
    """Value at Risk calculation result"""
    var_95: float  # 95% VaR
    var_99: float  # 99% VaR
    cvar_95: float  # 95% Conditional VaR (Expected Shortfall)
    cvar_99: float  # 99% Conditional VaR
    confidence_levels: List[float]


@dataclass
class KellyResult:
    """Kelly Criterion calculation result"""
    kelly_fraction: float
    quarter_kelly: float
    half_kelly: float
    win_probability: float
    payout_ratio: float
    expected_value: float


class RiskEngine:
    """Advanced risk calculations for position sizing and portfolio risk"""
    
    def __init__(self):
        self.return_history: Dict[str, List[float]] = {}
    
    def calculate_var(self, returns: List[float], 
                     confidence_levels: List[float] = [0.95, 0.99]) -> VaRResult:
        """Calculate parametric VaR and CVaR using historical simulation"""
        if not returns or len(returns) < 2:
            raise ValueError("Insufficient return data")
        
        returns_array = np.array(returns)
        
        var_results = {}
        cvar_results = {}
        
        for confidence in confidence_levels:
            alpha = 1 - confidence
            
            # Historical VaR
            var = np.percentile(returns_array, alpha * 100)
            var_results[confidence] = var
            
            # Conditional VaR (Expected Shortfall)
            # Average of returns that are worse than VaR
            tail_returns = returns_array[returns_array <= var]
            if len(tail_returns) > 0:
                cvar = np.mean(tail_returns)
            else:
                cvar = var
            cvar_results[confidence] = cvar
        
        return VaRResult(
            var_95=var_results.get(0.95, 0),
            var_99=var_results.get(0.99, 0),
            cvar_95=cvar_results.get(0.95, 0),
            cvar_99=cvar_results.get(0.99, 0),
            confidence_levels=confidence_levels
        )
    
    def calculate_var_portfolio(self, returns_matrix: pd.DataFrame,
                               weights: np.ndarray,
                               confidence_levels: List[float] = [0.95, 0.99]) -> VaRResult:
        """Calculate portfolio VaR using covariance matrix"""
        if returns_matrix.empty or len(weights) != len(returns_matrix.columns):
            raise ValueError("Invalid returns matrix or weights")
        
        # Calculate portfolio returns
        portfolio_returns = (returns_matrix * weights).sum(axis=1)
        
        return self.calculate_var(portfolio_returns.tolist(), confidence_levels)
    
    def calculate_kelly_criterion(self, win_probability: float, 
                                 payout_ratio: float,
                                 safety_fraction: float = 0.25) -> KellyResult:
        """Calculate Kelly Criterion for optimal position sizing"""
        if not (0 <= win_probability <= 1):
            raise ValueError("Win probability must be between 0 and 1")
        
        if payout_ratio <= 0:
            raise ValueError("Payout ratio must be positive")
        
        lose_probability = 1 - win_probability
        
        # Kelly Criterion: f* = (p*b - q) / b
        kelly_fraction = (win_probability * payout_ratio - lose_probability) / payout_ratio
        
        # Ensure non-negative
        kelly_fraction = max(0, kelly_fraction)
        
        # Apply safety fraction
        quarter_kelly = kelly_fraction * 0.25
        half_kelly = kelly_fraction * 0.5
        
        # Calculate expected value
        expected_value = (win_probability * payout_ratio) - lose_probability
        
        return KellyResult(
            kelly_fraction=kelly_fraction,
            quarter_kelly=quarter_kelly,
            half_kelly=half_kelly,
            win_probability=win_probability,
            payout_ratio=payout_ratio,
            expected_value=expected_value
        )
    
    def calculate_optimal_position_size(self, account_value: float,
                                       current_price: float,
                                       kelly_result: KellyResult,
                                       safety_fraction: float = 0.25) -> int:
        """Calculate optimal position size using Kelly Criterion"""
        # Use quarter or half Kelly for safety
        adjusted_kelly = kelly_result.quarter_kelly if safety_fraction == 0.25 else kelly_result.half_kelly
        
        # Calculate position value
        position_value = account_value * adjusted_kelly
        
        # Calculate number of shares
        shares = int(position_value / current_price)
        
        # Ensure minimum of 1 share
        shares = max(1, shares)
        
        return shares
    
    def calculate_max_drawdown(self, equity_curve: List[float]) -> Dict[str, float]:
        """Calculate maximum drawdown and drawdown duration"""
        if not equity_curve or len(equity_curve) < 2:
            return {"max_drawdown": 0.0, "max_drawdown_pct": 0.0, "duration": 0}
        
        equity_array = np.array(equity_curve)
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_array)
        
        # Calculate drawdown
        drawdown = (equity_array - running_max) / running_max
        
        # Find maximum drawdown
        max_drawdown_idx = np.argmin(drawdown)
        max_drawdown = drawdown[max_drawdown_idx]
        
        # Calculate duration (in periods)
        peak_idx = np.argmax(equity_array[:max_drawdown_idx])
        duration = max_drawdown_idx - peak_idx
        
        return {
            "max_drawdown": abs(max_drawdown),
            "max_drawdown_pct": abs(max_drawdown) * 100,
            "duration": duration,
            "peak_value": equity_array[peak_idx],
            "trough_value": equity_array[max_drawdown_idx]
        }
    
    def calculate_sharpe_ratio(self, returns: List[float], 
                              risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe Ratio"""
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        
        # Calculate excess returns (annualized)
        excess_returns = returns_array - (risk_free_rate / 252)  # Daily risk-free rate
        
        # Calculate Sharpe Ratio
        if np.std(excess_returns) == 0:
            return 0.0
        
        sharpe = np.mean(excess_returns) / np.std(excess_returns)
        
        # Annualize
        sharpe_annualized = sharpe * np.sqrt(252)
        
        return sharpe_annualized
    
    def calculate_sortino_ratio(self, returns: List[float],
                               risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino Ratio (downside risk only)"""
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        
        # Calculate excess returns
        excess_returns = returns_array - (risk_free_rate / 252)
        
        # Calculate downside deviation
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) == 0:
            return 0.0
        
        downside_deviation = np.std(downside_returns)
        
        if downside_deviation == 0:
            return 0.0
        
        # Calculate Sortino Ratio
        sortino = np.mean(excess_returns) / downside_deviation
        
        # Annualize
        sortino_annualized = sortino * np.sqrt(252)
        
        return sortino_annualized
    
    def calculate_beta(self, asset_returns: List[float], 
                      market_returns: List[float]) -> float:
        """Calculate beta relative to market"""
        if len(asset_returns) != len(market_returns) or len(asset_returns) < 2:
            return 1.0  # Default to market beta
        
        asset_array = np.array(asset_returns)
        market_array = np.array(market_returns)
        
        # Calculate covariance and variance
        covariance = np.cov(asset_array, market_array)[0, 1]
        market_variance = np.var(market_array)
        
        if market_variance == 0:
            return 1.0
        
        beta = covariance / market_variance
        return beta
    
    def calculate_correlation_matrix(self, returns_data: Dict[str, List[float]]) -> pd.DataFrame:
        """Calculate correlation matrix for multiple assets"""
        df = pd.DataFrame(returns_data)
        return df.corr()
    
    def calculate_portfolio_risk(self, weights: np.ndarray,
                                covariance_matrix: pd.DataFrame) -> Dict[str, float]:
        """Calculate portfolio risk metrics"""
        if len(weights) != len(covariance_matrix.columns):
            raise ValueError("Weights and covariance matrix dimensions don't match")
        
        # Portfolio variance
        portfolio_variance = np.dot(weights.T, np.dot(covariance_matrix.values, weights))
        portfolio_std = np.sqrt(portfolio_variance)
        
        # Annualize (assuming daily returns)
        portfolio_std_annual = portfolio_std * np.sqrt(252)
        
        return {
            "portfolio_variance": portfolio_variance,
            "portfolio_std": portfolio_std,
            "portfolio_std_annual": portfolio_std_annual,
            "portfolio_volatility": portfolio_std_annual * 100  # As percentage
        }
    
    def calculate_risk_parity_weights(self, covariance_matrix: pd.DataFrame) -> np.ndarray:
        """Calculate risk parity weights (inverse volatility weighting)"""
        # Calculate diagonal of covariance matrix (variances)
        variances = np.diag(covariance_matrix.values)
        volatilities = np.sqrt(variances)
        
        # Inverse volatility weights
        inv_vol = 1 / volatilities
        weights = inv_vol / np.sum(inv_vol)
        
        return weights
