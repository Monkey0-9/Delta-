"""
Auth command handler
"""

from rich.console import Console


class CommandAuth:
    """Handler for /auth command"""
    
    def __init__(self, console: Console, vault):
        self.console = console
        self.vault = vault
    
    def execute(self, args: list) -> None:
        """Execute auth command"""
        if not args or args[0].lower() == "wizard":
            self.console.print("[yellow]Interactive auth wizard coming soon[/yellow]")
            self.console.print("Current auth features:")
            self.console.print("  - AES-256 encrypted vault")
            self.console.print("  - Credential storage")
            self.console.print("  - Provider management")
        elif args[0].lower() == "test":
            self.console.print("[yellow]Auth testing coming soon[/yellow]")
        elif args[0].lower() == "list":
            self.list_providers()
        else:
            self.console.print("[red]Usage: /auth [wizard|test|list][/red]")
    
    def list_providers(self) -> None:
        """List configured providers"""
        if not self.vault:
            self.console.print("[yellow]Vault not initialized[/yellow]")
            return
        
        if not self.vault.is_unlocked():
            self.console.print("[yellow]Vault is locked. Unlock with password first.[/yellow]")
            return
        
        providers = self.vault.list_providers()
        if providers:
            from rich.table import Table
            table = Table(title="Configured Providers", show_header=True)
            table.add_column("Provider", style="cyan")
            table.add_column("Account ID", style="white")
            table.add_column("Environment", style="white")
            table.add_column("Created", style="white")
            
            for provider in providers:
                table.add_row(
                    provider.get("provider", "N/A"),
                    provider.get("account_id", "N/A"),
                    provider.get("environment", "N/A"),
                    provider.get("created_at", "N/A")[:10]
                )
            
            self.console.print(table)
        else:
            self.console.print("[yellow]No providers configured[/yellow]")
