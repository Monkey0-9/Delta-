"""
Rich tables, order tickets, and markdown renderer
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import Dict, Any, List, Optional
from datetime import datetime


class DeltaFormatter:
    """Rich formatting for DELTA OS output"""
    
    def __init__(self):
        self.console = Console()
    
    def format_order_ticket(self, order_data: Dict[str, Any]) -> Panel:
        """Format an order ticket preview"""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("Ticker", order_data.get("symbol", "N/A"))
        table.add_row("Action", order_data.get("action", "N/A"))
        table.add_row("Order Type", order_data.get("order_type", "N/A"))
        table.add_row("Quantity", str(order_data.get("quantity", 0)))
        table.add_row("Limit Price", f"${order_data.get('limit_price', 0):.2f}")
        table.add_row("Stop Loss", f"${order_data.get('stop_loss', 0):.2f}")
        table.add_row("Take Profit", f"${order_data.get('take_profit', 0):.2f}")
        table.add_row("Risk/Reward", str(order_data.get("risk_reward", "N/A")))
        table.add_row("Portfolio Risk", f"{order_data.get('portfolio_risk', 0):.2f}%")
        
        title = f"PROPOSED EXECUTION - {order_data.get('symbol', 'UNKNOWN')}"
        return Panel(table, title=title, border_style="yellow")
    
    def format_quote(self, quote_data: Dict[str, Any]) -> Panel:
        """Format a quote display"""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Field", style="cyan", width=15)
        table.add_column("Value", style="white")
        
        table.add_row("Symbol", quote_data.get("symbol", "N/A"))
        table.add_row("Last", f"${quote_data.get('last', 0):.2f}")
        table.add_row("Bid", f"${quote_data.get('bid', 0):.2f}")
        table.add_row("Ask", f"${quote_data.get('ask', 0):.2f}")
        table.add_row("Spread", f"${quote_data.get('ask', 0) - quote_data.get('bid', 0):.2f}")
        table.add_row("Volume", f"{quote_data.get('volume', 0):,}")
        table.add_row("Change", f"{quote_data.get('change_pct', 0):.2f}%")
        
        title = f"QUOTE - {quote_data.get('symbol', 'UNKNOWN')}"
        return Panel(table, title=title, border_style="green")
    
    def format_portfolio_summary(self, portfolio_data: Dict[str, Any]) -> Panel:
        """Format portfolio summary"""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("Cash", f"${portfolio_data.get('cash', 0):,.2f}")
        table.add_row("Portfolio Value", f"${portfolio_data.get('portfolio_value', 0):,.2f}")
        table.add_row("Buying Power", f"${portfolio_data.get('buying_power', 0):,.2f}")
        table.add_row("Margin Used", f"${portfolio_data.get('margin_used', 0):,.2f}")
        table.add_row("Open Positions", str(portfolio_data.get('position_count', 0)))
        table.add_row("Day P&L", f"${portfolio_data.get('day_pnl', 0):,.2f}")
        
        return Panel(table, title="PORTFOLIO SUMMARY", border_style="blue")
    
    def format_position(self, position_data: Dict[str, Any]) -> Table:
        """Format a single position"""
        pnl_color = "green" if position_data.get('unrealized_pl', 0) >= 0 else "red"
        
        table = Table(show_header=True)
        table.add_column("Symbol", style="cyan")
        table.add_column("Side", style="white")
        table.add_column("Qty", style="white")
        table.add_column("Avg Price", style="white")
        table.add_column("Current", style="white")
        table.add_column("P&L", style=pnl_color)
        table.add_column("P&L %", style=pnl_color)
        
        table.add_row(
            position_data.get("symbol", "N/A"),
            position_data.get("side", "N/A"),
            str(position_data.get("quantity", 0)),
            f"${position_data.get('avg_entry_price', 0):.2f}",
            f"${position_data.get('current_price', 0):.2f}",
            f"${position_data.get('unrealized_pl', 0):,.2f}",
            f"{position_data.get('unrealized_pl_pct', 0):.2f}%"
        )
        
        return table
    
    def format_news_item(self, news_item: Dict[str, Any]) -> Table:
        """Format a news item"""
        sentiment = news_item.get('sentiment', 0)
        if sentiment > 0.2:
            sentiment_color = "green"
            sentiment_label = "BULLISH"
        elif sentiment < -0.2:
            sentiment_color = "red"
            sentiment_label = "BEARISH"
        else:
            sentiment_color = "white"
            sentiment_label = "NEUTRAL"
        
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Field", style="cyan", width=10)
        table.add_column("Value", style="white")
        
        table.add_row("Title", news_item.get('title', 'N/A')[:60])
        table.add_row("Source", news_item.get('source', 'N/A'))
        table.add_row("Sentiment", f"[{sentiment_color}]{sentiment_label}[/{sentiment_color}] ({sentiment:.2f})")
        table.add_row("Time", news_item.get('published_at', 'N/A'))
        
        return table
    
    def format_quant_metrics(self, metrics: Dict[str, Any]) -> Panel:
        """Format quantitative metrics"""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Value", style="white")
        
        table.add_row("VWAP", f"${metrics.get('vwap', 0):.2f}")
        table.add_row("VWAP Deviation", f"{metrics.get('vwap_deviation', 0):.2f}σ")
        table.add_row("Upper 2σ", f"${metrics.get('upper_2sigma', 0):.2f}")
        table.add_row("Lower 2σ", f"${metrics.get('lower_2sigma', 0):.2f}")
        table.add_row("ATR", f"${metrics.get('atr', 0):.2f}")
        table.add_row("Beta", f"{metrics.get('beta', 0):.2f}")
        table.add_row("RSI", f"{metrics.get('rsi', 0):.2f}")
        table.add_row("Volume Profile", metrics.get('volume_profile_signal', 'N/A'))
        
        return Panel(table, title=f"QUANT METRICS - {metrics.get('symbol', 'UNKNOWN')}", border_style="magenta")
    
    def format_macro_data(self, macro_data: Dict[str, Any]) -> Panel:
        """Format macro economic data"""
        table = Table(show_header=False, box=None, padding=0)
        table.add_column("Indicator", style="cyan", width=20)
        table.add_column("Value", style="white")
        table.add_column("Change", style="white")
        
        table.add_row("10Y-2Y Spread", f"{macro_data.get('yield_spread', 0):.2f}%", f"{macro_data.get('yield_spread_change', 0):.2f}%")
        table.add_row("Fed Funds Rate", f"{macro_data.get('fed_funds', 0):.2f}%", f"{macro_data.get('fed_funds_change', 0):.2f}%")
        table.add_row("Net Liquidity", f"${macro_data.get('net_liquidity', 0):,.0f}B", f"{macro_data.get('net_liquidity_change', 0):.2f}%")
        table.add_row("CPI", f"{macro_data.get('cpi', 0):.2f}", f"{macro_data.get('cpi_change', 0):.2f}%")
        table.add_row("Regime Score", f"{macro_data.get('regime_score', 0):.0f}", macro_data.get('regime_label', 'NEUTRAL'))
        
        return Panel(table, title="MACRO INTELLIGENCE", border_style="cyan")
    
    def format_error(self, error_message: str) -> Panel:
        """Format an error message"""
        return Panel(error_message, title="ERROR", border_style="red")
    
    def format_warning(self, warning_message: str) -> Panel:
        """Format a warning message"""
        return Panel(warning_message, title="WARNING", border_style="yellow")
    
    def format_success(self, success_message: str) -> Panel:
        """Format a success message"""
        return Panel(success_message, title="SUCCESS", border_style="green")
    
    def format_info(self, info_message: str) -> Panel:
        """Format an info message"""
        return Panel(info_message, title="INFO", border_style="blue")
    
    def format_markdown(self, markdown_text: str) -> None:
        """Format and display markdown text"""
        from rich.markdown import Markdown
        self.console.print(Markdown(markdown_text))
