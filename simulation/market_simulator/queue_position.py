"""
Queue position calculator for institutional execution analysis.

This models realistic queue position effects:
- Price-time priority queue position
- Fill probability based on queue position
- Queue jump modeling
- Adverse selection from queue position
- Expected fill time estimation
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from .order_book import OrderBook, OrderSide


__all__ = [
    "QueuePositionInfo",
    "QueuePositionCalculator"
]


@dataclass
class QueuePositionInfo:
    """
    Complete queue position information.
    """
    queue_position: int  # 0-indexed position in queue
    queue_length: int  # Total orders at this price level
    queue_ahead_quantity: float  # Total quantity ahead in queue
    queue_behind_quantity: float  # Total quantity behind in queue
    fill_probability: float  # Probability of being filled
    expected_fill_time_seconds: float  # Expected time to fill
    adverse_selection_risk: float  # Risk of adverse selection


class QueuePositionCalculator:
    """
    Calculates queue position metrics and fill probabilities.
    
    Models:
    - Fill probability based on queue position
    - Expected fill time based on historical fill rates
    - Adverse selection risk based on queue position and market conditions
    """
    
    def __init__(self, 
                 base_fill_rate: float = 0.7,
                 fill_decay_factor: float = 0.1,
                 adverse_selection_base: float = 0.05):
        """
        Initialize queue position calculator.
        
        Args:
            base_fill_rate: Base fill probability for front of queue
            fill_decay_factor: How quickly fill probability decays with queue position
            adverse_selection_base: Base adverse selection risk
        """
        self.base_fill_rate = base_fill_rate
        self.fill_decay_factor = fill_decay_factor
        self.adverse_selection_base = adverse_selection_base
        
        # Historical fill rate tracking
        self.historical_fill_rates: Dict[str, List[float]] = {}
    
    def calculate_queue_position(self, 
                                order_book: OrderBook,
                                order_id: str,
                                side: OrderSide,
                                price: float) -> QueuePositionInfo:
        """
        Calculate complete queue position information.
        """
        # Get queue position from order book
        queue_position = order_book.get_queue_position(order_id, side, price)
        
        if queue_position == -1:
            # Order not found
            return QueuePositionInfo(
                queue_position=-1,
                queue_length=0,
                queue_ahead_quantity=0.0,
                queue_behind_quantity=0.0,
                fill_probability=0.0,
                expected_fill_time_seconds=0.0,
                adverse_selection_risk=1.0
            )
        
        # Get order book level info
        if side == OrderSide.BUY:
            level = order_book.bids.get(price)
        else:
            level = order_book.asks.get(price)
        
        if level is None:
            return QueuePositionInfo(
                queue_position=queue_position,
                queue_length=0,
                queue_ahead_quantity=0.0,
                queue_behind_quantity=0.0,
                fill_probability=0.0,
                expected_fill_time_seconds=0.0,
                adverse_selection_risk=1.0
            )
        
        queue_length = len(level.orders)
        
        # Calculate quantities ahead and behind
        queue_ahead_quantity = sum(
            order.quantity for order in level.orders[:queue_position]
        )
        queue_behind_quantity = sum(
            order.quantity for order in level.orders[queue_position + 1:]
        )
        
        # Calculate fill probability
        fill_probability = self._calculate_fill_probability(
            queue_position, queue_length, queue_ahead_quantity
        )
        
        # Calculate expected fill time
        expected_fill_time = self._calculate_expected_fill_time(
            queue_position, queue_ahead_quantity, fill_probability
        )
        
        # Calculate adverse selection risk
        adverse_selection_risk = self._calculate_adverse_selection_risk(
            queue_position, queue_length, fill_probability
        )
        
        return QueuePositionInfo(
            queue_position=queue_position,
            queue_length=queue_length,
            queue_ahead_quantity=queue_ahead_quantity,
            queue_behind_quantity=queue_behind_quantity,
            fill_probability=fill_probability,
            expected_fill_time_seconds=expected_fill_time,
            adverse_selection_risk=adverse_selection_risk
        )
    
    def _calculate_fill_probability(self, 
                                  queue_position: int,
                                  queue_length: int,
                                  queue_ahead_quantity: float) -> float:
        """
        Calculate fill probability based on queue position.
        
        Uses exponential decay model:
        P(fill) = base_rate * exp(-decay * position)
        """
        if queue_position == 0:
            return self.base_fill_rate
        
        # Adjust for queue position
        position_factor = math.exp(-self.fill_decay_factor * queue_position)
        
        # Adjust for quantity ahead
        quantity_factor = math.exp(-0.01 * queue_ahead_quantity / 1000)  # Decay with larger quantities
        
        fill_prob = self.base_fill_rate * position_factor * quantity_factor
        
        return max(0.0, min(1.0, fill_prob))
    
    def _calculate_expected_fill_time(self,
                                      queue_position: int,
                                      queue_ahead_quantity: float,
                                      fill_probability: float) -> float:
        """
        Calculate expected fill time in seconds.
        
        Assumes average fill rate of 100 shares per second for estimation.
        """
        if fill_probability == 0:
            return float('inf')
        
        # Base time to process queue ahead
        base_fill_rate = 100.0  # shares per second
        time_to_queue = queue_ahead_quantity / base_fill_rate
        
        # Adjust by fill probability
        expected_time = time_to_queue / fill_probability
        
        return expected_time
    
    def _calculate_adverse_selection_risk(self,
                                         queue_position: int,
                                         queue_length: int,
                                         fill_probability: float) -> float:
        """
        Calculate adverse selection risk.
        
        Higher risk when:
        - Deep in queue (low fill probability)
        - Large queue length (more competition)
        - Low fill probability
        """
        # Base risk
        risk = self.adverse_selection_base
        
        # Increase with queue position
        position_risk = 0.02 * queue_position
        
        # Increase with queue length
        length_risk = 0.01 * queue_length
        
        # Increase with low fill probability
        fill_risk = 0.1 * (1 - fill_probability)
        
        total_risk = risk + position_risk + length_risk + fill_risk
        
        return max(0.0, min(1.0, total_risk))
    
    def record_fill_outcome(self, 
                           symbol: str,
                           queue_position: int,
                           filled: bool) -> None:
        """
        Record fill outcome for learning historical fill rates.
        """
        if symbol not in self.historical_fill_rates:
            self.historical_fill_rates[symbol] = []
        
        self.historical_fill_rates[symbol].append(1.0 if filled else 0.0)
        
        # Keep only last 1000 observations
        if len(self.historical_fill_rates[symbol]) > 1000:
            self.historical_fill_rates[symbol] = self.historical_fill_rates[symbol][-1000:]
    
    def get_historical_fill_rate(self, symbol: str) -> Optional[float]:
        """
        Get historical fill rate for symbol.
        """
        if symbol not in self.historical_fill_rates or not self.historical_fill_rates[symbol]:
            return None
        
        return np.mean(self.historical_fill_rates[symbol])
    
    def update_parameters(self, 
                         base_fill_rate: Optional[float] = None,
                         fill_decay_factor: Optional[float] = None,
                         adverse_selection_base: Optional[float] = None) -> None:
        """
        Update model parameters based on historical data.
        """
        if base_fill_rate is not None:
            self.base_fill_rate = base_fill_rate
        if fill_decay_factor is not None:
            self.fill_decay_factor = fill_decay_factor
        if adverse_selection_base is not None:
            self.adverse_selection_base = adverse_selection_base
    
    def optimize_queue_position(self,
                               order_book: OrderBook,
                               side: OrderSide,
                               quantity: float,
                               max_queue_position: int = 5) -> Tuple[float, int]:
        """
        Find optimal price level considering queue position.
        
        Returns (optimal_price, expected_queue_position)
        """
        if side == OrderSide.BUY:
            prices = order_book.bid_prices[:max_queue_position + 1]
        else:
            prices = order_book.ask_prices[:max_queue_position + 1]
        
        if not prices:
            return (0.0, -1)
        
        best_score = -float('inf')
        best_price = prices[0]
        best_queue_pos = 0
        
        for i, price in enumerate(prices):
            if i > max_queue_position:
                break
            
            # Estimate queue position at this price
            estimated_queue_pos = i  # Simplified assumption
            
            # Calculate fill probability
            fill_prob = self._calculate_fill_probability(
                estimated_queue_pos, i + 1, quantity * i
            )
            
            # Score: balance between price improvement and fill probability
            if side == OrderSide.BUY:
                # For buys: lower price is better, but need high fill prob
                price_score = -price  # Lower price = higher score
            else:
                # For sells: higher price is better, but need high fill prob
                price_score = price  # Higher price = higher score
            
            total_score = price_score * fill_prob
            
            if total_score > best_score:
                best_score = total_score
                best_price = price
                best_queue_pos = estimated_queue_pos
        
        return (best_price, best_queue_pos)