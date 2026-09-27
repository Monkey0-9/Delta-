"""
Fuzzy slash command autocomplete and palette
"""

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class DeltaCommandCompleter(Completer):
    """Fuzzy command completer for DELTA OS slash commands"""
    
    def __init__(self):
        self.commands = {
            '/help': 'Show help message',
            '/model': 'Manage AI models (switch, list, info)',
            '/auth': 'Configure credentials (wizard, test, list)',
            '/broker': 'Broker connection (connect, status)',
            '/quote': 'Get real-time quote for ticker',
            '/news': 'Get latest news for ticker',
            '/macro': 'Macro economic data (yields, liquidity)',
            '/track': 'Manage watchlist (add, rm, list)',
            '/quant': 'Quantitative metrics (VWAP, ATR, Beta)',
            '/portfolio': 'View portfolio and positions',
            '/auto': 'Enable automation mode',
            '/manual': 'Enable manual mode',
            '/kill': 'Emergency kill switch',
            '/flatten': 'Liquidate positions (ticker or ALL)',
            '/clear': 'Clear screen',
            '/exit': 'Exit DELTA OS',
            '/quit': 'Exit DELTA OS',
        }
        
        # Subcommands for context-aware completion
        self.subcommands = {
            '/model': ['switch', 'list', 'info'],
            '/auth': ['wizard', 'test', 'list'],
            '/broker': ['connect', 'status', 'disconnect'],
            '/macro': ['yields', 'liquidity', 'inflation'],
            '/track': ['add', 'rm', 'list'],
        }
    
    def get_completions(self, document: Document, complete_event) -> List[Completion]:
        """Get completions for the current document"""
        text = document.text_before_cursor
        
        # Only complete if starting with /
        if not text.startswith('/'):
            return []
        
        words = text.split()
        
        # If just starting with /, show all commands
        if len(words) == 1 and text == '/':
            return [
                Completion(cmd, display=f"{cmd} - {desc}", display_meta="Command")
                for cmd, desc in self.commands.items()
            ]
        
        # If typing a command, show matching commands
        if len(words) == 1:
            prefix = words[0]
            return [
                Completion(cmd, display=f"{cmd} - {desc}", display_meta="Command")
                for cmd, desc in self.commands.items()
                if cmd.startswith(prefix)
            ]
        
        # If we have a command and potential subcommand
        if len(words) >= 2:
            command = words[0]
            if command in self.subcommands:
                # If typing subcommand
                if len(words) == 2:
                    prefix = words[1]
                    return [
                        Completion(subcmd, display=subcmd, display_meta="Subcommand")
                        for subcmd in self.subcommands[command]
                        if subcmd.startswith(prefix)
                    ]
        
        return []


class TickerCompleter(Completer):
    """Simple ticker completer for demo purposes"""
    
    def __init__(self):
        # Popular tickers for demo
        self.popular_tickers = [
            'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD',
            'INTC', 'NFLX', 'DIS', 'BA', 'JPM', 'V', 'WMT', 'PG'
        ]
    
    def get_completions(self, document: Document, complete_event) -> List[Completion]:
        """Get ticker completions"""
        text = document.text_before_cursor
        words = text.split()
        
        if not words:
            return []
        
        last_word = words[-1]
        
        # Only complete if the last word looks like it could be a ticker
        if last_word.isalpha() and len(last_word) <= 5:
            return [
                Completion(ticker, display=ticker, display_meta="Ticker")
                for ticker in self.popular_tickers
                if ticker.upper().startswith(last_word.upper())
            ]
        
        return []
