"""Stage-5 UI-4: evidence cards + consensus matrix + Why-drilldown (never bare sentiment)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    label: str
    value: float
    direction: str  # + (for) | - (against) | ~ (neutral)


@dataclass(frozen=True, slots=True)
class AnalysisCard:
    symbol: str
    signal: str
    confidence: float
    regime: str
    horizon: str
    evidence: tuple[EvidenceItem, ...]
    model: str
    oos_ic: float | None = None
    action: str = "REVIEW"


def render_card(card: AnalysisCard) -> str:
    lines = [f"{card.symbol}  Signal: {card.signal}  Confidence: {card.confidence:.0%}",
             f"Regime: {card.regime}  Horizon: {card.horizon}",
             "EVIDENCE"]
    for e in card.evidence:
        mark = "+" if e.direction == "+" else ("-" if e.direction == "-" else "~")
        lines.append(f"  [{mark}] {e.label} {e.value:+.2f}")
    lines.append(f"MODEL {card.model}  OOS IC: {card.oos_ic}  ACTION: {card.action}")
    return "\n".join(lines)


def consensus(votes: dict[str, str]) -> tuple[str, str]:
    """Alpha/Regime/News/Risk/Portfolio votes → (CONSENSUS, ACTION)."""
    vals = list(votes.values())
    if not vals:
        return ("NO_COVERAGE", "REVIEW")
    if all(v == vals[0] for v in vals):
        return (vals[0].upper(), "ELIGIBLE" if vals[0].lower() in ("buy", "bullish") else "REVIEW")
    bull = sum(1 for v in vals if v.lower() in ("buy", "bullish", "overweight"))
    bear = sum(1 for v in vals if v.lower() in ("sell", "bearish", "reduce", "underweight"))
    if bull and bear:
        return ("CONFLICTED", "REVIEW")
    return ("MIXED", "REVIEW")


__all__ = ["EvidenceItem", "AnalysisCard", "render_card", "consensus"]
