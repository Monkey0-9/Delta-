"""
OpenCode-style interactive CLI for DELTA OS
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, FormattedTextControl
from prompt_toolkit.layout.containers import Container
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.widgets import Box, Label
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.application import create_app_session, run_in_terminal
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from delta.core.config import Config, ExecutionMode, Theme
from delta.core.vault import Vault
from delta.core.events import EventBus, EventType
from delta.core.anti_tilt import AntiTiltGovernor
from delta.models.router import ModelRouter
from delta.data.router import DataRouter
from delta.trading.broker_base import UniversalBrokerAdapter
from delta.trading.kill_switch import KillSwitch
from delta.trading.risk_governor import RiskGovernor

logger = logging.getLogger(__name__)


class DeltaCLI:
    """OpenCode-style interactive CLI for DELTA OS"""
    
    def __init__(self):
        self.config: Optional[Config] = None
        self.vault: Optional[Vault] = None
        self.event_bus = EventBus()
        self.model_router: Optional[ModelRouter] = None
        self.data_router: Optional[DataRouter] = None
        self.broker: Optional[UniversalBrokerAdapter] = None
        self.kill_switch: Optional[KillSwitch] = None
        self.risk_governor: Optional[RiskGovernor] = None
        self.anti_tilt: Optional[AntiTiltGovernor] = None
        
        self.console = Console()
        self.running = False
        
        # Command handlers
        self.commands = {
            '/help': self.cmd_help,
            '/model': self.cmd_model,
            '/auth': self.cmd_auth,
            '/broker': self.cmd_broker,
            '/news': self.cmd_news,
            '/macro': self.cmd_macro,
            '/track': self.cmd_track,
            '/quant': self.cmd_quant,
            '/portfolio': self.cmd_portfolio,
            '/auto': self.cmd_auto,
            '/manual': self.cmd_manual,
            '/kill': self.cmd_kill,
            '/flatten': self.cmd_flatten,
            '/clear': self.cmd_clear,
            '/exit': self.cmd_exit,
            '/quit': self.cmd_exit
        }
    
    async def initialize(self) -> bool:
        """Initialize all DELTA OS components"""
        try:
            # Load configuration
            self.config = Config.load()
            if not self.config.config_dir.exists():
                self.config = Config.init_default()
            
            # Initialize vault
            self.vault = Vault(self.config.vault_path)
            if self.vault.exists():
                # Will need password to unlock later
                pass
            
            # Initialize anti-tilt governor
            self.anti_tilt = AntiTiltGovernor(
                consecutive_loss_limit=self.config.consecutive_loss_limit,
                cooldown_minutes=self.config.cooldown_minutes
            )
            
            # Initialize model router
            self.model_router = ModelRouter(self.config)
            await self.model_router.initialize()
            
            # Initialize data router
            self.data_router = DataRouter(self.config)
            await self.data_router.initialize()
            
            # Initialize broker (paper engine by default)
            from delta.core.registry import broker_registry
            broker_class = broker_registry.get_adapter_class("paper")
            if broker_class:
                self.broker = broker_class({"name": "paper", "initial_balance": 100000.0})
                await self.broker.initialize()
                await self.broker.connect()
            
            # Initialize kill switch
            if self.broker:
                self.kill_switch = KillSwitch(self.broker, self.event_bus)
            
            # Initialize risk governor
            self.risk_governor = RiskGovernor(self.config.risk.__dict__)
            
            # Start event bus
            await self.event_bus.start()
            
            logger.info("DELTA OS initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize DELTA OS: {e}")
            return False
    
    def print_header(self) -> None:
        """Print the DELTA OS header"""
        mode = self.config.execution_mode.value.upper() if self.config else "MANUAL"
        broker = "Paper: ACTIVE" if self.broker and self.broker.is_connected() else "DISCONNECTED"
        model = self.model_router.get_current_model() if self.model_router else "None"
        killswitch = "ARMED" if self.kill_switch and self.kill_switch.is_armed() else "DISARMED"
        
        header = f"""
╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║ DELTA OS v2.0 │ MODE: [{mode}] │ BROKER: [{broker}] │ MODEL: [{model}] │ KILLSWITCH: [{killswitch}]     ║
║ WORKSPACE: [{self.config.workspace if self.config else 'DEFAULT'}] │ THEME: [{self.config.theme.value if self.config else 'default'}]                       ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝
"""
        self.console.print(header)
    
    def print_welcome(self) -> None:
        """Print welcome message"""
        welcome = """
Type <cmd>/</cmd> to view commands, or enter any ticker / finance research question.

Examples:
  <cmd>/quote NVDA</cmd>           Get real-time quote
  <cmd>/news AAPL</cmd>            Get latest news
  <cmd>/macro yields</cmd>         View yield curve
  <cmd>/quant TSLA</cmd>           View quantitative metrics
  <cmd>/model switch qwen-3.6</cmd> Switch AI model
  <cmd>/portfolio</cmd>             View portfolio
  <cmd>/help</cmd>                 View all commands
"""
        self.console.print(Panel(welcome, title="Welcome to DELTA OS", border_style="blue"))
    
    async def run_interactive(self) -> None:
        """Run the interactive CLI loop"""
        self.running = True
        
        self.print_header()
        self.print_welcome()
        
        while self.running:
            try:
                # Get user input
                user_input = self.console.input("[bold cyan]DELTA > [/bold cyan]")
                
                if not user_input.strip():
                    continue
                
                # Process command
                await self.process_input(user_input)
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use /exit to quit[/yellow]")
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                logger.error(f"CLI error: {e}")
    
    async def process_input(self, user_input: str) -> None:
        """Process user input"""
        user_input = user_input.strip()
        
        # Check if it's a slash command
        if user_input.startswith('/'):
            parts = user_input.split()
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if command in self.commands:
                await self.commands[command](args)
            else:
                self.console.print(f"[red]Unknown command: {command}[/red]")
                self.console.print("Type [cyan]/help[/cyan] for available commands")
        else:
            # Treat as natural language query
            await self.handle_natural_language(user_input)
    
    async def handle_natural_language(self, query: str) -> None:
        """Handle natural language queries (OpenCode-grade: greeting fast-path + shared core)."""
        # Greeting/help fast-path: never reject, never crash (shared w/ delta_os).
        try:
            from delta_os.llm_gateway import conversational_fallback
            fb = conversational_fallback(query)
            if fb is not None:
                self.console.print(Panel(fb, title="DELTA", border_style="green"))
                return
        except Exception:
            pass
        self.console.print(f"[dim]Processing query: {query}[/dim]")
        
        # Check if it looks like a ticker request
        if len(query.split()) == 1 and query.isalpha() and len(query) <= 5:
            # Assume it's a ticker
            await self.cmd_quote([query.upper()])
        else:
            # Send to AI model
            if self.model_router:
                from delta.models.base_provider import ModelMessage
                messages = [ModelMessage(role="user", content=query)]
                
                try:
                    response = await self.model_router.generate(messages)
                    self.console.print(Panel(response.content, title="AI Response", border_style="green"))
                except Exception as e:
                    self.console.print(f"[red]AI Error: {e}[/red]")
            else:
                self.console.print("[yellow]No AI model available. Configure models with /model[/yellow]")
    
    # Command handlers
    async def cmd_help(self, args: list) -> None:
        """Show help for commands"""
        table = Table(title="DELTA OS Commands", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan", width=20)
        table.add_column("Description", style="white")
        
        commands_info = [
            ("/help", "Show this help message"),
            ("/model [switch|list]", "Manage AI models"),
            ("/auth [wizard]", "Configure credentials"),
            ("/broker [status]", "Broker connection status"),
            ("/quote [ticker]", "Get real-time quote"),
            ("/news [ticker]", "Get latest news"),
            ("/macro [yields]", "Macro economic data"),
            ("/track [add|rm|list]", "Manage watchlist"),
            ("/quant [ticker]", "Quantitative metrics"),
            ("/portfolio", "View portfolio"),
            ("/auto", "Enable automation mode"),
            ("/manual", "Enable manual mode"),
            ("/kill", "Emergency kill switch"),
            ("/flatten [ticker]", "Liquidate positions"),
            ("/clear", "Clear screen"),
            ("/exit", "Exit DELTA OS")
        ]
        
        for cmd, desc in commands_info:
            table.add_row(cmd, desc)
        
        self.console.print(table)
    
    async def cmd_model(self, args: list) -> None:
        """Handle model commands"""
        if not args:
            await self.cmd_model([])
            return
        
        action = args[0].lower()
        
        if action == "list":
            models = self.model_router.list_available_models()
            table = Table(title="Available Models", show_header=True)
            table.add_column("Name", style="cyan")
            table.add_column("Status", style="green")
            
            for model in models:
                is_current = model == self.model_router.get_current_model()
                status = "[CURRENT]" if is_current else "Available"
                table.add_row(model, status)
            
            self.console.print(table)
        
        elif action == "switch":
            if len(args) < 2:
                self.console.print("[red]Usage: /model switch <model_name>[/red]")
                return
            
            model_name = args[1]
            success = await self.model_router.switch_model(model_name)
            if success:
                self.console.print(f"[green]Switched to model: {model_name}[/green]")
            else:
                self.console.print(f"[red]Failed to switch to model: {model_name}[/red]")
        
        else:
            self.console.print("[red]Usage: /model [list|switch <name>][/red]")
    
    async def cmd_auth(self, args: list) -> None:
        """Handle authentication commands"""
        if not args or args[0].lower() == "wizard":
            self.console.print("[yellow]Interactive auth wizard not yet implemented[/yellow]")
            self.console.print("Use vault API programmatically or set credentials in config")
        else:
            self.console.print("[red]Usage: /auth [wizard][/red]")
    
    async def cmd_broker(self, args: list) -> None:
        """Handle broker commands"""
        if not args or args[0].lower() == "status":
            if self.broker:
                account = await self.broker.get_account()
                if account:
                    table = Table(title="Broker Status", show_header=True)
                    table.add_column("Field", style="cyan")
                    table.add_column("Value", style="white")
                    
                    table.add_row("Broker", self.broker.get_broker_name())
                    table.add_row("Environment", self.broker.get_environment())
                    table.add_row("Connected", "Yes" if self.broker.is_connected() else "No")
                    table.add_row("Account ID", account.account_id)
                    table.add_row("Buying Power", f"${account.buying_power:,.2f}")
                    table.add_row("Portfolio Value", f"${account.portfolio_value:,.2f}")
                    
                    self.console.print(table)
            else:
                self.console.print("[yellow]No broker connected[/yellow]")
        else:
            self.console.print("[red]Usage: /broker [status][/red]")
    
    async def cmd_quote(self, args: list) -> None:
        """Get quote for a ticker"""
        if not args:
            self.console.print("[red]Usage: /quote <ticker>[/red]")
            return
        
        ticker = args[0].upper()
        if self.data_router:
            quote = await self.data_router.get_quote(ticker)
            if quote:
                table = Table(title=f"Quote: {ticker}", show_header=True)
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="white")
                
                table.add_row("Last", f"${quote.last:.2f}")
                table.add_row("Bid", f"${quote.bid:.2f}")
                table.add_row("Ask", f"${quote.ask:.2f}")
                table.add_row("Volume", f"{quote.volume:,}")
                table.add_row("Quality", quote.quality.value)
                
                self.console.print(table)
            else:
                self.console.print(f"[red]Failed to get quote for {ticker}[/red]")
        else:
            self.console.print("[yellow]Data router not initialized[/yellow]")
    
    async def cmd_news(self, args: list) -> None:
        """Get news for a ticker"""
        if not args:
            self.console.print("[red]Usage: /news <ticker>[/red]")
            return
        
        ticker = args[0].upper()
        if self.data_router:
            news = await self.data_router.get_news(ticker, limit=5)
            if news:
                table = Table(title=f"News: {ticker}", show_header=True)
                table.add_column("Title", style="white")
                table.add_column("Sentiment", style="cyan")
                table.add_column("Source", style="green")
                
                for item in news:
                    sentiment_color = "green" if item.sentiment > 0 else "red" if item.sentiment < 0 else "white"
                    table.add_row(item.title[:50], f"[{sentiment_color}]{item.sentiment:.2f}[/{sentiment_color}]", item.source)
                
                self.console.print(table)
            else:
                self.console.print(f"[yellow]No news found for {ticker}[/yellow]")
        else:
            self.console.print("[yellow]Data router not initialized[/yellow]")
    
    async def cmd_macro(self, args: list) -> None:
        """Handle macro commands"""
        if not args or args[0].lower() == "yields":
            self.console.print("[yellow]Macro yield data requires FRED API key[/yellow]")
            self.console.print("Configure FRED credentials with /auth wizard")
        else:
            self.console.print("[red]Usage: /macro [yields][/red]")
    
    async def cmd_track(self, args: list) -> None:
        """Handle watchlist commands"""
        if not args or args[0].lower() == "list":
            self.console.print("[yellow]Watchlist feature coming soon[/yellow]")
        else:
            self.console.print("[red]Usage: /track [list|add|rm <ticker>][/red]")
    
    async def cmd_quant(self, args: list) -> None:
        """Handle quantitative commands (shared delta_os core fallback)."""
        if not args:
            self.console.print("[red]Usage: /quant <ticker>[/red]")
            return
        
        ticker = args[0].upper()
        try:
            from delta_os.data_router import DataRouter
            from delta_os import quantkit as Q
            r = DataRouter().quote(ticker)
            last = float(r.frame["close"].iloc[-1])
            b = Q.vwap_bands(r.frame).iloc[-1]
            loc = Q.vwap_location(last, b)
            badge = f" {r.provenance.badge}" if r.provenance.badge else ""
            self.console.print(f"[green]{ticker} ${last:,.2f}{badge} VWAP {b['vwap']:,.2f} ({loc:+.1f}σ)[/green]")
            return
        except Exception:
            pass
        self.console.print(f"[yellow]Quantitative analysis for {ticker} coming soon[/yellow]")
        self.console.print("Will include: VWAP bands, ATR, Beta, Volume Profile")
    
    async def cmd_portfolio(self, args: list) -> None:
        """Show portfolio information"""
        if self.broker:
            account = await self.broker.get_account()
            positions = await self.broker.get_positions()
            
            if account:
                table = Table(title="Portfolio Summary", show_header=True)
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="white")
                
                table.add_row("Cash", f"${account.cash:,.2f}")
                table.add_row("Portfolio Value", f"${account.portfolio_value:,.2f}")
                table.add_row("Buying Power", f"${account.buying_power:,.2f}")
                table.add_row("Margin Used", f"${account.margin_used:,.2f}")
                table.add_row("Open Positions", str(len(positions)))
                
                self.console.print(table)
                
                if positions:
                    pos_table = Table(title="Open Positions", show_header=True)
                    pos_table.add_column("Symbol", style="cyan")
                    pos_table.add_column("Qty", style="white")
                    pos_table.add_column("Avg Price", style="white")
                    pos_table.add_column("Current", style="white")
                    pos_table.add_column("P&L", style="green")
                    
                    for pos in positions:
                        pl_color = "green" if pos.unrealized_pl >= 0 else "red"
                        pos_table.add_row(
                            pos.symbol,
                            str(pos.quantity),
                            f"${pos.avg_entry_price:.2f}",
                            f"${pos.current_price:.2f}",
                            f"[{pl_color}]{pos.unrealized_pl:,.2f}[/{pl_color}]"
                        )
                    
                    self.console.print(pos_table)
            else:
                self.console.print("[yellow]No account information available[/yellow]")
        else:
            self.console.print("[yellow]No broker connected[/yellow]")
    
    async def cmd_auto(self, args: list) -> None:
        """Enable automation mode"""
        if self.config:
            self.config.execution_mode = ExecutionMode.AUTOMATION
            self.console.print("[green]Automation mode enabled[/green]")
            self.console.print("[yellow]Strategy will execute autonomously within risk limits[/yellow]")
        else:
            self.console.print("[red]Configuration not loaded[/red]")
    
    async def cmd_manual(self, args: list) -> None:
        """Enable manual mode"""
        if self.config:
            self.config.execution_mode = ExecutionMode.MANUAL
            self.console.print("[green]Manual mode enabled[/green]")
            self.console.print("[yellow]All trades require explicit confirmation[/yellow]")
        else:
            self.console.print("[red]Configuration not loaded[/red]")
    
    async def cmd_kill(self, args: list) -> None:
        """Trigger emergency kill switch"""
        if self.kill_switch:
            self.console.print("[red]⚠ EMERGENCY KILL SWITCH TRIGGERED ⚠[/red]")
            
            confirm = self.console.input("[yellow]Confirm kill switch? [y/N]: [/yellow]")
            if confirm.lower() == 'y':
                results = await self.kill_switch.trigger()
                self.console.print(f"[green]Kill switch executed[/green]")
                self.console.print(f"Cancelled orders: {results.get('layer_1', {}).get('cancelled_orders', 0)}")
            else:
                self.console.print("[yellow]Kill switch cancelled[/yellow]")
        else:
            self.console.print("[red]Kill switch not available[/red]")
    
    async def cmd_flatten(self, args: list) -> None:
        """Flatten positions"""
        if not args:
            self.console.print("[red]Usage: /flatten [ticker|ALL][/red]")
            return
        
        target = args[0].upper()
        
        if target == "ALL":
            if self.kill_switch:
                self.console.print("[red]⚠ FLATTENING ALL POSITIONS ⚠[/red]")
                confirm = self.console.input("[yellow]Confirm flatten ALL? [y/N]: [/yellow]")
                if confirm.lower() == 'y':
                    count = await self.kill_switch.flatten_positions_only()
                    self.console.print(f"[green]Flattened {count} positions[/green]")
                else:
                    self.console.print("[yellow]Flatten cancelled[/yellow]")
            else:
                self.console.print("[red]Kill switch not available[/red]")
        else:
            self.console.print(f"[yellow]Flattening {target} coming soon[/yellow]")
    
    async def cmd_clear(self, args: list) -> None:
        """Clear screen"""
        self.console.clear()
        self.print_header()
    
    async def cmd_exit(self, args: list) -> None:
        """Exit DELTA OS"""
        self.console.print("[yellow]Shutting down DELTA OS...[/yellow]")
        self.running = False
        
        # Cleanup
        if self.event_bus:
            await self.event_bus.stop()
        if self.broker:
            await self.broker.disconnect()
        
        self.console.print("[green]DELTA OS shutdown complete[/green]")


async def main():
    """Main entry point"""
    cli = DeltaCLI()
    
    if not await cli.initialize():
        print("Failed to initialize DELTA OS")
        sys.exit(1)
    
    await cli.run_interactive()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
        sys.exit(0)
