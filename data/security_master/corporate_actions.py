"""Corporate Action Normalization Engine.

W95: Handles cash/stock dividends, splits, spin-offs, mergers, and
other corporate actions to maintain adjusted and unadjusted price series.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class CorporateActionType(StrEnum):
    """Types of corporate actions."""
    CASH_DIVIDEND = "cash_dividend"
    STOCK_DIVIDEND = "stock_dividend"
    STOCK_SPLIT = "stock_split"
    REVERSE_SPLIT = "reverse_split"
    SPINOFF = "spinoff"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    RIGHTS_OFFERING = "rights_offering"
    TICKER_CHANGE = "ticker_change"
    DELISTING = "delisting"


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """
    Corporate action event with adjustment factors.
    
    Used to maintain both unadjusted prices (for execution) and
    adjusted prices (for alpha/signal generation).
    """
    action_id: UUID = field(default_factory=uuid4)
    asset_id: UUID = field(default_factory=uuid4)
    action_type: CorporateActionType = CorporateActionType.STOCK_SPLIT
    
    # Timing
    declaration_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ex_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    record_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payment_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Adjustment factors
    split_ratio: Decimal = Decimal("1")  # e.g., 4:1 split = 4.0
    cash_amount: Decimal = Decimal("0")  # Cash dividend per share
    stock_dividend_ratio: Decimal = Decimal("0")  # Stock dividend ratio
    
    # Spinoff / Merger specifics
    spinoff_asset_id: UUID | None = None
    spinoff_ratio: Decimal = Decimal("0")  # Ratio of new shares per old share
    merger_asset_id: UUID | None = None
    merger_ratio: Decimal = Decimal("0")  # Exchange ratio
    
    # Ticker changes
    old_ticker: str | None = None
    new_ticker: str | None = None
    
    # Metadata
    description: str = ""
    source: str = "unknown"
    
    def get_adjustment_factor(self) -> Decimal:
        """
        Calculate the price adjustment factor for this action.
        
        For splits: new_price = old_price / split_ratio
        For dividends: new_price = old_price - cash_amount
        """
        if self.action_type in (CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT):
            return self.split_ratio
        
        if self.action_type == CorporateActionType.STOCK_DIVIDEND:
            return Decimal("1") + self.stock_dividend_ratio
        
        if self.action_type == CorporateActionType.CASH_DIVIDEND:
            # For cash dividends, adjustment is subtractive, not multiplicative
            # This is handled in the price adjustment logic
            return Decimal("1")
        
        return Decimal("1")
    
    def is_applicable_at_date(self, query_date: datetime) -> bool:
        """Check if action is applicable at query date."""
        return query_date >= self.ex_date


class ActionNormalizer:
    """
    Normalizes corporate actions across price series.
    
    Maintains both:
    - Unadjusted prices: For execution and microstructure analysis
    - Adjusted prices: For alpha generation and signal computation
    """
    
    def __init__(self) -> None:
        self._actions: dict[UUID, list[CorporateAction]] = {}
        self._cumulative_factors: dict[UUID, dict[datetime, Decimal]] = {}
    
    def add_action(self, action: CorporateAction) -> None:
        """Add corporate action to normalizer."""
        if action.asset_id not in self._actions:
            self._actions[action.asset_id] = []
        
        self._actions[action.asset_id].append(action)
        # Invalidate cached cumulative factors
        if action.asset_id in self._cumulative_factors:
            del self._cumulative_factors[action.asset_id]
    
    def get_actions_for_asset(self, asset_id: UUID) -> list[CorporateAction]:
        """Get all corporate actions for an asset."""
        return self._actions.get(asset_id, [])
    
    def get_actions_between_dates(
        self,
        asset_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> list[CorporateAction]:
        """Get corporate actions between two dates."""
        actions = self.get_actions_for_asset(asset_id)
        return [
            a for a in actions
            if start_date <= a.ex_date <= end_date
        ]
    
    def calculate_cumulative_adjustment_factor(
        self,
        asset_id: UUID,
        from_date: datetime,
        to_date: datetime
    ) -> Decimal:
        """
        Calculate cumulative adjustment factor between two dates.
        
        Accounts for all splits, stock dividends, and other multiplicative
        corporate actions in the date range.
        """
        actions = self.get_actions_between_dates(asset_id, from_date, to_date)
        
        if not actions:
            return Decimal("1")
        
        # Sort by ex_date
        actions_sorted = sorted(actions, key=lambda a: a.ex_date)
        
        cumulative_factor = Decimal("1")
        for action in actions_sorted:
            cumulative_factor *= action.get_adjustment_factor()
        
        return cumulative_factor
    
    def adjust_price(
        self,
        asset_id: UUID,
        price: Decimal,
        original_date: datetime,
        target_date: datetime
    ) -> Decimal:
        """
        Adjust price from original_date to target_date.
        
        Adjusts for all corporate actions between the two dates.
        """
        if original_date == target_date:
            return price
        
        # Determine direction of adjustment
        if original_date < target_date:
            # Forward adjustment (older to newer)
            factor = self.calculate_cumulative_adjustment_factor(
                asset_id, original_date, target_date
            )
            return price * factor
        else:
            # Reverse adjustment (newer to older)
            factor = self.calculate_cumulative_adjustment_factor(
                asset_id, target_date, original_date
            )
            return price / factor if factor != 0 else price
    
    def adjust_for_cash_dividend(
        self,
        price: Decimal,
        dividend_amount: Decimal
    ) -> Decimal:
        """
        Adjust price for cash dividend.
        
        Cash dividends are subtractive, not multiplicative.
        """
        return price - dividend_amount
    
    def detect_split_anomaly(
        self,
        asset_id: UUID,
        price_before: Decimal,
        price_after: Decimal,
        date: datetime
    ) -> CorporateAction | None:
        """
        Detect potential split anomaly from price discontinuity.
        
        Returns a CorporateAction if a split is detected, None otherwise.
        """
        # Calculate price ratio
        if price_after == 0:
            return None
        
        ratio = price_before / price_after
        
        # Check for common split ratios
        common_ratios = {
            Decimal("2"): CorporateActionType.STOCK_SPLIT,      # 2:1
            Decimal("3"): CorporateActionType.STOCK_SPLIT,      # 3:1
            Decimal("4"): CorporateActionType.STOCK_SPLIT,      # 4:1
            Decimal("0.5"): CorporateActionType.REVERSE_SPLIT,   # 1:2
            Decimal("0.333"): CorporateActionType.REVERSE_SPLIT, # 1:3
        }
        
        for split_ratio, action_type in common_ratios.items():
            if abs(ratio - split_ratio) < Decimal("0.1"):  # 10% tolerance
                return CorporateAction(
                    asset_id=asset_id,
                    action_type=action_type,
                    split_ratio=split_ratio,
                    ex_date=date,
                    description=f"Detected {action_type.value} from price ratio {ratio:.2f}",
                    source="auto_detected"
                )
        
        return None
    
    def validate_action_sequence(self, asset_id: UUID) -> list[str]:
        """
        Validate corporate action sequence for consistency.
        
        Returns list of validation errors.
        """
        errors: list[str] = []
        actions = self.get_actions_for_asset(asset_id)
        
        # Sort by ex_date
        actions_sorted = sorted(actions, key=lambda a: a.ex_date)
        
        for i, action in enumerate(actions_sorted):
            # Check date consistency
            if action.record_date > action.ex_date:
                errors.append(
                    f"Action {action.action_id}: record_date after ex_date"
                )
            
            if action.ex_date > action.payment_date:
                errors.append(
                    f"Action {action.action_id}: ex_date after payment_date"
                )
            
            # Check for overlapping actions
            if i > 0:
                prev_action = actions_sorted[i - 1]
                if action.ex_date == prev_action.ex_date:
                    errors.append(
                        f"Action {action.action_id}: ex_date overlaps with previous action"
                    )
        
        return errors
