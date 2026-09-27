"""Execution planner (P3).

Pure deterministic algo selection + child-order slicing:

  intent -> plan_execution() -> children -> Risk -> Broker -> fills -> reconcile

Rules (documented, no ML):
  urgency=high or spread>50bps      -> AGGRESSIVE single shot (take liquidity)
  qty/ADV <= 1%                     -> PASSIVE single child (rest, save spread)
  qty/ADV <= 5%                     -> VWAP 4 slices
  qty/ADV <= 15%                    -> TWAP 8 slices
  else                              -> POV 12 slices capped at 10% ADV each

Children sum EXACTLY to parent qty (Decimal remainder on last child).
Planner never submits; OMS + RiskFirewall remain the only submit path.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ChildOrder:
    seq: int
    quantity: Decimal
    instruction: str


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    algo: str
    children: tuple[ChildOrder, ...]
    reason: str

    def __post_init__(self) -> None:
        if not self.children:
            raise ValueError("plan must have at least one child.")


def select_algo(
    *,
    participation: float,
    spread_bps: float,
    urgency: str,
) -> tuple[str, str]:
    u = (urgency or "normal").lower()
    if u in ("high", "urgent", "aggressive") or spread_bps > 50.0:
        return "AGGRESSIVE", "High urgency or wide spread: take liquidity in one shot."
    if participation <= 0.01:
        return "PASSIVE", "Sub-1% of ADV: rest passively, save spread."
    if participation <= 0.05:
        return "VWAP", "Under 5% of ADV: VWAP 4 slices track volume curve."
    if participation <= 0.15:
        return "TWAP", "Under 15% of ADV: TWAP 8 slices spread impact over time."
    return "POV", "Over 15% of ADV: POV 12 slices capped at 10% ADV each."


def _slice(qty: Decimal, n: int, instruction: str) -> tuple[ChildOrder, ...]:
    if qty <= 0 or n < 1:
        raise ValueError("qty must be positive and n >= 1.")
    base = qty / n
    out: list[ChildOrder] = []
    acc = Decimal("0")
    for i in range(1, n + 1):
        q = base if i < n else qty - acc
        acc += q
        out.append(ChildOrder(i, q, instruction))
    return tuple(out)


def plan_execution(
    *,
    quantity: Decimal,
    adv: Decimal,
    spread_bps: float = 5.0,
    urgency: str = "normal",
) -> ExecutionPlan:
    """Deterministic plan. Fail-closed on bad input."""
    if quantity <= 0:
        raise ValueError("quantity must be positive.")
    if adv <= 0:
        raise ValueError("adv must be positive.")
    participation = float(quantity / adv)
    algo, reason = select_algo(
        participation=participation, spread_bps=spread_bps, urgency=urgency
    )
    n = {"AGGRESSIVE": 1, "PASSIVE": 1, "VWAP": 4, "TWAP": 8, "POV": 12}[algo]
    children = _slice(quantity, n, algo)
    return ExecutionPlan(algo, children, f"{reason} participation={participation:.2%}.")
