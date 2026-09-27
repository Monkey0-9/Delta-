"""
Portfolio command handler
"""

from rich.console import Console
from rich.table import Table


class CommandPortfolio:
    """Handler for /portfolio command"""
    
    def __init__(self, console: Console, broker):
        self.console = console
        self.broker = broker
    
    def execute(self, args: list) -> None:
        """Execute portfolio command"""
        self.show_portfolio()
    
    async def show_portfolio(self) -> None:
        """Show portfolio information"""
        if not self.broker:
            self.console.print("[yellow]No broker connected[/yellow]")
            return
        
        # This would be async in the full implementation
        self.console.print("[yellow]Portfolio fetching requires async implementation[/yellow]")
        self.console.print("Will display:")
        self.console.print("  - Cash balance")
        self.console.print("  - Portfolio value")
        self.console.print("  - Buying power")
        self.console.print("  - Open positions")
        self.console.print("  - Unrealized P&L")
