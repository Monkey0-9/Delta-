"""
Abstract base interface for universal broker adapters
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    BRACKET = "bracket"


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(Enum):
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    OPG = "opg"  # At The Open
    CLS = "cls"  # At The Close


@dataclass
class AccountInfo:
    """Account information"""
    account_id: str
    account_type: str
    buying_power: float
    cash: float
    portfolio_value: float
    margin_used: float
    margin_available: float
    day_trading_buying_power: float
    last_equity: float
    last_maintenance_margin: float
    daytrade_count: int
    timestamp: datetime


@dataclass
class Position:
    """Open position"""
    symbol: str
    side: OrderSide
    quantity: int
    avg_entry_price: float
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_pl_pct: float
    timestamp: datetime


@dataclass
class Order:
    """Order structure"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: Optional[float] = None
    filled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OrderResult:
    """Result of order submission"""
    success: bool
    order_id: Optional[str] = None
    message: str = ""
    order: Optional[Order] = None


@dataclass
class Balance:
    """Account balance information"""
    currency: str
    cash: float
    available: float
    locked: float


class UniversalBrokerAdapter(ABC):
    """Abstract base class for all broker adapters"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.broker_name = config.get("name", "unknown")
        self.environment = config.get("environment", "paper")
        self.credentials = config.get("credentials", {})
        self._connected = False
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the broker connection"""
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the broker API"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the broker API"""
        pass
    
    @abstractmethod
    async def get_account(self) -> Optional[AccountInfo]:
        """Get account information"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get all open positions"""
        pass
    
    @abstractmethod
    async def get_orders(self) -> List[Order]:
        """Get all open orders"""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult:
        """Place an order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    async def cancel_all_orders(self) -> int:
        """Cancel all open orders, returns count of cancelled orders"""
        pass
    
    @abstractmethod
    async def get_balance(self) -> Optional[Balance]:
        """Get account balance"""
        pass
    
    @abstractmethod
    def supports_order_type(self, order_type: OrderType) -> bool:
        """Check if broker supports a specific order type"""
        pass
    
    @abstractmethod
    def supports_asset_class(self, asset_class: str) -> bool:
        """Check if broker supports a specific asset class"""
        pass
    
    def is_connected(self) -> bool:
        """Check if broker is connected"""
        return self._connected
    
    def is_initialized(self) -> bool:
        """Check if broker is initialized"""
        return self._initialized
    
    def get_broker_name(self) -> str:
        """Get the broker name"""
        return self.broker_name
    
    def get_environment(self) -> str:
        """Get the environment (paper/live)"""
        return self.environment
    
    async def health_check(self) -> bool:
        """Perform a health check on the broker connection"""
        try:
            account = await self.get_account()
            return account is not None
        except Exception:
            return False
    
    def validate_config(self) -> bool:
        """Validate the broker configuration"""
        return "name" in self.config and "environment" in self.config
    
    async def flatten_position(self, symbol: str) -> OrderResult:
        """Flatten (close) a position"""
        positions = await self.get_positions()
        for position in positions:
            if position.symbol == symbol:
                # Create opposite order to close position
                close_order = Order(
                    order_id="",  # Will be assigned by broker
                    symbol=symbol,
                    side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=abs(position.quantity)
                )
                return await self.place_order(close_order)
        
        return OrderResult(success=False, message=f"No position found for {symbol}")
    
    async def flatten_all_positions(self) -> List[OrderResult]:
        """Flatten all positions"""
        positions = await self.get_positions()
        results = []
        
        for position in positions:
            result = await self.flatten_position(position.symbol)
            results.append(result)
        
        return results


class PaperBrokerAdapter(UniversalBrokerAdapter):
    """Base class for paper trading engines"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.paper_balance = config.get("initial_balance", 100000.0)
    
    def get_environment(self) -> str:
        """Paper brokers always use paper environment"""
        return "paper"
    
    def supports_order_type(self, order_type: OrderType) -> bool:
        """Paper brokers typically support all order types"""
        return True
    
    def supports_asset_class(self, asset_class: str) -> bool:
        """Paper brokers can support any asset class for simulation"""
        return True


class LiveBrokerAdapter(UniversalBrokerAdapter):
    """Base class for live broker connections"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.required_credentials = config.get("required_credentials", [])
    
    def validate_credentials(self) -> bool:
        """Validate that required credentials are present"""
        for cred in self.required_credentials:
            if cred not in self.credentials:
                return False
        return True
    
    async def connect(self) -> bool:
        """Connect with credential validation"""
        if not self.validate_credentials():
            raise ValueError("Missing required credentials")
        return await super().connect()
