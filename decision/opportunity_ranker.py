"""FINAGENT opportunity ranker (Week 2).

Answers "which trade is best?" with BEST FOR WHAT? - never a universal
best stock. Produces a decision set across objectives plus a NO-TRADE slot.
"""
from __future__ import annotations

from dataclasses import dataclass

from quant.horizon.engines import ScoredOpportunity


@dataclass(frozen=True, slots=True)
class RankedSet:
    objective: str
    symbol: str
    reason: str
    decision: str
    risk_adjusted: float
    estimated_cost_bps: float


@dataclass(frozen=True, slots=True)
class DecisionSet:
    picks: tuple[RankedSet, ...]
    no_trade_reason: str = ""

    def render(self) -> str:
        lines = ["OPPORTUNITY ANALYSIS"]
        for p in self.picks:
            lines.append(f"- {p.objective}: {p.symbol} ({p.decision}) - {p.reason}")
        if self.no_trade_reason:
            lines.append(f"- No-trade: {self.no_trade_reason}")
        return "\n".join(lines)


def rank_best_for_what(opportunities: list[ScoredOpportunity]) -> DecisionSet:
    trades = [o for o in opportunities if o.decision == "TRADE"]
    if not trades:
        reason = "Current conditions do not justify additional exposure."
        if opportunities and all(o.decision == "WAIT" for o in opportunities):
            reason = "Signals present but uncertainty/cost/liquidity advise WAIT."
        return DecisionSet((), reason)
    by_ret = max(trades, key=lambda o: o.expected_return)
    by_ra = max(trades, key=lambda o: o.risk_adjusted)
    by_cost = min(trades, key=lambda o: o.estimated_cost_bps)
    by_conf = max(trades, key=lambda o: o.confidence)
    picks = (
        RankedSet("Highest expected return", by_ret.symbol, f"ER={by_ret.expected_return:+.3f} conf={by_ret.confidence:.2f}.", by_ret.decision, by_ret.risk_adjusted, by_ret.estimated_cost_bps),
        RankedSet("Best risk-adjusted", by_ra.symbol, f"ER/risk={by_ra.risk_adjusted:+.3f}.", by_ra.decision, by_ra.risk_adjusted, by_ra.estimated_cost_bps),
        RankedSet("Lowest execution cost", by_cost.symbol, f"Cost={by_cost.estimated_cost_bps:.1f}bps.", by_cost.decision, by_cost.risk_adjusted, by_cost.estimated_cost_bps),
        RankedSet("Highest conviction setup", by_conf.symbol, f"Confidence={by_conf.confidence:.2f}.", by_conf.decision, by_conf.risk_adjusted, by_conf.estimated_cost_bps),
    )
    # Deduplicate same symbol across objectives, keep first occurrence.
    seen: set[str] = set()
    uniq: list[RankedSet] = []
    for p in picks:
        if p.symbol not in seen:
            uniq.append(p)
            seen.add(p.symbol)
    return DecisionSet(tuple(uniq), "")


def explain_why(a: ScoredOpportunity, b: ScoredOpportunity) -> str:
    """Criterion-level comparison, not 'A is better'."""
    lines = [f"Why {a.symbol} vs {b.symbol}:"]
    lines.append(f"- Decision: {a.decision} vs {b.decision} (risk/cost/liquidity/confidence gates).")
    lines.append(f"- Expected return: {a.expected_return:+.4f} vs {b.expected_return:+.4f}.")
    lines.append(f"- Predicted risk: {a.predicted_risk:.4f} vs {b.predicted_risk:.4f}.")
    lines.append(f"- Risk-adjusted: {a.risk_adjusted:+.4f} vs {b.risk_adjusted:+.4f}.")
    lines.append(f"- Confidence: {a.confidence:.2f} vs {b.confidence:.2f}.")
    lines.append(f"- Cost: {a.estimated_cost_bps:.1f}bps vs {b.estimated_cost_bps:.1f}bps.")
    if a.decision != b.decision:
        lines.append(f"- Verdict differs because: {a.reason} || vs {b.reason}")
    else:
        lines.append("- Same verdict; rank differs on risk-adjusted return and cost.")
    return "\n".join(lines)
