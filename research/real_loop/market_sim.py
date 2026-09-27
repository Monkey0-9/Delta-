"""W111 event-driven market simulator on the native limit order book.

Deterministic: seed -> identical books, latencies, fills. Every event carries
(seq, event_ns, type) so runs replay bit-identically.

Microstructure source (labeled, never market truth): resting liquidity is
SYNTHESIZED from daily-bar volatility (spread/vol-calibrated ladder) because
no L1/L2 feed is configured. When a real book feed lands, replace
build_book_from_bar() — the engine interface does not change.

Latency model: deterministic per-order delay = base_ns + size_penalty, drawn
from a seeded RNG stream. Orders cross only after their latency elapses
(event-queue ordered by (arrival_ns, seq)).
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from decimal import Decimal

SIM_VERSION = "sim-v1"
TICK = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class SimFill:
    seq: int
    event_ns: int
    buy_id: str
    sell_id: str
    price: Decimal
    quantity: Decimal
    fee: Decimal


@dataclass
class SimEngine:
    seed: int = 7
    latency_base_ns: int = 50_000  # 50us venue latency
    latency_per_unit_ns: int = 100
    fee_bps: Decimal = Decimal("1.0")
    cash: Decimal = Decimal("1000000")
    position: Decimal = Decimal("0")
    _matcher = None
    _pending: list = field(default_factory=list)  # heap of (arrival_ns, seq, order)
    _fills: list = field(default_factory=list)
    _seq: int = 0
    _ns: int = 0
    _rng_state: int = 0

    def __post_init__(self) -> None:
        try:
            from native.lob import NativeMatcher

            self._matcher = NativeMatcher()
            self._native = True
        except Exception:
            from execution.matching.engine import PriceTimeMatcher

            self._matcher = PriceTimeMatcher()
            self._native = False
        self._rng_state = self.seed & 0xFFFFFFFF or 1
        self._counter = itertools.count()

    # -- deterministic RNG (xorshift32, no global state) --
    def _rand(self) -> float:
        x = self._rng_state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self._rng_state = x
        return x / 0xFFFFFFFF

    def close(self) -> None:
        try:
            self._matcher.close()
        except Exception:
            pass

    # -- book construction (SYNTHETIC microstructure, labeled) --
    def build_book_from_bar(self, mid: Decimal, vol_20d: float, book_levels: int = 10,
                            lot: Decimal = Decimal("100")) -> None:
        """Seed resting ladder: spread ~ vol-scaled, depth decaying. Synthetic.

        Refresh semantics: the previous bar's ladder is cancelled first, so no
        stale quote can ever trade in a later bar (stale liquidity = time
        travel). User orders are never touched.
        """
        import math

        if not math.isfinite(float(mid)) or not math.isfinite(vol_20d):
            raise ValueError("build_book_from_bar needs finite mid and vol (no NaN book).")
        for oid in getattr(self, "_mm_ids", ()):
            try:
                self._matcher.cancel(oid)
            except Exception:
                pass
        self._mm_ids: list[str] = []
        spread = max(TICK, mid * Decimal(str(vol_20d)) / Decimal("20"))
        half = spread / 2
        for i in range(1, book_levels + 1):
            q = lot * int(max(1, 8 * math.exp(-0.5 * i) + self._rand() * 2))
            for side, px in (("sell", mid + half + TICK * (i - 1)),
                             ("buy", mid - half - TICK * (i - 1))):
                oid = f"mk-{side}-{self._seq}-{i}"
                self._mm_ids.append(oid)
                self._matcher.add(oid, side, px, q)

    # -- order entry with deterministic latency --
    def submit(self, order_id: str, side: str, price: Decimal | None,
               quantity: Decimal) -> int:
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy|sell.")
        if quantity <= 0:
            raise ValueError("quantity must be positive.")
        if price is not None:
            import math

            if not math.isfinite(float(price)) or price <= 0:
                raise ValueError("limit price must be finite and positive.")
        self._seq += 1
        jitter = int(self._rand() * 20_000)  # 0-20us deterministic jitter
        arrival = self._ns + self.latency_base_ns + int(quantity) * self.latency_per_unit_ns + jitter
        tag = f"me-{order_id}"
        self._user_ids: list[str] = getattr(self, "_user_ids", [])
        self._user_ids.append(tag)
        self._user_raw: set[str] = getattr(self, "_user_raw", set())
        self._user_raw.add(order_id)
        heapq.heappush(self._pending, (arrival, next(self._counter),
                                       (order_id, side, price, quantity)))
        return arrival

    def cancel_user_orders(self) -> int:
        """Cancel all resting user orders (good-for-day semantics). Returns count."""
        n = 0
        for oid in getattr(self, "_user_ids", ()):
            try:
                n += bool(self._matcher.cancel(oid))
            except Exception:
                pass
        self._user_ids = []
        # drop queued (not yet arrived) user orders too — a cancelled order never arrives
        raw = getattr(self, "_user_raw", set())
        before = len(self._pending)
        self._pending = [e for e in self._pending if e[2][0] not in raw]
        heapq.heapify(self._pending)
        self._user_raw = set()
        return n + (before - len(self._pending))

    def _settle(self, fills: list, now_ns: int) -> None:
        for f in fills:
            self._seq += 1
            notional = f.price * f.quantity
            fee = notional * self.fee_bps / Decimal("10000")
            mine = f.buy_id.startswith("me-") or f.sell_id.startswith("me-")
            if mine:
                if f.buy_id.startswith("me-"):
                    self.position += f.quantity
                    self.cash -= notional + fee
                else:
                    self.position -= f.quantity
                    self.cash += notional - fee
            self._fills.append(SimFill(self._seq, now_ns, f.buy_id, f.sell_id,
                                       f.price, f.quantity, fee if mine else Decimal("0")))

    def step_until(self, target_ns: int, last_px: Decimal) -> list[SimFill]:
        """Advance event clock, crossing due orders. Market orders use last_px
        as a +inf/-inf limit (buy at +20% / sell at -20% collar, labeled)."""
        out: list[SimFill] = []
        while self._pending and self._pending[0][0] <= target_ns:
            arrival, _, (oid, side, price, qty) = heapq.heappop(self._pending)
            self._ns = max(self._ns, arrival)
            tag = f"me-{oid}"
            if price is None:  # market order -> collared limit
                price = last_px * Decimal("1.2") if side == "buy" else last_px * Decimal("0.8")
            n0 = len(self._fills)
            if self._native:
                self._settle(self._matcher.add(tag, side, price, qty), self._ns)
            else:
                self._settle(self._matcher.add(tag, side, price, qty), self._ns)
            out.extend(self._fills[n0:])
        self._ns = max(self._ns, target_ns)
        return out

    @property
    def fills(self) -> list[SimFill]:
        return list(self._fills)

    def mark(self, last_px: Decimal) -> dict:
        equity = self.cash + self.position * last_px
        return {"cash": self.cash, "position": self.position,
                "equity": equity, "n_fills": len(self._fills),
                "engine": "native" if self._native else "python-fallback",
                "sim_version": SIM_VERSION,
                "microstructure": "synthetic-ladder-NOT-market-data"}
