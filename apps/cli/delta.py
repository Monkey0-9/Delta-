from __future__ import annotations

from datetime import datetime
from typing import Any

from trader.intent import FinanceIntent, Intent
from trader.runtime import TraderRuntime
from trader.terminal import DeltaTerminal
from trader.opencode_terminal import OpenCodeTerminal


class ExistingSystemBackend:
    """Thin adapter kept for compatibility with the terminal contract."""

    def __init__(self) -> None:
        self._runtime = TraderRuntime()

    def dispatch(self, request: FinanceIntent) -> str:
        # Handle conversational intents before delegating to runtime
        if request.intent == Intent.GREETING:
            return self._handle_greeting(request.raw_text)
        
        if request.intent == Intent.DATE_TIME:
            return self._handle_date_time()
        
        if request.intent == Intent.GENERAL_INFO:
            return self._handle_general_info()
        
        if request.intent == Intent.INVESTOR_PERSPECTIVE:
            return self._handle_investor_perspective(request.raw_text)
        
        if request.intent == Intent.MARKET_SENTIMENT:
            return self._handle_market_sentiment()
        
        if request.intent == Intent.STRATEGY_DISCUSSION:
            return self._handle_strategy_discussion()
        
        # Delegate to runtime for all other intents
        return self._runtime.dispatch(request)
    
    def _handle_greeting(self, raw_text: str) -> str:
        """Handle greeting messages with context-aware responses."""
        hour = datetime.now().hour
        time_context = ""
        
        if 5 <= hour < 12:
            time_context = "Good morning"
        elif 12 <= hour < 17:
            time_context = "Good afternoon"
        elif 17 <= hour < 21:
            time_context = "Good evening"
        else:
            time_context = "Good night"
        
        return (
            f"{time_context}! Welcome to DELTA.\n"
            "I'm your Finance Intelligence & Trading OS, specialized for:\n"
            "• Market analysis and trading\n"
            "• Portfolio management and risk control\n"
            "• Quantitative research and strategy\n"
            "• Opportunity scanning and execution\n"
            "\n"
            "I can help you with market updates, portfolio reviews, "
            "trade opportunities, research analysis, and more.\n"
            "Type 'help' to see available commands or ask me anything about finance."
        )
    
    def _handle_date_time(self) -> str:
        """Handle date/time queries with market context."""
        now = datetime.now()
        
        # Determine if markets are open (simplified - NYSE hours)
        hour = now.hour
        day = now.weekday()
        market_status = "CLOSED"
        
        if 0 <= day <= 4:  # Monday to Friday
            if 9 <= hour < 16:  # 9 AM to 4 PM EST
                market_status = "OPEN"
            elif 16 <= hour < 20:  # After hours
                market_status = "AFTER HOURS"
            elif 4 <= hour < 9:  # Pre-market
                market_status = "PRE-MARKET"
        
        return (
            f"Current Date & Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"Day of Week: {now.strftime('%A')}\n"
            f"Market Status: {market_status}\n"
            "\n"
            "Market Hours (EST):\n"
            "• Pre-market: 4:00 AM - 9:30 AM\n"
            "• Regular: 9:30 AM - 4:00 PM\n"
            "• After-hours: 4:00 PM - 8:00 PM\n"
            "\n"
            "Type 'market update' for current market conditions."
        )
    
    def _handle_general_info(self) -> str:
        """Handle general information queries about DELTA."""
        return (
            "I am DELTA - Finance Intelligence & Trading OS\n"
            "\n"
            "My Capabilities:\n"
            "• Market Analysis: Real-time market data, news, and regime detection\n"
            "• Portfolio Management: Risk assessment, position tracking, rebalancing\n"
            "• Trading Execution: Order routing, algorithm selection, trade automation\n"
            "• Quantitative Research: Backtesting, strategy development, signal generation\n"
            "• Risk Management: VaR, stress testing, position limits, compliance\n"
            "• Opportunity Scanning: Multi-horizon trade idea generation\n"
            "\n"
            "Architecture:\n"
            "• Deterministic execution controller\n"
            "• Risk firewall with mandate-based limits\n"
            "• Multi-broker connectivity\n"
            "• Digital twin simulation\n"
            "• Closed-loop learning system\n"
            "\n"
            "Safety First:\n"
            "• All trades require explicit authorization\n"
            "• Risk limits cannot be overridden\n"
            "• Comprehensive audit trails\n"
            "• Emergency stop capabilities\n"
            "\n"
            "Type 'help' to see available commands or ask me specific finance questions."
        )
    
    def _handle_investor_perspective(self, raw_text: str) -> str:
        """Handle investor perspective queries with dynamic quant runtime dispatch."""
        try:
            # W94: Dispatch to quant runtime for dynamic analysis instead of static strings
            return self._runtime.dispatch(FinanceIntent(
                intent=Intent.INVESTOR_PERSPECTIVE,
                raw_text=raw_text
            ))
        except Exception as exc:
            # Fallback to generic response if runtime unavailable
            return (
                f"INVESTOR PERSPECTIVE - Dynamic Analysis\n"
                f"\n"
                f"Runtime analysis unavailable: {exc}\n"
                f"\n"
                f"Please ensure quant runtime is operational for real-time perspective analysis."
            )
    
    def _handle_market_sentiment(self) -> str:
        """Handle market sentiment queries with dynamic quant runtime dispatch."""
        try:
            # W94: Dispatch to quant runtime for dynamic analysis instead of static strings
            return self._runtime.dispatch(FinanceIntent(
                intent=Intent.MARKET_SENTIMENT,
                raw_text="market sentiment"
            ))
        except Exception as exc:
            # Fallback to generic response if runtime unavailable
            return (
                f"MARKET SENTIMENT - Dynamic Analysis\n"
                f"\n"
                f"Runtime analysis unavailable: {exc}\n"
                f"\n"
                f"Please ensure quant runtime is operational for real-time sentiment analysis."
            )
    
    def _handle_strategy_discussion(self) -> str:
        """Handle strategy discussion with dynamic quant runtime dispatch."""
        try:
            # W94: Dispatch to quant runtime for dynamic analysis instead of static strings
            return self._runtime.dispatch(FinanceIntent(
                intent=Intent.STRATEGY_DISCUSSION,
                raw_text="strategy discussion"
            ))
        except Exception as exc:
            # Fallback to generic response if runtime unavailable
            return (
                f"STRATEGY DISCUSSION - Dynamic Analysis\n"
                f"\n"
                f"Runtime analysis unavailable: {exc}\n"
                f"\n"
                f"Please ensure quant runtime is operational for real-time strategy analysis."
            )


def main() -> None:
    """Single `delta` launcher: bare -> OpenCode-style chat; args -> typer subs."""
    import sys

    if len(sys.argv) > 1:
        from apps.cli.main import app

        app()
        return
    terminal = OpenCodeTerminal(ExistingSystemBackend())
    terminal.run()


if __name__ == "__main__":
    main()
