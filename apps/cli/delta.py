from __future__ import annotations

from datetime import datetime
from typing import Any

from trader.intent import FinanceIntent, Intent
from trader.runtime import TraderRuntime
from trader.terminal import DeltaTerminal


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
        """Handle investor perspective queries with sophisticated quant insight."""
        return (
            "INVESTOR PERSPECTIVE - Quant Research View\n"
            "\n"
            "As a sophisticated investor, your mindset should focus on:\n"
            "\n"
            "1. RISK-ADJUSTED RETURNS\n"
            "   • Target Sharpe ratio > 1.5 for equity portfolios\n"
            "   • Maximum drawdown tolerance: 15-20% annually\n"
            "   • Position sizing: Kelly Criterion with 25% fractional Kelly\n"
            "\n"
            "2. PORTFOLIO CONSTRUCTION\n"
            "   • Core-satellite approach: 60% core beta, 40% alpha seeking\n"
            "   • Diversification across: geographies, sectors, factors, time horizons\n"
            "   • Rebalance quarterly or when drift > 5%\n"
            "\n"
            "3. WEALTH PRESERVATION\n"
            "   • Capital preservation as primary objective\n"
            "   • Inflation-hedging through real assets and TIPS\n"
            "   • Liquidity buffer: 6-12 months of expenses\n"
            "\n"
            "4. PSYCHOLOGICAL DISCIPLINE\n"
            "   • Remove emotion from investment decisions\n"
            "   • Follow systematic rules, not gut feelings\n"
            "   • Accept uncertainty as inherent to markets\n"
            "\n"
            "5. LONG-TERM COMPOUNDING\n"
            "   • Focus on process over outcomes\n"
            "   • Avoid market timing and overtrading\n"
            "   • Let winners run, cut losses systematically\n"
            "\n"
            "DELTA helps you implement these principles through:\n"
            "• Quantitative signal generation\n"
            "• Risk limit enforcement\n"
            "• Systematic execution\n"
            "• Performance attribution\n"
            "\n"
            "Ask about specific strategies or portfolio analysis."
        )
    
    def _handle_market_sentiment(self) -> str:
        """Handle market sentiment queries with macro analysis."""
        return (
            "MARKET SENTIMENT ANALYSIS\n"
            "\n"
            "Current Market Assessment:\n"
            "\n"
            "MACRO INDICATORS:\n"
            "• Interest Rate Environment: Monitor Fed policy and yield curve\n"
            "• Inflation Trends: CPI/PCE data and real interest rates\n"
            "• GDP Growth: Leading indicators and recession probability\n"
            "• Corporate Earnings: Forward estimates and revision trends\n"
            "\n"
            "SENTIMENT METRICS:\n"
            "• VIX (Volatility Index): Fear gauge and market stress\n"
            "• Put/Call Ratio: Options positioning sentiment\n"
            "• Margin Debt: Leverage and risk appetite\n"
            "• Fund Flows: EPFR data showing institutional positioning\n"
            "\n"
            "TECHNICAL REGIME:\n"
            "• Trend Analysis: Moving averages and momentum\n"
            "• Market Breadth: Advance/decline ratios\n"
            "• Sector Rotation: Relative strength analysis\n"
            "• Liquidity Conditions: TED spread and funding stress\n"
            "\n"
            "QUANT SIGNALS:\n"
            "• Factor Exposure: Value, Momentum, Quality, Low Volatility\n"
            "• Cross-asset Correlations: Risk-on vs risk-off regimes\n"
            "• Carry Trade Dynamics: Funding currency strength\n"
            "\n"
            "DELTA provides real-time sentiment analysis through:\n"
            "• Multi-factor scoring models\n"
            "• Regime detection algorithms\n"
            "• Risk budget optimization\n"
            "\n"
            "Type 'market update' for current conditions or 'analyze [symbol]' for specific analysis."
        )
    
    def _handle_strategy_discussion(self) -> str:
        """Handle strategy discussion with quant methodology."""
        return (
            "INVESTMENT STRATEGY FRAMEWORK\n"
            "\n"
            "QUANTITATIVE APPROACH TO STRATEGY:\n"
            "\n"
            "1. STRATEGY TAXONOMY\n"
            "   • Trend Following: Moving average crossovers, breakout systems\n"
            "   • Mean Reversion: Statistical arbitrage, pairs trading\n"
            "   • Factor Investing: Value, momentum, quality, low volatility\n"
            "   • Carry Trading: Currency, commodity, fixed income carry\n"
            "   • Machine Learning: Random forests, neural networks, ensemble methods\n"
            "\n"
            "2. BACKTESTING METHODOLOGY\n"
            "   • Out-of-sample validation: Walk-forward analysis\n"
            "   • Transaction cost modeling: Realistic slippage and commission\n"
            "   • Survivorship bias correction: Include delisted securities\n"
            "   • Regime analysis: Performance across different market conditions\n"
            "\n"
            "3. RISK MANAGEMENT\n"
            "   • Position sizing: Volatility targeting and risk parity\n"
            "   • Stop-loss design: ATR-based, volatility-adjusted\n"
            "   • Correlation monitoring: Dynamic correlation clustering\n"
            "   • Portfolio optimization: Mean-variance, risk parity, hierarchical\n"
            "\n"
            "4. EXECUTION ALGORITHMS\n"
            "   • VWAP: Volume-weighted average price execution\n"
            "   • TWAP: Time-weighted average price execution\n"
            "   • Implementation shortfall: Balancing market impact vs timing risk\n"
            "   • Smart order routing: Multi-venue optimization\n"
            "\n"
            "5. PERFORMANCE EVALUATION\n"
            "   • Sharpe Ratio: Risk-adjusted return metric\n"
            "   • Sortino Ratio: Downside risk-adjusted return\n"
            "   • Maximum Drawdown: Peak-to-trough decline\n"
            "   • Information Ratio: Active return vs tracking error\n"
            "\n"
            "DELTA implements these methodologies through:\n"
            "• Systematic backtesting engine\n"
            "• Real-time risk monitoring\n"
            "• Algorithmic execution\n"
            "• Performance attribution\n"
            "\n"
            "Ask about specific strategies or request analysis for your portfolio."
        )


def main() -> None:
    terminal = DeltaTerminal(ExistingSystemBackend())
    terminal.run()


if __name__ == "__main__":
    main()
