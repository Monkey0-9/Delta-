"""
Calibrated Market Impact Model for Execution Simulation.

This module implements realistic market impact modeling based on:
- Almgren-Chriss model (linear impact)
- Permanent vs temporary impact
- Volume-based impact
- Volatility-adjusted impact
- Venue-specific impact characteristics

Market impact is the cost incurred when trading due to:
1. Information leakage (permanent impact)
2. Liquidity consumption (temporary impact)
3. Price movement during execution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Tuple
import numpy as np

from core.contracts.canonical import Instrument, Currency, Side


class ImpactModel(Enum):
    """Market impact model types."""
    ALMGREN_CHRISS = "almgren_chriss"  # Linear impact model
    SQUARE_ROOT = "square_root"  # Square root law
    POWER_LAW = "power_law"  # General power law
    NONLINEAR = "nonlinear"  # Nonlinear model


class ImpactType(Enum):
    """Types of market impact."""
    PERMANENT = "permanent"  # Permanent price impact
    TEMPORARY = "temporary"  # Temporary price impact (recovers)
    TOTAL = "total"  # Total impact


@dataclass(frozen=True, slots=True)
class ImpactParameters:
    """
    Parameters for market impact calculation.
    
    Based on empirical studies of market impact:
    - Almgren-Chriss (2000): Linear impact model
    - Kyle (1985): Temporary impact model
    - Gatheral (2010): Square root law
    """
    # Permanent impact parameters
    permanent_impact_coefficient: float = 0.001  # Linear coefficient
    permanent_impact_power: float = 1.0  # Power law exponent
    
    # Temporary impact parameters
    temporary_impact_coefficient: float = 0.005  # Linear coefficient
    temporary_impact_power: float = 0.5  # Square root law typical
    
    # Volatility adjustment
    volatility_sensitivity: float = 0.5  # Impact scales with volatility
    
    # Volume adjustment
    volume_sensitivity: float = 0.8  # Impact scales with participation rate
    
    # Time adjustment
    time_decay: float = 0.1  # Impact decays over time
    
    # Venue-specific adjustments
    venue_adjustments: Dict[str, float] = field(default_factory=dict)


@dataclass
class ImpactMeasurement:
    """
    Individual market impact measurement.
    
    Attributes:
        timestamp: When the measurement was taken
        instrument: Instrument traded
        side: Order side
        quantity: Order quantity
        execution_price: Average execution price
        arrival_price: Price at order arrival
        permanent_impact_bps: Permanent impact in basis points
        temporary_impact_bps: Temporary impact in basis points
        total_impact_bps: Total impact in basis points
        participation_rate: Order participation rate
        volatility: Market volatility at execution
        venue: Execution venue
        metadata: Additional metadata
    """
    timestamp: datetime
    instrument: Instrument
    side: Side
    quantity: Decimal
    execution_price: Decimal
    arrival_price: Decimal
    permanent_impact_bps: float
    temporary_impact_bps: float
    total_impact_bps: float
    participation_rate: float
    volatility: float
    venue: str
    metadata: Dict = field(default_factory=dict)
    
    @property
    def price_impact(self) -> Decimal:
        """Price impact in currency units."""
        return (self.execution_price - self.arrival_price) * self.quantity
    
    @property
    def slippage_bps(self) -> float:
        """Slippage in basis points."""
        if self.side == Side.BUY:
            return float((self.execution_price - self.arrival_price) / self.arrival_price * 10000)
        else:
            return float((self.arrival_price - self.execution_price) / self.arrival_price * 10000)


class MarketImpactModel:
    """
    Calibrated market impact model for execution simulation.
    
    Features:
    - Multiple impact models (Almgren-Chriss, square root, power law)
    - Permanent vs temporary impact separation
    - Volatility and volume adjustments
    - Venue-specific impact characteristics
    - Historical impact analysis
    """
    
    # Default impact parameters (based on empirical studies)
    DEFAULT_PARAMETERS = ImpactParameters()
    
    # Typical participation rates by venue
    TYPICAL_PARTICIPATION_RATES: Dict[str, float] = {
        "NYSE": 0.15,  # 15% average participation
        "NASDAQ": 0.12,
        "ARCA": 0.10,
        "BATS": 0.08,
        "DARK_POOL": 0.25,  # Higher participation in dark pools
    }
    
    def __init__(
        self,
        parameters: Optional[ImpactParameters] = None,
        model_type: ImpactModel = ImpactModel.SQUARE_ROOT
    ):
        """
        Initialize market impact model.
        
        Args:
            parameters: Impact parameters (uses defaults if None)
            model_type: Impact model to use
        """
        self._parameters = parameters or self.DEFAULT_PARAMETERS
        self._model_type = model_type
        
        # Impact history for analysis
        self._measurements: List[ImpactMeasurement] = []
        
        # Random seed for reproducibility
        self._seed = 42
        
    def calculate_impact(
        self,
        instrument: Instrument,
        side: Side,
        quantity: Decimal,
        arrival_price: Decimal,
        avg_daily_volume: Decimal,
        volatility: float = 0.2,
        participation_rate: Optional[float] = None,
        venue: str = "NYSE",
        execution_time_seconds: float = 1.0
    ) -> Tuple[float, float, float]:
        """
        Calculate market impact for an order.
        
        Args:
            instrument: Instrument being traded
            side: Order side
            quantity: Order quantity
            arrival_price: Price at order arrival
            avg_daily_volume: Average daily volume
            volatility: Market volatility (annualized)
            participation_rate: Order participation rate (optional)
            venue: Execution venue
            execution_time_seconds: Time to execute order
            
        Returns:
            Tuple of (permanent_impact_bps, temporary_impact_bps, total_impact_bps)
        """
        # Calculate participation rate if not provided
        if participation_rate is None:
            participation_rate = self.TYPICAL_PARTICIPATION_RATES.get(
                venue, 0.10
            )
        
        # Normalize quantity relative to ADV
        quantity_ratio = float(quantity / avg_daily_volume)
        
        # Adjust for volatility
        vol_adjustment = 1.0 + (volatility - 0.2) * self._parameters.volatility_sensitivity
        
        # Adjust for participation rate
        participation_adjustment = participation_rate ** self._parameters.volume_sensitivity
        
        # Calculate permanent impact
        if self._model_type == ImpactModel.ALMGREN_CHRISS:
            # Linear impact model
            permanent_impact = (
                self._parameters.permanent_impact_coefficient *
                quantity_ratio *
                vol_adjustment *
                participation_adjustment
            )
        elif self._model_type == ImpactModel.SQUARE_ROOT:
            # Square root law
            permanent_impact = (
                self._parameters.permanent_impact_coefficient *
                np.sqrt(quantity_ratio) *
                vol_adjustment *
                participation_adjustment
            )
        elif self._model_type == ImpactModel.POWER_LAW:
            # General power law
            permanent_impact = (
                self._parameters.permanent_impact_coefficient *
                (quantity_ratio ** self._parameters.permanent_impact_power) *
                vol_adjustment *
                participation_adjustment
            )
        else:
            # Default to square root
            permanent_impact = (
                self._parameters.permanent_impact_coefficient *
                np.sqrt(quantity_ratio) *
                vol_adjustment *
                participation_adjustment
            )
        
        # Calculate temporary impact
        if self._model_type == ImpactModel.ALMGREN_CHRISS:
            temporary_impact = (
                self._parameters.temporary_impact_coefficient *
                quantity_ratio *
                vol_adjustment *
                participation_adjustment *
                np.exp(-self._parameters.time_decay * execution_time_seconds)
            )
        elif self._model_type == ImpactModel.SQUARE_ROOT:
            temporary_impact = (
                self._parameters.temporary_impact_coefficient *
                np.sqrt(quantity_ratio) *
                vol_adjustment *
                participation_adjustment *
                np.exp(-self._parameters.time_decay * execution_time_seconds)
            )
        elif self._model_type == ImpactModel.POWER_LAW:
            temporary_impact = (
                self._parameters.temporary_impact_coefficient *
                (quantity_ratio ** self._parameters.temporary_impact_power) *
                vol_adjustment *
                participation_adjustment *
                np.exp(-self._parameters.time_decay * execution_time_seconds)
            )
        else:
            temporary_impact = (
                self._parameters.temporary_impact_coefficient *
                np.sqrt(quantity_ratio) *
                vol_adjustment *
                participation_adjustment *
                np.exp(-self._parameters.time_decay * execution_time_seconds)
            )
        
        # Apply venue adjustment if specified
        venue_adjustment = self._parameters.venue_adjustments.get(venue, 1.0)
        permanent_impact *= venue_adjustment
        temporary_impact *= venue_adjustment
        
        # Convert to basis points
        permanent_impact_bps = permanent_impact * 10000
        temporary_impact_bps = temporary_impact * 10000
        total_impact_bps = permanent_impact_bps + temporary_impact_bps
        
        return permanent_impact_bps, temporary_impact_bps, total_impact_bps
    
    def record_execution(
        self,
        instrument: Instrument,
        side: Side,
        quantity: Decimal,
        execution_price: Decimal,
        arrival_price: Decimal,
        avg_daily_volume: Decimal,
        volatility: float = 0.2,
        venue: str = "NYSE"
    ) -> ImpactMeasurement:
        """
        Record an execution and calculate actual impact.
        
        Args:
            instrument: Instrument traded
            side: Order side
            quantity: Order quantity
            execution_price: Average execution price
            arrival_price: Price at order arrival
            avg_daily_volume: Average daily volume
            volatility: Market volatility
            venue: Execution venue
            
        Returns:
            ImpactMeasurement with calculated impact
        """
        # Calculate participation rate
        participation_rate = float(quantity / avg_daily_volume)
        
        # Calculate actual slippage
        if side == Side.BUY:
            actual_slippage_bps = float(
                (execution_price - arrival_price) / arrival_price * 10000
            )
        else:
            actual_slippage_bps = float(
                (arrival_price - execution_price) / arrival_price * 10000
            )
        
        # Estimate permanent vs temporary impact
        # (In practice, this requires post-trade analysis)
        permanent_impact_bps = actual_slippage_bps * 0.3  # 30% permanent
        temporary_impact_bps = actual_slippage_bps * 0.7  # 70% temporary
        total_impact_bps = actual_slippage_bps
        
        measurement = ImpactMeasurement(
            timestamp=datetime.now(timezone.utc),
            instrument=instrument,
            side=side,
            quantity=quantity,
            execution_price=execution_price,
            arrival_price=arrival_price,
            permanent_impact_bps=permanent_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            total_impact_bps=total_impact_bps,
            participation_rate=participation_rate,
            volatility=volatility,
            venue=venue
        )
        
        self._measurements.append(measurement)
        return measurement
    
    def get_impact_summary(
        self,
        instrument: Optional[Instrument] = None,
        venue: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get impact summary statistics.
        
        Args:
            instrument: Filter by instrument (optional)
            venue: Filter by venue (optional)
            
        Returns:
            Dictionary with summary statistics
        """
        filtered = self._measurements
        
        if instrument is not None:
            filtered = [m for m in filtered if m.instrument == instrument]
        
        if venue is not None:
            filtered = [m for m in filtered if m.venue == venue]
        
        if not filtered:
            return {
                "count": 0,
                "mean_total_impact_bps": 0.0,
                "std_total_impact_bps": 0.0,
                "mean_permanent_impact_bps": 0.0,
                "mean_temporary_impact_bps": 0.0,
                "mean_participation_rate": 0.0,
                "mean_slippage_bps": 0.0,
            }
        
        total_impacts = [m.total_impact_bps for m in filtered]
        permanent_impacts = [m.permanent_impact_bps for m in filtered]
        temporary_impacts = [m.temporary_impact_bps for m in filtered]
        participation_rates = [m.participation_rate for m in filtered]
        slippages = [m.slippage_bps for m in filtered]
        
        return {
            "count": len(filtered),
            "mean_total_impact_bps": float(np.mean(total_impacts)),
            "std_total_impact_bps": float(np.std(total_impacts)),
            "mean_permanent_impact_bps": float(np.mean(permanent_impacts)),
            "mean_temporary_impact_bps": float(np.mean(temporary_impacts)),
            "mean_participation_rate": float(np.mean(participation_rates)),
            "mean_slippage_bps": float(np.mean(slippages)),
        }
    
    def clear_measurements(self) -> None:
        """Clear all impact measurements."""
        self._measurements.clear()
    
    def set_seed(self, seed: int) -> None:
        """
        Set random seed for reproducibility.
        
        Args:
            seed: Random seed
        """
        self._seed = seed
        np.random.seed(seed)


__all__ = [
    "ImpactModel",
    "ImpactType",
    "ImpactParameters",
    "ImpactMeasurement",
    "MarketImpactModel",
]
