"""
Kill command handler
"""

from rich.console import Console


class CommandKill:
    """Handler for /kill command"""
    
    def __init__(self, console: Console, kill_switch):
        self.console = console
        self.kill_switch = kill_switch
    
    def execute(self, args: list) -> None:
        """Execute kill command"""
        if not self.kill_switch:
            self.console.print("[red]Kill switch not available[/red]")
            return
        
        self.console.print("[red]⚠ EMERGENCY KILL SWITCH TRIGGERED ⚠[/red]")
        self.console.print("[yellow]This will:[/yellow]")
        self.console.print("  1. Cancel all resting orders")
        self.console.print("  2. Lock the trading engine")
        self.console.print("  3. Optionally flatten all positions")
        
        confirm = self.console.input("[yellow]Confirm kill switch? [y/N]: [/yellow]")
        if confirm.lower() == 'y':
            self.console.print("[red]Executing kill switch...[/red]")
            self.console.print("[yellow]Kill switch execution requires async implementation[/yellow]")
        else:
            self.console.print("[yellow]Kill switch cancelled[/yellow]")
