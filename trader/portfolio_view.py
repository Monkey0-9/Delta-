"""FINAGENT portfolio view (Week 1).

Personal-investor snapshot: WHAT DO I OWN? WHAT RISK AM I TAKING?
WHAT CHANGED? Deterministic summary over PortfolioState, no trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from portfolio.state import PortfolioState


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    equity: Decimal
    cash: Decimal
    cash_pct: float
    n_positions: int
    top_weight: float
    concentration_hhi: float
    concentrated: bool
    flags: tuple[str, ...]

    def render(self) -> str:
        def bars(x: float) -> str:
            n = int(round(max(0.0, min(1.0, x)) * 10))
            return "#" * n + "-" * (10 - n)
        lines = [
            "CURRENT PORTFOLIO",
            f"Equity: {self.equity}  Cash: {self.cash} ({self.cash_pct:.0%})",
            f"Positions: {self.n_positions}",
            f"Concentration {bars(min(1.0, self.concentration_hhi * 4.0))} HHI={self.concentration_hhi:.4f} top={self.top_weight:.1%}",
        ]
        lines.extend(f"- {f}" for f in self.flags)
        if not self.flags:
            lines.append("- No concentration or cash warnings.")
        return "\n".join(lines)


def summarize(portfolio: PortfolioState) -> PortfolioSummary:
    equity = portfolio.equity
    cash_pct = float(portfolio.cash / equity) if equity > 0 else 1.0
    weights = [float(p.market_value / equity) for p in portfolio.positions] if equity > 0 else []
    top = max(weights) if weights else 0.0
    hhi = sum(w * w for w in weights)
    flags: list[str] = []
    if top > 0.35:
        flags.append(f"Concentrated: top position {top:.0%} exceeds 35% mandate intuition.")
    if hhi > 0.25 and len(weights) > 1:
        flags.append(f"High concentration: HHI {hhi:.3f}. Consider OPTION B (trim correlated) or OPTION C (diversify).")
    if cash_pct < 0.05 and len(weights) > 0:
        flags.append("Low cash buffer (<5%). New trades will increase turnover/cost pressure.")
    if not portfolio.positions:
        flags.append("Portfolio is empty/cash. Opportunity scan may propose first entries within mandate.")
    return PortfolioSummary(
        equity=equity,
        cash=portfolio.cash,
        cash_pct=max(0.0, min(1.0, cash_pct)),
        n_positions=len(portfolio.positions),
        top_weight=top,
        concentration_hhi=hhi,
        concentrated=bool(top > 0.35 or hhi > 0.25),
        flags=tuple(flags),
    )
