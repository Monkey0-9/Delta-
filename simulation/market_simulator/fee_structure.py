"""
Institutional fee structure modeling for realistic execution costs.

This implements production-quality fee structures:
- Maker-taker fee models
- Exchange-specific fee schedules
- Volume-based fee tiers
- Rebate structures
- Fee optimization for execution algorithms
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
import math


class FeeModel(Enum):
    """Fee model types."""
    MAKER_TAKER = "MAKER_TAKER"
    FIXED = "FIXED"
    TIERED_VOLUME = "TIERED_VOLUME"
    REBATE_HEAVY = "REBATE_HEAVY"


__all__ = [
    "FeeModel",
    "FeeSchedule",
    "FeeCalculation",
    "FeeStructure",
    "MakerTakerFees",
    "ExchangeFees",
    "FeeOptimizer",
    "FeeStructureFactory"
]


@dataclass
class FeeSchedule:
    """
    Fee schedule for a specific exchange/venue.
    """
    exchange: str
    maker_fee_bps: float  # Negative = rebate
    taker_fee_bps: float
    min_fee_usd: float = 0.0
    max_fee_usd: float = float('inf')
    volume_tiers: Dict[str, tuple] = None  # Volume -> (maker_bps, taker_bps)
    
    def __post_init__(self):
        if self.volume_tiers is None:
            self.volume_tiers = {}


@dataclass
class FeeCalculation:
    """
    Result of fee calculation.
    """
    fee_usd: float
    fee_bps: float
    rebate_usd: float
    rebate_bps: float
    net_cost_usd: float
    tier_applied: str = "DEFAULT"


class FeeStructure:
    """
    Base class for fee structure calculations.
    """
    
    def __init__(self, schedule: FeeSchedule):
        self.schedule = schedule
    
    def calculate_fee(self,
                     notional: float,
                     is_maker: bool,
                     monthly_volume: float = 0.0) -> FeeCalculation:
        """
        Calculate fee for a trade.
        
        Args:
            notional: Trade notional value
            is_maker: True if maker order, False if taker
            monthly_volume: Monthly trading volume for tier calculation
            
        Returns:
            FeeCalculation with cost breakdown
        """
        raise NotImplementedError("Subclasses must implement calculate_fee")


class MakerTakerFees(FeeStructure):
    """
    Standard maker-taker fee structure.
    
    Makers receive rebates, takers pay fees.
    """
    
    def calculate_fee(self,
                     notional: float,
                     is_maker: bool,
                     monthly_volume: float = 0.0) -> FeeCalculation:
        """
        Calculate maker-taker fee.
        """
        # Check volume tiers
        tier = self._get_volume_tier(monthly_volume)
        tier_data = self.schedule.volume_tiers.get(tier)
        if tier_data is not None:
            # Extract from tuple format (threshold, (maker_bps, taker_bps))
            if isinstance(tier_data, tuple) and len(tier_data) == 2 and isinstance(tier_data[1], tuple):
                maker_bps, taker_bps = tier_data[1]
            else:
                # Direct (maker_bps, taker_bps) format
                maker_bps, taker_bps = tier_data
        else:
            maker_bps, taker_bps = (self.schedule.maker_fee_bps, self.schedule.taker_fee_bps)
        
        if is_maker:
            fee_bps = maker_bps
        else:
            fee_bps = taker_bps
        
        # Calculate fee in USD
        fee_usd = notional * abs(fee_bps) / 10000 if fee_bps > 0 else 0.0
        rebate_usd = notional * abs(fee_bps) / 10000 if fee_bps < 0 else 0.0
        rebate_bps = abs(fee_bps) if fee_bps < 0 else 0.0
        
        # Apply min/max fee constraints
        fee_usd = max(self.schedule.min_fee_usd, min(fee_usd, self.schedule.max_fee_usd))
        
        net_cost = fee_usd - rebate_usd
        
        return FeeCalculation(
            fee_usd=fee_usd,
            fee_bps=abs(fee_bps) if fee_bps > 0 else 0.0,
            rebate_usd=rebate_usd,
            rebate_bps=rebate_bps,
            net_cost_usd=net_cost,
            tier_applied=tier
        )
    
    def _get_volume_tier(self, monthly_volume: float) -> str:
        """Get volume tier based on monthly volume."""
        if not self.schedule.volume_tiers:
            return "DEFAULT"

        # Handle different tier formats
        if "TIER_1" in self.schedule.volume_tiers:
            # Simple tier system without thresholds
            return "TIER_1"

        # Sort tiers by volume threshold (if using threshold format)
        try:
            sorted_tiers = sorted(
                [(tier, data[0]) for tier, data in self.schedule.volume_tiers.items() if isinstance(data, tuple) and len(data) > 0],
                key=lambda x: x[1],
                reverse=True
            )

            for tier, threshold in sorted_tiers:
                if monthly_volume >= threshold:
                    return tier
        except (IndexError, TypeError):
            pass

        return "DEFAULT"


class ExchangeFees(FeeStructure):
    """
    Exchange-specific fee structures.
    
    Models different fee schedules for major exchanges.
    """
    
    # Common exchange fee schedules
    EXCHANGE_SCHEDULES = {
        "NYSE": FeeSchedule(
            exchange="NYSE",
            maker_fee_bps=-0.15,  # 0.15 bps rebate
            taker_fee_bps=0.25,   # 0.25 bps fee
            volume_tiers={}
        ),
        "NASDAQ": FeeSchedule(
            exchange="NASDAQ",
            maker_fee_bps=-0.20,
            taker_fee_bps=0.30,
            volume_tiers={}
        ),
        "BATS": FeeSchedule(
            exchange="BATS",
            maker_fee_bps=-0.30,
            taker_fee_bps=0.30,
            volume_tiers={}
        ),
        "ARCA": FeeSchedule(
            exchange="ARCA",
            maker_fee_bps=-0.25,
            taker_fee_bps=0.30,
            volume_tiers={}
        )
    }
    
    def __init__(self, exchange: str):
        """
        Initialize with exchange-specific schedule.
        
        Args:
            exchange: Exchange identifier (NYSE, NASDAQ, BATS, ARCA)
        """
        schedule = self.EXCHANGE_SCHEDULES.get(exchange)
        if schedule is None:
            # Default schedule
            schedule = FeeSchedule(
                exchange=exchange,
                maker_fee_bps=-0.20,
                taker_fee_bps=0.30
            )
        
        super().__init__(schedule)
    
    def calculate_fee(self,
                     notional: float,
                     is_maker: bool,
                     monthly_volume: float = 0.0) -> FeeCalculation:
        """
        Calculate exchange fee.
        """
        maker_taker = MakerTakerFees(self.schedule)
        return maker_taker.calculate_fee(notional, is_maker, monthly_volume)


class FeeOptimizer:
    """
    Optimizes execution across venues to minimize fees.
    
    Considers:
    - Fee differentials across venues
    - Liquidity availability
    - Market impact
    - Total cost of execution
    """
    
    def __init__(self, exchanges: List[str]):
        """
        Initialize fee optimizer.
        
        Args:
            exchanges: List of exchange identifiers
        """
        self.exchanges = exchanges
        self.fee_structures = {
            exchange: ExchangeFees(exchange) 
            for exchange in exchanges
        }
    
    def calculate_all_venue_costs(self,
                                  notional: float,
                                  is_maker: bool,
                                  monthly_volume: float = 0.0) -> Dict[str, FeeCalculation]:
        """
        Calculate costs across all venues.
        
        Returns:
            Dictionary mapping exchange to FeeCalculation
        """
        costs = {}
        for exchange, fee_structure in self.fee_structures.items():
            costs[exchange] = fee_structure.calculate_fee(
                notional, is_maker, monthly_volume
            )
        return costs
    
    def find_optimal_venue(self,
                          notional: float,
                          is_maker: bool,
                          monthly_volume: float = 0.0,
                          liquidity_constraints: Dict[str, float] = None) -> str:
        """
        Find optimal venue for execution.
        
        Args:
            notional: Trade notional
            is_maker: True if maker order
            monthly_volume: Monthly volume for tier calculation
            liquidity_constraints: Minimum liquidity required per venue
            
        Returns:
            Optimal exchange identifier
        """
        if liquidity_constraints is None:
            liquidity_constraints = {}
        
        costs = self.calculate_all_venue_costs(notional, is_maker, monthly_volume)
        
        # Filter venues with sufficient liquidity
        available_venues = [
            exchange for exchange in self.exchanges
            if liquidity_constraints.get(exchange, 0) >= notional
        ]
        
        if not available_venues:
            # No venue has sufficient liquidity, return cheapest anyway
            available_venues = self.exchanges
        
        # Find venue with minimum net cost
        optimal_venue = min(
            available_venues,
            key=lambda x: costs[x].net_cost_usd
        )
        
        return optimal_venue
    
    def estimate_fee_savings(self,
                            notional: float,
                            is_maker: bool,
                            current_venue: str,
                            monthly_volume: float = 0.0) -> Dict[str, float]:
        """
        Estimate potential fee savings by switching venues.
        
        Returns:
            Dictionary with savings vs other venues
        """
        current_cost = self.fee_structures[current_venue].calculate_fee(
            notional, is_maker, monthly_volume
        )
        
        all_costs = self.calculate_all_venue_costs(notional, is_maker, monthly_volume)
        
        savings = {}
        for exchange, cost in all_costs.items():
            if exchange != current_venue:
                savings[exchange] = current_cost.net_cost_usd - cost.net_cost_usd
        
        return savings


class FeeStructureFactory:
    """
    Factory for creating fee structures.
    """
    
    @staticmethod
    def create_maker_taker(maker_fee_bps: float,
                          taker_fee_bps: float,
                          exchange: str = "SIM") -> MakerTakerFees:
        """
        Create maker-taker fee structure.
        
        Args:
            maker_fee_bps: Maker fee (negative for rebate)
            taker_fee_bps: Taker fee
            exchange: Exchange identifier
            
        Returns:
            MakerTakerFees instance
        """
        schedule = FeeSchedule(
            exchange=exchange,
            maker_fee_bps=maker_fee_bps,
            taker_fee_bps=taker_fee_bps
        )
        return MakerTakerFees(schedule)
    
    @staticmethod
    def create_exchange_fees(exchange: str) -> ExchangeFees:
        """
        Create exchange-specific fee structure.
        
        Args:
            exchange: Exchange identifier
            
        Returns:
            ExchangeFees instance
        """
        return ExchangeFees(exchange)
    
    @staticmethod
    def get_rebate_heavy_schedule(exchange: str = "SIM") -> FeeSchedule:
        """
        Get rebate-heavy fee schedule (common for dark pools).
        
        Args:
            exchange: Exchange identifier
            
        Returns:
            FeeSchedule with high rebates
        """
        return FeeSchedule(
            exchange=exchange,
            maker_fee_bps=-0.50,  # 0.50 bps rebate
            taker_fee_bps=0.10,   # 0.10 bps fee
            volume_tiers={
                "HIGH_VOLUME": (1_000_000, (-0.60, 0.05))
            }
        )