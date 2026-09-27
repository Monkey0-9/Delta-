"""W99/W111 paper broker + OMS/EMS + reconciliation.

Deterministic: order IDs derive from (sequence, seed, symbol, side, qty, price)
— no wall-clock, no time.time_ns(). Same seed + same inputs => same IDs, fills,
positions. Set seed per experiment for exact replay.
"""
from __future__ import annotations

import hashlib
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
    fee: float = 0.0


@dataclass
class PaperLedger:
    cash: float = 1_000_000.0
    positions: dict[str, float] = field(default_factory=dict)
    orders: dict[str, PaperOrder] = field(default_factory=dict)
    fills: list[dict] = field(default_factory=list)
    seen_idempotency: set[str] = field(default_factory=set)
    seed: int = 42
    fee_bps: float = 1.0
    _seq: int = 0

    def _order_id(self, symbol: str, side: str, quantity: float, price: float,
                  idempotency_key: str) -> str:
        self._seq += 1
        raw = f"{self.seed}:{self._seq}:{symbol}:{side}:{quantity}:{price}:{idempotency_key}"
        return "PO-" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

    def submit(self, symbol: str, side: str, quantity: float, price: float,
               idempotency_key: str = "") -> PaperOrder:
        if idempotency_key and idempotency_key in self.seen_idempotency:
            for o in self.orders.values():
                if o.symbol == symbol and abs(o.quantity - quantity) < 1e-9:
                    return o
            raise RuntimeError(f"duplicate idempotency key with different terms: {idempotency_key}")
        if idempotency_key:
            self.seen_idempotency.add(idempotency_key)
        oid = self._order_id(symbol, side, quantity, price, idempotency_key)
        fill_frac = 0.7 + (int(oid[-2:], 16) % 31) / 100
        fill_qty = quantity * fill_frac
        px = price * (1 + (0.0002 if side == "BUY" else -0.0002))  # spread cross
        fee = fill_qty * px * self.fee_bps / 1e4
        order = PaperOrder(oid, symbol, side, quantity, price,
                           "PARTIAL" if fill_frac < 1 else "FILLED",
                           round(fill_qty, 6), round(px, 4), round(fee, 2))
        notional = fill_qty * px * (1 if side == "BUY" else -1)
        if side == "BUY":
            self.positions[symbol] = self.positions.get(symbol, 0.0) + fill_qty
            self.cash -= (notional + fee)
        else:
            self.positions[symbol] = self.positions.get(symbol, 0.0) - fill_qty
            self.cash -= (notional - fee)  # negative notional -> cash increases, minus fee
        self.orders[oid] = order
        self.fills.append({"order_id": oid, "symbol": symbol, "side": side,
                           "qty": fill_qty, "price": px, "fee": fee,
                           "seq": self._seq, "seed": self.seed})
        return order

    def reconcile(self, prices: dict[str, float]) -> dict:
        """OMS/EMS/custodian-style reconciliation: positions vs fills, cash, fees."""
        equity = self.cash + sum(q * prices.get(s, 0.0) for s, q in self.positions.items())
        fill_qty: dict[str, float] = {}
        fees = 0.0
        for f in self.fills:
            sgn = 1 if f.get("side", "BUY") == "BUY" else -1
            fill_qty[f["symbol"]] = fill_qty.get(f["symbol"], 0.0) + sgn * f["qty"]
            fees += float(f.get("fee", 0.0))
        breaks = [s for s, q in self.positions.items()
                  if abs(q - fill_qty.get(s, 0.0)) > 1e-6]
        return {"cash": round(self.cash, 2), "equity": round(equity, 2),
                "positions": dict(self.positions), "n_orders": len(self.orders),
                "n_fills": len(self.fills), "total_fees": round(fees, 2),
                "breaks": breaks, "ok": not breaks, "seed": self.seed}
