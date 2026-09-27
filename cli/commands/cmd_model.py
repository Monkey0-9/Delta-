"""
Model command handler
"""

from rich.table import Table
from rich.console import Console


class CommandModel:
    """Handler for /model command"""
    
    def __init__(self, console: Console, model_router):
        self.console = console
        self.model_router = model_router
    
    def execute(self, args: list) -> None:
        """Execute model command"""
        if not args:
            self.show_usage()
            return
        
        action = args[0].lower()
        
        if action == "list":
            self.list_models()
        elif action == "switch":
            if len(args) < 2:
                self.console.print("[red]Usage: /model switch <model_name>[/red]")
                return
            self.switch_model(args[1])
        elif action == "info":
            if len(args) < 2:
                self.console.print("[red]Usage: /model info <model_name>[/red]")
                return
            self.show_model_info(args[1])
        else:
            self.console.print(f"[red]Unknown action: {action}[/red]")
            self.show_usage()
    
    def show_usage(self) -> None:
        """Show usage information"""
        self.console.print("""
[bold]/model[/bold] - Manage AI models

[cyan]Usage:[/cyan]
  /model list                    - List available models
  /model switch <name>           - Switch to a model
  /model info <name>             - Get model information
        """)
    
    def list_models(self) -> None:
        """List available models"""
        if not self.model_router:
            self.console.print("[yellow]Model router not initialized[/yellow]")
            return
        
        models = self.model_router.list_available_models()
        current_model = self.model_router.get_current_model()
        
        table = Table(title="Available Models", show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        
        for model in models:
            is_current = model == current_model
            status = "[CURRENT]" if is_current else "Available"
            table.add_row(model, status)
        
        self.console.print(table)
    
    def switch_model(self, model_name: str) -> None:
        """Switch to a different model"""
        if not self.model_router:
            self.console.print("[yellow]Model router not initialized[/yellow]")
            return
        
        # This would be async in the full implementation
        self.console.print(f"[yellow]Switching to model: {model_name}[/yellow]")
        self.console.print("[yellow]Model switching requires async implementation[/yellow]")
    
    def show_model_info(self, model_name: str) -> None:
        """Show information about a specific model"""
        if not self.model_router:
            self.console.print("[yellow]Model router not initialized[/yellow]")
            return
        
        info = self.model_router.get_model_info(model_name)
        if info:
            table = Table(title=f"Model Info: {model_name}", show_header=False)
            table.add_column("Field", style="cyan", width=20)
            table.add_column("Value", style="white")
            
            table.add_row("Model", info.get("model", "N/A"))
            table.add_row("Endpoint", info.get("endpoint", "N/A"))
            table.add_row("Max Context", str(info.get("capabilities", {}).get("max_context_tokens", "N/A")))
            table.add_row("Function Calling", str(info.get("capabilities", {}).get("supports_function_calling", False)))
            table.add_row("Streaming", str(info.get("capabilities", {}).get("supports_streaming", False)))
            table.add_row("Initialized", str(info.get("initialized", False)))
            
            self.console.print(table)
        else:
            self.console.print(f"[red]Model not found: {model_name}[/red]")
