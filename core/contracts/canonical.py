"""
DELTA Canonical Event Contracts

This module defines the canonical semantic contracts for all major DELTA events.
These contracts serve as the single source of truth for cross-language interoperability
between Python, Rust, and C++ implementations.

PRINCIPLE: One semantic definition → Multiple language representations

All contracts must be:
- Versioned with semantic versioning
- Serializable across language boundaries
- Hashable for content addressing
- Validatable with schema constraints
- Immutable for thread safety
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


# ============================================================================
# VERSIONING
# ============================================================================

CANONICAL_CONTRACT_VERSION = "1.0.0"


class ContractVersion:
    """Semantic versioning for canonical contracts."""
    
    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def is_compatible(self, other: ContractVersion) -> bool:
        """Check if versions are compatible (same major version)."""
        return self.major == other.major


CURRENT_VERSION = ContractVersion(1, 0, 0)


# ============================================================================
# FOUNDATIONAL TYPES
# ============================================================================

class AssetClass(Enum):
    """Standard asset class enumeration."""
    EQUITY = "equity"
    ETF = "etf"
    FUTURE = "future"
    OPTION = "option"
    FX = "fx"
    RATE = "rate"
    BOND = "bond"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    INDEX = "index"


class Currency(Enum):
    """ISO 4217 currency codes."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CHF = "CHF"
    CAD = "CAD"
    AUD = "AUD"
    CNY = "CNY"


class Side(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Order status enumeration."""
    CREATED = "created"
    VALIDATED = "validated"
    RISK_APPROVED = "risk_approved"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class TimeInForce(Enum):
    """Time in force enumeration."""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    GTX = "gtx"  # Good Till Crossing


class FailureCategory(Enum):
    """Failure categorization for learning system.

    Single source of truth. All other FailureType enums are aliases.
    """
    NO_FAILURE = "no_failure"
    MODEL_ERROR = "model_error"
    REGIME_ERROR = "regime_error"
    DATA_ERROR = "data_error"
    EVENT_ERROR = "event_error"
    RISK_ERROR = "risk_error"
    EXECUTION_ERROR = "execution_error"
    LIQUIDITY_ERROR = "liquidity_error"
    PORTFOLIO_ERROR = "portfolio_error"
    DECISION_ERROR = "decision_error"
    UNKNOWN = "unknown"


# Legacy alias map for the pre-unification learning/failures vocabulary.
# PREDICTION -> MODEL_ERROR, REGIME -> REGIME_ERROR, DATA -> DATA_ERROR,
# NEWS -> EVENT_ERROR, RISK -> RISK_ERROR, EXECUTION -> EXECUTION_ERROR,
# RELATIONSHIP -> PORTFOLIO_ERROR, DECISION -> DECISION_ERROR.
LEGACY_FAILURE_ALIASES: dict[str, FailureCategory] = {
    "PREDICTION": FailureCategory.MODEL_ERROR,
    "REGIME": FailureCategory.REGIME_ERROR,
    "DATA": FailureCategory.DATA_ERROR,
    "NEWS": FailureCategory.EVENT_ERROR,
    "RISK": FailureCategory.RISK_ERROR,
    "EXECUTION": FailureCategory.EXECUTION_ERROR,
    "RELATIONSHIP": FailureCategory.PORTFOLIO_ERROR,
    "DECISION": FailureCategory.DECISION_ERROR,
    "UNKNOWN": FailureCategory.UNKNOWN,
}


def normalize_failure_category(value: str) -> FailureCategory:
    """Resolve a legacy or canonical failure label to FailureCategory."""
    key = value.strip().upper()
    if key in LEGACY_FAILURE_ALIASES:
        return LEGACY_FAILURE_ALIASES[key]
    lowered = value.strip().lower()
    for member in FailureCategory:
        if member.value == lowered:
            return member
    raise ValueError(f"unknown failure category: {value!r}")


# ============================================================================
# CANONICAL EVENT CONTRACTS
# ============================================================================

@dataclass(frozen=True, slots=True)
class Timestamps:
    """
    Multi-timestamp structure for point-in-time correctness.
    
    Critical for preventing look-ahead bias in quantitative research.
    """
    event_time: datetime  # When the event actually occurred
    received_time: datetime  # When the system received the event
    published_time: Optional[datetime] = None  # When the event was published
    effective_time: Optional[datetime] = None  # When the event becomes effective
    available_at: Optional[datetime] = None  # When the event became available for use
    
    def __post_init__(self):
        """Validate timestamp ordering."""
        if self.received_time < self.event_time:
            raise ValueError("received_time must be >= event_time")
        if self.published_time and self.published_time < self.event_time:
            raise ValueError("published_time must be >= event_time")
    
    def is_available_at(self, timestamp: datetime) -> bool:
        """Check if event was available at given timestamp."""
        available = self.available_at or self.received_time
        return timestamp >= available


@dataclass(frozen=True, slots=True)
class Instrument:
    """
    Canonical instrument definition.
    """
    symbol: str
    asset_class: AssetClass
    currency: Currency
    exchange: Optional[str] = None
    isin: Optional[str] = None
    cusip: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    multiplier: Optional[Decimal] = None  # For futures/options
    tick_size: Optional[Decimal] = None
    
    def content_hash(self) -> str:
        """Generate content hash for instrument identity."""
        # Simplified hash - in production use cryptographic hash
        return f"{self.symbol}:{self.asset_class.value}:{self.currency.value}"


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """
    Canonical market data event.
    
    This is the fundamental unit of market data in DELTA.
    All market data from any provider must be normalized to this contract.
    """
    instrument: Instrument
    timestamps: Timestamps
    event_id: UUID = field(default_factory=uuid4)
    price: Optional[Decimal] = None
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    bid_size: Optional[Decimal] = None
    ask_size: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    open_interest: Optional[Decimal] = None
    spread: Optional[Decimal] = None
    volatility: Optional[Decimal] = None
    
    # Metadata
    source: str = "unknown"
    quality_score: float = 1.0  # 0.0 to 1.0
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate market event structure."""
        # At least price or bid/ask must be present
        if self.price is None and (self.bid is None or self.ask is None):
            raise ValueError("Either price or bid/ask must be present")
    
    def is_available_at(self, timestamp: datetime) -> bool:
        """Point-in-time availability check."""
        return self.timestamps.is_available_at(timestamp)
    
    def mid_price(self) -> Optional[Decimal]:
        """Calculate mid price from bid/ask."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / Decimal("2")
        return self.price


@dataclass(frozen=True, slots=True)
class Quote:
    """
    Canonical quote contract.
    """
    instrument: Instrument
    timestamps: Timestamps
    bid: Decimal
    ask: Decimal
    event_id: UUID = field(default_factory=uuid4)
    bid_size: Optional[Decimal] = None
    ask_size: Optional[Decimal] = None
    mid: Optional[Decimal] = None
    spread: Optional[Decimal] = None
    source: str = "unknown"
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate quote structure."""
        if self.bid >= self.ask:
            raise ValueError("bid must be less than ask")


@dataclass(frozen=True, slots=True)
class Trade:
    """
    Canonical trade execution contract.
    """
    instrument: Instrument
    timestamps: Timestamps
    price: Decimal
    quantity: Decimal
    side: Side
    event_id: UUID = field(default_factory=uuid4)
    trade_id: Optional[str] = None
    source: str = "unknown"
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate trade structure."""
        if self.price <= 0:
            raise ValueError("price must be positive")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")


@dataclass(frozen=True, slots=True)
class OrderBookUpdate:
    """
    Canonical order book update contract.
    
    Used for L2/L3 market depth updates.
    """
    instrument: Instrument
    timestamps: Timestamps
    event_id: UUID = field(default_factory=uuid4)
    bids: list[tuple[Decimal, Decimal]] = field(default_factory=list)  # (price, size)
    asks: list[tuple[Decimal, Decimal]] = field(default_factory=list)  # (price, size)
    sequence: Optional[int] = None
    source: str = "unknown"
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate order book update structure."""
        # Validate bids are descending
        for i in range(len(self.bids) - 1):
            if self.bids[i][0] <= self.bids[i + 1][0]:
                raise ValueError("bids must be in descending order")
        
        # Validate asks are ascending
        for i in range(len(self.asks) - 1):
            if self.asks[i][0] >= self.asks[i + 1][0]:
                raise ValueError("asks must be in ascending order")


@dataclass(frozen=True, slots=True)
class Signal:
    """
    Canonical quantitative signal contract.
    """
    instrument: Instrument
    timestamps: Timestamps
    value: Decimal
    signal_id: UUID = field(default_factory=uuid4)
    confidence: Optional[float] = None  # 0.0 to 1.0
    signal_type: str = "unknown"  # momentum, mean_reversion, etc.
    horizon: str = "unknown"  # intraday, short, medium, long
    metadata: dict[str, Any] = field(default_factory=dict)
    model_version: Optional[str] = None
    feature_version: Optional[str] = None
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate signal structure."""
        if self.confidence is not None and (self.confidence < 0.0 or self.confidence > 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class Forecast:
    """
    Canonical forecast contract.
    
    Standardizes model outputs across the system.
    """
    instrument: Instrument
    timestamps: Timestamps
    expected_return: Decimal
    forecast_id: UUID = field(default_factory=uuid4)
    horizon: str = "unknown"  # 1D, 1W, 1M, etc.
    risk: Optional[Decimal] = None  # Standard deviation
    confidence: Optional[float] = None  # 0.0 to 1.0
    model_version: str = "unknown"
    feature_version: Optional[str] = None
    model_disagreement: Optional[float] = None  # Ensemble disagreement
    data_uncertainty: Optional[float] = None
    regime_uncertainty: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate forecast structure."""
        if self.risk is not None and self.risk < 0:
            raise ValueError("risk must be non-negative")
        if self.confidence is not None and (self.confidence < 0.0 or self.confidence > 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
    
    def sharpe_ratio(self, risk_free_rate: Decimal = Decimal("0.0")) -> Optional[Decimal]:
        """Calculate Sharpe ratio."""
        if self.risk is None or self.risk == 0:
            return None
        return (self.expected_return - risk_free_rate) / self.risk


@dataclass(frozen=True, slots=True)
class Decision:
    """
    Canonical portfolio decision contract.
    
    Represents a candidate portfolio action before risk authorization.
    """
    instrument: Instrument
    timestamps: Timestamps
    decision_id: UUID = field(default_factory=uuid4)
    action: str = "unknown"  # BUY, SELL, HOLD, REDUCE
    quantity: Optional[Decimal] = None
    target_weight: Optional[Decimal] = None
    expected_return: Optional[Decimal] = None
    risk: Optional[Decimal] = None
    confidence: Optional[float] = None
    horizon: str = "unknown"
    reasoning: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)
    forecast_id: Optional[UUID] = None
    strategy_version: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate decision structure."""
        if self.action not in ["BUY", "SELL", "HOLD", "REDUCE", "unknown"]:
            raise ValueError("action must be BUY, SELL, HOLD, REDUCE, or unknown")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """
    Canonical risk authorization decision.
    
    This is the critical safety boundary - no order reaches execution
    without passing through this contract.
    """
    decision_id: UUID  # Reference to original decision
    timestamps: Timestamps
    risk_decision_id: UUID = field(default_factory=uuid4)
    authorized: bool = False
    action: str = "BLOCK"  # APPROVE, REDUCE, BLOCK
    original_quantity: Optional[Decimal] = None
    authorized_quantity: Optional[Decimal] = None
    rejection_reason: Optional[str] = None
    risk_checks: dict[str, bool] = field(default_factory=dict)
    position_limit: Optional[bool] = None
    leverage_limit: Optional[bool] = None
    concentration_limit: Optional[bool] = None
    liquidity_limit: Optional[bool] = None
    exposure_limit: Optional[bool] = None
    freshness_check: Optional[bool] = None
    kill_switch_active: Optional[bool] = None
    portfolio_impact: Optional[Decimal] = None
    portfolio_risk: Optional[Decimal] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate risk decision structure."""
        if self.action not in ["APPROVE", "REDUCE", "BLOCK"]:
            raise ValueError("action must be APPROVE, REDUCE, or BLOCK")
        if self.authorized and self.action == "BLOCK":
            raise ValueError("authorized decisions cannot have BLOCK action")


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    """
    Canonical execution intent contract.
    
    Represents an authorized order ready for execution.
    """
    risk_decision_id: UUID
    instrument: Instrument
    timestamps: Timestamps
    side: Side
    order_type: OrderType
    quantity: Decimal
    execution_id: UUID = field(default_factory=uuid4)
    price: Optional[Decimal] = None  # None for market orders
    time_in_force: TimeInForce = TimeInForce.DAY
    algorithm: Optional[str] = None  # TWAP, VWAP, POV, etc.
    algorithm_params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate execution intent structure."""
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("price is required for limit orders")


@dataclass(frozen=True, slots=True)
class Order:
    """
    Canonical order lifecycle contract.
    """
    execution_id: UUID
    instrument: Instrument
    timestamps: Timestamps
    side: Side
    order_type: OrderType
    quantity: Decimal
    order_id: UUID = field(default_factory=uuid4)
    price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    exchange_order_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate order structure."""
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.filled_quantity < 0 or self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity must be between 0 and quantity")
    
    def remaining_quantity(self) -> Decimal:
        """Calculate remaining quantity to fill."""
        return self.quantity - self.filled_quantity
    
    def is_fully_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.filled_quantity == self.quantity


@dataclass(frozen=True, slots=True)
class Fill:
    """
    Canonical fill confirmation contract.
    """
    order_id: UUID
    instrument: Instrument
    timestamps: Timestamps
    side: Side
    quantity: Decimal
    price: Decimal
    fill_id: UUID = field(default_factory=uuid4)
    exchange_fill_id: Optional[str] = None
    fees: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate fill structure."""
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.price <= 0:
            raise ValueError("price must be positive")


@dataclass(frozen=True, slots=True)
class Position:
    """
    Canonical position contract.
    """
    instrument: Instrument
    timestamps: Timestamps
    quantity: Decimal
    position_id: UUID = field(default_factory=uuid4)
    avg_cost: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    currency: Currency = Currency.USD
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate position structure."""
        pass
    
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0
    
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """
    Canonical portfolio state contract.
    """
    timestamps: Timestamps
    snapshot_id: UUID = field(default_factory=uuid4)
    positions: dict[str, Position] = field(default_factory=dict)
    cash: Decimal = Decimal("0")
    total_value: Optional[Decimal] = None
    gross_exposure: Optional[Decimal] = None
    net_exposure: Optional[Decimal] = None
    leverage: Optional[Decimal] = None
    currency: Currency = Currency.USD
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate portfolio snapshot structure."""
        pass


@dataclass(frozen=True, slots=True)
class Failure:
    """
    Canonical failure event contract.
    
    Used for failure attribution and learning.
    """
    timestamps: Timestamps
    category: FailureCategory
    failure_id: UUID = field(default_factory=uuid4)
    severity: str = "medium"  # low, medium, high, critical
    description: str = ""
    root_cause: Optional[str] = None
    affected_component: Optional[str] = None
    related_decision_id: Optional[UUID] = None
    related_order_id: Optional[UUID] = None
    related_forecast_id: Optional[UUID] = None
    financial_impact: Optional[Decimal] = None
    confidence: Optional[float] = None  # Confidence in failure attribution
    recovery_action: Optional[str] = None
    prevention_action: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate failure structure."""
        if self.severity not in ["low", "medium", "high", "critical"]:
            raise ValueError("severity must be low, medium, high, or critical")


@dataclass(frozen=True, slots=True)
class Experience:
    """
    Canonical experience contract for learning system.
    
    Stores lessons learned from failures and successes.
    """
    timestamps: Timestamps
    experience_id: UUID = field(default_factory=uuid4)
    state_context: dict[str, Any] = field(default_factory=dict)
    decision_context: dict[str, Any] = field(default_factory=dict)
    outcome: str = "unknown"  # success, failure, partial
    lesson: str = ""
    confidence: Optional[float] = None
    applicable_regimes: list[str] = field(default_factory=list)
    applicable_instruments: list[str] = field(default_factory=list)
    applicable_horizons: list[str] = field(default_factory=list)
    related_failure_id: Optional[UUID] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate experience structure."""
        if self.outcome not in ["success", "failure", "partial", "unknown"]:
            raise ValueError("outcome must be success, failure, partial, or unknown")


@dataclass(frozen=True, slots=True)
class WorldState:
    """
    Canonical financial world state contract.
    
    This is the central state representation for DELTA.
    All decisions are made based on the current world state.
    """
    timestamps: Timestamps
    state_id: UUID = field(default_factory=uuid4)
    
    # Market State
    market_returns: Optional[dict[str, Decimal]] = None
    market_volatility: Optional[dict[str, Decimal]] = None
    market_spread: Optional[dict[str, Decimal]] = None
    market_liquidity: Optional[dict[str, Decimal]] = None
    market_correlation: Optional[dict[str, dict[str, Decimal]]] = None
    
    # Macro State
    macro_rates: Optional[dict[str, Decimal]] = None
    macro_inflation: Optional[dict[str, Decimal]] = None
    macro_growth: Optional[dict[str, Decimal]] = None
    macro_credit: Optional[dict[str, Decimal]] = None
    
    # Portfolio State
    portfolio_state: Optional[PortfolioSnapshot] = None
    
    # Regime State
    regime_trend: Optional[str] = None
    regime_volatility: Optional[str] = None
    regime_correlation: Optional[str] = None
    regime_liquidity: Optional[str] = None
    regime_macro: Optional[str] = None
    regime_crisis: Optional[bool] = None
    
    # Uncertainty State
    uncertainty_data: Optional[float] = None
    uncertainty_model: Optional[float] = None
    uncertainty_regime: Optional[float] = None
    uncertainty_execution: Optional[float] = None
    
    # System State
    system_health: Optional[str] = None
    system_performance: Optional[dict[str, Any]] = None
    
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CANONICAL_CONTRACT_VERSION
    
    def __post_init__(self):
        """Validate world state structure."""
        pass
    
    def state_hash(self) -> str:
        """Generate deterministic hash of world state."""
        # Simplified hash - in production use cryptographic hash
        components = [
            str(self.timestamps.event_time),
            str(self.regime_trend),
            str(self.regime_volatility),
            str(self.regime_crisis),
        ]
        return "|".join(components)


# ============================================================================
# CONTRACT VALIDATION
# ============================================================================

def validate_contract(contract: Any) -> bool:
    """
    Validate that a contract instance conforms to its schema.
    
    Args:
        contract: Any canonical contract instance
        
    Returns:
        True if contract is valid, raises exception otherwise
    """
    # Check contract version
    if hasattr(contract, 'contract_version'):
        if contract.contract_version != CANONICAL_CONTRACT_VERSION:
            raise ValueError(f"Contract version mismatch: {contract.contract_version} != {CANONICAL_CONTRACT_VERSION}")
    
    # Check for required fields (dataclass handles this via __post_init__)
    # Additional validation can be added here
    
    return True


def validate_contract_compatibility(version: str) -> bool:
    """
    Check if a contract version is compatible with current version.
    
    Args:
        version: Contract version string
        
    Returns:
        True if compatible, False otherwise
    """
    try:
        major, minor, patch = map(int, version.split('.'))
        other_version = ContractVersion(major, minor, patch)
        return CURRENT_VERSION.is_compatible(other_version)
    except (ValueError, AttributeError):
        return False


# ============================================================================
# SERIALIZATION HELPERS
# ============================================================================

def contract_to_dict(contract: Any) -> dict:
    """
    Convert canonical contract to dictionary for serialization.
    
    Args:
        contract: Any canonical contract instance
        
    Returns:
        Dictionary representation of contract
    """
    import dataclasses
    
    # Handle frozen dataclasses with slots
    if dataclasses.is_dataclass(contract):
        result = {}
        for field in dataclasses.fields(contract):
            value = getattr(contract, field.name)
            if value is None:
                result[field.name] = None
            elif isinstance(value, Enum):
                result[field.name] = value.value
            elif isinstance(value, UUID):
                result[field.name] = str(value)
            elif isinstance(value, datetime):
                result[field.name] = value.isoformat()
            elif isinstance(value, Decimal):
                result[field.name] = str(value)
            elif dataclasses.is_dataclass(value):
                # Recursively handle nested dataclass objects
                result[field.name] = contract_to_dict(value)
            elif isinstance(value, (dict, list)):
                # Recursively handle nested structures
                if isinstance(value, dict):
                    result[field.name] = {k: contract_to_dict(v) if dataclasses.is_dataclass(v) else v 
                                   for k, v in value.items()}
                else:
                    result[field.name] = [contract_to_dict(item) if dataclasses.is_dataclass(item) else item 
                                  for item in value]
            else:
                result[field.name] = value
        return result
    return {}


def dict_to_contract(contract_type: type, data: dict) -> Any:
    """
    Convert dictionary to canonical contract instance.
    
    Args:
        contract_type: Contract class to instantiate
        data: Dictionary representation
        
    Returns:
        Contract instance
    """
    import dataclasses
    
    # Get the contract's field annotations to know what types to expect
    annotations = getattr(contract_type, '__annotations__', {})
    
    # Handle enum conversions and nested objects
    processed_data = {}
    for key, value in data.items():
        if value is None:
            processed_data[key] = None
            continue
        
        expected_type = annotations.get(key)
        
        # Handle nested dataclass objects
        if expected_type and dataclasses.is_dataclass(expected_type):
            # This is a nested dataclass
            if isinstance(value, dict):
                processed_data[key] = dict_to_contract(expected_type, value)
            else:
                processed_data[key] = value
        # Try to convert to appropriate types
        elif key.endswith('_time') and isinstance(value, str):
            processed_data[key] = datetime.fromisoformat(value)
        elif key == 'event_id' or key.endswith('_id'):
            processed_data[key] = UUID(value)
        elif isinstance(value, str) and value in [e.value for e in AssetClass]:
            processed_data[key] = AssetClass(value)
        elif isinstance(value, str) and value in [e.value for e in Currency]:
            processed_data[key] = Currency(value)
        elif isinstance(value, str) and value in [e.value for e in Side]:
            processed_data[key] = Side(value)
        elif isinstance(value, str) and value in [e.value for e in OrderType]:
            processed_data[key] = OrderType(value)
        elif isinstance(value, str) and value in [e.value for e in OrderStatus]:
            processed_data[key] = OrderStatus(value)
        elif isinstance(value, str) and value in [e.value for e in TimeInForce]:
            processed_data[key] = TimeInForce(value)
        elif isinstance(value, str) and value in [e.value for e in FailureCategory]:
            processed_data[key] = FailureCategory(value)
        elif isinstance(value, (int, float, str)) and key in ['price', 'quantity', 'bid', 'ask', 'expected_return', 'risk', 'filled_quantity', 'avg_fill_price']:
            processed_data[key] = Decimal(str(value))
        else:
            processed_data[key] = value
    
    return contract_type(**processed_data)


# ============================================================================
# CONTRACT REGISTRY
# ============================================================================

CONTRACT_REGISTRY = {
    'MarketEvent': MarketEvent,
    'Quote': Quote,
    'Trade': Trade,
    'OrderBookUpdate': OrderBookUpdate,
    'Signal': Signal,
    'Forecast': Forecast,
    'Decision': Decision,
    'RiskDecision': RiskDecision,
    'ExecutionIntent': ExecutionIntent,
    'Order': Order,
    'Fill': Fill,
    'Position': Position,
    'PortfolioSnapshot': PortfolioSnapshot,
    'Failure': Failure,
    'Experience': Experience,
    'WorldState': WorldState,
}


def get_contract(contract_name: str) -> type:
    """
    Get contract class by name.
    
    Args:
        contract_name: Name of contract class
        
    Returns:
        Contract class
    """
    if contract_name not in CONTRACT_REGISTRY:
        raise ValueError(f"Unknown contract: {contract_name}")
    return CONTRACT_REGISTRY[contract_name]


def list_contracts() -> list[str]:
    """List all available contract names."""
    return list(CONTRACT_REGISTRY.keys())


# ============================================================================
# MODULE SELF-TEST
# ============================================================================

if __name__ == "__main__":
    # Test basic contract creation
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ"
    )
    
    timestamps = Timestamps(
        event_time=datetime.now(timezone.utc),
        received_time=datetime.now(timezone.utc)
    )
    
    market_event = MarketEvent(
        instrument=instrument,
        timestamps=timestamps,
        price=Decimal("150.25"),
        source="test"
    )
    
    # Test validation
    assert validate_contract(market_event)
    
    # Test serialization
    event_dict = contract_to_dict(market_event)
    reconstructed = dict_to_contract(MarketEvent, event_dict)
    
    assert reconstructed.instrument.symbol == market_event.instrument.symbol
    assert reconstructed.price == market_event.price
    
    # Test contract registry
    assert "MarketEvent" in list_contracts()
    assert get_contract("MarketEvent") == MarketEvent
    
    print("Canonical contracts self-test: PASS")