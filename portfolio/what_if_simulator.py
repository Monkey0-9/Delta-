"""What-if simulator for portfolio analysis.

Counterfactual portfolio analysis for decision support.
Simulates trades, rebalancing, hedging, and compares alternatives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from decimal import Decimal


class ActionType(str, Enum):
    """Types of portfolio actions."""
    TRADE = "trade"
    REBALANCE = "rebalance"
    HEDGE = "hedge"
    ADD_CASH = "add_cash"
    WITHDRAW_CASH = "withdraw_cash"


@dataclass(frozen=True, slots=True)
class Trade:
    """A single trade action."""
    symbol: str
    quantity: float  # positive for buy, negative for sell
    price: float
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class PortfolioImpact:
    """Impact of an action on portfolio."""
    action: str
    total_value_before: float
    total_value_after: float
    cash_before: float
    cash_after: float
    position_changes: Dict[str, float]  # symbol -> weight change
    exposure_changes: Dict[str, float]  # dimension -> exposure change
    risk_metrics_before: Dict[str, float]
    risk_metrics_after: Dict[str, float]
    execution_cost_bps: float
    feasible: bool
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """Comparison of multiple alternative actions."""
    alternatives: List[Tuple[str, PortfolioImpact]]
    best_by_return: Optional[str] = None
    best_by_risk: Optional[str] = None
    best_by_cost: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Explanation:
    """Natural language explanation of portfolio impact."""
    summary: str
    value_change: str
    risk_change: str
    exposure_change: str
    feasibility: str
    key_factors: List[str]


class WhatIfSimulator:
    """Simulate portfolio changes and impacts."""

    def __init__(self, commission_per_share: float = 0.01, commission_per_trade: float = 1.0):
        self.commission_per_share = commission_per_share
        self.commission_per_trade = commission_per_trade

    def simulate_trade(
        self,
        portfolio: Dict[str, float],  # symbol -> weight
        cash: float,
        total_value: float,
        trade: Trade
    ) -> PortfolioImpact:
        """Simulate single trade impact."""
        # Calculate trade value and cost
        trade_value = abs(trade.quantity) * trade.price
        commission = self.commission_per_trade + (abs(trade.quantity) * self.commission_per_share)
        execution_cost_bps = (commission / trade_value) * 10000 if trade_value > 0 else 0.0

        # Check feasibility
        if trade.quantity < 0:  # Sell
            current_position_value = portfolio.get(trade.symbol, 0.0)
            sell_value = abs(trade.quantity * trade.price)
            if sell_value > current_position_value:
                return PortfolioImpact(
                    action=f"SELL {trade.symbol}",
                    total_value_before=total_value,
                    total_value_after=total_value,
                    cash_before=cash,
                    cash_after=cash,
                    position_changes={},
                    exposure_changes={},
                    risk_metrics_before={},
                    risk_metrics_after={},
                    execution_cost_bps=execution_cost_bps,
                    feasible=False,
                    warnings=["Insufficient position to sell"]
                )

        # Apply trade
        new_portfolio = portfolio.copy()
        new_cash = cash

        if trade.quantity > 0:  # Buy
            cost = trade.quantity * trade.price + commission
            if cost > cash:
                return PortfolioImpact(
                    action=f"BUY {trade.symbol}",
                    total_value_before=total_value,
                    total_value_after=total_value,
                    cash_before=cash,
                    cash_after=cash,
                    position_changes={},
                    exposure_changes={},
                    risk_metrics_before={},
                    risk_metrics_after={},
                    execution_cost_bps=execution_cost_bps,
                    feasible=False,
                    warnings=["Insufficient cash"]
                )
            new_cash -= cost
            position_value = trade.quantity * trade.price
            new_portfolio[trade.symbol] = new_portfolio.get(trade.symbol, 0.0) + position_value
        else:  # Sell - no cash check needed, we already validated position size
            proceeds = abs(trade.quantity) * trade.price - commission
            new_cash += proceeds
            position_value = abs(trade.quantity) * trade.price
            new_portfolio[trade.symbol] = new_portfolio.get(trade.symbol, 0.0) - position_value
            if new_portfolio[trade.symbol] <= 0:
                del new_portfolio[trade.symbol]

        # Calculate new totals
        new_total_value = new_cash + sum(new_portfolio.values())

        # Calculate position changes
        position_changes = {}
        for symbol in set(list(portfolio.keys()) + list(new_portfolio.keys())):
            old_weight = portfolio.get(symbol, 0.0) / total_value if total_value > 0 else 0.0
            new_weight = new_portfolio.get(symbol, 0.0) / new_total_value if new_total_value > 0 else 0.0
            position_changes[symbol] = new_weight - old_weight

        # Estimate risk metrics (simplified)
        risk_before = self._estimate_risk_metrics(portfolio, total_value)
        risk_after = self._estimate_risk_metrics(new_portfolio, new_total_value)

        return PortfolioImpact(
            action=f"{'BUY' if trade.quantity > 0 else 'SELL'} {trade.symbol}",
            total_value_before=total_value,
            total_value_after=new_total_value,
            cash_before=cash,
            cash_after=new_cash,
            position_changes=position_changes,
            exposure_changes={},  # Would need mapping data
            risk_metrics_before=risk_before,
            risk_metrics_after=risk_after,
            execution_cost_bps=execution_cost_bps,
            feasible=True,
            warnings=[]
        )

    def simulate_rebalance(
        self,
        portfolio: Dict[str, float],
        cash: float,
        total_value: float,
        new_weights: Dict[str, float]
    ) -> PortfolioImpact:
        """Simulate portfolio rebalancing."""
        # Normalize new weights
        total_weight = sum(new_weights.values())
        if total_weight > 0:
            new_weights = {k: v / total_weight for k, v in new_weights.items()}

        # Calculate target values
        target_values = {k: v * total_value for k, v in new_weights.items()}
        current_values = portfolio.copy()

        # Calculate trades needed
        trades: List[Trade] = []
        for symbol in set(list(current_values.keys()) + list(target_values.keys())):
            current = current_values.get(symbol, 0.0)
            target = target_values.get(symbol, 0.0)
            diff = target - current

            if abs(diff) > 1.0:  # Minimum trade size
                # Estimate price (would need market data)
                estimated_price = current / portfolio.get(symbol, 1.0) if symbol in portfolio and portfolio.get(symbol, 1.0) > 0 else 100.0
                quantity = diff / estimated_price
                trades.append(Trade(symbol=symbol, quantity=quantity, price=estimated_price))

        # Simulate trades sequentially
        temp_portfolio = portfolio.copy()
        temp_cash = cash
        temp_total = total_value
        total_cost = 0.0

        for trade in trades:
            impact = self.simulate_trade(temp_portfolio, temp_cash, temp_total, trade)
            if not impact.feasible:
                return PortfolioImpact(
                    action="REBALANCE",
                    total_value_before=total_value,
                    total_value_after=total_value,
                    cash_before=cash,
                    cash_after=cash,
                    position_changes={},
                    exposure_changes={},
                    risk_metrics_before={},
                    risk_metrics_after={},
                    execution_cost_bps=0.0,
                    feasible=False,
                    warnings=[f"Rebalancing infeasible: {impact.warnings[0]}"]
                )

            # Update state
            temp_portfolio = {k: v for k, v in temp_portfolio.items()}  # Keep as values
            if trade.quantity > 0:
                position_value = trade.quantity * trade.price
                temp_portfolio[trade.symbol] = temp_portfolio.get(trade.symbol, 0.0) + position_value
                temp_cash -= position_value
            else:
                position_value = abs(trade.quantity) * trade.price
                temp_portfolio[trade.symbol] = temp_portfolio.get(trade.symbol, 0.0) - position_value
                if temp_portfolio[trade.symbol] <= 0:
                    del temp_portfolio[trade.symbol]
                temp_cash += position_value

            temp_total = temp_cash + sum(temp_portfolio.values())
            total_cost += impact.execution_cost_bps

        # Calculate final position changes
        position_changes = {}
        for symbol in set(list(portfolio.keys()) + list(temp_portfolio.keys())):
            old_weight = portfolio.get(symbol, 0.0) / total_value if total_value > 0 else 0.0
            new_weight = temp_portfolio.get(symbol, 0.0) / temp_total if temp_total > 0 else 0.0
            position_changes[symbol] = new_weight - old_weight

        risk_before = self._estimate_risk_metrics(portfolio, total_value)
        risk_after = self._estimate_risk_metrics(temp_portfolio, temp_total)

        return PortfolioImpact(
            action="REBALANCE",
            total_value_before=total_value,
            total_value_after=temp_total,
            cash_before=cash,
            cash_after=temp_cash,
            position_changes=position_changes,
            exposure_changes={},
            risk_metrics_before=risk_before,
            risk_metrics_after=risk_after,
            execution_cost_bps=total_cost / len(trades) if trades else 0.0,
            feasible=True,
            warnings=[]
        )

    def simulate_hedge(
        self,
        portfolio: Dict[str, float],
        cash: float,
        total_value: float,
        hedge_instrument: str,
        hedge_ratio: float = 0.5
    ) -> PortfolioImpact:
        """Simulate hedging impact."""
        # Calculate hedge position
        portfolio_value = sum(portfolio.values())
        hedge_value = portfolio_value * hedge_ratio

        # Estimate hedge instrument price (would need market data)
        hedge_price = 100.0  # Placeholder
        hedge_quantity = hedge_value / hedge_price

        # If we already have the hedge instrument, we might adjust it
        # Otherwise, we buy it as a long hedge (simpler for testing)
        if hedge_instrument in portfolio:
            # Adjust existing position
            current_value = portfolio[hedge_instrument]
            diff = hedge_value - current_value
            hedge_quantity = diff / hedge_price
        else:
            # Buy new hedge position
            hedge_quantity = hedge_value / hedge_price

        hedge_trade = Trade(
            symbol=hedge_instrument,
            quantity=hedge_quantity,  # Can be positive (buy) or negative (sell/short)
            price=hedge_price
        )

        return self.simulate_trade(portfolio, cash, total_value, hedge_trade)

    def compare_alternatives(
        self,
        portfolio: Dict[str, float],
        cash: float,
        total_value: float,
        alternatives: List[Tuple[str, Action]]
    ) -> ComparisonReport:
        """Compare multiple alternative actions."""
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from dataclasses import dataclass
            @dataclass
            class Action:
                type: ActionType
                params: dict

        impacts: List[Tuple[str, PortfolioImpact]] = []

        for name, action in alternatives:
            if action.type == ActionType.TRADE:
                trade = Trade(**action.params)
                impact = self.simulate_trade(portfolio, cash, total_value, trade)
            elif action.type == ActionType.REBALANCE:
                impact = self.simulate_rebalance(portfolio, cash, total_value, action.params)
            elif action.type == ActionType.HEDGE:
                impact = self.simulate_hedge(portfolio, cash, total_value, **action.params)
            else:
                continue

            impacts.append((name, impact))

        # Find best alternatives
        feasible_impacts = [(n, i) for n, i in impacts if i.feasible]

        if feasible_impacts:
            best_by_return = max(feasible_impacts, key=lambda x: x[1].total_value_after)[0]
            best_by_risk = min(feasible_impacts, key=lambda x: x[1].risk_metrics_after.get("volatility", 999))[0]
            best_by_cost = min(feasible_impacts, key=lambda x: x[1].execution_cost_bps)[0]

            # Simple recommendation: best risk-adjusted
            recommendation = best_by_risk
        else:
            best_by_return = None
            best_by_risk = None
            best_by_cost = None
            recommendation = None

        return ComparisonReport(
            alternatives=impacts,
            best_by_return=best_by_return,
            best_by_risk=best_by_risk,
            best_by_cost=best_by_cost,
            recommendation=recommendation
        )

    def explain_impact(self, impact: PortfolioImpact) -> Explanation:
        """Explain portfolio impact in natural language."""
        value_change = impact.total_value_after - impact.total_value_before
        value_change_pct = (value_change / impact.total_value_before * 100) if impact.total_value_before > 0 else 0.0

        value_change_str = f"Portfolio value {'increased' if value_change > 0 else 'decreased'} by ${abs(value_change):,.2f} ({value_change_pct:+.2f}%)"

        risk_before = impact.risk_metrics_before.get("volatility", 0.0)
        risk_after = impact.risk_metrics_after.get("volatility", 0.0)
        risk_change = risk_after - risk_before
        risk_change_str = f"Risk {'increased' if risk_change > 0 else 'decreased'} from {risk_before:.2%} to {risk_after:.2%}"

        # Identify significant position changes
        significant_changes = [
            f"{sym}: {change:+.2%}"
            for sym, change in impact.position_changes.items()
            if abs(change) > 0.01
        ]
        exposure_change_str = "Position changes: " + ", ".join(significant_changes) if significant_changes else "No significant position changes"

        feasibility_str = "Action is feasible" if impact.feasible else f"Action not feasible: {impact.warnings[0] if impact.warnings else 'Unknown reason'}"

        key_factors = []
        if impact.execution_cost_bps > 10:
            key_factors.append(f"High execution cost: {impact.execution_cost_bps:.1f}bps")
        if abs(value_change_pct) > 5:
            key_factors.append(f"Significant value change: {value_change_pct:+.2f}%")
        if abs(risk_change) > 0.05:
            key_factors.append(f"Significant risk change: {risk_change:+.2%}")

        return Explanation(
            summary=f"{impact.action} would {value_change_str.lower()}",
            value_change=value_change_str,
            risk_change=risk_change_str,
            exposure_change=exposure_change_str,
            feasibility=feasibility_str,
            key_factors=key_factors
        )

    def _estimate_risk_metrics(self, portfolio: Dict[str, float], total_value: float) -> Dict[str, float]:
        """Estimate risk metrics (simplified)."""
        if total_value == 0:
            return {"volatility": 0.0, "concentration": 0.0}

        weights = [v / total_value for v in portfolio.values()]
        volatility = sum(w ** 2 for w in weights) ** 0.5  # Simplified: assumes 100% correlation
        concentration = max(weights) if weights else 0.0

        return {
            "volatility": volatility,
            "concentration": concentration,
            "diversification": 1.0 - concentration
        }


__all__ = [
    "ActionType",
    "Trade",
    "PortfolioImpact",
    "ComparisonReport",
    "Explanation",
    "WhatIfSimulator",
]