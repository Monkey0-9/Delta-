"""
Auto command handler
"""

from rich.console import Console


class CommandAuto:
    """Handler for /auto command"""
    
    def __init__(self, console: Console, config):
        self.console = console
        self.config = config
    
    def execute(self, args: list) -> None:
        """Execute auto command"""
        if not args or args[0].lower() == "on":
            self.enable_automation()
        elif args[0].lower() == "off":
            self.disable_automation()
        elif args[0].lower() == "status":
            self.show_status()
        else:
            self.console.print("[red]Usage: /auto [on|off|status][/red]")
    
    def enable_automation(self) -> None:
        """Enable automation mode"""
        if self.config:
            from delta.core.config import ExecutionMode
            self.config.execution_mode = ExecutionMode.AUTOMATION
            self.console.print("[green]Automation mode enabled[/green]")
            self.console.print("[yellow]Strategy will execute autonomously within risk limits[/yellow]")
            self.console.print("  - Max position: 5% of portfolio")
            self.console.print("  - Max leverage: 1.5x")
            self.console.print("  - Daily circuit breaker: 2% drawdown")
        else:
            self.console.print("[red]Configuration not loaded[/red]")
    
    def disable_automation(self) -> None:
        """Disable automation mode"""
        if self.config:
            from delta.core.config import ExecutionMode
            self.config.execution_mode = ExecutionMode.MANUAL
            self.console.print("[green]Manual mode enabled[/green]")
            self.console.print("[yellow]All trades require explicit confirmation[/yellow]")
        else:
            self.console.print("[red]Configuration not loaded[/red]")
    
    def show_status(self) -> None:
        """Show automation status"""
        if self.config:
            mode = self.config.execution_mode.value.upper()
            self.console.print(f"[cyan]Current mode: {mode}[/cyan]")
            
            if self.config.execution_mode.value == "automation":
                self.console.print("[yellow]Risk limits:[/yellow]")
                self.console.print(f"  - Max position: {self.config.risk.max_position_pct}%")
                self.console.print(f"  - Max leverage: {self.config.risk.max_leverage}x")
                self.console.print(f"  - Daily drawdown limit: {self.config.risk.daily_drawdown_limit}%")
        else:
            self.console.print("[red]Configuration not loaded[/red]")
