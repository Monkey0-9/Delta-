"""
Local paper trading engine with realistic simulation
"""

import random
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from delta.trading.broker_base import (
    PaperBrokerAdapter, Order, Position, AccountInfo, OrderResult,
    OrderSide, OrderType, OrderStatus, TimeInForce, Balance
)

logger = logging.getLogger(__name__)


class PaperTradingEngine(PaperBrokerAdapter):
    """Realistic paper trading engine with slippage and spread simulation"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.account_id = "PAPER-DEMO"
        self.cash = config.get("initial_balance", 100000.0)
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        self.market_data: Dict[str, Dict[str, float]] = {}
        
        # Simulation parameters
        self.spread_bps = config.get("spread_bps", 10)  # 10 bps spread
        self.slippage_bps = config.get("slippage_bps", 5)  # 5 bps slippage
        self.fill_probability = config.get("fill_probability", 0.95)
        self.commission_per_share = config.get("commission_per_share", 0.01)
    
    async def initialize(self) -> bool:
        """Initialize the paper engine"""
        self._initialized = True
        logger.info(f"Initialized Paper Trading Engine with ${self.cash:,.2f}")
        return True
    
    async def connect(self) -> bool:
        """Connect to paper engine"""
        self._connected = True
        logger.info("Paper engine connected")
        return True
    
    async def disconnect(self) -> bool:
        """Disconnect from paper engine"""
        self._connected = False
        logger.info("Paper engine disconnected")
        return True
    
    async def get_account(self) -> Optional[AccountInfo]:
        """Get account information"""
        portfolio_value = self.cash + sum(
            pos.market_value for pos in self.positions.values()
        )
        margin_used = sum(
            pos.market_value * 0.5 for pos in self.positions.values() 
            if pos.side == OrderSide.SELL
        )
        
        return AccountInfo(
            account_id=self.account_id,
            account_type="paper",
            buying_power=self.cash,
            cash=self.cash,
            portfolio_value=portfolio_value,
            margin_used=margin_used,
            margin_available=self.cash - margin_used,
            day_trading_buying_power=self.cash * 4,
            last_equity=portfolio_value,
            last_maintenance_margin=margin_used * 0.25,
            daytrade_count=0,
            timestamp=datetime.utcnow()
        )
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions"""
        # Update market values based on current prices
        for symbol, position in self.positions.items():
            current_price = self._get_current_price(symbol)
            if current_price:
                position.current_price = current_price
                position.market_value = position.quantity * current_price
                unrealized_pl = (current_price - position.avg_entry_price) * position.quantity
                if position.side == OrderSide.SELL:
                    unrealized_pl = -unrealized_pl
                position.unrealized_pl = unrealized_pl
                position.unrealized_pl_pct = (unrealized_pl / position.cost_basis) * 100 if position.cost_basis > 0 else 0
                position.timestamp = datetime.utcnow()
        
        return list(self.positions.values())
    
    async def get_orders(self) -> List[Order]:
        """Get all open orders"""
        return [order for order in self.orders.values() if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]]
    
    async def place_order(self, order: Order) -> OrderResult:
        """Place an order"""
        if not self._connected:
            return OrderResult(success=False, message="Not connected")
        
        # Generate order ID
        self.order_counter += 1
        order.order_id = f"PAPER-{self.order_counter:06d}"
        order.created_at = datetime.utcnow()
        order.updated_at = datetime.utcnow()
        
        # Get current price
        current_price = self._get_current_price(order.symbol)
        if not current_price:
            return OrderResult(success=False, message=f"No market data for {order.symbol}")
        
        # Simulate order processing
        if order.order_type == OrderType.MARKET:
            return await self._execute_market_order(order, current_price)
        elif order.order_type == OrderType.LIMIT:
            return await self._execute_limit_order(order, current_price)
        elif order.order_type == OrderType.STOP:
            return await self._execute_stop_order(order, current_price)
        else:
            return OrderResult(success=False, message=f"Order type {order.order_type} not supported")
    
    async def _execute_market_order(self, order: Order, current_price: float) -> OrderResult:
        """Execute a market order with slippage"""
        # Calculate execution price with slippage
        slippage = current_price * (self.slippage_bps / 10000)
        if order.side == OrderSide.BUY:
            execution_price = current_price + slippage
        else:
            execution_price = current_price - slippage
        
        # Check buying power
        required_capital = order.quantity * execution_price
        if order.side == OrderSide.BUY and required_capital > self.cash:
            return OrderResult(success=False, message="Insufficient buying power")
        
        # Simulate fill
        if random.random() > self.fill_probability:
            order.status = OrderStatus.REJECTED
            return OrderResult(success=False, message="Order rejected (simulation)")
        
        # Execute order
        commission = order.quantity * self.commission_per_share
        total_cost = required_capital + commission
        
        if order.side == OrderSide.BUY:
            self.cash -= total_cost
            self._update_position(order.symbol, OrderSide.BUY, order.quantity, execution_price)
        else:
            self.cash += total_cost - commission
            self._update_position(order.symbol, OrderSide.SELL, order.quantity, execution_price)
        
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = execution_price
        order.filled_at = datetime.utcnow()
        
        self.orders[order.order_id] = order
        
        logger.info(f"Paper order filled: {order.symbol} {order.side} {order.quantity} @ {execution_price:.2f}")
        
        return OrderResult(
            success=True,
            order_id=order.order_id,
            message="Order filled",
            order=order
        )
    
    async def _execute_limit_order(self, order: Order, current_price: float) -> OrderResult:
        """Execute a limit order"""
        if order.price is None:
            return OrderResult(success=False, message="Limit price required")
        
        # Check if limit order can be filled immediately
        can_fill = False
        if order.side == OrderSide.BUY and current_price <= order.price:
            can_fill = True
        elif order.side == OrderSide.SELL and current_price >= order.price:
            can_fill = True
        
        if can_fill:
            return await self._execute_market_order(order, order.price)
        else:
            # Place order in book
            order.status = OrderStatus.SUBMITTED
            self.orders[order.order_id] = order
            return OrderResult(
                success=True,
                order_id=order.order_id,
                message="Limit order placed in book",
                order=order
            )
    
    async def _execute_stop_order(self, order: Order, current_price: float) -> OrderResult:
        """Execute a stop order"""
        if order.stop_price is None:
            return OrderResult(success=False, message="Stop price required")
        
        # Check if stop is triggered
        triggered = False
        if order.side == OrderSide.BUY and current_price >= order.stop_price:
            triggered = True
        elif order.side == OrderSide.SELL and current_price <= order.stop_price:
            triggered = True
        
        if triggered:
            # Convert to market order
            market_order = Order(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                order_type=OrderType.MARKET,
                quantity=order.quantity,
                time_in_force=order.time_in_force
            )
            return await self._execute_market_order(market_order, current_price)
        else:
            order.status = OrderStatus.SUBMITTED
            self.orders[order.order_id] = order
            return OrderResult(
                success=True,
                order_id=order.order_id,
                message="Stop order placed",
                order=order
            )
    
    def _update_position(self, symbol: str, side: OrderSide, quantity: int, price: float) -> None:
        """Update position after order fill"""
        if symbol in self.positions:
            existing = self.positions[symbol]
            if existing.side == side:
                # Add to existing position
                total_quantity = existing.quantity + quantity
                avg_price = ((existing.avg_entry_price * existing.quantity) + (price * quantity)) / total_quantity
                existing.quantity = total_quantity
                existing.avg_entry_price = avg_price
                existing.cost_basis = avg_price * total_quantity
            else:
                # Close or reduce position
                if quantity >= existing.quantity:
                    # Full close
                    del self.positions[symbol]
                else:
                    # Partial close
                    existing.quantity -= quantity
                    existing.cost_basis = existing.avg_entry_price * existing.quantity
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                side=side,
                quantity=quantity,
                avg_entry_price=price,
                current_price=price,
                market_value=quantity * price,
                cost_basis=quantity * price,
                unrealized_pl=0.0,
                unrealized_pl_pct=0.0,
                timestamp=datetime.utcnow()
            )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.utcnow()
                logger.info(f"Paper order cancelled: {order_id}")
                return True
        return False
    
    async def cancel_all_orders(self) -> int:
        """Cancel all open orders"""
        cancelled_count = 0
        for order_id in list(self.orders.keys()):
            if await self.cancel_order(order_id):
                cancelled_count += 1
        return cancelled_count
    
    async def get_balance(self) -> Optional[Balance]:
        """Get account balance"""
        return Balance(
            currency="USD",
            cash=self.cash,
            available=self.cash,
            locked=0.0
        )
    
    def supports_order_type(self, order_type: OrderType) -> bool:
        """Paper engine supports all order types"""
        return True
    
    def supports_asset_class(self, asset_class: str) -> bool:
        """Paper engine supports all asset classes"""
        return True
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for simulation"""
        if symbol in self.market_data:
            return self.market_data[symbol]["price"]
        
        # Generate realistic price if not in market data
        base_price = random.uniform(50, 200)
        self.market_data[symbol] = {
            "price": base_price,
            "bid": base_price * 0.9995,
            "ask": base_price * 1.0005
        }
        return base_price
    
    def set_market_price(self, symbol: str, price: float) -> None:
        """Set market price for simulation"""
        spread = price * (self.spread_bps / 10000)
        self.market_data[symbol] = {
            "price": price,
            "bid": price - spread,
            "ask": price + spread
        }
        logger.debug(f"Set market price for {symbol}: ${price:.2f}")


# Register the adapter
from delta.core.registry import broker_registry
broker_registry.register_adapter("paper", PaperTradingEngine)
