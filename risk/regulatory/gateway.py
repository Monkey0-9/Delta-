"""Regulatory Risk Gateway implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from .checks import (
    PriceCollarCheck,
    MaxOrderSizeCheck,
    ShortLocateCheck,
    FatFingerCheck,
    CapitalThresholdCheck
)


class CheckType(StrEnum):
    """Types of regulatory checks."""
    PRICE_COLLAR = "price_collar"
    MAX_ORDER_SIZE = "max_order_size"
    SHORT_LOCATE = "short_locate"
    FAT_FINGER = "fat_finger"
    CAPITAL_THRESHOLD = "capital_threshold"
    DUPLICATE_ORDER = "duplicate_order"
    STALE_DATA = "stale_data"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Result of a regulatory check."""
    check_type: CheckType
    passed: bool
    message: str
    check_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegulatoryConfig:
    """Configuration for regulatory gateway."""
    # Price collar settings
    price_collar_bps: Decimal = Decimal("100")  # 1% from NBBO
    max_deviation_pct: Decimal = Decimal("5")  # 5% max deviation
    
    # Order size limits
    max_order_notional: Decimal = Decimal("1000000")  # $1M max
    max_order_shares: int = 10000  # 10K shares max
    
    # Short sale settings
    require_locate: bool = True
    locate_ttl_hours: int = 24
    
    # Capital settings
    capital_threshold: Decimal = Decimal("10000000")  # $10M threshold
    credit_limit: Decimal = Decimal("5000000")  # $5M credit limit
    
    # Fat finger settings
    max_notional_jump: Decimal = Decimal("10")  # 10x jump threshold
    
    # Duplicate order settings
    duplicate_window_seconds: int = 10
    max_duplicate_orders: int = 5


class RegulatoryGateway:
    """
    Pre-trade regulatory risk gateway (SEC Rule 15c3-5).
    
    Implements hardware/kernel-level checks:
    - Order price collars (preventing fat-finger orders)
    - Max dollar caps
    - Short locate validation
    - Fat-finger traps
    - Duplicate order suppression
    """
    
    def __init__(self, config: RegulatoryConfig | None = None) -> None:
        self._config = config or RegulatoryConfig()
        self._seen_orders: dict[str, datetime] = {}
        self._short_locates: dict[str, datetime] = {}  # symbol -> locate expiry
    
    def check_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        limit_price: Decimal | None,
        reference_price: Decimal,
        current_capital: Decimal,
        current_exposure: Decimal
    ) -> list[CheckResult]:
        """
        Run all regulatory checks on an order.
        
        Returns list of check results. Order is rejected if any check fails.
        """
        results: list[CheckResult] = []
        
        # Price collar check
        if limit_price is not None:
            price_check = self._check_price_collar(
                limit_price, reference_price, symbol
            )
            results.append(price_check)
            
            if not price_check.passed:
                return results  # Fail fast
        
        # Max order size check
        size_check = self._check_max_order_size(
            quantity, limit_price, reference_price
        )
        results.append(size_check)
        
        if not size_check.passed:
            return results
        
        # Short locate check
        if side.lower() == "sell":
            locate_check = self._check_short_locate(symbol)
            results.append(locate_check)
            
            if not locate_check.passed:
                return results
        
        # Fat finger check
        fat_finger_check = self._check_fat_finger(
            quantity, limit_price, reference_price, current_exposure
        )
        results.append(fat_finger_check)
        
        if not fat_finger_check.passed:
            return results
        
        # Capital threshold check
        capital_check = self._check_capital_threshold(
            current_capital, current_exposure, quantity, limit_price, reference_price
        )
        results.append(capital_check)
        
        if not capital_check.passed:
            return results
        
        # Duplicate order check
        duplicate_check = self._check_duplicate_order(order_id)
        results.append(duplicate_check)
        
        if not duplicate_check.passed:
            return results
        
        return results
    
    def _check_price_collar(
        self,
        limit_price: Decimal,
        reference_price: Decimal,
        symbol: str
    ) -> CheckResult:
        """Check if order price is within collar."""
        if reference_price == 0:
            return CheckResult(
                check_type=CheckType.PRICE_COLLAR,
                passed=False,
                message="Reference price is zero",
                details={"symbol": symbol}
            )
        
        deviation_bps = abs(limit_price - reference_price) / reference_price * Decimal("10000")
        
        if deviation_bps > self._config.price_collar_bps:
            return CheckResult(
                check_type=CheckType.PRICE_COLLAR,
                passed=False,
                message=f"Price deviation {deviation_bps:.2f} bps exceeds collar {self._config.price_collar_bps} bps",
                details={
                    "symbol": symbol,
                    "limit_price": float(limit_price),
                    "reference_price": float(reference_price),
                    "deviation_bps": float(deviation_bps),
                }
            )
        
        return CheckResult(
            check_type=CheckType.PRICE_COLLAR,
            passed=True,
            message="Price within collar",
            details={
                "symbol": symbol,
                "deviation_bps": float(deviation_bps),
            }
        )
    
    def _check_max_order_size(
        self,
        quantity: Decimal,
        limit_price: Decimal | None,
        reference_price: Decimal
    ) -> CheckResult:
        """Check if order size exceeds limits."""
        # Check share limit
        if quantity > self._config.max_order_shares:
            return CheckResult(
                check_type=CheckType.MAX_ORDER_SIZE,
                passed=False,
                message=f"Order quantity {quantity} exceeds max {self._config.max_order_shares}",
                details={"quantity": float(quantity)}
            )
        
        # Check notional limit
        price = limit_price or reference_price
        notional = quantity * price
        
        if notional > self._config.max_order_notional:
            return CheckResult(
                check_type=CheckType.MAX_ORDER_SIZE,
                passed=False,
                message=f"Order notional ${notional:,.2f} exceeds max ${self._config.max_order_notional:,.2f}",
                details={"notional": float(notional)}
            )
        
        return CheckResult(
            check_type=CheckType.MAX_ORDER_SIZE,
            passed=True,
            message="Order size within limits",
            details={"notional": float(notional)}
        )
    
    def _check_short_locate(self, symbol: str) -> CheckResult:
        """Check if short locate is available."""
        if not self._config.require_locate:
            return CheckResult(
                check_type=CheckType.SHORT_LOCATE,
                passed=True,
                message="Short locate not required"
            )
        
        symbol = symbol.upper()
        
        if symbol not in self._short_locates:
            return CheckResult(
                check_type=CheckType.SHORT_LOCATE,
                passed=False,
                message=f"No short locate available for {symbol}",
                details={"symbol": symbol}
            )
        
        # Check if locate has expired
        locate_expiry = self._short_locates[symbol]
        if datetime.now(timezone.utc) > locate_expiry:
            return CheckResult(
                check_type=CheckType.SHORT_LOCATE,
                passed=False,
                message=f"Short locate expired for {symbol}",
                details={"symbol": symbol, "expiry": locate_expiry}
            )
        
        return CheckResult(
            check_type=CheckType.SHORT_LOCATE,
            passed=True,
            message="Short locate valid",
            details={"symbol": symbol}
        )
    
    def _check_fat_finger(
        self,
        quantity: Decimal,
        limit_price: Decimal | None,
        reference_price: Decimal,
        current_exposure: Decimal
    ) -> CheckResult:
        """Check for fat-finger errors."""
        price = limit_price or reference_price
        notional = quantity * price
        
        # Check for sudden jump in notional
        if current_exposure > 0:
            jump_ratio = notional / current_exposure
            
            if jump_ratio > self._config.max_notional_jump:
                return CheckResult(
                    check_type=CheckType.FAT_FINGER,
                    passed=False,
                    message=f"Order notional ${notional:,.2f} is {jump_ratio:.1f}x current exposure ${current_exposure:,.2f}",
                    details={
                        "notional": float(notional),
                        "current_exposure": float(current_exposure),
                        "jump_ratio": float(jump_ratio),
                    }
                )
        
        return CheckResult(
            check_type=CheckType.FAT_FINGER,
            passed=True,
            message="No fat-finger detected",
            details={"notional": float(notional)}
        )
    
    def _check_capital_threshold(
        self,
        current_capital: Decimal,
        current_exposure: Decimal,
        quantity: Decimal,
        limit_price: Decimal | None,
        reference_price: Decimal
    ) -> CheckResult:
        """Check capital threshold."""
        price = limit_price or reference_price
        new_exposure = current_exposure + quantity * price
        
        if new_exposure > self._config.capital_threshold:
            return CheckResult(
                check_type=CheckType.CAPITAL_THRESHOLD,
                passed=False,
                message=f"Projected exposure ${new_exposure:,.2f} exceeds capital threshold ${self._config.capital_threshold:,.2f}",
                details={
                    "current_exposure": float(current_exposure),
                    "new_exposure": float(new_exposure),
                    "capital_threshold": float(self._config.capital_threshold),
                }
            )
        
        if new_exposure > self._config.credit_limit:
            return CheckResult(
                check_type=CheckType.CAPITAL_THRESHOLD,
                passed=False,
                message=f"Projected exposure ${new_exposure:,.2f} exceeds credit limit ${self._config.credit_limit:,.2f}",
                details={
                    "current_exposure": float(current_exposure),
                    "new_exposure": float(new_exposure),
                    "credit_limit": float(self._config.credit_limit),
                }
            )
        
        return CheckResult(
            check_type=CheckType.CAPITAL_THRESHOLD,
            passed=True,
            message="Capital within limits",
            details={"new_exposure": float(new_exposure)}
        )
    
    def _check_duplicate_order(self, order_id: str) -> CheckResult:
        """Check for duplicate orders."""
        now = datetime.now(timezone.utc)
        
        if order_id in self._seen_orders:
            last_seen = self._seen_orders[order_id]
            time_diff = (now - last_seen).total_seconds()
            
            if time_diff < self._config.duplicate_window_seconds:
                return CheckResult(
                    check_type=CheckType.DUPLICATE_ORDER,
                    passed=False,
                    message=f"Duplicate order {order_id} seen {time_diff:.1f}s ago",
                    details={
                        "order_id": order_id,
                        "last_seen": last_seen,
                        "time_diff_seconds": time_diff,
                    }
                )
        
        self._seen_orders[order_id] = now
        return CheckResult(
            check_type=CheckType.DUPLICATE_ORDER,
            passed=True,
            message="No duplicate detected",
            details={"order_id": order_id}
        )
    
    def add_short_locate(self, symbol: str, locate_id: str, expiry_hours: int = 24) -> None:
        """Add a short locate for a symbol."""
        symbol = symbol.upper()
        expiry = datetime.now(timezone.utc).replace(
            hour=expiry_hours
        )
        self._short_locates[symbol] = expiry
    
    def expire_old_locates(self) -> None:
        """Remove expired short locates."""
        now = datetime.now(timezone.utc)
        expired = [
            symbol for symbol, expiry in self._short_locates.items()
            if now > expiry
        ]
        
        for symbol in expired:
            del self._short_locates[symbol]
