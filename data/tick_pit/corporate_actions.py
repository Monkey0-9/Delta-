"""
Corporate actions handling for PIT correctness.

This implements institutional-grade corporate action management:
- Stock splits
- Dividends
- Mergers
- Spin-offs
- Price adjustments
- Historical tracking
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import hashlib


class ActionType(Enum):
    """Corporate action type enumeration."""
    STOCK_SPLIT = "STOCK_SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    CASH_DIVIDEND = "CASH_DIVIDEND"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    MERGER = "MERGER"
    SPINOFF = "SPINOFF"
    RIGHTS_OFFERING = "RIGHTS_OFFERING"
    NAME_CHANGE = "NAME_CHANGE"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """
    Corporate action data structure.
    """
    action_id: str
    symbol: str
    action_type: ActionType
    announcement_date: date
    ex_date: date
    record_date: date
    payable_date: Optional[date] = None
    split_ratio: Optional[float] = None  # For splits
    dividend_amount: Optional[float] = None  # For dividends
    new_symbol: Optional[str] = None  # For symbol changes
    description: str = ""
    
    @property
    def action_hash(self) -> str:
        """Compute hash of action for versioning."""
        action_str = "|".join([
            self.action_id,
            self.symbol,
            self.action_type.value,
            self.announcement_date.isoformat(),
            self.ex_date.isoformat(),
            str(self.split_ratio) if self.split_ratio else "",
            str(self.dividend_amount) if self.dividend_amount else "",
            self.new_symbol or ""
        ])
        return hashlib.sha256(action_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "action_id": self.action_id,
            "symbol": self.symbol,
            "action_type": self.action_type.value,
            "announcement_date": self.announcement_date.isoformat(),
            "ex_date": self.ex_date.isoformat(),
            "record_date": self.record_date.isoformat(),
            "payable_date": self.payable_date.isoformat() if self.payable_date else None,
            "split_ratio": self.split_ratio,
            "dividend_amount": self.dividend_amount,
            "new_symbol": self.new_symbol,
            "description": self.description,
            "action_hash": self.action_hash
        }


class CorporateActionHandler:
    """
    Handles corporate actions for PIT correctness.
    
    Features:
    - Price adjustment for splits
    - Dividend handling
    - Symbol change tracking
    - Historical adjustment tracking
    """
    
    def __init__(self):
        """Initialize corporate action handler."""
        self.actions: Dict[str, CorporateAction] = {}  # action_id -> action
        self.symbol_actions: Dict[str, List[CorporateAction]] = {}  # symbol -> actions
        self.adjustment_history: Dict[str, List[Tuple[datetime, float]]] = {}  # symbol -> [(timestamp, adjustment_factor)]
    
    def add_action(self, action: CorporateAction) -> None:
        """
        Add corporate action.
        
        Args:
            action: Corporate action to add
        """
        self.actions[action.action_id] = action
        
        if action.symbol not in self.symbol_actions:
            self.symbol_actions[action.symbol] = []
        self.symbol_actions[action.symbol].append(action)
    
    def get_actions_for_symbol(self, 
                             symbol: str,
                             start_date: Optional[date] = None,
                             end_date: Optional[date] = None) -> List[CorporateAction]:
        """
        Get corporate actions for symbol in date range.
        
        Args:
            symbol: Symbol to query
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            List of corporate actions
        """
        if symbol not in self.symbol_actions:
            return []
        
        actions = self.symbol_actions[symbol]
        
        if start_date is None and end_date is None:
            return actions
        
        filtered = []
        for action in actions:
            if start_date and action.ex_date < start_date:
                continue
            if end_date and action.ex_date > end_date:
                continue
            filtered.append(action)
        
        return filtered
    
    def adjust_price_for_split(self,
                                price: float,
                                symbol: str,
                                as_of: datetime) -> Tuple[float, Optional[CorporateAction]]:
        """
        Adjust price for stock splits.
        
        Args:
            price: Original price
            symbol: Symbol
            as_of: As-of timestamp
            
        Returns:
            (adjusted_price, applied_action)
        """
        as_of_date = as_of.date()
        
        # Get relevant splits
        actions = self.get_actions_for_symbol(symbol, end_date=as_of_date)
        splits = [a for a in actions if a.action_type in [ActionType.STOCK_SPLIT, ActionType.REVERSE_SPLIT]]
        
        if not splits:
            return price, None
        
        # Apply most recent split
        most_recent = max(splits, key=lambda a: a.ex_date)
        
        if most_recent.split_ratio is None:
            return price, None
        
        if most_recent.action_type == ActionType.STOCK_SPLIT:
            # Stock split: price decreases (e.g., 2-for-1: price / 2)
            adjusted_price = price / most_recent.split_ratio
        else:
            # Reverse split: price increases (e.g., 1-for-2: price * 2)
            adjusted_price = price * most_recent.split_ratio
        
        return adjusted_price, most_recent
    
    def adjust_volume_for_split(self,
                                volume: float,
                                symbol: str,
                                as_of: datetime) -> Tuple[float, Optional[CorporateAction]]:
        """
        Adjust volume for stock splits.
        
        Args:
            volume: Original volume
            symbol: Symbol
            as_of: As-of timestamp
            
        Returns:
            (adjusted_volume, applied_action)
        """
        as_of_date = as_of.date()
        
        # Get relevant splits
        actions = self.get_actions_for_symbol(symbol, end_date=as_of_date)
        splits = [a for a in actions if a.action_type in [ActionType.STOCK_SPLIT, ActionType.REVERSE_SPLIT]]
        
        if not splits:
            return volume, None
        
        # Apply most recent split
        most_recent = max(splits, key=lambda a: a.ex_date)
        
        if most_recent.split_ratio is None:
            return volume, None
        
        if most_recent.action_type == ActionType.STOCK_SPLIT:
            # Stock split: volume increases (e.g., 2-for-1: volume * 2)
            adjusted_volume = volume * most_recent.split_ratio
        else:
            # Reverse split: volume decreases (e.g., 1-for-2: volume / 2)
            adjusted_volume = volume / most_recent.split_ratio
        
        return adjusted_volume, most_recent
    
    def get_dividend_adjustment(self,
                               symbol: str,
                               as_of: datetime) -> float:
        """
        Get dividend adjustment for symbol.
        
        Args:
            symbol: Symbol
            as_of: As-of timestamp
            
        Returns:
            Total dividend amount
        """
        as_of_date = as_of.date()
        
        # Get relevant dividends
        actions = self.get_actions_for_symbol(symbol, end_date=as_of_date)
        dividends = [a for a in actions if a.action_type in [ActionType.CASH_DIVIDEND, ActionType.STOCK_DIVIDEND]]
        
        total_dividend = sum(d.dividend_amount or 0 for d in dividends)
        
        return total_dividend
    
    def resolve_symbol(self,
                      symbol: str,
                      as_of: datetime) -> str:
        """
        Resolve symbol considering symbol changes.
        
        Args:
            symbol: Symbol to resolve
            as_of: As-of timestamp
            
        Returns:
            Correct symbol for as-of date
        """
        as_of_date = as_of.date()
        
        # Get relevant symbol changes
        actions = self.get_actions_for_symbol(symbol, end_date=as_of_date)
        symbol_changes = [a for a in actions if a.action_type == ActionType.SYMBOL_CHANGE]
        
        if not symbol_changes:
            return symbol
        
        # Apply most recent symbol change
        most_recent = max(symbol_changes, key=lambda a: a.ex_date)
        
        return most_recent.new_symbol or symbol
    
    def get_adjustment_history(self, symbol: str) -> List[Tuple[datetime, float]]:
        """
        Get adjustment history for symbol.
        
        Args:
            symbol: Symbol to query
            
        Returns:
            List of (timestamp, adjustment_factor) tuples
        """
        return self.adjustment_history.get(symbol, [])
    
    def track_adjustment(self,
                        symbol: str,
                        timestamp: datetime,
                        adjustment_factor: float) -> None:
        """
        Track price adjustment for symbol.
        
        Args:
            symbol: Symbol
            timestamp: Adjustment timestamp
            adjustment_factor: Adjustment factor (e.g., 0.5 for 2-for-1 split)
        """
        if symbol not in self.adjustment_history:
            self.adjustment_history[symbol] = []
        
        self.adjustment_history[symbol].append((timestamp, adjustment_factor))
    
    def create_pit_adjusted_price(self,
                                   original_price: float,
                                   symbol: str,
                                   as_of: datetime) -> Dict:
        """
        Create PIT-adjusted price with full adjustment tracking.
        
        Args:
            original_price: Original price
            symbol: Symbol
            as_of: As-of timestamp
            
        Returns:
            Dictionary with adjustment details
        """
        # Adjust for splits
        adjusted_price, split_action = self.adjust_price_for_split(original_price, symbol, as_of)
        
        # Get dividend adjustment
        dividend = self.get_dividend_adjustment(symbol, as_of)
        
        # Resolve symbol
        resolved_symbol = self.resolve_symbol(symbol, as_of)
        
        return {
            "original_price": original_price,
            "adjusted_price": adjusted_price,
            "symbol": symbol,
            "resolved_symbol": resolved_symbol,
            "split_action": split_action.to_dict() if split_action else None,
            "dividend_adjustment": dividend,
            "as_of": as_of.isoformat(),
            "adjustment_factor": adjusted_price / original_price if original_price > 0 else 1.0
        }


__all__ = [
    "ActionType",
    "CorporateAction",
    "CorporateActionHandler"
]