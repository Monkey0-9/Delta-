"""
Pre-trade risk governor with position sizing and leverage limits
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging
from delta.trading.broker_base import Order, AccountInfo, Position, OrderSide

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result of a risk check"""
    approved: bool
    reason: str
    max_quantity: Optional[int] = None
    suggested_price: Optional[float] = None


class RiskGovernor:
    """Pre-trade risk governor enforcing position limits and leverage constraints"""
    
    def __init__(self, config: Dict[str, Any]):
        self.max_position_pct = config.get("max_position_pct", 5.0)
        self.max_leverage = config.get("max_leverage", 1.5)
        self.daily_drawdown_limit = config.get("daily_drawdown_limit", 2.0)
        self.kelly_fraction = config.get("kelly_fraction", 0.25)
        
        self.daily_pnl = 0.0
        self.daily_start_equity: Optional[float] = None
        self.position_limits: Dict[str, int] = {}
    
    def set_daily_start_equity(self, equity: float) -> None:
        """Set the starting equity for the day"""
        self.daily_start_equity = equity
        self.daily_pnl = 0.0
        logger.info(f"Daily start equity set to ${equity:,.2f}")
    
    def update_daily_pnl(self, pnl: float) -> None:
        """Update daily P&L"""
        self.daily_pnl += pnl
        logger.debug(f"Daily P&L updated: ${self.daily_pnl:,.2f}")
    
    def check_order(self, order: Order, account: AccountInfo, 
                   current_price: float) -> RiskCheckResult:
        """Perform pre-trade risk checks on an order"""
        # Check if daily drawdown limit reached
        if self.daily_start_equity:
            drawdown_pct = (self.daily_pnl / self.daily_start_equity) * 100
            if drawdown_pct < -self.daily_drawdown_limit:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Daily drawdown limit reached: {drawdown_pct:.2f}%"
                )
        
        # Check leverage
        margin_used = account.margin_used
        if order.side == OrderSide.BUY:
            required_margin = order.quantity * current_price
        else:
            required_margin = order.quantity * current_price * 0.5  # Short margin typically 50%
        
        total_margin = margin_used + required_margin
        if account.portfolio_value > 0:
            leverage = total_margin / account.portfolio_value
            if leverage > self.max_leverage:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Max leverage exceeded: {leverage:.2f}x > {self.max_leverage}x"
                )
        
        # Check position size limit
        position_value = order.quantity * current_price
        if account.portfolio_value > 0:
            position_pct = (position_value / account.portfolio_value) * 100
            if position_pct > self.max_position_pct:
                # Calculate max allowed quantity
                max_value = account.portfolio_value * (self.max_position_pct / 100)
                max_quantity = int(max_value / current_price)
                return RiskCheckResult(
                    approved=False,
                    reason=f"Position size limit exceeded: {position_pct:.2f}% > {self.max_position_pct}%",
                    max_quantity=max_quantity
                )
        
        # Check buying power
        if order.side == OrderSide.BUY:
            required_capital = order.quantity * current_price
            if required_capital > account.buying_power:
                max_quantity = int(account.buying_power / current_price)
                return RiskCheckResult(
                    approved=False,
                    reason=f"Insufficient buying power: ${required_capital:,.2f} > ${account.buying_power:,.2f}",
                    max_quantity=max_quantity
                )
        
        return RiskCheckResult(
            approved=True,
            reason="Order passes all risk checks"
        )
    
    def calculate_position_size(self, account: AccountInfo, current_price: float,
                               win_prob: float, payout_ratio: float) -> int:
        """Calculate optimal position size using Fractional Kelly Criterion"""
        try:
            # Kelly Criterion: f* = (p*b - q) / b
            # where p = win probability, b = payout ratio, q = 1-p
            q = 1 - win_prob
            kelly_fraction = (win_prob * payout_ratio - q) / payout_ratio
            
            # Apply conservative safety fraction
            adjusted_fraction = kelly_fraction * self.kelly_fraction
            
            # Ensure positive and bounded
            adjusted_fraction = max(0, min(adjusted_fraction, 0.25))
            
            # Calculate position value
            position_value = account.portfolio_value * adjusted_fraction
            
            # Calculate quantity
            quantity = int(position_value / current_price)
            
            # Ensure minimum size of 1
            quantity = max(1, quantity)
            
            # Check against position limit
            max_position_value = account.portfolio_value * (self.max_position_pct / 100)
            max_quantity = int(max_position_value / current_price)
            
            quantity = min(quantity, max_quantity)
            
            logger.info(f"Kelly sizing: {adjusted_fraction:.4f} -> {quantity} shares")
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            # Return conservative default
            return int((account.portfolio_value * 0.01) / current_price)
    
    def set_position_limit(self, symbol: str, max_quantity: int) -> None:
        """Set a custom position limit for a symbol"""
        self.position_limits[symbol] = max_quantity
        logger.info(f"Set position limit for {symbol}: {max_quantity}")
    
    def get_risk_status(self, account: AccountInfo) -> Dict[str, Any]:
        """Get current risk status"""
        leverage = account.margin_used / account.portfolio_value if account.portfolio_value > 0 else 0
        drawdown_pct = (self.daily_pnl / self.daily_start_equity * 100) if self.daily_start_equity else 0
        
        return {
            "daily_pnl": self.daily_pnl,
            "daily_drawdown_pct": drawdown_pct,
            "leverage": leverage,
            "max_leverage": self.max_leverage,
            "max_position_pct": self.max_position_pct,
            "buying_power": account.buying_power,
            "margin_used": account.margin_used,
            "margin_available": account.margin_available,
            "position_limits": self.position_limits
        }
    
    def reset_daily(self) -> None:
        """Reset daily statistics"""
        self.daily_pnl = 0.0
        self.daily_start_equity = None
        logger.info("Daily risk statistics reset")
