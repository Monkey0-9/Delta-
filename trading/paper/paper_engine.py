"""
Paper and Shadow Trading Infrastructure for DELTA OS.

This module implements comprehensive paper and shadow trading with:
- Real-time paper trading engine
- Shadow trading (live order mirroring)
- Performance tracking and analytics
- P&L attribution
- Risk monitoring
- Live vs shadow comparison
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
import numpy as np
from collections import defaultdict

from core.contracts.canonical import (
    Instrument,
    Timestamps,
    Side,
    OrderType,
    OrderStatus,
    Order,
    Fill,
    PortfolioSnapshot,
)
from execution.matching.l2_order_book import L2OrderBook
from execution.simulation.latency_model import LatencyModel
from execution.simulation.market_impact import MarketImpactModel


class TradingMode(Enum):
    """Trading mode enumeration."""
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


@dataclass
class PaperTrade:
    """
    Paper trade record.
    
    Attributes:
        trade_id: Unique trade identifier
        order_id: Order identifier
        instrument: Instrument
        side: Order side
        quantity: Order quantity
        execution_price: Execution price
        target_price: Target price
        slippage_bps: Slippage in basis points
        timestamp: Trade timestamp
        mode: Trading mode
    """
    trade_id: str
    order_id: str
    instrument: Instrument
    side: Side
    quantity: Decimal
    execution_price: Decimal
    target_price: Decimal
    slippage_bps: float
    timestamp: datetime
    mode: TradingMode
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def pnl(self) -> Decimal:
        """Calculate P&L."""
        if self.side == Side.BUY:
            return (self.execution_price - self.target_price) * self.quantity
        else:
            return (self.target_price - self.execution_price) * self.quantity


@dataclass
class PortfolioState:
    """
    Portfolio state snapshot.
    
    Attributes:
        timestamp: Snapshot timestamp
        cash: Available cash
        positions: Current positions
        total_value: Total portfolio value
        unrealized_pnl: Unrealized P&L
        realized_pnl: Realized P&L
    """
    timestamp: datetime
    cash: Decimal
    positions: Dict[str, Decimal] = field(default_factory=dict)
    total_value: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")


class PaperTradingEngine:
    """
    Paper trading engine for strategy validation.
    
    Features:
    - Real-time paper trading
    - Order simulation
    - Fill simulation
    - P&L tracking
    - Risk monitoring
    """
    
    def __init__(
        self,
        initial_cash: Decimal = Decimal("1000000"),
        instruments: List[Instrument] = None
    ):
        """
        Initialize paper trading engine.
        
        Args:
            initial_cash: Initial cash amount
            instruments: List of tradable instruments
        """
        self._initial_cash = initial_cash
        self._cash = initial_cash
        self._instruments = instruments or []
        self._order_books: Dict[str, L2OrderBook] = {}
        
        # Initialize order books for each instrument
        for instrument in self._instruments:
            self._order_books[instrument.symbol] = L2OrderBook(instrument)
        
        # State tracking
        self._positions: Dict[str, Decimal] = {}
        self._trades: List[PaperTrade] = []
        self._portfolio_history: List[PortfolioState] = []
        
        # Performance tracking
        self._total_pnl = Decimal("0")
        self._win_count = 0
        self._loss_count = 0
        
        # Latency and impact models
        self._latency_model = LatencyModel()
        self._impact_model = MarketImpactModel()
        
        # Risk limits
        self._max_position_size = Decimal("10000")
        self._max_total_exposure = Decimal("500000")
        self._max_drawdown = Decimal("0.15")  # 15%
    
    def submit_order(
        self,
        instrument: Instrument,
        side: Side,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: str = "GTC"
    ) -> str:
        """
        Submit order to paper trading engine.
        
        Args:
            instrument: Instrument to trade
            side: Order side
            order_type: Order type
            quantity: Order quantity
            price: Limit price (None for market orders)
            time_in_force: Time in force
            
        Returns:
            Order ID
        """
        # Risk checks
        if not self._check_risk_limits(instrument, side, quantity):
            raise ValueError("Order rejected by risk limits")
        
        # Get order book
        order_book = self._order_books.get(instrument.symbol)
        if order_book is None:
            order_book = L2OrderBook(instrument)
            self._order_books[instrument.symbol] = order_book
        
        # Determine execution price
        if price is None:
            # Market order
            if side == Side.BUY:
                price = order_book.best_ask or Decimal("0")
            else:
                price = order_book.best_bid or Decimal("0")
        
        # Apply latency model
        latency_us = self._latency_model.sample_latency(
            venue="NYSE",
            component=None,  # Total latency
            volatility_adjustment=1.0,
            time_of_day_adjustment=1.0
        )
        
        # Apply market impact
        avg_daily_volume = Decimal("10000000")
        perm_impact, temp_impact, total_impact = self._impact_model.calculate_impact(
            instrument=instrument,
            side=side,
            quantity=quantity,
            arrival_price=price,
            avg_daily_volume=avg_daily_volume,
            volatility=0.2,
            venue="NYSE"
        )
        
        # Adjust price for impact
        execution_price = price * (1 + Decimal(str(total_impact)) / Decimal("10000"))
        
        # Generate order ID
        order_id = f"paper_{datetime.now(timezone.utc).timestamp()}_{hash(str(instrument.symbol))}"
        
        # Simulate fill
        if self._simulate_fill(order_id, instrument, side, quantity, execution_price):
            # Record trade
            trade = PaperTrade(
                trade_id=f"trade_{order_id}",
                order_id=order_id,
                instrument=instrument,
                side=side,
                quantity=quantity,
                execution_price=execution_price,
                target_price=price,
                slippage_bps=float(total_impact),
                timestamp=datetime.now(timezone.utc),
                mode=TradingMode.PAPER
            )
            
            self._trades.append(trade)
            
            # Update position
            self._update_position(instrument, side, quantity, execution_price)
            
            # Update cash
            if side == Side.BUY:
                self._cash -= execution_price * quantity
            else:
                self._cash += execution_price * quantity
            
            # Track P&L
            self._total_pnl += trade.pnl
            
            # Track win/loss
            if trade.pnl > 0:
                self._win_count += 1
            else:
                self._loss_count += 1
        
        # Update portfolio state
        self._update_portfolio_state()
        
        return order_id
    
    def _check_risk_limits(
        self,
        instrument: Instrument,
        side: Side,
        quantity: Decimal
    ) -> bool:
        """Check if order passes risk limits."""
        # Check position size limit
        current_position = self._positions.get(instrument.symbol, Decimal("0"))
        new_position = current_position + quantity if side == Side.BUY else -quantity
        
        if abs(new_position) > self._max_position_size:
            return False
        
        # Check total exposure limit
        total_exposure = sum(abs(pos) for pos in self._positions.values())
        if total_exposure + quantity > self._max_total_exposure:
            return False
        
        # Check drawdown limit
        if self._total_pnl < -self._initial_cash * self._max_drawdown:
            return False
        
        return True
    
    def _simulate_fill(
        self,
        order_id: str,
        instrument: Instrument,
        side: Side,
        quantity: Decimal,
        price: Decimal
    ) -> bool:
        """Simulate order fill (simplified)."""
        # In production, this would use the order book to determine fills
        # For now, assume fills are always successful in paper trading
        return True
    
    def _update_position(
        self,
        instrument: Instrument,
        side: Side,
        quantity: Decimal,
        price: Decimal
    ) -> None:
        """Update position."""
        symbol = instrument.symbol
        current_position = self._positions.get(symbol, Decimal("0"))
        
        if side == Side.BUY:
            self._positions[symbol] = current_position + quantity
        else:
            self._positions[symbol] = current_position - quantity
    
    def _update_portfolio_state(self) -> None:
        """Update portfolio state snapshot."""
        # Calculate total value
        total_value = self._cash
        
        # Add position values
        for symbol, quantity in self._positions.items():
            order_book = self._order_books.get(symbol)
            if order_book:
                mid_price = order_book.mid_price
                if mid_price:
                    total_value += quantity * mid_price
        
        # Calculate unrealized P&L
        unrealized_pnl = total_value - self._initial_cash
        
        state = PortfolioState(
            timestamp=datetime.now(timezone.utc),
            cash=self._cash,
            positions=self._positions.copy(),
            total_value=total_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=self._total_pnl
        )
        
        self._portfolio_history.append(state)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if not self._portfolio_history:
            return {}
        
        # Calculate returns
        values = [state.total_value for state in self._portfolio_history]
        if len(values) > 1:
            returns = pd.Series(values).pct_change().dropna()
            
            total_return = float((values[-1] / values[0] - 1))
            
            if len(returns) > 0 and returns.std() > 0:
                sharpe_ratio = float(returns.mean() / returns.std() * np.sqrt(252))
            else:
                sharpe_ratio = 0.0
            
            # Calculate max drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = float(drawdown.min())
        else:
            total_return = 0.0
            sharpe_ratio = 0.0
            max_drawdown = 0.0
        
        win_rate = self._win_count / (self._win_count + self._loss_count) if (self._win_count + self._loss_count) > 0 else 0.0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(self._trades),
            'win_count': self._win_count,
            'loss_count': self._loss_count,
            'current_cash': float(self._cash),
            'total_value': float(self._portfolio_history[-1].total_value if self._portfolio_history else self._initial_cash),
        }


class ShadowTradingEngine:
    """
    Shadow trading engine for live order mirroring.
    
    Features:
    - Live order mirroring
    - Shadow fill simulation
    - Shadow vs live comparison
    - Execution quality analysis
    """
    
    def __init__(self, paper_engine: PaperTradingEngine):
        """
        Initialize shadow trading engine.
        
        Args:
            paper_engine: Paper trading engine for comparison
        """
        self._paper_engine = paper_engine
        self._shadow_trades: List[PaperTrade] = []
        self._live_trades: List[PaperTrade] = []
        self._comparison_metrics: Dict[str, Any] = {}
    
    def mirror_live_order(
        self,
        live_order_id: str,
        instrument: Instrument,
        side: Side,
        quantity: Decimal,
        live_price: Decimal
    ) -> str:
        """
        Mirror live order to shadow environment.
        
        Args:
            live_order_id: Live order ID
            instrument: Instrument
            side: Order side
            quantity: Order quantity
            live_price: Live execution price
            
        Returns:
            Shadow order ID
        """
        # Submit shadow order
        shadow_order_id = self._paper_engine.submit_order(
            instrument=instrument,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=live_price
        )
        
        return shadow_order_id
    
    def compare_performance(self) -> Dict[str, Any]:
        """
        Compare shadow vs live performance.
        
        Returns:
            Performance comparison metrics
        """
        if not self._shadow_trades or not self._live_trades:
            return {}
        
        # Calculate correlation between shadow and live P&L
        shadow_pnl = [trade.pnl for trade in self._shadow_trades]
        live_pnl = [trade.pnl for trade in self._live_trades]
        
        if len(shadow_pnl) > 1 and len(live_pnl) > 1:
            correlation = np.corrcoef(shadow_pnl, live_pnl)[0, 1]
        else:
            correlation = 0.0
        
        # Calculate slippage difference
        shadow_slippage = np.mean([trade.slippage_bps for trade in self._shadow_trades])
        live_slippage = np.mean([trade.slippage_bps for trade in self._live_trades])
        slippage_difference = shadow_slippage - live_slippage
        
        return {
            'correlation': correlation,
            'shadow_slippage_bps': shadow_slippage,
            'live_slippion_bps': live_slippage,
            'slippage_difference_bps': slippage_difference,
            'shadow_trade_count': len(self._shadow_trades),
            'live_trade_count': len(self._live_trades),
        }


class LongDurationValidator:
    """
    Long-duration paper/shadow validation orchestrator.
    
    Features:
    - Extended paper trading runs
    - Shadow trading validation
    - Performance tracking
    - Risk monitoring
    - Reporting
    """
    
    def __init__(self, duration_days: int = 30):
        """
        Initialize long-duration validator.
        
        Args:
            duration_days: Validation duration in days
        """
        self._duration_days = duration_days
        self._paper_engine = PaperTradingEngine()
        self._shadow_engine = ShadowTradingEngine(self._paper_engine)
        
        # Validation state
        self._start_date = datetime.now(timezone.utc)
        self._end_date = self._start_date + timedelta(days=duration_days)
        self._is_running = False
    
    def start_validation(self) -> None:
        """Start long-duration validation."""
        self._is_running = True
        self._start_date = datetime.now(timezone.utc)
        self._end_date = self._start_date + timedelta(days=self._duration_days)
    
    def stop_validation(self) -> None:
        """Stop validation and generate report."""
        self._is_running = False
        self._end_date = datetime.now(timezone.utc)
    
    def is_validation_complete(self) -> bool:
        """Check if validation is complete."""
        if not self._is_running:
            return datetime.now(timezone.utc) >= self._end_date
        return False
    
    def get_validation_report(self) -> Dict[str, Any]:
        """
        Get validation report.
        
        Returns:
            Complete validation report
        """
        paper_metrics = self._paper_engine.get_performance_metrics()
        shadow_metrics = self._shadow_engine.compare_performance()
        
        return {
            'validation_period': {
                'start_date': self._start_date.isoformat(),
                'end_date': self._end_date.isoformat(),
                'duration_days': self._duration_days,
                'is_complete': self.is_validation_complete(),
            },
            'paper_trading': {
                'metrics': paper_metrics,
                'trade_count': len(self._paper_engine._trades),
            },
            'shadow_trading': {
                'metrics': shadow_metrics,
                'comparison': shadow_metrics,
            },
            'overall': {
                'paper_sharpe': paper_metrics.get('sharpe_ratio', 0),
                'paper_max_drawdown': paper_metrics.get('max_drawdown', 0),
                'shadow_live_correlation': shadow_metrics.get('correlation', 0),
                'validation_status': 'complete' if self.is_validation_complete() else 'in_progress',
            }
        }


__all__ = [
    "TradingMode",
    "PaperTrade",
    "PortfolioState",
    "PaperTradingEngine",
    "ShadowTradingEngine",
    "LongDurationValidator",
]
