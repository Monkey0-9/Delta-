"""
Track command handler
"""

from rich.console import Console


class CommandTrack:
    """Handler for /track command"""
    
    def __init__(self, console: Console):
        self.console = console
        self.watchlist = []  # Simple in-memory watchlist
    
    def execute(self, args: list) -> None:
        """Execute track command"""
        if not args or args[0].lower() == "list":
            self.list_watchlist()
        elif args[0].lower() == "add":
            if len(args) < 2:
                self.console.print("[red]Usage: /track add <ticker>[/red]")
                return
            self.add_to_watchlist(args[1])
        elif args[0].lower() == "rm":
            if len(args) < 2:
                self.console.print("[red]Usage: /track rm <ticker>[/red]")
                return
            self.remove_from_watchlist(args[1])
        else:
            self.console.print("[red]Usage: /track [list|add|rm <ticker>][/red]")
    
    def list_watchlist(self) -> None:
        """List watchlist"""
        if not self.watchlist:
            self.console.print("[yellow]Watchlist is empty[/yellow]")
            return
        
        from rich.table import Table
        table = Table(title="Watchlist", show_header=True)
        table.add_column("Ticker", style="cyan")
        table.add_column("Added", style="white")
        
        for item in self.watchlist:
            table.add_row(item["ticker"], item["added"])
        
        self.console.print(table)
    
    def add_to_watchlist(self, ticker: str) -> None:
        """Add ticker to watchlist"""
        from datetime import datetime
        ticker = ticker.upper()
        
        if any(item["ticker"] == ticker for item in self.watchlist):
            self.console.print(f"[yellow]{ticker} already in watchlist[/yellow]")
            return
        
        self.watchlist.append({
            "ticker": ticker,
            "added": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        self.console.print(f"[green]Added {ticker} to watchlist[/green]")
    
    def remove_from_watchlist(self, ticker: str) -> None:
        """Remove ticker from watchlist"""
        ticker = ticker.upper()
        original_count = len(self.watchlist)
        self.watchlist = [item for item in self.watchlist if item["ticker"] != ticker]
        
        if len(self.watchlist) < original_count:
            self.console.print(f"[green]Removed {ticker} from watchlist[/green]")
        else:
            self.console.print(f"[yellow]{ticker} not in watchlist[/yellow]")
