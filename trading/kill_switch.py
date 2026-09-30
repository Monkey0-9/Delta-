"""
Triple-layer emergency kill switch for order cancellation and position liquidation
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
try:
    from core.domain.timestamp import utc_now
except ImportError:  # installed-package layout
    from delta.core.domain.timestamp import utc_now  # type: ignore
try:
    from core.events import EventBus, EventType, Event
except ImportError:  # installed-package layout
    from delta.core.events import EventBus, EventType, Event  # type: ignore
try:
    from core.events.event_bus import EventBus as _EB  # noqa: F401 (re-export check)
except ImportError:
    pass
from delta.trading.broker_base import UniversalBrokerAdapter, Order, Position

logger = logging.getLogger(__name__)


class KillSwitchState:
    """Kill switch state"""
    ARMED = "armed"
    TRIGGERED = "triggered"
    COOLDOWN = "cooldown"


class KillSwitch:
    """Triple-layer emergency kill switch"""
    
    def __init__(self, broker: UniversalBrokerAdapter, event_bus: EventBus):
        self.broker = broker
        self.event_bus = event_bus
        self.state = KillSwitchState.ARMED
        self.triggered_at: Optional[datetime] = None
        self.triggered_by: str = ""
        self.cancelled_orders_count = 0
        self.liquidated_positions_count = 0
        self._lock = asyncio.Lock()
        self._halt_callbacks: List[Callable[[], Awaitable[None] | None]] = []

    def register_halt_callback(self, cb: Callable[[], Awaitable[None] | None]) -> None:
        """Register an engine-halt hook (Layer 2). Called on trigger; a
        kill switch with no registered halt target is a decorative switch."""
        self._halt_callbacks.append(cb)

    async def trigger(self, flatten_positions: bool = False, *,
                      actor: str = "operator") -> Dict[str, Any]:
        """Trigger the kill switch (Layer 1: Cancel orders, Layer 2: Lock engine)"""
        async with self._lock:
            if self.state == KillSwitchState.TRIGGERED:
                logger.warning("Kill switch already triggered")
                return {"status": "already_triggered"}

            logger.critical("KILL SWITCH TRIGGERED by %s", actor)
            self.state = KillSwitchState.TRIGGERED
            self.triggered_at = utc_now()
            self.triggered_by = actor
            
            results = {
                "triggered_at": self.triggered_at.isoformat(),
                "layer_1": {},
                "layer_2": {},
                "layer_3": {}
            }
            
            # Layer 1: Cancel all resting orders
            try:
                cancelled_count = await self._cancel_all_orders()
                self.cancelled_orders_count = cancelled_count
                results["layer_1"] = {
                    "status": "success",
                    "cancelled_orders": cancelled_count
                }
                logger.critical(f"Layer 1: Cancelled {cancelled_count} orders")
            except Exception as e:
                results["layer_1"] = {
                    "status": "error",
                    "error": str(e)
                }
                logger.error(f"Layer 1 error: {e}")
            
            # Layer 2: Lock engine into HALTED state
            try:
                await self._lock_engine()
                results["layer_2"] = {
                    "status": "success",
                    "message": "Engine locked into HALTED state"
                }
                logger.critical("Layer 2: Engine locked")
            except Exception as e:
                results["layer_2"] = {
                    "status": "error",
                    "error": str(e)
                }
                logger.error(f"Layer 2 error: {e}")
            
            # Layer 3: Flatten positions (optional)
            if flatten_positions:
                try:
                    liquidated_count = await self._flatten_all_positions()
                    self.liquidated_positions_count = liquidated_count
                    results["layer_3"] = {
                        "status": "success",
                        "liquidated_positions": liquidated_count
                    }
                    logger.critical(f"Layer 3: Liquidated {liquidated_count} positions")
                except Exception as e:
                    results["layer_3"] = {
                        "status": "error",
                        "error": str(e)
                    }
                    logger.error(f"Layer 3 error: {e}")
            
            # Publish event (tz-aware clock; Event import fixed — was NameError)
            await self.event_bus.publish(Event(
                event_type=EventType.KILL_SWITCH_TRIGGERED,
                data=results,
                timestamp=utc_now(),
                source="kill_switch"
            ))
            
            return results
    
    async def _cancel_all_orders(self) -> int:
        """Cancel all resting orders"""
        try:
            cancelled_count = await self.broker.cancel_all_orders()
            return cancelled_count
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            raise
    
    async def _lock_engine(self) -> None:
        """Lock the trading engine into HALTED state via registered hooks.

        Previously a ``pass`` placeholder: Layer 2 claimed to lock the engine
        but executed nothing. Now every registered halt callback runs; with
        zero callbacks registered a warning is logged so the gap is visible.
        """
        if not self._halt_callbacks:
            logger.warning("Layer 2: no engine halt callbacks registered — engine NOT locked")
            return
        for cb in self._halt_callbacks:
            res = cb()
            if asyncio.isawaitable(res):
                await res
    
    async def _flatten_all_positions(self) -> int:
        """Flatten all positions to cash"""
        try:
            positions = await self.broker.get_positions()
            liquidated_count = 0
            
            for position in positions:
                result = await self.broker.flatten_position(position.symbol)
                if result.success:
                    liquidated_count += 1
            
            return liquidated_count
        except Exception as e:
            logger.error(f"Error flattening positions: {e}")
            raise
    
    async def cancel_orders_only(self) -> int:
        """Layer 1 only: Cancel all orders without locking engine"""
        try:
            cancelled_count = await self._cancel_all_orders()
            self.cancelled_orders_count = cancelled_count
            logger.info(f"Cancelled {cancelled_count} orders (Layer 1 only)")
            return cancelled_count
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            raise
    
    async def flatten_positions_only(self) -> int:
        """Layer 3 only: Flatten positions without cancelling orders"""
        try:
            liquidated_count = await self._flatten_all_positions()
            self.liquidated_positions_count = liquidated_count
            logger.info(f"Liquidated {liquidated_count} positions (Layer 3 only)")
            return liquidated_count
        except Exception as e:
            logger.error(f"Error flattening positions: {e}")
            raise
    
    def is_triggered(self) -> bool:
        """Check if kill switch is triggered"""
        return self.state == KillSwitchState.TRIGGERED
    
    def is_armed(self) -> bool:
        """Check if kill switch is armed"""
        return self.state == KillSwitchState.ARMED
    
    def reset(self, *, actor: str, reason: str = "") -> None:
        """Reset the kill switch. Authenticated: only the triggering actor
        may re-arm (mirrors risk.kill_switch.KillSwitch). Previously any
        caller could silently re-arm live trading."""
        if self.state == KillSwitchState.ARMED:
            return
        if actor != self.triggered_by:
            raise PermissionError("only the triggering actor may reset the kill switch.")
        logger.warning("Kill switch reset by %s: %s", actor, reason)
        self.state = KillSwitchState.ARMED
        self.triggered_at = None
        self.triggered_by = ""
        self.cancelled_orders_count = 0
        self.liquidated_positions_count = 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get kill switch status"""
        return {
            "state": self.state,
            "armed": self.is_armed(),
            "triggered": self.is_triggered(),
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "cancelled_orders": self.cancelled_orders_count,
            "liquidated_positions": self.liquidated_positions_count
        }
    
    def arm(self, *, actor: str = "operator") -> None:
        """Arm the kill switch"""
        self.state = KillSwitchState.ARMED
        logger.info("Kill switch armed by %s", actor)

    def disarm(self, *, actor: str, reason: str = "") -> None:
        """Disarm the kill switch (authenticated — previously anonymous)."""
        if not actor:
            raise PermissionError("disarm requires an authenticated actor.")
        self.state = KillSwitchState.COOLDOWN
        logger.warning("Kill switch disarmed by %s: %s — entering cooldown", actor, reason)
