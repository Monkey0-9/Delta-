"""Lightweight paper trading engine (DELTA OS).

Broker-dependency free: stdlib only. Fills at touch price adjusted for
slippage, tracks cash / positions / PnL with average-cost accounting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Union

__all__ = ["PaperEngine", "PaperOrder", "PaperFill"]

Number = Union[int, float, Decimal]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class PaperOrder:
    order_id: str
    symbol: str
    side: str  # "buy" | "sell"
    qty: float
    touch_price: float
    fill_price: float
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass(slots=True)
class PaperFill:
    order_id: str
    symbol: str
    side: str
    qty: float
    price: float
    timestamp: datetime = field(default_factory=_utcnow)


class PaperEngine:
    """Minimal cash-and-carry paper engine.

    Fill model: fill at touch price with symmetric slippage —
    buys lift (pay more), sells hit (receive less).
    """

    def __init__(
        self,
        initial_cash: Number = 1_000_000.0,
        slippage_bps: Number = 1.0,
    ) -> None:
        if float(initial_cash) <= 0:
            raise ValueError("initial_cash must be positive.")
        if float(slippage_bps) < 0:
            raise ValueError("slippage_bps must be non-negative.")
        self._initial_cash = float(initial_cash)
        self._cash = float(initial_cash)
        self._slippage_bps = float(slippage_bps)
        self._positions: Dict[str, float] = {}
        self._avg_cost: Dict[str, float] = {}
        self._marks: Dict[str, float] = {}
        self._realized = 0.0
        self._orders: List[PaperOrder] = []
        self._fills: List[PaperFill] = []
        self._seq = 0

    # -- properties --
    @property
    def cash(self) -> float:
        """Current cash balance."""
        return self._cash

    @property
    def positions(self) -> Dict[str, float]:
        """Current positions keyed by symbol."""
        return dict(self._positions)

    @property
    def fills(self) -> List[PaperFill]:
        """All fills in submission order."""
        return list(self._fills)

    # -- core API --
    def submit_order(
        self,
        symbol: str,
        side: str,
        qty: Number,
        price: Optional[Number] = None,
        touch_price: Optional[Number] = None,
    ) -> PaperFill:
        """Submit and immediately fill an order at touch +/- slippage.

        Args:
            symbol: Instrument symbol.
            side: "buy" or "sell" (case-insensitive).
            qty: Quantity (shares, must be positive).
            price: Limit/touch price; alias for touch_price.
            touch_price: Reference touch price to fill against.

        Returns:
            The resulting PaperFill.
        """
        s = side.lower()
        if s not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'.")
        q = float(qty)
        if q <= 0:
            raise ValueError("qty must be positive.")
        touch = touch_price if touch_price is not None else price
        if touch is None:
            touch = self._marks.get(symbol)
        if touch is None:
            raise ValueError(f"no price for {symbol!r}: pass price/touch_price or mark() first.")
        touch_f = float(touch)
        if touch_f <= 0:
            raise ValueError("touch price must be positive.")
        slip = self._slippage_bps / 10_000.0
        fill_px = touch_f * (1.0 + slip) if s == "buy" else touch_f * (1.0 - slip)
        notional = fill_px * q
        if s == "buy" and notional > self._cash + 1e-9:
            raise ValueError("insufficient cash.")
        # Cash + position + average-cost accounting.
        pos = self._positions.get(symbol, 0.0)
        avg = self._avg_cost.get(symbol, 0.0)
        if s == "buy":
            self._cash -= notional
            new_pos = pos + q
            self._avg_cost[symbol] = (avg * pos + fill_px * q) / new_pos if new_pos else 0.0
            self._positions[symbol] = new_pos
        else:
            self._cash += notional
            if pos > 0:  # closing/ flipping long -> realize
                closed = min(q, pos)
                self._realized += (fill_px - avg) * closed
            elif pos < 0:  # extending short: update short avg
                new_pos = pos - q
                self._avg_cost[symbol] = (avg * abs(pos) + fill_px * q) / abs(new_pos)
            else:  # opening short
                self._avg_cost[symbol] = fill_px
            new_pos = pos - q
            self._positions[symbol] = new_pos
            if abs(new_pos) < 1e-9:
                self._positions.pop(symbol, None)
                self._avg_cost.pop(symbol, None)
        self._marks[symbol] = touch_f
        self._seq += 1
        oid = f"paper-{self._seq}"
        fill = PaperFill(order_id=oid, symbol=symbol, side=s, qty=q, price=fill_px)
        self._orders.append(
            PaperOrder(order_id=oid, symbol=symbol, side=s, qty=q,
                       touch_price=touch_f, fill_price=fill_px, timestamp=fill.timestamp)
        )
        self._fills.append(fill)
        return fill

    def mark(self, symbol: str, price: Number) -> None:
        """Update the mark price used for unrealized PnL."""
        p = float(price)
        if p <= 0:
            raise ValueError("mark price must be positive.")
        self._marks[symbol] = p

    def unrealized(self) -> float:
        """Unrealized PnL vs average cost at current marks."""
        total = 0.0
        for sym, pos in self._positions.items():
            if abs(pos) < 1e-12:
                continue
            mark = self._marks.get(sym)
            if mark is None:
                continue
            total += (mark - self._avg_cost.get(sym, mark)) * pos
        return total

    def equity(self) -> float:
        """Cash plus marked position value."""
        total = self._cash
        for sym, pos in self._positions.items():
            mark = self._marks.get(sym, self._avg_cost.get(sym, 0.0))
            total += pos * mark
        return total

    def get_pnl(self) -> Dict[str, float]:
        """Return realized / unrealized / total PnL vs initial cash."""
        u = self.unrealized()
        total = self.equity() - self._initial_cash
        return {"realized": self._realized, "unrealized": u, "total": total}

    def reset(self) -> None:
        """Reset to initial cash with no positions."""
        self._cash = self._initial_cash
        self._positions.clear()
        self._avg_cost.clear()
        self._marks.clear()
        self._realized = 0.0
        self._orders.clear()
        self._fills.clear()
        self._seq = 0
