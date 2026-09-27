"""
Help command handler
"""

from rich.table import Table
from rich.console import Console


class CommandHelp:
    """Handler for /help command"""
    
    def __init__(self, console: Console):
        self.console = console
    
    def execute(self, args: list) -> None:
        """Execute help command"""
        if args:
            # Show help for specific command
            self.show_command_help(args[0])
        else:
            # Show general help
            self.show_general_help()
    
    def show_general_help(self) -> None:
        """Show general help message"""
        table = Table(title="DELTA OS Commands", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan", width=20)
        table.add_column("Description", style="white")
        
        commands_info = [
            ("/help [command]", "Show help for commands"),
            ("/model [list|switch]", "Manage AI models"),
            ("/auth [wizard]", "Configure credentials"),
            ("/broker [status]", "Broker connection status"),
            ("/quote <ticker>", "Get real-time quote"),
            ("/news <ticker>", "Get latest news"),
            ("/macro [yields]", "Macro economic data"),
            ("/track [add|rm|list]", "Manage watchlist"),
            ("/quant <ticker>", "Quantitative metrics"),
            ("/portfolio", "View portfolio"),
            ("/auto", "Enable automation mode"),
            ("/manual", "Enable manual mode"),
            ("/kill", "Emergency kill switch"),
            ("/flatten [ticker|ALL]", "Liquidate positions"),
            ("/clear", "Clear screen"),
            ("/exit", "Exit DELTA OS")
        ]
        
        for cmd, desc in commands_info:
            table.add_row(cmd, desc)
        
        self.console.print(table)
    
    def show_command_help(self, command: str) -> None:
        """Show help for specific command"""
        command_help = {
            "/model": """
            [bold]/model[/bold] - Manage AI models
            
            [cyan]Usage:[/cyan]
              /model list                    - List available models
              /model switch <name>           - Switch to a model
              /model info <name>             - Get model information
            
            [cyan]Available models:[/cyan]
              - local-qwen (Ollama local)
              - groq (Groq API)
              - huggingface (HuggingFace API)
            """,
            
            "/auth": """
            [bold]/auth[/bold] - Configure credentials
            
            [cyan]Usage:[/cyan]
              /auth wizard                   - Interactive credential setup
              /auth test <provider>          - Test provider connection
              /auth list                     - List configured providers
            
            [cyan]Supported providers:[/cyan]
              - Alpaca Markets
              - Interactive Brokers
              - FRED
              - Google Gemini
              - Anthropic Claude
              - OpenAI
            """,
            
            "/broker": """
            [bold]/broker[/bold] - Broker connection management
            
            [cyan]Usage:[/cyan]
              /broker status                 - Show broker status
              /broker connect <name>         - Connect to broker
              /broker disconnect             - Disconnect from broker
            """,
            
            "/kill": """
            [bold]/kill[/bold] - Emergency kill switch
            
            [cyan]Usage:[/cyan]
              /kill                          - Trigger kill switch
            
            [yellow]WARNING:[/yellow] This will cancel all orders and lock the trading engine.
            Use with caution in emergency situations only.
            """,
            
            "/flatten": """
            [bold]/flatten[/bold] - Liquidate positions
            
            [cyan]Usage:[/cyan]
              /flatten <ticker>              - Liquidate specific position
              /flatten ALL                   - Liquidate all positions
            
            [yellow]WARNING:[/yellow] This will immediately close positions at market prices.
            """,
        }
        
        help_text = command_help.get(command.lower(), f"No help available for command: {command}")
        self.console.print(help_text)
