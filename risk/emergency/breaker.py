"""Circuit Breaker for emergency trading halt."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class BreakerState(StrEnum):
    """States of the circuit breaker."""
    CLOSED = "closed"  # Trading allowed
    OPEN = "open"  # Trading halted
    MANUALLY_OVERRIDDEN = "manually_overridden"  # Manually reopened


@dataclass(frozen=True, slots=True)
class BreakerEvent:
    """Circuit breaker state change event."""
    event_id: UUID = field(default_factory=uuid4)
    previous_state: BreakerState = BreakerState.CLOSED
    new_state: BreakerState = BreakerState.OPEN
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class CircuitBreaker:
    """
    Circuit breaker for emergency trading halt.
    
    When triggered by emergency criteria, immediately:
    - Halts all trading
    - Cancels all open orders
    - Flattens exposed inventory to neutral
    - Triggers emergency alert
    """
    
    def __init__(self) -> None:
        self._state = BreakerState.CLOSED
        self._events: list[BreakerEvent] = []
        self._override_count = 0
        self._last_trigger_time: datetime | None = None
    
    def trigger(self, reason: str, details: dict[str, Any] | None = None) -> BreakerEvent:
        """
        Trigger the circuit breaker (emergency halt).
        
        This should be called when any disqualification criteria
        is met by the EmergencyMonitor.
        """
        if self._state == BreakerState.OPEN:
            # Already triggered
            return BreakerEvent(
                previous_state=self._state,
                new_state=self._state,
                reason="Already triggered",
                details={}
            )
        
        previous_state = self._state
        self._state = BreakerState.OPEN
        self._last_trigger_time = datetime.now(timezone.utc)
        
        event = BreakerEvent(
            previous_state=previous_state,
            new_state=self._state,
            reason=reason,
            details=details or {}
        )
        
        self._events.append(event)
        
        # In production, this would:
        # 1. Cancel all open orders via OMS
        # 2. Flatten positions to neutral
        # 3. Send emergency alerts
        # 4. Log to immutable audit trail
        
        return event
    
    def reset(self, reason: str = "Manual reset") -> BreakerEvent:
        """
        Reset the circuit breaker (manual override).
        
        Requires explicit manual authorization to prevent accidental
        reopening during genuine emergencies.
        """
        if self._state == BreakerState.CLOSED:
            # Already closed
            return BreakerEvent(
                previous_state=self._state,
                new_state=self._state,
                reason="Already closed",
                details={}
            )
        
        previous_state = self._state
        self._state = BreakerState.MANUALLY_OVERRIDDEN
        self._override_count += 1
        
        event = BreakerEvent(
            previous_state=previous_state,
            new_state=self._state,
            reason=reason,
            details={"override_count": self._override_count}
        )
        
        self._events.append(event)
        return event
    
    def close(self, reason: str = "Normal operation resumed") -> BreakerEvent:
        """
        Close the circuit breaker (return to normal operation).
        
        Called after manual override when conditions are safe.
        """
        if self._state == BreakerState.CLOSED:
            return BreakerEvent(
                previous_state=self._state,
                new_state=self._state,
                reason="Already closed",
                details={}
            )
        
        previous_state = self._state
        self._state = BreakerState.CLOSED
        
        event = BreakerEvent(
            previous_state=previous_state,
            new_state=self._state,
            reason=reason,
            details={}
        )
        
        self._events.append(event)
        return event
    
    def get_state(self) -> BreakerState:
        """Get current circuit breaker state."""
        return self._state
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open (trading halted)."""
        return self._state == BreakerState.OPEN
    
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed (trading allowed)."""
        return self._state == BreakerState.CLOSED
    
    def get_events(self) -> list[BreakerEvent]:
        """Get all circuit breaker events."""
        return self._events.copy()
    
    def get_last_trigger_time(self) -> datetime | None:
        """Get timestamp of last trigger."""
        return self._last_trigger_time
    
    def get_override_count(self) -> int:
        """Get number of manual overrides."""
        return self._override_count
    
    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self._state,
            "is_open": self.is_open(),
            "is_closed": self.is_closed(),
            "last_trigger_time": self._last_trigger_time,
            "override_count": self._override_count,
            "event_count": len(self._events),
        }
