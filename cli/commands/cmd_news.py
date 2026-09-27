"""
News command handler
"""

from rich.console import Console
from rich.table import Table


class CommandNews:
    """Handler for /news command"""
    
    def __init__(self, console: Console, data_router):
        self.console = console
        self.data_router = data_router
    
    def execute(self, args: list) -> None:
        """Execute news command"""
        if not args:
            self.console.print("[red]Usage: /news <ticker>[/red]")
            return
        
        ticker = args[0].upper()
        self.console.print(f"[yellow]Fetching news for {ticker}...[/yellow]")
        self.console.print("[yellow]News fetching requires async implementation[/yellow]")
