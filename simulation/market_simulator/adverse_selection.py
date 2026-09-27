"""
Adverse selection modeling for institutional execution analysis.

This models realistic adverse selection effects:
- Information asymmetry costs
- Queue position adverse selection
- Market condition effects
- Toxic order flow detection
- Execution cost optimization under adverse selection
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
import math


class MarketCondition(Enum):
    """Market condition types."""
    NORMAL = "NORMAL"
    VOLATILE = "VOLATILE"
    STRESSED = "STRESSED"
    CRASH = "CRASH"


__all__ = [
    "MarketCondition",
    "AdverseSelectionMetrics",
    "AdverseSelectionModel",
    "AdverseSelectionOptimizer"
]


@dataclass
class AdverseSelectionMetrics:
    """
    Adverse selection metrics for an execution.
    """
    information_cost_bps: float
    timing_cost_bps: float
    selection_cost_bps: float
    total_adverse_selection_bps: float
    toxicity_score: float  # 0-1, higher = more toxic
    market_condition: MarketCondition
    queue_position_factor: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AdverseSelectionModel:
    """
    Models adverse selection costs in execution.
    
    Factors:
    - Information asymmetry
    - Market volatility
    - Queue position
    - Order flow toxicity
    - Market conditions
    """
    
    def __init__(self,
                 base_information_cost: float = 1.0,
                 base_timing_cost: float = 0.5,
                 base_selection_cost: float = 0.3,
                 volatility_sensitivity: float = 2.0):
        """
        Initialize adverse selection model.
        
        Args:
            base_information_cost: Base information cost in bps
            base_timing_cost: Base timing cost in bps
            base_selection_cost: Base selection cost in bps
            volatility_sensitivity: How volatility affects costs
        """
        self.base_information_cost = base_information_cost
        self.base_timing_cost = base_timing_cost
        self.base_selection_cost = base_selection_cost
        self.volatility_sensitivity = volatility_sensitivity
        
        # Historical toxicity tracking
        self.toxicity_history: List[float] = []
    
    def calculate_adverse_selection(self,
                                   queue_position: int,
                                   queue_length: int,
                                   volatility: float,
                                   market_condition: MarketCondition,
                                   order_size: float,
                                   avg_daily_volume: float) -> AdverseSelectionMetrics:
        """
        Calculate adverse selection metrics.
        
        Args:
            queue_position: Position in queue (0-indexed)
            queue_length: Total queue length
            volatility: Current volatility
            market_condition: Current market condition
            order_size: Order size
            avg_daily_volume: Average daily volume
            
        Returns:
            AdverseSelectionMetrics with cost breakdown
        """
        # Market condition multiplier
        condition_multiplier = self._get_condition_multiplier(market_condition)
        
        # Volatility multiplier
        vol_multiplier = 1.0 + (volatility - 0.02) * self.volatility_sensitivity
        
        # Queue position factor (deeper queue = higher adverse selection)
        queue_factor = (queue_position + 1) / max(queue_length, 1)
        
        # Information cost (asymmetry)
        information_cost = (
            self.base_information_cost * 
            condition_multiplier * 
            vol_multiplier * 
            queue_factor
        )
        
        # Timing cost (execution delay)
        timing_cost = (
            self.base_timing_cost * 
            condition_multiplier * 
            vol_multiplier * 
            queue_factor * 0.5
        )
        
        # Selection cost (being picked off)
        selection_cost = (
            self.base_selection_cost * 
            condition_multiplier * 
            vol_multiplier * 
            queue_factor * 0.8
        )
        
        # Total adverse selection
        total_adverse_selection = information_cost + timing_cost + selection_cost
        
        # Toxicity score (0-1)
        toxicity_score = self._calculate_toxicity_score(
            total_adverse_selection,
            volatility,
            market_condition,
            queue_factor
        )
        
        return AdverseSelectionMetrics(
            information_cost_bps=information_cost,
            timing_cost_bps=timing_cost,
            selection_cost_bps=selection_cost,
            total_adverse_selection_bps=total_adverse_selection,
            toxicity_score=toxicity_score,
            market_condition=market_condition,
            queue_position_factor=queue_factor
        )
    
    def _get_condition_multiplier(self, condition: MarketCondition) -> float:
        """Get market condition multiplier."""
        multipliers = {
            MarketCondition.NORMAL: 1.0,
            MarketCondition.VOLATILE: 1.5,
            MarketCondition.STRESSED: 2.5,
            MarketCondition.CRASH: 4.0
        }
        return multipliers.get(condition, 1.0)
    
    def _calculate_toxicity_score(self,
                                 adverse_selection_bps: float,
                                 volatility: float,
                                 market_condition: MarketCondition,
                                 queue_factor: float) -> float:
        """
        Calculate toxicity score (0-1).
        
        Higher scores indicate more toxic order flow.
        """
        # Base toxicity from adverse selection
        base_toxicity = min(adverse_selection_bps / 10.0, 1.0)
        
        # Volatility contribution
        vol_toxicity = min(volatility / 0.10, 1.0)
        
        # Market condition contribution
        condition_toxicity = {
            MarketCondition.NORMAL: 0.0,
            MarketCondition.VOLATILE: 0.3,
            MarketCondition.STRESSED: 0.6,
            MarketCondition.CRASH: 0.9
        }.get(market_condition, 0.0)
        
        # Queue position contribution
        queue_toxicity = queue_factor * 0.5
        
        # Combined toxicity score
        toxicity = (
            0.4 * base_toxicity +
            0.2 * vol_toxicity +
            0.2 * condition_toxicity +
            0.2 * queue_toxicity
        )
        
        return max(0.0, min(1.0, toxicity))
    
    def detect_toxic_flow(self,
                         recent_adverse_selections: List[float],
                         threshold: float = 0.7) -> bool:
        """
        Detect if recent order flow is toxic.
        
        Args:
            recent_adverse_selections: Recent adverse selection measurements
            threshold: Toxicity threshold
            
        Returns:
            True if flow is toxic
        """
        if not recent_adverse_selections:
            return False
        
        avg_toxicity = np.mean(recent_adverse_selections)
        return avg_toxicity > threshold
    
    def optimize_execution_under_adverse_selection(self,
                                                   adverse_selection: AdverseSelectionMetrics,
                                                   current_price: float,
                                                   order_quantity: float) -> Tuple[str, float]:
        """
        Optimize execution strategy given adverse selection.
        
        Returns:
            (strategy, adjusted_quantity)
            strategy: "AGGRESSIVE", "PASSIVE", "CANCEL"
            adjusted_quantity: Optimized order quantity
        """
        toxicity = adverse_selection.toxicity_score
        total_cost = adverse_selection.total_adverse_selection_bps
        
        if toxicity > 0.8:
            # High toxicity - cancel or be very aggressive
            if total_cost > 5.0:
                return ("CANCEL", 0.0)
            else:
                # Execute immediately
                return ("AGGRESSIVE", order_quantity)
        
        elif toxicity > 0.5:
            # Moderate toxicity - reduce size or split
            adjusted_quantity = order_quantity * 0.5
            return ("PASSIVE", adjusted_quantity)
        
        else:
            # Low toxicity - normal execution
            return ("PASSIVE", order_quantity)
    
    def record_toxicity(self, toxicity_score: float) -> None:
        """Record toxicity score for historical tracking."""
        self.toxicity_history.append(toxicity_score)
        
        # Keep only last 1000 measurements
        if len(self.toxicity_history) > 1000:
            self.toxicity_history = self.toxicity_history[-1000:]
    
    def get_toxicity_trend(self, window: int = 50) -> Dict:
        """
        Get toxicity trend statistics.
        
        Args:
            window: Number of recent measurements to analyze
            
        Returns:
            Dictionary with trend statistics
        """
        if not self.toxicity_history:
            return {
                "current_toxicity": 0.0,
                "average_toxicity": 0.0,
                "trend": "STABLE",
                "toxicity_rolling_avg": 0.0
            }
        
        recent = self.toxicity_history[-window:]
        current = self.toxicity_history[-1]
        average = np.mean(recent)
        
        # Determine trend
        if len(recent) < 10:
            trend = "INSUFFICIENT_DATA"
        elif average > current * 1.2:
            trend = "IMPROVING"
        elif average < current * 0.8:
            trend = "DETERIORATING"
        else:
            trend = "STABLE"
        
        return {
            "current_toxicity": current,
            "average_toxicity": average,
            "trend": trend,
            "toxicity_rolling_avg": average,
            "max_toxicity": max(recent),
            "min_toxicity": min(recent)
        }
    
    def calculate_optimal_queue_position(self,
                                       volatility: float,
                                       market_condition: MarketCondition,
                                       max_queue_position: int = 10) -> int:
        """
        Calculate optimal queue position to minimize adverse selection.
        
        Returns:
            Optimal queue position (0-indexed)
        """
        # Calculate adverse selection for each queue position
        costs = []
        for pos in range(max_queue_position):
            metrics = self.calculate_adverse_selection(
                queue_position=pos,
                queue_length=max_queue_position,
                volatility=volatility,
                market_condition=market_condition,
                order_size=1000,
                avg_daily_volume=1_000_000
            )
            costs.append(metrics.total_adverse_selection_bps)
        
        # Find position with minimum cost
        optimal_position = int(np.argmin(costs))
        
        return optimal_position


class AdverseSelectionOptimizer:
    """
    Optimizes execution strategies to minimize adverse selection.
    
    Combines adverse selection modeling with execution optimization.
    """
    
    def __init__(self, adverse_selection_model: AdverseSelectionModel):
        self.model = adverse_selection_model
    
    def optimize_order_placement(self,
                                current_price: float,
                                order_quantity: float,
                                volatility: float,
                                market_condition: MarketCondition,
                                available_venues: List[str]) -> Dict:
        """
        Optimize order placement to minimize adverse selection.
        
        Returns:
            Dictionary with optimal placement strategy
        """
        # Calculate adverse selection for different scenarios
        metrics = self.model.calculate_adverse_selection(
            queue_position=0,
            queue_length=10,
            volatility=volatility,
            market_condition=market_condition,
            order_size=order_quantity,
            avg_daily_volume=1_000_000
        )
        
        # Get execution strategy
        strategy, adjusted_quantity = self.model.optimize_execution_under_adverse_selection(
            metrics, current_price, order_quantity
        )
        
        # Calculate optimal queue position
        optimal_queue = self.model.calculate_optimal_queue_position(
            volatility, market_condition
        )
        
        return {
            "strategy": strategy,
            "adjusted_quantity": adjusted_quantity,
            "optimal_queue_position": optimal_queue,
            "adverse_selection_bps": metrics.total_adverse_selection_bps,
            "toxicity_score": metrics.toxicity_score,
            "recommended_venue": available_venues[0] if available_venues else None
        }