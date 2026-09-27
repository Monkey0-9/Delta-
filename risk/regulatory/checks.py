"""Individual regulatory check implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Result of a regulatory check."""
    passed: bool
    message: str
    details: dict[str, Any]


class RegulatoryCheck(ABC):
    """Base class for regulatory checks."""
    
    @abstractmethod
    def check(self, **kwargs) -> CheckResult:
        """Execute the regulatory check."""
        pass


class PriceCollarCheck(RegulatoryCheck):
    """Price collar check to prevent fat-finger orders."""
    
    def __init__(self, collar_bps: Decimal = Decimal("100")):
        self._collar_bps = collar_bps
    
    def check(self, limit_price: Decimal, reference_price: Decimal, **kwargs) -> CheckResult:
        """Check if price is within collar."""
        if reference_price == 0:
            return CheckResult(
                passed=False,
                message="Reference price is zero",
                details={}
            )
        
        deviation_bps = abs(limit_price - reference_price) / reference_price * Decimal("10000")
        
        if deviation_bps > self._collar_bps:
            return CheckResult(
                passed=False,
                message=f"Price deviation {deviation_bps:.2f} bps exceeds collar",
                details={"deviation_bps": float(deviation_bps)}
            )
        
        return CheckResult(
            passed=True,
            message="Price within collar",
            details={"deviation_bps": float(deviation_bps)}
        )


class MaxOrderSizeCheck(RegulatoryCheck):
    """Maximum order size check."""
    
    def __init__(self, max_notional: Decimal = Decimal("1000000"), max_shares: int = 10000):
        self._max_notional = max_notional
        self._max_shares = max_shares
    
    def check(self, quantity: Decimal, price: Decimal, **kwargs) -> CheckResult:
        """Check if order size exceeds limits."""
        if quantity > self._max_shares:
            return CheckResult(
                passed=False,
                message=f"Order quantity {quantity} exceeds max {self._max_shares}",
                details={"quantity": float(quantity)}
            )
        
        notional = quantity * price
        if notional > self._max_notional:
            return CheckResult(
                passed=False,
                message=f"Order notional ${notional:,.2f} exceeds max ${self._max_notional:,.2f}",
                details={"notional": float(notional)}
            )
        
        return CheckResult(
            passed=True,
            message="Order size within limits",
            details={"notional": float(notional)}
        )


class ShortLocateCheck(RegulatoryCheck):
    """Short locate validation check."""
    
    def __init__(self, require_locate: bool = True):
        self._require_locate = require_locate
        self._locates: dict[str, bool] = {}
    
    def add_locate(self, symbol: str) -> None:
        """Add a short locate for a symbol."""
        self._locates[symbol.upper()] = True
    
    def check(self, symbol: str, **kwargs) -> CheckResult:
        """Check if short locate is available."""
        if not self._require_locate:
            return CheckResult(
                passed=True,
                message="Short locate not required",
                details={}
            )
        
        symbol = symbol.upper()
        if symbol not in self._locates:
            return CheckResult(
                passed=False,
                message=f"No short locate available for {symbol}",
                details={"symbol": symbol}
            )
        
        return CheckResult(
            passed=True,
            message="Short locate valid",
            details={"symbol": symbol}
        )


class FatFingerCheck(RegulatoryCheck):
    """Fat-finger error detection check."""
    
    def __init__(self, max_jump_ratio: Decimal = Decimal("10")):
        self._max_jump_ratio = max_jump_ratio
    
    def check(self, notional: Decimal, current_exposure: Decimal, **kwargs) -> CheckResult:
        """Check for sudden jump in order size."""
        if current_exposure == 0:
            return CheckResult(
                passed=True,
                message="No current exposure to compare",
                details={}
            )
        
        jump_ratio = notional / current_exposure
        
        if jump_ratio > self._max_jump_ratio:
            return CheckResult(
                passed=False,
                message=f"Order notional is {jump_ratio:.1f}x current exposure",
                details={"jump_ratio": float(jump_ratio)}
            )
        
        return CheckResult(
            passed=True,
            message="No fat-finger detected",
            details={"jump_ratio": float(jump_ratio)}
        )


class CapitalThresholdCheck(RegulatoryCheck):
    """Capital threshold check."""
    
    def __init__(self, capital_threshold: Decimal = Decimal("10000000")):
        self._capital_threshold = capital_threshold
    
    def check(self, current_exposure: Decimal, new_exposure: Decimal, **kwargs) -> CheckResult:
        """Check if exposure exceeds capital threshold."""
        if new_exposure > self._capital_threshold:
            return CheckResult(
                passed=False,
                message=f"Projected exposure ${new_exposure:,.2f} exceeds threshold ${self._capital_threshold:,.2f}",
                details={"new_exposure": float(new_exposure)}
            )
        
        return CheckResult(
            passed=True,
            message="Capital within limits",
            details={"new_exposure": float(new_exposure)}
        )
