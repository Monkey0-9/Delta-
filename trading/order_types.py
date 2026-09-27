"""
Standardized order models, enums, and tickets
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from delta.trading.broker_base import (
    OrderSide, OrderType, OrderStatus, TimeInForce
)


class OrderClass(Enum):
    """Order classification"""
    SIMPLE = "simple"
    BRACKET = "bracket"
    OCO = "oco"  # One-Cancels-Other
    TRAILING_STOP = "trailing_stop"


@dataclass
class OrderTicket:
    """Order ticket with full details"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    order_class: OrderClass = OrderClass.SIMPLE
    
    # Bracket order fields
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    
    # Trailing stop fields
    trail_amount: Optional[float] = None
    trail_percent: Optional[float] = None
    
    # Metadata
    strategy_id: Optional[str] = None
    notes: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order ticket to dictionary"""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force.value,
            "order_class": self.order_class.value,
            "take_profit_price": self.take_profit_price,
            "stop_loss_price": self.stop_loss_price,
            "trail_amount": self.trail_amount,
            "trail_percent": self.trail_percent,
            "strategy_id": self.strategy_id,
            "notes": self.notes,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderTicket":
        """Create order ticket from dictionary"""
        return cls(
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            order_type=OrderType(data["order_type"]),
            quantity=data["quantity"],
            limit_price=data.get("limit_price"),
            stop_price=data.get("stop_price"),
            time_in_force=TimeInForce(data.get("time_in_force", "gtc")),
            order_class=OrderClass(data.get("order_class", "simple")),
            take_profit_price=data.get("take_profit_price"),
            stop_loss_price=data.get("stop_loss_price"),
            trail_amount=data.get("trail_amount"),
            trail_percent=data.get("trail_percent"),
            strategy_id=data.get("strategy_id"),
            notes=data.get("notes"),
            tags=data.get("tags", {})
        )


@dataclass
class OrderConfirmation:
    """Order confirmation with execution details"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    filled_quantity: int
    avg_fill_price: Optional[float]
    status: OrderStatus
    created_at: datetime
    filled_at: Optional[datetime]
    message: str
    commission: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert confirmation to dictionary"""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "message": self.message,
            "commission": self.commission
        }


@dataclass
class BracketOrder:
    """Bracket order with take-profit and stop-loss"""
    parent_order: OrderTicket
    take_profit: OrderTicket
    stop_loss: OrderTicket
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bracket order to dictionary"""
        return {
            "parent_order": self.parent_order.to_dict(),
            "take_profit": self.take_profit.to_dict(),
            "stop_loss": self.stop_loss.to_dict()
        }


class OrderBuilder:
    """Builder pattern for creating complex orders"""
    
    def __init__(self, symbol: str, side: OrderSide, quantity: int):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.order_type = OrderType.MARKET
        self.limit_price: Optional[float] = None
        self.stop_price: Optional[float] = None
        self.time_in_force = TimeInForce.GTC
        self.take_profit_price: Optional[float] = None
        self.stop_loss_price: Optional[float] = None
    
    def market_order(self) -> "OrderBuilder":
        """Set as market order"""
        self.order_type = OrderType.MARKET
        return self
    
    def limit_order(self, price: float) -> "OrderBuilder":
        """Set as limit order"""
        self.order_type = OrderType.LIMIT
        self.limit_price = price
        return self
    
    def stop_order(self, price: float) -> "OrderBuilder":
        """Set as stop order"""
        self.order_type = OrderType.STOP
        self.stop_price = price
        return self
    
    def stop_limit_order(self, stop_price: float, limit_price: float) -> "OrderBuilder":
        """Set as stop-limit order"""
        self.order_type = OrderType.STOP_LIMIT
        self.stop_price = stop_price
        self.limit_price = limit_price
        return self
    
    def time_in_force(self, tif: TimeInForce) -> "OrderBuilder":
        """Set time in force"""
        self.time_in_force = tif
        return self
    
    def with_bracket(self, take_profit: float, stop_loss: float) -> "OrderBuilder":
        """Add take-profit and stop-loss"""
        self.take_profit_price = take_profit
        self.stop_loss_price = stop_loss
        return self
    
    def build(self) -> OrderTicket:
        """Build the order ticket"""
        order_class = OrderClass.BRACKET if (self.take_profit_price or self.stop_loss_price) else OrderClass.SIMPLE
        
        return OrderTicket(
            symbol=self.symbol,
            side=self.side,
            order_type=self.order_type,
            quantity=self.quantity,
            limit_price=self.limit_price,
            stop_price=self.stop_price,
            time_in_force=self.time_in_force,
            order_class=order_class,
            take_profit_price=self.take_profit_price,
            stop_loss_price=self.stop_loss_price
        )
