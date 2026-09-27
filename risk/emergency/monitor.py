"""Emergency Monitor for continuous disqualification checking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from .criteria import (
    EmergencyCriteria,
    DisqualificationType,
    DisqualificationEvent
)


@dataclass(frozen=True, slots=True)
class MarketState:
    """Current market state for monitoring."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Market data
    best_bid: Decimal = Decimal("0")
    best_ask: Decimal = Decimal("0")
    last_price: Decimal = Decimal("0")
    
    # Portfolio state
    current_exposure: Decimal = Decimal("0")
    daily_pnl: Decimal = Decimal("0")
    daily_drawdown: float = 0.0
    
    # Position reconciliation
    oms_position: int = 0
    broker_position: int = 0
    custodian_position: int = 0
    oms_cash: Decimal = Decimal("0")
    broker_cash: Decimal = Decimal("0")
    custodian_cash: Decimal = Decimal("0")
    
    # Model performance
    deflated_sharpe: float = 1.0
    pbo_score: float = 0.0
    
    # Factor exposures
    beta_exposure: float = 0.0
    sector_exposure: float = 0.0
    
    # Liquidity
    adv: Decimal = Decimal("1000000")
    current_position: Decimal = Decimal("0")
    
    # Data quality
    tri_temporal_valid: bool = True
    demo_path_active: bool = False


class EmergencyMonitor:
    """
    Continuous monitor for emergency disqualification criteria.
    
    Monitors the 10 non-negotiable criteria and triggers
    circuit breaker when any threshold is breached.
    """
    
    def __init__(self, criteria: EmergencyCriteria | None = None) -> None:
        self._criteria = criteria or EmergencyCriteria()
        self._events: list[DisqualificationEvent] = []
        self._is_triggered = False
    
    def check_market_state(self, state: MarketState) -> list[DisqualificationEvent]:
        """
        Check market state against all disqualification criteria.
        
        Returns list of triggered events (empty if none triggered).
        """
        events: list[DisqualificationEvent] = []
        
        # 1. Tri-Temporal Clock Inversion
        if self._criteria.tri_temporal_inversion_enabled:
            event = self._check_tri_temporal_inversion(state)
            if event:
                events.append(event)
        
        # 2. Crossed Market
        if self._criteria.crossed_market_enabled:
            event = self._check_crossed_market(state)
            if event:
                events.append(event)
        
        # 3. PBO Exceeded
        event = self._check_pbo_threshold(state)
        if event:
            events.append(event)
        
        # 4. Daily Drawdown Breach
        event = self._check_daily_drawdown(state)
        if event:
            events.append(event)
        
        # 5. Position Reconciliation Gap
        event = self._check_reconciliation_gap(state)
        if event:
            events.append(event)
        
        # 6. Deflated Sharpe Rejection
        event = self._check_dsr_threshold(state)
        if event:
            events.append(event)
        
        # 7. Price Collar Breach
        event = self._check_price_collar(state)
        if event:
            events.append(event)
        
        # 8. Demo Path Call
        if self._criteria.demo_path_detection_enabled:
            event = self._check_demo_path(state)
            if event:
                events.append(event)
        
        # 9. Liquidity Horizon Collapse
        event = self._check_liquidity_horizon(state)
        if event:
            events.append(event)
        
        # 10. Factor Neutrality Breach
        event = self._check_factor_neutrality(state)
        if event:
            events.append(event)
        
        # Record events
        self._events.extend(events)
        
        # Trigger circuit breaker if any events
        if events:
            self._is_triggered = True
        
        return events
    
    def _check_tri_temporal_inversion(self, state: MarketState) -> DisqualificationEvent | None:
        """Check for tri-temporal clock inversion."""
        if not state.tri_temporal_valid:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.TRI_TEMPORAL_INVERSION,
                details={"valid": state.tri_temporal_valid}
            )
        return None
    
    def _check_crossed_market(self, state: MarketState) -> DisqualificationEvent | None:
        """Check for crossed market (bid >= ask)."""
        if state.best_bid >= state.best_ask:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.CROSSED_MARKET,
                details={
                    "best_bid": float(state.best_bid),
                    "best_ask": float(state.best_ask),
                }
            )
        return None
    
    def _check_pbo_threshold(self, state: MarketState) -> DisqualificationEvent | None:
        """Check if PBO exceeds safe threshold."""
        if state.pbo_score > self._criteria.pbo_threshold:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.PBO_EXCEEDED,
                details={
                    "pbo_score": state.pbo_score,
                    "threshold": self._criteria.pbo_threshold,
                }
            )
        return None
    
    def _check_daily_drawdown(self, state: MarketState) -> DisqualificationEvent | None:
        """Check if daily drawdown exceeds limit."""
        if abs(state.daily_drawdown) > self._criteria.daily_drawdown_limit_pct:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.DRAWDOWN_BREACH,
                details={
                    "daily_drawdown": state.daily_drawdown,
                    "limit": self._criteria.daily_drawdown_limit_pct,
                }
            )
        return None
    
    def _check_reconciliation_gap(self, state: MarketState) -> DisqualificationEvent | None:
        """Check for position reconciliation gaps."""
        # Check position reconciliation
        position_gap = max(
            abs(state.oms_position - state.broker_position),
            abs(state.broker_position - state.custodian_position),
            abs(state.oms_position - state.custodian_position)
        )
        
        # Check cash reconciliation
        cash_gap = max(
            abs(state.oms_cash - state.broker_cash),
            abs(state.broker_cash - state.custodian_cash),
            abs(state.oms_cash - state.custodian_cash)
        )
        
        if (position_gap > self._criteria.reconciliation_tolerance_shares or
            cash_gap > self._criteria.reconciliation_tolerance_cash):
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.RECONCILIATION_GAP,
                details={
                    "position_gap": position_gap,
                    "cash_gap": float(cash_gap),
                }
            )
        return None
    
    def _check_dsr_threshold(self, state: MarketState) -> DisqualificationEvent | None:
        """Check if deflated Sharpe ratio is below threshold."""
        if state.deflated_sharpe < self._criteria.dsr_threshold:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.DSR_REJECTION,
                details={
                    "deflated_sharpe": state.deflated_sharpe,
                    "threshold": self._criteria.dsr_threshold,
                }
            )
        return None
    
    def _check_price_collar(self, state: MarketState) -> DisqualificationEvent | None:
        """Check for price collar breach."""
        if state.last_price == 0:
            return None
        
        deviation_bps = abs(state.last_price - (state.best_bid + state.best_ask) / 2) / state.last_price * Decimal("10000")
        
        if deviation_bps > self._criteria.price_collar_bps:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.COLLAR_BREACH,
                details={
                    "deviation_bps": float(deviation_bps),
                    "threshold": float(self._criteria.price_collar_bps),
                }
            )
        return None
    
    def _check_demo_path(self, state: MarketState) -> DisqualificationEvent | None:
        """Check for demo path activation."""
        if state.demo_path_active:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.DEMO_PATH_CALL,
                details={"demo_path_active": state.demo_path_active}
            )
        return None
    
    def _check_liquidity_horizon(self, state: MarketState) -> DisqualificationEvent | None:
        """Check for liquidity horizon collapse."""
        if state.adv == 0:
            return None
        
        liquidity_ratio = float(state.current_position / state.adv)
        
        if liquidity_ratio > self._criteria.liquidity_horizon_limit_pct:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.LIQUIDITY_COLLAPSE,
                details={
                    "liquidity_ratio": liquidity_ratio,
                    "threshold": self._criteria.liquidity_horizon_limit_pct,
                }
            )
        return None
    
    def _check_factor_neutrality(self, state: MarketState) -> DisqualificationEvent | None:
        """Check for factor neutrality breach."""
        beta_breach = abs(state.beta_exposure) > self._criteria.factor_neutrality_beta_tolerance
        sector_breach = abs(state.sector_exposure) > self._criteria.factor_neutrality_sector_tolerance
        
        if beta_breach or sector_breach:
            return DisqualificationEvent(
                disqualification_type=DisqualificationType.FACTOR_NEUTRALITY_BREACH,
                details={
                    "beta_exposure": state.beta_exposure,
                    "sector_exposure": state.sector_exposure,
                    "beta_breach": beta_breach,
                    "sector_breach": sector_breach,
                }
            )
        return None
    
    def is_triggered(self) -> bool:
        """Check if circuit breaker is currently triggered."""
        return self._is_triggered
    
    def get_events(self) -> list[DisqualificationEvent]:
        """Get all disqualification events."""
        return self._events.copy()
    
    def reset(self) -> None:
        """Reset the monitor (after manual override)."""
        self._events.clear()
        self._is_triggered = False
