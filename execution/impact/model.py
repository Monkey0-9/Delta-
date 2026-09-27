"""Market Impact Models for execution simulation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
import numpy as np


class ImpactModelType(StrEnum):
    """Types of market impact models."""
    ALMGREN_CHRISS = "almgren_chriss"
    KYLE_LAMBDA = "kyle_lambda"
    SQUARE_ROOT = "square_root"
    LINEAR = "linear"


@dataclass(frozen=True, slots=True)
class ImpactParameters:
    """Parameters for market impact models."""
    gamma: float = 0.1  # Temporary impact coefficient
    eta: float = 0.05  # Permanent impact coefficient
    sigma: float = 0.02  # Volatility
    adv: float = 1_000_000.0  # Average daily volume
    tau: float = 1.0  # Trading horizon in days


class MarketImpactModel:
    """Base class for market impact models."""
    
    def __init__(self, params: ImpactParameters) -> None:
        self._params = params
    
    def calculate_impact(
        self,
        order_size: float,
        price: float
    ) -> dict[str, float]:
        """Calculate market impact for an order."""
        raise NotImplementedError
    
    def calculate_temporary_impact(
        self,
        participation_rate: float
    ) -> float:
        """Calculate temporary market impact."""
        raise NotImplementedError
    
    def calculate_permanent_impact(
        self,
        participation_rate: float
    ) -> float:
        """Calculate permanent market impact."""
        raise NotImplementedError


class AlmgrenChrissModel(MarketImpactModel):
    """
    Almgren-Chriss market impact model.
    
    Models both temporary and permanent impact:
    - Temporary impact: decays with time, related to execution speed
    - Permanent impact: persists, related to total order size
    
    Formula:
        ΔP = γσ√(V/ADV) + ησ(V/ADV)
    
    where:
    - γ: temporary impact coefficient
    - η: permanent impact coefficient
    - σ: volatility
    - V: order volume
    - ADV: average daily volume
    """
    
    def calculate_impact(
        self,
        order_size: float,
        price: float
    ) -> dict[str, float]:
        """Calculate total market impact using Almgren-Chriss model."""
        params = self._params
        
        # Calculate participation rate
        participation_rate = order_size / params.adv if params.adv > 0 else 0
        
        # Calculate temporary impact
        temp_impact = self.calculate_temporary_impact(participation_rate)
        
        # Calculate permanent impact
        perm_impact = self.calculate_permanent_impact(participation_rate)
        
        # Total impact
        total_impact = temp_impact + perm_impact
        
        # Price impact in currency units
        price_impact = price * total_impact
        
        return {
            "temporary_impact_bps": temp_impact * 10000,
            "permanent_impact_bps": perm_impact * 10000,
            "total_impact_bps": total_impact * 10000,
            "price_impact": price_impact,
            "participation_rate": participation_rate,
        }
    
    def calculate_temporary_impact(
        self,
        participation_rate: float
    ) -> float:
        """
        Calculate temporary market impact.
        
        Formula: γσ√(V/ADV)
        """
        params = self._params
        
        if participation_rate <= 0:
            return 0.0
        
        # Square root impact
        sqrt_participation = np.sqrt(participation_rate)
        
        # Temporary impact
        temp_impact = params.gamma * params.sigma * sqrt_participation
        
        return temp_impact
    
    def calculate_permanent_impact(
        self,
        participation_rate: float
    ) -> float:
        """
        Calculate permanent market impact.
        
        Formula: ησ(V/ADV)
        """
        params = self._params
        
        if participation_rate <= 0:
            return 0.0
        
        # Linear impact
        perm_impact = params.eta * params.sigma * participation_rate
        
        return perm_impact


class KyleLambdaModel(MarketImpactModel):
    """
    Kyle's Lambda model for market impact.
    
    Models how informed traders' order flow affects prices.
    
    Formula:
        λ = ΔP / V = 1 / (2 * depth)
    
    where depth is the market depth parameter.
    """
    
    def __init__(self, params: ImpactParameters, market_depth: float = 1000000.0) -> None:
        super().__init__(params)
        self._market_depth = market_depth
    
    def calculate_impact(
        self,
        order_size: float,
        price: float
    ) -> dict[str, float]:
        """Calculate market impact using Kyle's Lambda model."""
        # Lambda parameter
        lambda_param = 1.0 / (2 * self._market_depth)
        
        # Price impact
        price_impact = lambda_param * order_size
        
        # Convert to basis points
        impact_bps = (price_impact / price) * 10000 if price > 0 else 0
        
        return {
            "lambda": lambda_param,
            "price_impact": price_impact,
            "impact_bps": impact_bps,
            "market_depth": self._market_depth,
        }
    
    def calculate_temporary_impact(self, participation_rate: float) -> float:
        """Kyle model doesn't distinguish temporary vs permanent."""
        return 0.0
    
    def calculate_permanent_impact(self, participation_rate: float) -> float:
        """Kyle model doesn't distinguish temporary vs permanent."""
        return 0.0
