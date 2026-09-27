"""
Behavioral risk monitor and anti-tilt safeguards
"""

from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TiltState(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    COOLDOWN = "cooldown"
    LOCKED = "locked"


@dataclass
class TradeResult:
    """Result of a trade for tilt monitoring"""
    ticker: str
    side: str
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    timestamp: datetime


class AntiTiltGovernor:
    """Monitors trader behavior and enforces anti-tilt safeguards"""
    
    def __init__(self, consecutive_loss_limit: int = 3, cooldown_minutes: int = 30):
        self.consecutive_loss_limit = consecutive_loss_limit
        self.cooldown_minutes = cooldown_minutes
        self.trade_history: List[TradeResult] = []
        self.consecutive_losses: int = 0
        self.state: TiltState = TiltState.NORMAL
        self.cooldown_until: Optional[datetime] = None
        self.max_drawdown: float = 0.0
        self.daily_pnl: float = 0.0
        self.last_trade_time: Optional[datetime] = None
    
    def record_trade(self, result: TradeResult) -> None:
        """Record a trade result for tilt monitoring"""
        self.trade_history.append(result)
        self.daily_pnl += result.pnl
        self.last_trade_time = result.timestamp
        
        # Track consecutive losses
        if result.pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Calculate max drawdown
        cumulative_pnl = sum(t.pnl for t in self.trade_history)
        if cumulative_pnl < self.max_drawdown:
            self.max_drawdown = cumulative_pnl
        
        # Check tilt conditions
        self._check_tilt_conditions()
    
    def _check_tilt_conditions(self) -> None:
        """Check if tilt safeguards should be triggered"""
        # Check consecutive losses
        if self.consecutive_losses >= self.consecutive_loss_limit:
            self._trigger_cooldown("consecutive_losses")
            return
        
        # Check if already in cooldown
        if self.state == TiltState.COOLDOWN:
            if datetime.utcnow() >= self.cooldown_until:
                self._exit_cooldown()
            return
        
        # Warning state
        if self.consecutive_losses >= self.consecutive_loss_limit - 1:
            self.state = TiltState.WARNING
            logger.warning(f"Anti-tilt warning: {self.consecutive_losses} consecutive losses")
    
    def _trigger_cooldown(self, reason: str) -> None:
        """Trigger cooldown mode"""
        self.state = TiltState.COOLDOWN
        self.cooldown_until = datetime.utcnow() + timedelta(minutes=self.cooldown_minutes)
        logger.warning(f"Anti-tilt cooldown triggered: {reason}. Cooldown until {self.cooldown_until}")
    
    def _exit_cooldown(self) -> None:
        """Exit cooldown mode"""
        self.state = TiltState.NORMAL
        self.consecutive_losses = 0
        self.cooldown_until = None
        logger.info("Anti-tilt cooldown ended")
    
    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed"""
        if self.state == TiltState.COOLDOWN:
            if datetime.utcnow() < self.cooldown_until:
                remaining = (self.cooldown_until - datetime.utcnow()).total_seconds() / 60
                return False, f"In cooldown mode. {remaining:.1f} minutes remaining."
            else:
                self._exit_cooldown()
        
        if self.state == TiltState.LOCKED:
            return False, "Trading is locked. Contact administrator."
        
        if self.state == TiltState.WARNING:
            logger.warning("Trading allowed but in warning state")
        
        return True, "Trading allowed"
    
    def get_position_sizing_multiplier(self) -> float:
        """Get position sizing multiplier based on tilt state"""
        if self.state == TiltState.COOLDOWN:
            return 0.0
        elif self.state == TiltState.WARNING:
            return 0.5  # Reduce size by 50%
        elif self.max_drawdown < -0.015:  # More than 1.5% drawdown
            return 0.75  # Reduce size by 25%
        else:
            return 1.0
    
    def get_tilt_status(self) -> dict:
        """Get current tilt status"""
        status = {
            "state": self.state.value,
            "consecutive_losses": self.consecutive_losses,
            "daily_pnl": self.daily_pnl,
            "max_drawdown": self.max_drawdown,
            "trade_count": len(self.trade_history)
        }
        
        if self.cooldown_until:
            remaining = (self.cooldown_until - datetime.utcnow()).total_seconds() / 60
            status["cooldown_remaining_minutes"] = max(0, remaining)
        
        return status
    
    def reset_daily(self) -> None:
        """Reset daily statistics"""
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        if self.state == TiltState.COOLDOWN:
            self._exit_cooldown()
        logger.info("Daily tilt statistics reset")
    
    def force_unlock(self) -> None:
        """Force unlock (admin override)"""
        self.state = TiltState.NORMAL
        self.consecutive_losses = 0
        self.cooldown_until = None
        logger.warning("Anti-tilt governor force unlocked")
    
    def get_recent_trades(self, limit: int = 10) -> List[TradeResult]:
        """Get recent trade results"""
        return self.trade_history[-limit:]
