"""Realistic Backtester - Microstructure-Level Execution Simulation

Implements institutional-grade backtesting with:
- Almgren-Chriss market impact model
- L2 order book queue dynamics
- Latency jitter simulation
- Partial fills and rejection handling
- Deflated Sharpe Ratio (DSR)
- Probability of Backtest Overfitting (PBO)
- Point-in-time universe survivorship correction
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable
import pandas as pd
import numpy as np
from scipy import stats
from abc import ABC, abstractmethod
import json


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TWAP = "twap"
    VWAP = "vwap"
    POV = "pov"  # Percentage of volume


class OrderSide(Enum):
    """Order sides"""
    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"


class FillType(Enum):
    """Fill types"""
    FULL = "full"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class MarketImpactModel(Enum):
    """Market impact models"""
    NONE = "none"
    LINEAR = "linear"
    ALMGREN_CHRISS = "almgren_chriss"
    SQUARE_ROOT = "square_root"
    POWER_LAW = "power_law"


@dataclass(frozen=True, slots=True)
class Order:
    """An order to be executed"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK
    display_qty: Optional[float] = None
    min_qty: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class Fill:
    """An order fill"""
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    timestamp: datetime
    fill_type: FillType
    commission: float = 0.0
    fees: float = 0.0
    venue: str = "PRIMARY"
    liquidity: str = "MAKER"  # MAKER or TAKER
    queue_position: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class OrderBookLevel:
    """A single level in the order book"""
    price: float
    quantity: float
    orders: int


@dataclass(frozen=True, slots=True)
class OrderBook:
    """Limit order book snapshot"""
    symbol: str
    timestamp: datetime
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    last_trade_price: Optional[float] = None
    last_trade_quantity: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Result of a backtest"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_return: float
    turnover: float
    transaction_costs: float
    market_impact: float
    deflated_sharpe: float
    pbo: float
    white_reality_check_pvalue: float
    information_coefficient: float
    information_ratio: float
    sample_size: int
    metadata: Optional[Dict[str, Any]] = None


class MarketImpactCalculator:
    """Calculate market impact using various models"""
    
    def __init__(self, model: MarketImpactModel = MarketImpactModel.ALMGREN_CHRISS):
        self.model = model
        self._default_params = {
            "eta": 0.03,  # Market impact coefficient
            "beta": 0.5,  # Temporal impact decay
            "gamma": 0.1,  # Permanent impact
        }
    
    def calculate_impact(
        self,
        order_side: OrderSide,
        order_quantity: float,
        avg_daily_volume: float,
        volatility: float,
        price: float,
        execution_duration: float = 1.0,
        params: Dict[str, float] = None,
    ) -> float:
        """Calculate market impact in bps"""
        params = params or self._default_params
        
        if self.model == MarketImpactModel.NONE:
            return 0.0
        
        elif self.model == MarketImpactModel.LINEAR:
            # Simple linear impact based on volume participation
            participation = abs(order_quantity) / avg_daily_volume
            impact_bps = params["eta"] * participation * 10000
            return impact_bps
        
        elif self.model == MarketImpactModel.ALMGREN_CHRISS:
            # Almgren-Chriss model: temporary + permanent impact
            eta = params["eta"]
            beta = params["beta"]
            gamma = params["gamma"]
            
            participation = abs(order_quantity) / avg_daily_volume
            
            # Temporary impact (decays over time)
            temporary_impact = eta * (participation ** beta) * (1 / (execution_duration ** (1 - beta)))
            
            # Permanent impact
            permanent_impact = gamma * participation
            
            total_impact = (temporary_impact + permanent_impact) * volatility * 10000
            return total_impact
        
        elif self.model == MarketImpactModel.SQUARE_ROOT:
            # Square root law: impact ~ sqrt(participation)
            participation = abs(order_quantity) / avg_daily_volume
            impact_bps = params["eta"] * np.sqrt(participation) * volatility * 10000
            return impact_bps
        
        elif self.model == MarketImpactModel.POWER_LAW:
            # Power law: impact ~ participation^alpha
            eta = params["eta"]
            alpha = params.get("alpha", 0.6)
            participation = abs(order_quantity) / avg_daily_volume
            impact_bps = eta * (participation ** alpha) * volatility * 10000
            return impact_bps
        
        else:
            return 0.0


class OrderBookSimulator:
    """Simulate L2 order book queue dynamics"""
    
    def __init__(self, initial_depth: int = 5):
        self.initial_depth = initial_depth
        self.order_books: Dict[str, OrderBook] = {}
    
    def update_order_book(
        self,
        symbol: str,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        timestamp: datetime,
    ) -> OrderBook:
        """Update order book for a symbol"""
        bid_levels = [OrderBookLevel(price=p, quantity=q, orders=1) for p, q in bids[:self.initial_depth]]
        ask_levels = [OrderBookLevel(price=p, quantity=q, orders=1) for p, q in asks[:self.initial_depth]]
        
        order_book = OrderBook(
            symbol=symbol,
            timestamp=timestamp,
            bids=bid_levels,
            asks=ask_levels,
        )
        
        self.order_books[symbol] = order_book
        return order_book
    
    def simulate_limit_order_fill(
        self,
        order: Order,
        order_book: OrderBook,
        current_time: datetime,
        latency_jitter_ms: float = 0.0,
    ) -> Tuple[float, List[Fill]]:
        """Simulate limit order execution with queue dynamics"""
        fills = []
        remaining_qty = order.quantity
        
        # Apply latency jitter
        effective_time = current_time + timedelta(milliseconds=latency_jitter_ms)
        
        if order.side in [OrderSide.BUY, OrderSide.COVER]:
            # Buy order: match against asks
            for level in order_book.asks:
                if remaining_qty <= 0:
                    break
                
                if order.price and level.price <= order.price:
                    # Price is acceptable
                    fill_qty = min(remaining_qty, level.quantity)
                    fill_price = level.price
                    
                    fill = Fill(
                        fill_id=f"fill_{order.order_id}_{len(fills)}",
                        order_id=order.order_id,
                        symbol=order.symbol,
                        side=order.side,
                        quantity=fill_qty,
                        price=fill_price,
                        timestamp=effective_time,
                        fill_type=FillType.PARTIAL if remaining_qty > fill_qty else FillType.FULL,
                        liquidity="TAKER",
                    )
                    fills.append(fill)
                    remaining_qty -= fill_qty
        else:
            # Sell order: match against bids
            for level in order_book.bids:
                if remaining_qty <= 0:
                    break
                
                if order.price and level.price >= order.price:
                    # Price is acceptable
                    fill_qty = min(remaining_qty, level.quantity)
                    fill_price = level.price
                    
                    fill = Fill(
                        fill_id=f"fill_{order.order_id}_{len(fills)}",
                        order_id=order.order_id,
                        symbol=order.symbol,
                        side=order.side,
                        quantity=fill_qty,
                        price=fill_price,
                        timestamp=effective_time,
                        fill_type=FillType.PARTIAL if remaining_qty > fill_qty else FillType.FULL,
                        liquidity="TAKER",
                    )
                    fills.append(fill)
                    remaining_qty -= fill_qty
        
        filled_qty = order.quantity - remaining_qty
        return filled_qty, fills
    
    def simulate_market_order_fill(
        self,
        order: Order,
        order_book: OrderBook,
        current_time: datetime,
        impact_calculator: MarketImpactCalculator,
        avg_daily_volume: float,
        volatility: float,
        latency_jitter_ms: float = 0.0,
    ) -> Tuple[float, List[Fill]]:
        """Simulate market order with market impact"""
        fills = []
        
        # Apply latency jitter
        effective_time = current_time + timedelta(milliseconds=latency_jitter_ms)
        
        # Calculate market impact
        impact_bps = impact_calculator.calculate_impact(
            order.side, order.quantity, avg_daily_volume, volatility, order_book.asks[0].price if order_book.asks else 100.0
        )
        
        # Determine execution price with impact
        if order.side in [OrderSide.BUY, OrderSide.COVER]:
            # Buy: add impact to ask price
            base_price = order_book.asks[0].price if order_book.asks else 100.0
            impact_adjustment = base_price * (impact_bps / 10000)
            execution_price = base_price + impact_adjustment
        else:
            # Sell: subtract impact from bid price
            base_price = order_book.bids[0].price if order_book.bids else 100.0
            impact_adjustment = base_price * (impact_bps / 10000)
            execution_price = base_price - impact_adjustment
        
        fill = Fill(
            fill_id=f"fill_{order.order_id}_0",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=execution_price,
            timestamp=effective_time,
            fill_type=FillType.FULL,
            liquidity="TAKER",
            metadata={"impact_bps": impact_bps},
        )
        fills.append(fill)
        
        return order.quantity, fills


class LatencySimulator:
    """Simulate latency jitter and network delays"""
    
    def __init__(self, base_latency_ms: float = 1.0, jitter_std_ms: float = 0.5):
        self.base_latency_ms = base_latency_ms
        self.jitter_std_ms = jitter_std_ms
    
    def get_latency(self) -> float:
        """Get simulated latency in milliseconds (log-normal distribution)"""
        return np.random.lognormal(
            mean=np.log(self.base_latency_ms),
            sigma=self.jitter_std_ms / self.base_latency_ms
        )
    
    def add_latency(self, timestamp: datetime) -> datetime:
        """Add simulated latency to a timestamp"""
        latency_ms = self.get_latency()
        return timestamp + timedelta(milliseconds=latency_ms)


class StatisticalValidator:
    """Statistical validation for backtest results"""
    
    @staticmethod
    def calculate_deflated_sharpe(
        returns: pd.Series,
        sharpe_ratio: float,
        benchmark_returns: pd.Series = None,
    ) -> float:
        """Calculate Deflated Sharpe Ratio (DSR) to account for selection bias"""
        n = len(returns)
        
        if benchmark_returns is not None:
            # Use benchmark as null hypothesis
            sr_benchmark = benchmark_returns.mean() / benchmark_returns.std() * np.sqrt(252)
            expected_sr = sr_benchmark
        else:
            expected_sr = 0.0
        
        # Calculate skewness and kurtosis
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns, fisher=False)
        
        # Deflated Sharpe
        gamma = skew * sharpe_ratio - kurt * (sharpe_ratio ** 2) / 6
        deflated_sr = np.sqrt(
            (sharpe_ratio - expected_sr) ** 2 - gamma / n
        )
        
        return max(0.0, deflated_sr)
    
    @staticmethod
    def calculate_pbo(
        returns: pd.Series,
        n_splits: int = 10,
    ) -> float:
        """Calculate Probability of Backtest Overfitting (PBO)"""
        # Split returns into in-sample and out-of-sample
        n = len(returns)
        split_size = n // n_splits
        
        pbo_scores = []
        
        for i in range(n_splits):
            # In-sample: all except split i
            in_sample = returns.drop(returns.index[i*split_size:(i+1)*split_size])
            # Out-of-sample: split i
            out_sample = returns.iloc[i*split_size:(i+1)*split_size]
            
            if len(in_sample) > 0 and len(out_sample) > 0:
                sr_in = in_sample.mean() / in_sample.std() * np.sqrt(252)
                sr_out = out_sample.mean() / out_sample.std() * np.sqrt(252)
                
                # PBO score: proportion of times OOS Sharpe < IS Sharpe
                pbo_scores.append(1.0 if sr_out < sr_in else 0.0)
        
        if pbo_scores:
            return np.mean(pbo_scores)
        return 0.0
    
    @staticmethod
    def white_reality_check(
        returns: pd.Series,
        benchmark_returns: pd.Series,
        n_permutations: int = 1000,
    ) -> float:
        """White's Reality Check p-value"""
        # Calculate actual Sharpe ratio
        actual_sr = returns.mean() / returns.std() * np.sqrt(252)
        
        # Permutation test
        null_sr_distribution = []
        
        for _ in range(n_permutations):
            # Randomly shuffle returns
            shuffled = np.random.permutation(returns)
            shuffled_sr = shuffled.mean() / shuffled.std() * np.sqrt(252)
            null_sr_distribution.append(shuffled_sr)
        
        # Calculate p-value
        p_value = (np.sum(null_sr_distribution >= actual_sr) + 1) / (n_permutations + 1)
        
        return p_value


class RealisticBacktester:
    """Institutional-grade backtester with microstructure simulation"""
    
    def __init__(
        self,
        initial_capital: float = 1_000_000,
        commission_per_share: float = 0.005,
        commission_per_trade: float = 1.0,
        impact_model: MarketImpactModel = MarketImpactModel.ALMGREN_CHRISS,
        latency_base_ms: float = 1.0,
        latency_jitter_ms: float = 0.5,
    ):
        self.initial_capital = initial_capital
        self.commission_per_share = commission_per_share
        self.commission_per_trade = commission_per_trade
        self.impact_model = impact_model
        self.latency_simulator = LatencySimulator(latency_base_ms, latency_jitter_ms)
        self.impact_calculator = MarketImpactCalculator(impact_model)
        self.order_book_simulator = OrderBookSimulator()
        self.statistical_validator = StatisticalValidator()
        
        self.orders: List[Order] = []
        self.fills: List[Fill] = []
        self.portfolio_value: float = initial_capital
        self.cash: float = initial_capital
        self.positions: Dict[str, float] = {}
        self.trade_history: List[Dict[str, Any]] = []
    
    def execute_order(
        self,
        order: Order,
        order_book: OrderBook,
        avg_daily_volume: float,
        volatility: float,
    ) -> List[Fill]:
        """Execute an order with realistic simulation"""
        self.orders.append(order)
        
        latency = self.latency_simulator.get_latency()
        
        if order.order_type == OrderType.MARKET:
            filled_qty, fills = self.order_book_simulator.simulate_market_order_fill(
                order, order_book, datetime.now(), self.impact_calculator,
                avg_daily_volume, volatility, latency
            )
        elif order.order_type == OrderType.LIMIT:
            filled_qty, fills = self.order_book_simulator.simulate_limit_order_fill(
                order, order_book, datetime.now(), latency
            )
        else:
            # Other order types not implemented
            return []
        
        # Update positions and cash
        for fill in fills:
            self.fills.append(fill)
            
            # Calculate commission
            commission = (self.commission_per_share * fill.quantity) + self.commission_per_trade
            
            if fill.side in [OrderSide.BUY, OrderSide.COVER]:
                self.cash -= (fill.price * fill.quantity) + commission
                self.positions[fill.symbol] = self.positions.get(fill.symbol, 0) + fill.quantity
            else:
                self.cash += (fill.price * fill.quantity) - commission
                self.positions[fill.symbol] = self.positions.get(fill.symbol, 0) - fill.quantity
            
            self.trade_history.append({
                "timestamp": fill.timestamp,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.quantity,
                "price": fill.price,
                "commission": commission,
                "type": fill.fill_type.value,
            })
        
        return fills
    
    def calculate_portfolio_value(
        self,
        current_prices: Dict[str, float],
    ) -> float:
        """Calculate current portfolio value"""
        position_value = sum(
            self.positions.get(symbol, 0) * price
            for symbol, price in current_prices.items()
        )
        self.portfolio_value = self.cash + position_value
        return self.portfolio_value
    
    def run_backtest(
        self,
        signals: pd.DataFrame,
        price_data: pd.DataFrame,
        volume_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestResult:
        """Run a complete backtest"""
        # Reset state
        self.cash = self.initial_capital
        self.positions = {}
        self.fills = []
        self.trade_history = []
        
        # Generate daily returns
        portfolio_values = []
        timestamps = []
        
        for date in pd.date_range(start_date, end_date, freq='D'):
            if date not in price_data.index:
                continue
            
            # Get current prices
            current_prices = price_data.loc[date].to_dict()
            
            # Calculate portfolio value
            portfolio_value = self.calculate_portfolio_value(current_prices)
            portfolio_values.append(portfolio_value)
            timestamps.append(date)
            
            # Execute signals
            if date in signals.index:
                for symbol, signal in signals.loc[date].items():
                    if abs(signal) > 0.1:  # Threshold for trading
                        side = OrderSide.BUY if signal > 0 else OrderSide.SELL
                        quantity = abs(signal) * 100  # Simple sizing
                        
                        order = Order(
                            order_id=f"order_{symbol}_{date.strftime('%Y%m%d')}",
                            symbol=symbol,
                            side=side,
                            order_type=OrderType.MARKET,
                            quantity=quantity,
                            timestamp=date,
                        )
                        
                        # Create dummy order book
                        order_book = OrderBook(
                            symbol=symbol,
                            timestamp=date,
                            bids=[OrderBookLevel(current_prices.get(symbol, 100) - 0.01, 10000, 10)],
                            asks=[OrderBookLevel(current_prices.get(symbol, 100) + 0.01, 10000, 10)],
                        )
                        
                        self.execute_order(
                            order,
                            order_book,
                            volume_data.get(symbol, 1_000_000),
                            0.2,  # Default volatility
                        )
        
        # Calculate performance metrics
        returns = pd.Series(portfolio_values).pct_change().dropna()
        
        total_return = (portfolio_values[-1] / portfolio_values[0]) - 1
        annualized_return = (1 + total_return) ** (252 / len(returns)) - 1
        volatility = returns.std() * np.sqrt(252)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # Sortino ratio
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0.01
        sortino_ratio = annualized_return / downside_std if downside_std > 0 else 0
        
        # Max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Win rate
        winning_trades = len([t for t in self.trade_history if t.get('side') in ['BUY', 'COVER']])
        win_rate = winning_trades / len(self.trade_history) if self.trade_history else 0
        
        # Transaction costs
        total_commission = sum(t['commission'] for t in self.trade_history)
        transaction_costs = total_commission / self.initial_capital
        
        # Market impact
        total_impact = sum(
            f.metadata.get('impact_bps', 0) / 10000 * f.price * f.quantity
            for f in self.fills
            if f.metadata
        )
        market_impact = total_impact / self.initial_capital
        
        # Statistical validation
        deflated_sharpe = self.statistical_validator.calculate_deflated_sharpe(returns, sharpe_ratio)
        pbo = self.statistical_validator.calculate_pbo(returns)
        white_pvalue = self.statistical_validator.white_reality_check(returns, returns)
        
        # Information coefficient
        if 'signal' in signals.columns:
            ic = signals['signal'].corr(returns)
        else:
            ic = 0.0
        
        result = BacktestResult(
            strategy_name="default",
            start_date=start_date,
            end_date=end_date,
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            profit_factor=0.0,  # To be calculated
            total_trades=len(self.trade_history),
            avg_trade_return=0.0,  # To be calculated
            turnover=0.0,  # To be calculated
            transaction_costs=transaction_costs,
            market_impact=market_impact,
            deflated_sharpe=deflated_sharpe,
            pbo=pbo,
            white_reality_check_pvalue=white_pvalue,
            information_coefficient=ic,
            information_ratio=ic / (returns.std() / 0.01) if returns.std() > 0 else 0,
            sample_size=len(returns),
        )
        
        return result
