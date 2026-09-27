"""
Institutional-grade market impact modeling.

This implements production-quality market impact models:
- Almgren-Chriss impact model (permanent + temporary)
- Kyle lambda model (market depth)
- Linear and non-linear impact
- Volume participation rate effects
- Market condition adjustments
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
import math


class ImpactModelType(Enum):
    """Market impact model types."""
    ALMGREN_CHRISS = "ALMGREN_CHRISS"
    KYLE_LAMBDA = "KYLE_LAMBDA"
    LINEAR = "LINEAR"
    SQUARE_ROOT = "SQUARE_ROOT"


__all__ = [
    "ImpactModelType",
    "ImpactParameters",
    "ImpactEstimate",
    "MarketImpactModel",
    "AlmgrenChrissImpact",
    "KyleLambdaImpact",
    "LinearImpact",
    "SquareRootImpact",
    "ImpactModelFactory"
]


@dataclass
class ImpactParameters:
    """
    Parameters for market impact model.
    """
    permanent_impact_coef: float  # Permanent impact coefficient
    temporary_impact_coef: float  # Temporary impact coefficient
    volatility: float  # Asset volatility
    avg_daily_volume: float  # Average daily volume
    spread_bps: float  # Spread in basis points
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "permanent_impact_coef": self.permanent_impact_coef,
            "temporary_impact_coef": self.temporary_impact_coef,
            "volatility": self.volatility,
            "avg_daily_volume": self.avg_daily_volume,
            "spread_bps": self.spread_bps
        }


@dataclass
class ImpactEstimate:
    """
    Market impact estimate.
    """
    permanent_impact_bps: float
    temporary_impact_bps: float
    total_impact_bps: float
    execution_price: float
    arrival_price: float
    participation_rate: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MarketImpactModel:
    """
    Base class for market impact models.
    """
    
    def __init__(self, params: ImpactParameters):
        self.params = params
    
    def calculate_impact(self,
                       order_side: str,
                       order_quantity: float,
                       current_price: float,
                       participation_rate: float) -> ImpactEstimate:
        """
        Calculate market impact for an order.
        
        Args:
            order_side: "BUY" or "SELL"
            order_quantity: Order quantity
            current_price: Current market price
            participation_rate: Order size as fraction of ADV
        
        Returns:
            ImpactEstimate with impact components
        """
        raise NotImplementedError("Subclasses must implement calculate_impact")


class AlmgrenChrissImpact(MarketImpactModel):
    """
    Almgren-Chriss market impact model.
    
    Models permanent and temporary impact:
    - Permanent impact: γ * σ * sqrt(ADV) * participation_rate
    - Temporary impact: η * σ * sqrt(ADV) * participation_rate
    
    Where:
    - γ: permanent impact coefficient
    - η: temporary impact coefficient  
    - σ: volatility
    - ADV: average daily volume
    """
    
    def calculate_impact(self,
                       order_side: str,
                       order_quantity: float,
                       current_price: float,
                       participation_rate: float) -> ImpactEstimate:
        """
        Calculate Almgren-Chriss impact.
        """
        # Calculate square root of participation rate
        sqrt_participation = math.sqrt(participation_rate)
        
        # Calculate volatility factor
        vol_factor = self.params.volatility * math.sqrt(self.params.avg_daily_volume)
        
        # Permanent impact (linear in participation rate)
        permanent_impact = (
            self.params.permanent_impact_coef * 
            vol_factor * 
            participation_rate
        )
        
        # Temporary impact (square root of participation rate)
        temporary_impact = (
            self.params.temporary_impact_coef * 
            vol_factor * 
            sqrt_participation
        )
        
        # Convert to basis points
        permanent_impact_bps = permanent_impact / current_price * 10000
        temporary_impact_bps = temporary_impact / current_price * 10000
        
        # Total impact
        total_impact_bps = permanent_impact_bps + temporary_impact_bps
        
        # Calculate execution price
        if order_side == "BUY":
            # Buyers pay more
            execution_price = current_price * (1 + total_impact_bps / 10000)
        else:
            # Sellers receive less
            execution_price = current_price * (1 - total_impact_bps / 10000)
        
        arrival_price = current_price
        
        return ImpactEstimate(
            permanent_impact_bps=permanent_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            total_impact_bps=total_impact_bps,
            execution_price=execution_price,
            arrival_price=arrival_price,
            participation_rate=participation_rate
        )


class KyleLambdaImpact(MarketImpactModel):
    """
    Kyle lambda market impact model.
    
    Models market depth:
    - Impact = λ * order_size / ADV
    - Where λ is the market depth parameter
    """
    
    def __init__(self, params: ImpactParameters, lambda_param: float = 0.001):
        super().__init__(params)
        self.lambda_param = lambda_param
    
    def calculate_impact(self,
                       order_side: str,
                       order_quantity: float,
                       current_price: float,
                       participation_rate: float) -> ImpactEstimate:
        """
        Calculate Kyle lambda impact.
        """
        # Kyle model: impact = λ * (order_size / ADV)
        impact_fraction = self.lambda_param * participation_rate
        
        # Convert to basis points
        total_impact_bps = impact_fraction * 10000
        
        # Kyle model primarily models temporary impact
        permanent_impact_bps = total_impact_bps * 0.3  # 30% permanent
        temporary_impact_bps = total_impact_bps * 0.7  # 70% temporary
        
        # Calculate execution price
        if order_side == "BUY":
            execution_price = current_price * (1 + total_impact_bps / 10000)
        else:
            execution_price = current_price * (1 - total_impact_bps / 10000)
        
        arrival_price = current_price
        
        return ImpactEstimate(
            permanent_impact_bps=permanent_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            total_impact_bps=total_impact_bps,
            execution_price=execution_price,
            arrival_price=arrival_price,
            participation_rate=participation_rate
        )


class LinearImpact(MarketImpactModel):
    """
    Linear market impact model.
    
    Simple linear relationship: impact = α * participation_rate
    """
    
    def calculate_impact(self,
                       order_side: str,
                       order_quantity: float,
                       current_price: float,
                       participation_rate: float) -> ImpactEstimate:
        """
        Calculate linear impact.
        """
        # Linear impact
        total_impact_bps = (
            self.params.permanent_impact_coef * 
            participation_rate * 
            10000
        )
        
        # Split between permanent and temporary
        permanent_impact_bps = total_impact_bps * 0.4
        temporary_impact_bps = total_impact_bps * 0.6
        
        # Calculate execution price
        if order_side == "BUY":
            execution_price = current_price * (1 + total_impact_bps / 10000)
        else:
            execution_price = current_price * (1 - total_impact_bps / 10000)
        
        arrival_price = current_price
        
        return ImpactEstimate(
            permanent_impact_bps=permanent_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            total_impact_bps=total_impact_bps,
            execution_price=execution_price,
            arrival_price=arrival_price,
            participation_rate=participation_rate
        )


class SquareRootImpact(MarketImpactModel):
    """
    Square root market impact model.
    
    Impact scales with square root of order size: impact = α * sqrt(participation_rate)
    """
    
    def calculate_impact(self,
                       order_side: str,
                       order_quantity: float,
                       current_price: float,
                       participation_rate: float) -> ImpactEstimate:
        """
        Calculate square root impact.
        """
        # Square root impact
        sqrt_participation = math.sqrt(participation_rate)
        total_impact_bps = (
            self.params.permanent_impact_coef * 
            sqrt_participation * 
            10000
        )
        
        # Split between permanent and temporary
        permanent_impact_bps = total_impact_bps * 0.35
        temporary_impact_bps = total_impact_bps * 0.65
        
        # Calculate execution price
        if order_side == "BUY":
            execution_price = current_price * (1 + total_impact_bps / 10000)
        else:
            execution_price = current_price * (1 - total_impact_bps / 10000)
        
        arrival_price = current_price
        
        return ImpactEstimate(
            permanent_impact_bps=permanent_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            total_impact_bps=total_impact_bps,
            execution_price=execution_price,
            arrival_price=arrival_price,
            participation_rate=participation_rate
        )


class ImpactModelFactory:
    """
    Factory for creating market impact models.
    """
    
    @staticmethod
    def create_model(model_type: ImpactModelType, 
                   params: ImpactParameters,
                   **kwargs) -> MarketImpactModel:
        """
        Create market impact model.
        
        Args:
            model_type: Type of impact model
            params: Impact parameters
            **kwargs: Additional model-specific parameters
            
        Returns:
            MarketImpactModel instance
        """
        if model_type == ImpactModelType.ALMGREN_CHRISS:
            return AlmgrenChrissImpact(params)
        elif model_type == ImpactModelType.KYLE_LAMBDA:
            lambda_param = kwargs.get('lambda_param', 0.001)
            return KyleLambdaImpact(params, lambda_param)
        elif model_type == ImpactModelType.LINEAR:
            return LinearImpact(params)
        elif model_type == ImpactModelType.SQUARE_ROOT:
            return SquareRootImpact(params)
        else:
            raise ValueError(f"Unknown impact model type: {model_type}")
    
    @staticmethod
    def get_default_params(volatility: float = 0.02,
                         avg_daily_volume: float = 1_000_000,
                         spread_bps: float = 5.0) -> ImpactParameters:
        """
        Get default impact parameters.
        
        Args:
            volatility: Asset volatility (daily)
            avg_daily_volume: Average daily volume
            spread_bps: Spread in basis points
            
        Returns:
            Default ImpactParameters
        """
        return ImpactParameters(
            permanent_impact_coef=0.001,  # Typical permanent impact coefficient
            temporary_impact_coef=0.01,   # Typical temporary impact coefficient
            volatility=volatility,
            avg_daily_volume=avg_daily_volume,
            spread_bps=spread_bps
        )