"""Emergency Disqualification Criteria implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class DisqualificationType(StrEnum):
    """Types of emergency disqualification criteria."""
    
    # 1. Tri-Temporal Clock Inversion
    TRI_TEMPORAL_INVERSION = "tri_temporal_inversion"
    
    # 2. Zero-Bid / Crossed Market
    CROSSED_MARKET = "crossed_market"
    
    # 3. PBO Exceeds Safe Threshold
    PBO_EXCEEDED = "pbo_exceeded"
    
    # 4. Single-Day Drawdown Breach
    DRAWDOWN_BREACH = "daily_drawdown_breach"
    
    # 5. Position Reconciliation Gap
    RECONCILIATION_GAP = "reconciliation_gap"
    
    # 6. Deflated Sharpe Rejection
    DSR_REJECTION = "dsr_rejection"
    
    # 7. Pre-Trade Collar Breach
    COLLAR_BREACH = "collar_breach"
    
    # 8. Non-Zero Demo Path Call
    DEMO_PATH_CALL = "demo_path_call"
    
    # 9. Liquidity Horizon Collapse
    LIQUIDITY_COLLAPSE = "liquidity_collapse"
    
    # 10. Factor Neutrality Breach
    FACTOR_NEUTRALITY_BREACH = "factor_neutrality_breach"


@dataclass(frozen=True, slots=True)
class EmergencyCriteria:
    """
    Emergency disqualification criteria configuration.
    
    Implements the 10 non-negotiable "Red Button" criteria that
    immediately halt all trading when triggered.
    """
    
    # 1. Tri-Temporal Clock Inversion
    tri_temporal_inversion_enabled: bool = True
    
    # 2. Crossed Market
    crossed_market_enabled: bool = True
    crossed_market_threshold_bps: Decimal = Decimal("0")  # Bid >= Ask
    
    # 3. PBO Threshold
    pbo_threshold: float = 0.15  # 15% overfitting risk threshold
    
    # 4. Daily Drawdown
    daily_drawdown_limit_pct: float = 0.10  # 10% daily drawdown limit
    
    # 5. Reconciliation Tolerance
    reconciliation_tolerance_shares: int = 100  # Shares tolerance
    reconciliation_tolerance_cash: Decimal = Decimal("1000")  # $1000 tolerance
    
    # 6. DSR Threshold
    dsr_threshold: float = 0.99  # 99% confidence threshold
    
    # 7. Price Collar
    price_collar_bps: Decimal = Decimal("300")  # 3% from NBBO
    
    # 8. Demo Path Detection
    demo_path_detection_enabled: bool = True
    
    # 9. Liquidity Horizon
    liquidity_horizon_limit_pct: float = 0.10  # 10% of ADV
    
    # 10. Factor Neutrality
    factor_neutrality_beta_tolerance: float = 0.10  # 10% beta tolerance
    factor_neutrality_sector_tolerance: float = 0.15  # 15% sector tolerance


@dataclass(frozen=True, slots=True)
class DisqualificationEvent:
    """Record of a disqualification event."""
    event_id: UUID = field(default_factory=uuid4)
    disqualification_type: DisqualificationType = DisqualificationType.CROSSED_MARKET
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "critical"  # critical, severe, moderate
    
    def __str__(self) -> str:
        return (
            f"DisqualificationEvent(id={self.event_id}, "
            f"type={self.disqualification_type}, "
            f"timestamp={self.timestamp}, "
            f"severity={self.severity})"
        )
