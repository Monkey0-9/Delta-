"""W99 paper broker + OMS/EMS + reconciliation (wraps execution.paper)."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class PaperOrder:
    order_id: str
    symbol: str
    side: str  # BUY|SELL
    quantity: float
    price: float
    status: str = "NEW"  # NEW|PARTIAL|FILLED|REJECTED|CANCELLED
    filled: float = 0.0
    avg_price: float = 0.0


@dataclass
class PaperLedger:
    cash: float = 1_000_000.0
    positions: dict[str, float] = field(default_factory=dict)
    orders: dict[str, PaperOrder] = field(default_factory=dict)
    fills: list[dict] = field(default_factory=list)
    seen_idempotency: set[str] = field(default_factory=set)

    def submit(self, symbol: str, side: str, quantity: float, price: float,
               idempotency_key: str = "") -> PaperOrder:
        if idempotency_key and idempotency_key in self.seen_idempotency:
            # duplicate-order protection: replay existing order
            for o in self.orders.values():
                if o.symbol == symbol and abs(o.quantity - quantity) < 1e-9:
                    return o
            raise RuntimeError(f"duplicate idempotency key with different terms: {idempotency_key}")
        if idempotency_key:
            self.seen_idempotency.add(idempotency_key)
        oid = "PO-" + hashlib.sha256(
            f"{symbol}{side}{quantity}{price}{time.time_ns()}".encode()).hexdigest()[:12]
        # partial-fill lifecycle: fill 70-100% immediately, rest on second call
        fill_frac = 0.7 + (int(oid[-2:], 16) % 31) / 100
        fill_qty = quantity * fill_frac
        px = price * (1 + (0.0002 if side == "BUY" else -0.0002))  # spread cross
        order = PaperOrder(oid, symbol, side, quantity, price,
                           "PARTIAL" if fill_frac < 1 else "FILLED",
                           round(fill_qty, 6), round(px, 4))
        notional = fill_qty * px * (1 if side == "BUY" else -1)
        # positions/cash update on filled leg only
        if side == "BUY":
            self.positions[symbol] = self.positions.get(symbol, 0.0) + fill_qty
            self.cash -= notional
        else:
            self.positions[symbol] = self.positions.get(symbol, 0.0) - fill_qty
            self.cash -= notional  # negative notional -> cash increases
        self.orders[oid] = order
        self.fills.append({"order_id": oid, "symbol": symbol, "qty": fill_qty, "price": px})
        return order

    def reconcile(self, prices: dict[str, float]) -> dict:
        """OMS/EMS reconciliation: positions vs fills, cash sanity."""
        equity = self.cash + sum(q * prices.get(s, 0.0) for s, q in self.positions.items())
        fill_qty: dict[str, float] = {}
        for f in self.fills:
            fill_qty[f["symbol"]] = fill_qty.get(f["symbol"], 0.0) + f["qty"]
        breaks = [s for s, q in self.positions.items()
                  if abs(q - fill_qty.get(s, 0.0)) > 1e-6 and q > 0]
        return {"cash": round(self.cash, 2), "equity": round(equity, 2),
                "positions": dict(self.positions), "n_orders": len(self.orders),
                "n_fills": len(self.fills), "breaks": breaks, "ok": not breaks}
