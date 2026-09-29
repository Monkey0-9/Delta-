"""Paper trading orchestrator: strategy loop + risk hook (DELTA OS).

Stdlib only. Wraps PaperEngine so strategies can be stepped bar-by-bar
with an optional pre-trade risk check.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from .engine import PaperEngine, PaperFill

__all__ = ["PaperOrchestrator", "StrategyFn", "RiskCheckFn"]

StrategyFn = Callable[[Mapping[str, Any], PaperEngine], List[Mapping[str, Any]]]
RiskCheckFn = Callable[[Mapping[str, Any], PaperEngine], bool]


@dataclass(slots=True)
class _DefaultRisk:
    max_qty: float = 10_000.0
    max_notional: float = 1_000_000.0


class PaperOrchestrator:
    """Drive a PaperEngine through strategy steps with risk gating.

    Strategy protocol: fn(market_update, engine) -> iterable of order dicts
    with keys {symbol, side, qty, price?/touch_price?}. Risk protocol:
    fn(order, engine) -> True to allow, False to reject.
    """

    def __init__(
        self,
        engine: Optional[PaperEngine] = None,
        strategy: Optional[StrategyFn] = None,
        risk_check: Optional[RiskCheckFn] = None,
        max_qty: float = 10_000.0,
        max_notional: float = 1_000_000.0,
    ) -> None:
        self.engine = engine or PaperEngine()
        self._strategy = strategy
        self._risk_check = risk_check
        self._limits = _DefaultRisk(max_qty=max_qty, max_notional=max_notional)
        self.rejected: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []

    # -- wiring --
    def set_strategy(self, fn: StrategyFn) -> None:
        """Attach the strategy callback."""
        self._strategy = fn

    def set_risk_check(self, fn: RiskCheckFn) -> None:
        """Attach a custom risk-check hook (overrides default limits)."""
        self._risk_check = fn

    # -- risk --
    def default_risk_check(self, order: Mapping[str, Any], engine: PaperEngine) -> bool:
        """Reject orders breaching qty/notional/cash limits."""
        try:
            qty = float(order.get("qty", order.get("quantity", 0)))
        except (TypeError, ValueError):
            return False
        if qty <= 0 or qty > self._limits.max_qty:
            return False
        price = order.get("price", order.get("touch_price"))
        if price is not None:
            try:
                if abs(qty * float(price)) > self._limits.max_notional:
                    return False
            except (TypeError, ValueError):
                return False
        if str(order.get("side", "")).lower() == "buy" and price is not None:
            try:
                if qty * float(price) > engine.cash + 1e-9:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _check(self, order: Mapping[str, Any]) -> bool:
        hook = self._risk_check or self.default_risk_check
        return bool(hook(order, self.engine))

    # -- loop --
    def step(self, market_update: Mapping[str, Any]) -> Dict[str, Any]:
        """Run one strategy step: update marks, generate + filter + fill orders."""
        marks = market_update.get("marks") or market_update.get("prices") or {}
        if isinstance(marks, Mapping):
            for sym, px in marks.items():
                try:
                    self.engine.mark(str(sym), float(px))  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
        orders: Iterable[Mapping[str, Any]] = []
        if self._strategy is not None:
            result = self._strategy(dict(market_update), self.engine)
            orders = result or []
        fills: List[PaperFill] = []
        for od in orders:
            o = dict(od)
            if not self._check(o):
                self.rejected.append(o)
                continue
            try:
                fills.append(
                    self.engine.submit_order(
                        symbol=str(o["symbol"]),
                        side=str(o["side"]),
                        qty=float(o.get("qty", o.get("quantity"))),  # type: ignore[arg-type]
                        price=o.get("price", o.get("touch_price")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                self.rejected.append(o)
        record = {
            "market": dict(market_update),
            "fills": fills,
            "pnl": self.engine.get_pnl(),
            "equity": self.engine.equity(),
        }
        self.history.append(record)
        return record

    def run(self, updates: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        """Step through a sequence of market updates; return step records."""
        out: List[Dict[str, Any]] = []
        for u in updates:
            out.append(self.step(u))
        return out

    @property
    def pnl(self) -> Dict[str, float]:
        """Current engine PnL breakdown."""
        return self.engine.get_pnl()
