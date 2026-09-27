"""
Persistent bottom status bar with real-time information chips
"""

from prompt_toolkit.layout.containers import Window, Container
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import HTML
from typing import Optional
from datetime import datetime


class StatusBar:
    """Persistent status bar showing real-time system information"""
    
    def __init__(self):
        self.mode = "MANUAL"
        self.broker_status = "DISCONNECTED"
        self.model = "None"
        self.kill_switch = "ARMED"
        self.regime = "NEUTRAL"
        self.day_pnl = 0.0
        self.var_99 = 0.0
    
    def update_mode(self, mode: str) -> None:
        """Update execution mode"""
        self.mode = mode.upper()
    
    def update_broker_status(self, status: str) -> None:
        """Update broker connection status"""
        self.broker_status = status.upper()
    
    def update_model(self, model: str) -> None:
        """Update current model"""
        self.model = model
    
    def update_kill_switch(self, status: str) -> None:
        """Update kill switch status"""
        self.kill_switch = status.upper()
    
    def update_regime(self, regime: str) -> None:
        """Update macro regime"""
        self.regime = regime.upper()
    
    def update_day_pnl(self, pnl: float) -> None:
        """Update daily P&L"""
        self.day_pnl = pnl
    
    def update_var(self, var: float) -> None:
        """Update VaR"""
        self.var_99 = var
    
    def get_status_text(self) -> str:
        """Get formatted status bar text"""
        pnl_color = "green" if self.day_pnl >= 0 else "red"
        pnl_sign = "+" if self.day_pnl >= 0 else ""
        
        status = f"""
[bold]MODE:[/bold] [{self.mode}]{self.mode}[/{self.mode}] │
[bold]BROKER:[/bold] [{self.broker_status}]{self.broker_status}[/{self.broker_status}] │
[bold]MODEL:[/bold] {self.model} │
[bold]KILLSWITCH:[/bold] [{self.kill_switch}]{self.kill_switch}[/{self.kill_switch}] │
[bold]REGIME:[/bold] {self.regime} │
[bold]DAY PNL:[/bold] [{pnl_color}]{pnl_sign}${self.day_pnl:,.2f}[/{pnl_color}] │
[bold]VAR 99%:[/bold] {self.var_99:.2f}%
"""
        return status
    
    def get_container(self) -> Container:
        """Get the status bar container"""
        return Window(
            height=1,
            content=FormattedTextControl(
                lambda: HTML(self.get_status_text())
            ),
            style="class:status"
        )
    
    def to_dict(self) -> dict:
        """Get status as dictionary"""
        return {
            "mode": self.mode,
            "broker_status": self.broker_status,
            "model": self.model,
            "kill_switch": self.kill_switch,
            "regime": self.regime,
            "day_pnl": self.day_pnl,
            "var_99": self.var_99
        }
