"""
Macro command handler
"""

from rich.console import Console


class CommandMacro:
    """Handler for /macro command"""
    
    def __init__(self, console: Console, data_router):
        self.console = console
        self.data_router = data_router
    
    def execute(self, args: list) -> None:
        """Execute macro command"""
        if not args or args[0].lower() == "yields":
            self.console.print("[yellow]Macro yield data requires FRED API key[/yellow]")
            self.console.print("Configure FRED credentials with /auth wizard")
        elif args[0].lower() == "liquidity":
            self.console.print("[yellow]Net liquidity data requires FRED API key[/yellow]")
        else:
            self.console.print("[red]Usage: /macro [yields|liquidity][/red]")
