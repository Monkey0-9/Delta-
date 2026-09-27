from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from trader.intent import FinanceIntent, Intent
from trader.terminal import DeltaTerminal


class ExistingSystemBackend:
    """Adapter between the new terminal contract and the existing DELTA runtime.

    Keep the adapter tiny. Do not duplicate the agent, decision engine,
    broker layer, risk firewall, or quant engine here.
    """

    def dispatch(self, request: FinanceIntent) -> str:
        # Handle conversational intents
        if request.intent == Intent.GREETING:
            return self._handle_greeting(request.raw_text)
        
        if request.intent == Intent.DATE_TIME:
            return self._handle_date_time()
        
        if request.intent == Intent.GENERAL_INFO:
            return self._handle_general_info()
        
        # WAVE 2 replaces this with the existing TraderService /
        # Agent Runtime integration after its concrete API is bound.
        #
        # Deliberately fail closed instead of manufacturing a finance answer.
        if request.intent == Intent.TRADE_DECISION:
            return (
                "DELTA routing is active.\n"
                f"Horizon: {request.horizon.value}\n"
                f"Objective: {request.objective.value}\n"
                "\n"
                "The quantitative opportunity pipeline is the next "
                "runtime binding; no trade recommendation is fabricated."
            )

        return (
            "DELTA routing is active.\n"
            f"Intent: {request.intent.value}\n"
            f"Horizon: {request.horizon.value}\n"
        )
    
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


def main() -> None:
    terminal = DeltaTerminal(ExistingSystemBackend())
    terminal.run()


if __name__ == "__main__":
    main()
    