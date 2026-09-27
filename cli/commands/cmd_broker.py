"""
Broker command handler
"""

from rich.console import Console
from rich.table import Table


class CommandBroker:
    """Handler for /broker command"""
    
    def __init__(self, console: Console, broker):
        self.console = console
        self.broker = broker
    
    def execute(self, args: list) -> None:
        """Execute broker command"""
        if not args or args[0].lower() == "status":
            self.show_status()
        elif args[0].lower() == "connect":
            self.console.print("[yellow]Broker connection coming soon[/yellow]")
        elif args[0].lower() == "disconnect":
            self.console.print("[yellow]Broker disconnection coming soon[/yellow]")
        else:
            self.console.print("[red]Usage: /broker [status|connect|disconnect][/red]")
    
    def show_status(self) -> None:
        """Show broker status"""
        if not self.broker:
            self.console.print("[yellow]No broker connected[/yellow]")
            return
        
        table = Table(title="Broker Status", show_header=True)
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("Broker", self.broker.get_broker_name())
        table.add_row("Environment", self.broker.get_environment())
        table.add_row("Connected", "Yes" if self.broker.is_connected() else "No")
        table.add_row("Initialized", "Yes" if self.broker.is_initialized() else "No")
        
        self.console.print(table)
