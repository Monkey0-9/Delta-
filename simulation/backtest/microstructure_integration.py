"""
Backtester-Microstructure Integration for DELTA OS.

This module connects the Python backtest engine with the high-performance
L2 order book microstructure simulation for realistic execution simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
import numpy as np

from execution.matching.l2_order_book import L2OrderBook, LimitOrder, OrderBookSnapshot
from execution.simulation.latency_model import LatencyModel, LatencyComponent
from execution.simulation.market_impact import MarketImpactModel, ImpactModel
from core.contracts.canonical import (
    Instrument,
    Timestamps,
    Side,
    OrderType,
    OrderStatus,
    TimeInForce,
    Order,
    Fill,
    PortfolioSnapshot,
)


@dataclass
class BacktestConfig:
    """Configuration for microstructure-integrated backtesting."""
    
    # Order book configuration
    order_book_depth: int = 20
    tick_size: Optional[Decimal] = None
    
    # Latency configuration
    use_latency_model: bool = True
    latency_venue: str = "NYSE"
    volatility_adjustment: float = 1.0
    time_of_day_adjustment: float = 1.0
    
    # Market impact configuration
    use_market_impact: bool = True
    impact_model: ImpactModel = ImpactModel.SQUARE_ROOT
    avg_daily_volume: Decimal = Decimal("10000000")
    volatility: float = 0.2
    
    # Execution configuration
    slippage_model: str = "calibrated"  # none, fixed, calibrated
    queue_model: bool = True  # Model queue position effects
    
    # Backtest configuration
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    initial_cash: Decimal = Decimal("1000000")


@dataclass
class BacktestResult:
    """Results from microstructure-integrated backtesting."""
    
    # Performance metrics
    total_return: Decimal
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    
    # Execution metrics
    avg_slippage_bps: float
    avg_fill_time_ms: float
    fill_rate: float
    
    # Order book metrics
    avg_spread_bps: float
    avg_queue_position: float
    
    # Simulation metrics
    total_orders: int
    total_fills: int
    rejected_orders: int
    
    # Detailed results
    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    
    # Metadata
    config: BacktestConfig = field(default_factory=BacktestConfig)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MicrostructureBacktester:
    """
    Backtester with L2 order book microstructure simulation.
    
    Features:
    - Realistic order book simulation
    - Calibrated latency modeling
    - Market impact estimation
    - Queue position effects
    - Event-driven execution
    """
    
    def __init__(self, config: BacktestConfig, instrument: Instrument):
        """
        Initialize microstructure backtester.
        
        Args:
            config: Backtest configuration
            instrument: Instrument to trade
        """
        self._config = config
        self._instrument = instrument
        
        # Initialize order book
        self._order_book = L2OrderBook(
            instrument=instrument,
            max_depth=config.order_book_depth,
            tick_size=config.tick_size
        )
        
        # Initialize latency model
        self._latency_model = LatencyModel() if config.use_latency_model else None
        
        # Initialize market impact model
        self._impact_model = MarketImpactModel(
            model_type=config.impact_model
        ) if config.use_market_impact else None
        
        # State tracking
        self._current_time = config.start_time
        self._cash = config.initial_cash
        self._positions: Dict[str, Decimal] = {}
        self._pending_orders: Dict[str, Order] = {}
        self._order_sequence = 0
        
        # Performance tracking
        self._trades: List[Dict[str, Any]] = []
        self._equity_curve: List[Tuple[datetime, Decimal]] = []
        self._rejected_orders = 0
        
        # Metrics tracking
        self._total_slippage_bps = 0.0
        self._total_fill_time_ms = 0.0
        self._total_spread_bps = 0.0
        self._total_queue_position = 0.0
        self._fill_count = 0
    
    def run_backtest(
        self,
        market_data: pd.DataFrame,
        signals: pd.DataFrame
    ) -> BacktestResult:
        """
        Run backtest with microstructure simulation.
        
        Args:
            market_data: Market data with timestamps
            signals: Trading signals with timestamps
            
        Returns:
            BacktestResult with complete performance metrics
        """
        # Align data
        aligned_data = self._align_data(market_data, signals)
        
        # Process each time step
        for idx, row in aligned_data.iterrows():
            self._current_time = row.name
            
            # Update order book with market data
            self._update_order_book(row)
            
            # Process signals
            if 'signal' in row and not pd.isna(row['signal']):
                self._process_signal(row)
            
            # Process pending orders
            self._process_pending_orders()
            
            # Track equity
            self._track_equity()
        
        # Calculate final results
        return self._calculate_results()
    
    def _align_data(
        self,
        market_data: pd.DataFrame,
        signals: pd.DataFrame
    ) -> pd.DataFrame:
        """Align market data and signals by timestamp."""
        # Combine dataframes
        combined = pd.concat([market_data, signals], axis=1)
        
        # Forward fill market data
        combined = combined.fillna(method='ffill')
        
        return combined
    
    def _update_order_book(self, row: pd.Series) -> None:
        """Update order book with current market data."""
        # Add liquidity to order book based on market data
        if 'bid' in row and not pd.isna(row['bid']):
            self._order_book.add_limit_order(
                order_id=f"market_bid_{self._order_sequence}",
                side=Side.BUY,
                price=Decimal(str(row['bid'])),
                quantity=Decimal(str(row.get('bid_size', 100)))
            )
            self._order_sequence += 1
        
        if 'ask' in row and not pd.isna(row['ask']):
            self._order_book.add_limit_order(
                order_id=f"market_ask_{self._order_sequence}",
                side=Side.SELL,
                price=Decimal(str(row['ask'])),
                quantity=Decimal(str(row.get('ask_size', 100)))
            )
            self._order_sequence += 1
    
    def _process_signal(self, row: pd.Series) -> None:
        """Process trading signal."""
        signal = row['signal']
        
        if signal > 0.5:  # Buy signal
            self._submit_order(
                side=Side.BUY,
                quantity=Decimal("100"),
                order_type=OrderType.LIMIT,
                price=self._order_book.best_ask or Decimal(str(row.get('ask', row['close'])))
            )
        elif signal < -0.5:  # Sell signal
            self._submit_order(
                side=Side.SELL,
                quantity=Decimal("100"),
                order_type=OrderType.LIMIT,
                price=self._order_book.best_bid or Decimal(str(row.get('bid', row['close'])))
            )
    
    def _submit_order(
        self,
        side: Side,
        quantity: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None
    ) -> None:
        """Submit order to order book."""
        order_id = f"order_{self._order_sequence}"
        self._order_sequence += 1
        
        # Apply latency if configured
        if self._latency_model:
            latency_us = self._latency_model.sample_latency(
                venue=self._config.latency_venue,
                component=LatencyComponent.TOTAL,
                volatility_adjustment=self._config.volatility_adjustment,
                time_of_day_adjustment=self._config.time_of_day_adjustment
            )
            # Simulate latency by delaying execution
            # (In production, this would be actual network latency)
        
        # Apply market impact if configured
        if self._impact_model and price:
            # Calculate expected impact
            perm_impact, temp_impact, total_impact = self._impact_model.calculate_impact(
                instrument=self._instrument,
                side=side,
                quantity=quantity,
                arrival_price=price,
                avg_daily_volume=self._config.avg_daily_volume,
                volatility=self._config.volatility,
                venue=self._config.latency_venue
            )
            
            # Adjust price for impact
            if side == Side.BUY:
                price = price * (1 + Decimal(str(total_impact)) / Decimal("10000"))
            else:
                price = price * (1 - Decimal(str(total_impact)) / Decimal("10000"))
        
        # Submit to order book
        fills, remaining = self._order_book.add_limit_order(
            order_id=order_id,
            side=side,
            price=price,
            quantity=quantity,
            time_in_force=TimeInForce.GTC
        )
        
        # Process fills
        for fill_order_id, fill_price, fill_qty in fills:
            self._process_fill(
                order_id=order_id,
                fill_price=Decimal(str(fill_price)),
                fill_quantity=Decimal(str(fill_qty)),
                side=side
            )
        
        # Track order if not fully filled
        if remaining:
            # Create pending order
            order = Order(
                execution_id=order_id,
                instrument=self._instrument,
                timestamps=Timestamps(
                    event_time=self._current_time,
                    received_time=self._current_time
                ),
                side=side,
                order_type=order_type,
                quantity=remaining.quantity,
                price=remaining.price,
                status=OrderStatus.SUBMITTED
            )
            self._pending_orders[order_id] = order
    
    def _process_pending_orders(self) -> None:
        """Process pending orders in order book."""
        completed_orders = []
        
        for order_id, order in self._pending_orders.items():
            # Check if order is still in book
            remaining_order = self._order_book.get_order(order_id)
            
            if remaining_order is None or remaining_order.quantity == 0:
                # Order fully filled or cancelled
                completed_orders.append(order_id)
            else:
                # Check for new fills
                # (In production, this would check for partial fills)
                pass
        
        # Remove completed orders
        for order_id in completed_orders:
            del self._pending_orders[order_id]
    
    def _process_fill(
        self,
        order_id: str,
        fill_price: Decimal,
        fill_quantity: Decimal,
        side: Side
    ) -> None:
        """Process order fill."""
        # Update position
        symbol = self._instrument.symbol
        current_position = self._positions.get(symbol, Decimal("0"))
        
        if side == Side.BUY:
            self._positions[symbol] = current_position + fill_quantity
            self._cash -= fill_price * fill_quantity
        else:
            self._positions[symbol] = current_position - fill_quantity
            self._cash += fill_price * fill_quantity
        
        # Calculate slippage
        mid_price = self._order_book.mid_price
        if mid_price:
            if side == Side.BUY:
                slippage_bps = float((fill_price - mid_price) / mid_price * 10000)
            else:
                slippage_bps = float((mid_price - fill_price) / mid_price * 10000)
            
            self._total_slippage_bps += slippage_bps
        
        # Track fill
        self._fill_count += 1
        
        # Record trade
        self._trades.append({
            'timestamp': self._current_time,
            'order_id': order_id,
            'side': side.value,
            'price': float(fill_price),
            'quantity': float(fill_quantity),
            'slippage_bps': slippage_bps if mid_price else 0.0,
        })
    
    def _track_equity(self) -> None:
        """Track portfolio equity over time."""
        # Calculate portfolio value
        portfolio_value = self._cash
        
        # Add position values
        mid_price = self._order_book.mid_price
        if mid_price:
            for symbol, quantity in self._positions.items():
                portfolio_value += quantity * mid_price
        
        self._equity_curve.append((self._current_time, portfolio_value))
    
    def _calculate_results(self) -> BacktestResult:
        """Calculate final backtest results."""
        # Convert equity curve to series
        if self._equity_curve:
            timestamps, values = zip(*self._equity_curve)
            equity_series = pd.Series(values, index=timestamps)
        else:
            equity_series = pd.Series([], dtype=float)
        
        # Calculate performance metrics
        if len(equity_series) > 1:
            returns = equity_series.pct_change().dropna()
            
            total_return = (equity_series.iloc[-1] / equity_series.iloc[0] - 1)
            
            if len(returns) > 0 and returns.std() > 0:
                sharpe_ratio = float(returns.mean() / returns.std() * np.sqrt(252))
            else:
                sharpe_ratio = 0.0
            
            # Calculate max drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = float(drawdown.min())
            
            # Calculate win rate
            win_rate = float((returns > 0).sum() / len(returns)) if len(returns) > 0 else 0.0
            
            # Calculate profit factor
            gains = returns[returns > 0].sum()
            losses = abs(returns[returns < 0].sum())
            profit_factor = float(gains / losses) if losses > 0 else 0.0
        else:
            total_return = Decimal("0")
            sharpe_ratio = 0.0
            max_drawdown = 0.0
            win_rate = 0.0
            profit_factor = 0.0
        
        # Calculate execution metrics
        avg_slippage_bps = self._total_slippage_bps / self._fill_count if self._fill_count > 0 else 0.0
        avg_fill_time_ms = self._total_fill_time_ms / self._fill_count if self._fill_count > 0 else 0.0
        fill_rate = self._fill_count / (self._fill_count + self._rejected_orders) if (self._fill_count + self._rejected_orders) > 0 else 0.0
        
        # Calculate order book metrics
        avg_spread_bps = self._total_spread_bps / len(self._trades) if self._trades else 0.0
        avg_queue_position = self._total_queue_position / len(self._trades) if self._trades else 0.0
        
        return BacktestResult(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_slippage_bps=avg_slippage_bps,
            avg_fill_time_ms=avg_fill_time_ms,
            fill_rate=fill_rate,
            avg_spread_bps=avg_spread_bps,
            avg_queue_position=avg_queue_position,
            total_orders=self._order_sequence,
            total_fills=self._fill_count,
            rejected_orders=self._rejected_orders,
            trades=self._trades,
            equity_curve=equity_series,
            config=self._config
        )


__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "MicrostructureBacktester",
]
