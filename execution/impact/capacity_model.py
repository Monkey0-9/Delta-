"""
Alpha Capacity and Crowding Pipeline for DELTA OS.

This module implements capacity estimation and crowding detection for:
- Maximum AUM estimation per strategy
- Capacity decay curves
- Market impact vs AUM modeling
- Cross-manager signal correlation
- Flow toxicity analysis
- Optimal position sizing under crowding
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Tuple, Any
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression


class CapacityModel(Enum):
    """Capacity estimation models."""
    LINEAR = "linear"
    SQUARE_ROOT = "square_root"
    POWER_LAW = "power_law"
    NONLINEAR = "nonlinear"


class CrowdingLevel(Enum):
    """Crowding level classification."""
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


@dataclass
class CapacityEstimate:
    """
    Capacity estimation for a strategy.
    
    Attributes:
        strategy_id: Strategy identifier
        max_aum: Maximum AUM in USD
        optimal_aum: Optimal AUM for best risk-adjusted returns
        capacity_decay: Capacity decay rate
        market_impact_slope: Market impact slope parameter
        liquidity_constraint: Liquidity constraint
        metadata: Additional metadata
    """
    strategy_id: str
    max_aum: Decimal
    optimal_aum: Decimal
    capacity_decay: float
    market_impact_slope: float
    liquidity_constraint: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def utilization_ratio(self) -> float:
        """Ratio of optimal to max capacity."""
        if self.max_aum == 0:
            return 0.0
        return float(self.optimal_aum / self.max_aum)


@dataclass
class CrowdingSignal:
    """
    Crowding detection signal.
    
    Attributes:
        timestamp: Signal timestamp
        crowding_level: Crowding level
        signal_correlation: Cross-signal correlation
        flow_toxicity: Flow toxicity metric
        adverse_selection: Adverse selection risk
        recommended_action: Recommended action
        metadata: Additional metadata
    """
    timestamp: datetime
    crowding_level: CrowdingLevel
    signal_correlation: float
    flow_toxicity: float
    adverse_selection: float
    recommended_action: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapacityModel:
    """
    Capacity estimation model for alpha strategies.
    
    Features:
    - Maximum AUM estimation
    - Capacity decay curves
    - Market impact modeling
    - Liquidity constraints
    - Optimal sizing
    """
    
    def __init__(self, model_type: CapacityModel = CapacityModel.SQUARE_ROOT):
        """
        Initialize capacity model.
        
        Args:
            model_type: Capacity model type
        """
        self._model_type = model_type
        self._calibrated_params: Dict[str, float] = {}
        
        # Default parameters (should be calibrated with historical data)
        self._default_params = {
            'linear': {'slope': 0.001, 'intercept': 0.0},
            'square_root': {'coefficient': 0.01, 'power': 0.5},
            'power_law': {'coefficient': 0.005, 'power': 0.6},
            'nonlinear': {'params': [0.001, 0.0001, 0.00001]}
        }
    
    def estimate_capacity(
        self,
        avg_daily_volume: Decimal,
        volatility: float = 0.2,
        participation_rate: float = 0.1,
        strategy_specific_params: Optional[Dict[str, float]] = None
    ) -> CapacityEstimate:
        """
        Estimate strategy capacity.
        
        Args:
            avg_daily_volume: Average daily volume
            volatility: Market volatility
            participation_rate: Strategy participation rate
            strategy_specific_params: Strategy-specific parameters
            
        Returns:
            CapacityEstimate
        """
        params = strategy_specific_params or self._default_params[self._model_type.value]
        
        # Calculate market impact at different AUM levels
        if self._model_type == CapacityModel.LINEAR:
            # Linear impact: impact = slope * AUM
            slope = params['slope']
            max_aum = avg_daily_volume / (slope * 100)
            market_impact_slope = slope
        
        elif self._model_type == CapacityModel.SQUARE_ROOT:
            # Square root law: impact = coefficient * sqrt(AUM)
            coefficient = params['coefficient']
            # Solve for AUM where impact = 10 bps (0.1%)
            max_aum = (0.001 / coefficient) ** 2
            market_impact_slope = coefficient
        
        elif self._model_type == CapacityModel.POWER_LAW:
            # Power law: impact = coefficient * AUM^power
            coefficient = params['coefficient']
            power = params['power']
            # Solve for AUM where impact = 10 bps
            max_aum = (0.001 / coefficient) ** (1 / power)
            market_impact_slope = coefficient
        
        else:
            # Nonlinear model
            max_aum = avg_daily_volume * 0.1  # Conservative estimate
            market_impact_slope = 0.001
        
        # Adjust for volatility
        volatility_adjustment = 1.0 / (1.0 + volatility)
        max_aum = max_aum * Decimal(str(volatility_adjustment))
        
        # Adjust for participation rate
        participation_adjustment = 1.0 / (1.0 + participation_rate * 10)
        max_aum = max_aum * Decimal(str(participation_adjustment))
        
        # Calculate optimal AUM (typically 50-70% of max)
        optimal_aum = max_aum * Decimal("0.6")
        
        # Capacity decay (performance degradation with scale)
        capacity_decay = 0.1  # 10% decay per doubling of AUM
        
        # Liquidity constraint
        liquidity_constraint = avg_daily_volume * Decimal("0.05")  # 5% of ADV
        
        return CapacityEstimate(
            strategy_id="strategy",
            max_aum=max_aum,
            optimal_aum=optimal_aum,
            capacity_decay=capacity_decay,
            market_impact_slope=market_impact_slope,
            liquidity_constraint=liquidity_constraint
        )
    
    def calculate_capacity_curve(
        self,
        max_aum: Decimal,
        num_points: int = 100
    ) -> Tuple[List[Decimal], List[float]]:
        """
        Calculate capacity decay curve.
        
        Args:
            max_aum: Maximum AUM
            num_points: Number of points on curve
            
        Returns:
            Tuple of (AUM levels, expected returns)
        """
        aum_levels = np.linspace(0, float(max_aum), num_points)
        expected_returns = []
        
        for i, aum in enumerate(aum_levels):
            if i == 0:
                expected_returns.append(1.0)  # 100% return at zero AUM
            else:
                # Apply capacity decay
                decay_factor = np.exp(-self._default_params['square_root']['coefficient'] * np.sqrt(aum))
                expected_returns.append(decay_factor)
        
        return [Decimal(str(aum)) for aum in aum_levels], expected_returns


class CrowdingDetector:
    """
    Crowding detection and analysis.
    
    Features:
    - Cross-manager signal correlation
    - Flow toxicity analysis
    - Adverse selection risk
    - Optimal position sizing under crowding
    """
    
    def __init__(self):
        """Initialize crowding detector."""
        self._signal_history: Dict[str, List[float]] = {}
        self._flow_history: List[float] = []
        self._correlation_threshold = 0.7
        self._toxicity_threshold = 0.8
    
    def add_signal(self, manager_id: str, signal_value: float, timestamp: datetime) -> None:
        """
        Add signal value for correlation tracking.
        
        Args:
            manager_id: Manager/strategy identifier
            signal_value: Signal value
            timestamp: Signal timestamp
        """
        if manager_id not in self._signal_history:
            self._signal_history[manager_id] = []
        
        self._signal_history[manager_id].append(signal_value)
    
    def add_flow(self, flow_value: float, timestamp: datetime) -> None:
        """
        Add order flow data for toxicity analysis.
        
        Args:
            flow_value: Order flow value
            timestamp: Flow timestamp
        """
        self._flow_history.append(flow_value)
    
    def detect_crowding(
        self,
        manager_id: str,
        current_signal: float
    ) -> CrowdingSignal:
        """
        Detect crowding for a manager/strategy.
        
        Args:
            manager_id: Manager/strategy identifier
            current_signal: Current signal value
            
        Returns:
            CrowdingSignal
        """
        # Calculate cross-signal correlation
        signal_correlation = self._calculate_signal_correlation(manager_id)
        
        # Calculate flow toxicity
        flow_toxicity = self._calculate_flow_toxicity()
        
        # Calculate adverse selection risk
        adverse_selection = self._calculate_adverse_selection(current_signal, flow_toxicity)
        
        # Classify crowding level
        crowding_level = self._classify_crowding(
            signal_correlation,
            flow_toxicity,
            adverse_selection
        )
        
        # Determine recommended action
        recommended_action = self._get_recommended_action(crowding_level)
        
        return CrowdingSignal(
            timestamp=datetime.now(timezone.utc),
            crowding_level=crowding_level,
            signal_correlation=signal_correlation,
            flow_toxicity=flow_toxicity,
            adverse_selection=adverse_selection,
            recommended_action=recommended_action
        )
    
    def _calculate_signal_correlation(self, manager_id: str) -> float:
        """Calculate cross-signal correlation."""
        if manager_id not in self._signal_history:
            return 0.0
        
        signals = self._signal_history[manager_id]
        if len(signals) < 10:
            return 0.0
        
        # Calculate autocorrelation
        series = pd.Series(signals)
        if len(series) > 1:
            return series.autocorr(lag=1) or 0.0
        
        return 0.0
    
    def _calculate_flow_toxicity(self) -> float:
        """Calculate flow toxicity."""
        if len(self._flow_history) < 10:
            return 0.0
        
        # Calculate flow toxicity as inverse flow predictability
        flows = np.array(self._flow_history[-100:])  # Last 100 flows
        
        # Calculate autocorrelation
        if len(flows) > 1:
            autocorr = np.corrcoef(flows[:-1], flows[1:])
            if not np.isnan(autocorr):
                return abs(autocorr[0, 1]) if autocorr.size > 0 else 0.0
        
        return 0.0
    
    def _calculate_adverse_selection(self, signal: float, flow_toxicity: float) -> float:
        """Calculate adverse selection risk."""
        # Adverse selection increases with flow toxicity and signal extremity
        signal_extremity = abs(signal)
        return signal_extremity * flow_toxicity
    
    def _classify_crowding(
        self,
        signal_correlation: float,
        flow_toxicity: float,
        adverse_selection: float
    ) -> CrowdingLevel:
        """Classify crowding level."""
        crowding_score = (signal_correlation + flow_toxicity + adverse_selection) / 3
        
        if crowding_score < 0.3:
            return CrowdingLevel.NONE
        elif crowding_score < 0.5:
            return CrowdingLevel.LOW
        elif crowding_score < 0.7:
            return CrowdingLevel.MODERATE
        elif crowding_score < 0.9:
            return CrowdingLevel.HIGH
        else:
            return CrowdingLevel.SEVERE
    
    def _get_recommended_action(self, crowding_level: CrowdingLevel) -> str:
        """Get recommended action based on crowding level."""
        actions = {
            CrowdingLevel.NONE: "Proceed normally",
            CrowdingLevel.LOW: "Monitor closely",
            CrowdingLevel.MODERATE: "Reduce position size",
            CrowdingLevel.HIGH: "Significantly reduce exposure",
            CrowdingLevel.SEVERE: "Exit position immediately"
        }
        return actions.get(crowding_level, "Proceed normally")


class CapacityCrowdingPipeline:
    """
    Combined capacity and crowding analysis pipeline.
    
    Features:
    - Capacity estimation
    - Crowding detection
    - Optimal position sizing
    - Risk-adjusted sizing
    """
    
    def __init__(self):
        """Initialize pipeline."""
        self._capacity_model = CapacityModel()
        self._crowding_detector = CrowdingDetector()
    
    def analyze_strategy(
        self,
        strategy_id: str,
        avg_daily_volume: Decimal,
        volatility: float = 0.2,
        manager_signals: Optional[Dict[str, List[float]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze strategy capacity and crowding.
        
        Args:
            strategy_id: Strategy identifier
            avg_daily_volume: Average daily volume
            volatility: Market volatility
            manager_signals: Historical signals from other managers
            
        Returns:
            Analysis results
        """
        # Estimate capacity
        capacity_estimate = self._capacity_model.estimate_capacity(
            avg_daily_volume=avg_daily_volume,
            volatility=volatility
        )
        
        # Detect crowding if signals provided
        crowding_signals = []
        if manager_signals:
            for manager_id, signals in manager_signals.items():
                for signal in signals[-10:]:  # Last 10 signals
                    self._crowding_detector.add_signal(manager_id, signal, datetime.now(timezone.utc))
                
                crowding_signal = self._crowding_detector.detect_crowding(manager_id, signals[-1])
                crowding_signals.append(crowding_signal)
        
        # Calculate capacity curve
        aum_levels, expected_returns = self._capacity_model.calculate_capacity_curve(
            capacity_estimate.max_aum
        )
        
        return {
            'strategy_id': strategy_id,
            'capacity_estimate': {
                'max_aum': float(capacity_estimate.max_aum),
                'optimal_aum': float(capacity_estimate.optimal_aum),
                'capacity_decay': capacity_estimate.capacity_decay,
                'utilization_ratio': capacity_estimate.utilization_ratio,
            },
            'crowding_analysis': {
                'level': s.crowding_level.value if crowding_signals else 'none',
                'count': len([s for s in crowding_signals if s.crowding_level != CrowdingLevel.NONE]),
                'recommended_action': crowding_signals[0].recommended_action if crowding_signals else 'Proceed normally',
            },
            'capacity_curve': {
                'aum_levels': [float(a) for a in aum_levels],
                'expected_returns': expected_returns,
            }
        }


__all__ = [
    "CapacityModel",
    "CapacityEstimate",
    "CrowdingDetector",
    "CrowdingSignal",
    "CrowdingLevel",
    "CapacityCrowdingPipeline",
]
