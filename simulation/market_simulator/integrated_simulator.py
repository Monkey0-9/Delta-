"""
Integrated market simulator combining all components.

This provides a complete institutional-grade market simulation:
- L2/L3 order book
- Matching engine
- Queue position analysis
- Latency modeling
- Market impact
- Fee calculation
- Adverse selection
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from .order_book import OrderBook, LimitOrder, MarketOrder, OrderSide
from .matching_engine import MatchingEngine, ExecutionResult, OrderType, OrderStatus
from .queue_position import QueuePositionCalculator, QueuePositionInfo
from .latency_model import LatencyModel, LatencyDistribution
from .market_impact import MarketImpactModel, ImpactModelType, ImpactParameters, ImpactModelFactory
from .fee_structure import FeeStructure, ExchangeFees, FeeOptimizer
from .adverse_selection import AdverseSelectionModel, MarketCondition, AdverseSelectionOptimizer


__all__ = [
    "SimulationResult",
    "IntegratedMarketSimulator"
]


@dataclass
class SimulationResult:
    """
    Complete simulation result for an order.
    """
    order_id: str
    execution_result: ExecutionResult
    queue_position_info: Optional[QueuePositionInfo]
    latency_ms: float
    market_impact: Optional[dict]
    fee_calculation: Optional[dict]
    adverse_selection: Optional[dict]
    total_cost_bps: float
    timestamp: datetime


class IntegratedMarketSimulator:
    """
    Integrated market simulator combining all institutional components.
    
    Provides:
    - Realistic order book simulation
    - Execution with market impact
    - Fee calculation
    - Adverse selection analysis
    - Latency modeling
    """
    
    def __init__(self, 
                 symbol: str,
                 exchange: str = "SIM",
                 latency_distribution: LatencyDistribution = LatencyDistribution.LOG_NORMAL):
        """
        Initialize integrated market simulator.
        
        Args:
            symbol: Symbol to simulate
            exchange: Exchange identifier
            latency_distribution: Latency distribution type
        """
        self.symbol = symbol
        self.exchange = exchange
        
        # Core components
        self.order_book = OrderBook(symbol, exchange)
        self.matching_engine = MatchingEngine(symbol, exchange)
        # Share the order book between simulator and matching engine
        self.matching_engine.order_book = self.order_book
        self.queue_calculator = QueuePositionCalculator()
        self.latency_model = LatencyModel(distribution=latency_distribution)
        
        # Market impact model
        impact_params = ImpactParameters(
            permanent_impact_coef=0.001,
            temporary_impact_coef=0.01,
            volatility=0.02,
            avg_daily_volume=1_000_000,
            spread_bps=5.0
        )
        self.impact_model = ImpactModelFactory.create_model(
            ImpactModelType.ALMGREN_CHRISS, impact_params
        )
        
        # Fee structure
        self.fee_structure = ExchangeFees(exchange)
        
        # Adverse selection model
        self.adverse_selection_model = AdverseSelectionModel()
        self.adverse_selection_optimizer = AdverseSelectionOptimizer(self.adverse_selection_model)
        
        # Simulation history
        self.simulation_history: List[SimulationResult] = []
    
    def seed_order_book(self, 
                       num_bids: int = 10,
                       num_asks: int = 10,
                       base_price: float = 100.0,
                       spread_bps: float = 5.0) -> None:
        """
        Seed order book with initial liquidity.
        
        Args:
            num_bids: Number of bid levels
            num_asks: Number of ask levels
            base_price: Base price around which to seed
            spread_bps: Spread in basis points
        """
        mid_price = base_price
        half_spread = (spread_bps / 10000) * mid_price / 2
        
        # Seed bids
        for i in range(num_bids):
            price = mid_price - half_spread - (i * 0.01)
            quantity = 1000 + (i * 100)
            
            order = LimitOrder(
                order_id=f"SEED_BID_{i}",
                side=OrderSide.BUY,
                price=price,
                quantity=quantity,
                timestamp=datetime.now(timezone.utc),
                exchange=self.exchange
            )
            self.order_book.add_limit_order(order)
        
        # Seed asks
        for i in range(num_asks):
            price = mid_price + half_spread + (i * 0.01)
            quantity = 1000 + (i * 100)
            
            order = LimitOrder(
                order_id=f"SEED_ASK_{i}",
                side=OrderSide.SELL,
                price=price,
                quantity=quantity,
                timestamp=datetime.now(timezone.utc),
                exchange=self.exchange
            )
            self.order_book.add_limit_order(order)
    
    def submit_limit_order(self,
                          side: str,
                          price: float,
                          quantity: float,
                          order_type: OrderType = OrderType.GTC,
                          participant: str = "DEFAULT") -> SimulationResult:
        """
        Submit limit order with full simulation.
        
        Args:
            side: "BUY" or "SELL"
            price: Limit price
            quantity: Order quantity
            order_type: Order type (GTC, IOC, FOK)
            participant: Participant identifier
            
        Returns:
            Complete SimulationResult
        """
        order_id = str(uuid.uuid4())
        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        
        # Create order
        order = LimitOrder(
            order_id=order_id,
            side=order_side,
            price=price,
            quantity=quantity,
            timestamp=datetime.now(timezone.utc),
            exchange=self.exchange,
            participant=participant
        )
        
        # Measure latency
        self.latency_model.measure_latency("TOTAL", self.exchange, self.symbol)
        latency_ms = self.latency_model.sample_latency("TOTAL", self.exchange, self.symbol)
        
        # Submit to matching engine
        execution_result = self.matching_engine.submit_limit_order(order, order_type)
        
        # Calculate queue position if order added to book
        queue_position_info = None
        if execution_result.status in [OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED]:
            queue_position_info = self.queue_calculator.calculate_queue_position(
                self.order_book, order_id, order_side, price
            )
        
        # Calculate market impact
        market_impact = None
        if execution_result.fills:
            participation_rate = quantity / 1_000_000  # Assuming 1M ADV
            impact_estimate = self.impact_model.calculate_impact(
                side, quantity, price, participation_rate
            )
            market_impact = {
                "permanent_impact_bps": impact_estimate.permanent_impact_bps,
                "temporary_impact_bps": impact_estimate.temporary_impact_bps,
                "total_impact_bps": impact_estimate.total_impact_bps
            }
        
        # Calculate fees
        fee_calculation = None
        if execution_result.fills:
            total_notional = sum(f.price * f.quantity for f in execution_result.fills)
            is_maker = (execution_result.fills[0].liquidity_indicator == "MAKER")
            fee_result = self.fee_structure.calculate_fee(total_notional, is_maker)
            fee_calculation = {
                "fee_usd": fee_result.fee_usd,
                "rebate_usd": fee_result.rebate_usd,
                "net_cost_usd": fee_result.net_cost_usd,
                "tier_applied": fee_result.tier_applied
            }
        
        # Calculate adverse selection
        adverse_selection = None
        if queue_position_info:
            vol = 0.02  # Default volatility
            condition = MarketCondition.NORMAL
            adv_metrics = self.adverse_selection_model.calculate_adverse_selection(
                queue_position_info.queue_position,
                queue_position_info.queue_length,
                vol,
                condition,
                quantity,
                1_000_000
            )
            adverse_selection = {
                "total_adverse_selection_bps": adv_metrics.total_adverse_selection_bps,
                "toxicity_score": adv_metrics.toxicity_score,
                "information_cost_bps": adv_metrics.information_cost_bps
            }
        
        # Calculate total cost
        total_cost_bps = 0.0
        if market_impact:
            total_cost_bps += market_impact["total_impact_bps"]
        if fee_calculation:
            total_notional = sum(f.price * f.quantity for f in execution_result.fills)
            if total_notional > 0:
                total_cost_bps += (fee_calculation["net_cost_usd"] / total_notional) * 10000
        if adverse_selection:
            total_cost_bps += adverse_selection["total_adverse_selection_bps"]
        
        # Create simulation result
        result = SimulationResult(
            order_id=order_id,
            execution_result=execution_result,
            queue_position_info=queue_position_info,
            latency_ms=latency_ms,
            market_impact=market_impact,
            fee_calculation=fee_calculation,
            adverse_selection=adverse_selection,
            total_cost_bps=total_cost_bps,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.simulation_history.append(result)
        
        return result
    
    def submit_market_order(self,
                           side: str,
                           quantity: float,
                           participant: str = "DEFAULT") -> SimulationResult:
        """
        Submit market order with full simulation.
        
        Args:
            side: "BUY" or "SELL"
            quantity: Order quantity
            participant: Participant identifier
            
        Returns:
            Complete SimulationResult
        """
        order_id = str(uuid.uuid4())
        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        
        # Create market order
        order = MarketOrder(
            order_id=order_id,
            side=order_side,
            quantity=quantity,
            timestamp=datetime.now(timezone.utc),
            exchange=self.exchange,
            participant=participant
        )
        
        # Measure latency
        latency_ms = self.latency_model.sample_latency("TOTAL", self.exchange, self.symbol)
        
        # Submit to matching engine
        execution_result = self.matching_engine.submit_market_order(order)
        
        # Calculate market impact (market orders always takers)
        market_impact = None
        if execution_result.fills:
            avg_price = execution_result.average_price
            participation_rate = quantity / 1_000_000
            impact_estimate = self.impact_model.calculate_impact(
                side, quantity, avg_price, participation_rate
            )
            market_impact = {
                "permanent_impact_bps": impact_estimate.permanent_impact_bps,
                "temporary_impact_bps": impact_estimate.temporary_impact_bps,
                "total_impact_bps": impact_estimate.total_impact_bps
            }
        
        # Calculate fees (market orders always takers)
        fee_calculation = None
        if execution_result.fills:
            total_notional = sum(f.price * f.quantity for f in execution_result.fills)
            fee_result = self.fee_structure.calculate_fee(total_notional, is_maker=False)
            fee_calculation = {
                "fee_usd": fee_result.fee_usd,
                "rebate_usd": fee_result.rebate_usd,
                "net_cost_usd": fee_result.net_cost_usd,
                "tier_applied": fee_result.tier_applied
            }
        
        # Calculate total cost
        total_cost_bps = 0.0
        if market_impact:
            total_cost_bps += market_impact["total_impact_bps"]
        if fee_calculation:
            total_notional = sum(f.price * f.quantity for f in execution_result.fills)
            if total_notional > 0:
                total_cost_bps += (fee_calculation["net_cost_usd"] / total_notional) * 10000
        
        # Create simulation result
        result = SimulationResult(
            order_id=order_id,
            execution_result=execution_result,
            queue_position_info=None,  # Market orders don't have queue position
            latency_ms=latency_ms,
            market_impact=market_impact,
            fee_calculation=fee_calculation,
            adverse_selection=None,  # Market orders have immediate execution
            total_cost_bps=total_cost_bps,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.simulation_history.append(result)
        
        return result
    
    def get_market_state(self) -> Dict:
        """Get current market state."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "order_book": self.order_book.get_l2_snapshot(depth=10),
            "matching_engine": self.matching_engine.get_market_state(),
            "latency_stats": self.latency_model.get_percentiles(),
            "simulation_count": len(self.simulation_history)
        }
    
    def get_simulation_summary(self) -> Dict:
        """Get summary of all simulations."""
        if not self.simulation_history:
            return {
                "total_simulations": 0,
                "avg_latency_ms": 0.0,
                "avg_total_cost_bps": 0.0,
                "fill_rate": 0.0
            }
        
        total_latency = sum(r.latency_ms for r in self.simulation_history)
        total_cost = sum(r.total_cost_bps for r in self.simulation_history)
        filled_orders = sum(1 for r in self.simulation_history if r.execution_result.filled_quantity > 0)
        
        return {
            "total_simulations": len(self.simulation_history),
            "avg_latency_ms": total_latency / len(self.simulation_history),
            "avg_total_cost_bps": total_cost / len(self.simulation_history),
            "fill_rate": filled_orders / len(self.simulation_history),
            "latency_distribution": self.latency_model.distribution.value
        }