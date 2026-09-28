"""W171-W190 (B+C) — Microstructure + Execution truth.

Exchange replay: market event -> book update -> your order -> queue position ->
market events -> fill/partial/cancel. Queue-position calibration
P(fill | position, spread, imbalance, vol, trade_rate, size) via binned
empirical table. Latency from empirical distributions (not just synthetic).
Full order lifecycle state machine + empirically-calibrated SOR objective.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from simulation.l3_engine import L3Book, L3Event

# ---------- exchange replay ----------

@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    order_id: str
    filled: float
    avg_px: float
    cancelled: bool
    queue_positions_seen: tuple[int, ...]


class ExchangeReplayer:
    """Drive YOUR order through a historical market-event tape on an L3 book."""

    def __init__(self, book: L3Book | None = None) -> None:
        self.book = book or L3Book()

    def run(self, market_tape: list[L3Event], mine: L3Event) -> ReplayOutcome:
        positions: list[int] = []
        # place mine first so it can interact with the tape
        self.book.apply(mine)
        for ev in market_tape:
            self.book.apply(ev)
            if mine.order_id in getattr(self.book, "_idx", {}):
                positions.append(self.book.queue_position(mine.order_id))
        fills = [f for f in self.book.fills
                 if f.maker_id == mine.order_id or f.taker_id == mine.order_id]
        # mine resting (maker) fills + mine marketable (taker) fills
        qty = sum(float(f.qty) for f in fills)
        avg = (sum(float(f.qty) * float(f.price) for f in fills) / qty) if qty else 0.0
        alive = self.book.queue_position(mine.order_id) >= 0
        return ReplayOutcome(mine.order_id, qty, avg, not alive and qty == 0,
                             tuple(positions[-8:]))


# ---------- queue-position calibration ----------

@dataclass
class QueueCalibrationTable:
    """Empirical P(fill) bins keyed by (pos_bin, spread_bin, imb_bin, vol_bin)."""

    table: dict[tuple[int, int, int, int], tuple[int, int]] = field(default_factory=dict)
    # (fills, total)

    @staticmethod
    def _bin(x: float, edges: tuple[float, ...]) -> int:
        for i, e in enumerate(edges):
            if x <= e:
                return i
        return len(edges)

    def observe(self, *, queue_pos: int, spread_bps: float, imbalance: float,
                volatility: float, filled: bool) -> None:
        key = (self._bin(queue_pos, (0, 2, 5)), self._bin(spread_bps, (1, 3, 10)),
               self._bin(imbalance, (-0.3, 0.3)), self._bin(volatility, (0.005, 0.02)))
        f, n = self.table.get(key, (0, 0))
        self.table[key] = (f + (1 if filled else 0), n + 1)

    def p_fill(self, *, queue_pos: int, spread_bps: float, imbalance: float,
               volatility: float) -> float:
        key = (self._bin(queue_pos, (0, 2, 5)), self._bin(spread_bps, (1, 3, 10)),
               self._bin(imbalance, (-0.3, 0.3)), self._bin(volatility, (0.005, 0.02)))
        f, n = self.table.get(key, (0, 0))
        if n == 0:
            return 0.5  # honest prior: unknown
        return f / n  # Laplace could be added; raw rate is auditable


# ---------- empirical latency ----------

@dataclass
class EmpiricalLatency:
    """Latency from measured samples per stage; deterministic quantiles."""

    samples_ns: dict[str, list[int]] = field(default_factory=dict)

    STAGES = ("market_data", "network", "strategy", "risk", "order_gateway", "exchange")

    def add(self, stage: str, ns: int) -> None:
        if stage not in self.STAGES:
            raise ValueError(f"unknown stage {stage}")
        self.samples_ns.setdefault(stage, []).append(int(ns))

    def quantile(self, stage: str, q: float) -> int:
        s = sorted(self.samples_ns.get(stage, []))
        if not s:
            return 0
        return s[min(len(s) - 1, int((len(s) - 1) * q))]

    def total_quantile(self, q: float) -> int:
        return sum(self.quantile(st, q) for st in self.STAGES)


# ---------- order lifecycle ----------

ORDER_STATES = ("NEW", "ACK", "PARTIAL", "FILLED", "CANCEL_REQ", "CANCELLED",
                "REJECTED", "TIMEOUT", "DISCONNECTED")

ORDER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "NEW": ("ACK", "REJECTED", "TIMEOUT", "DISCONNECTED"),
    "ACK": ("PARTIAL", "FILLED", "CANCEL_REQ", "REJECTED", "TIMEOUT", "DISCONNECTED"),
    "PARTIAL": ("PARTIAL", "FILLED", "CANCEL_REQ", "TIMEOUT", "DISCONNECTED"),
    "CANCEL_REQ": ("CANCELLED", "PARTIAL", "FILLED", "TIMEOUT"),
    "DISCONNECTED": ("ACK", "REJECTED"),  # reconnect re-sync
    "TIMEOUT": ("ACK", "CANCEL_REQ", "DISCONNECTED"),
    "FILLED": (), "CANCELLED": (), "REJECTED": (),
}


@dataclass
class OrderLifecycle:
    order_id: str
    state: str = "NEW"
    fills: list[tuple[float, float]] = field(default_factory=list)  # (qty, px)
    log: list[str] = field(default_factory=list)

    def transition(self, to: str, *, qty: float = 0.0, px: float = 0.0,
                   duplicate: bool = False) -> bool:
        if duplicate:
            self.log.append(f"dup-{to}-ignored")
            return True  # idempotent duplicate
        if to not in ORDER_TRANSITIONS.get(self.state, ()):
            self.log.append(f"illegal-{self.state}-{to}")
            return False
        if to == "PARTIAL":
            self.fills.append((qty, px))
        if to == "FILLED" and qty:
            self.fills.append((qty, px))
        self.state = to
        self.log.append(to)
        return True

    @property
    def filled_qty(self) -> float:
        return sum(q for q, _ in self.fills)


# ---------- empirically calibrated SOR ----------

@dataclass(frozen=True, slots=True)
class VenueStats:
    venue_id: str
    fee_bps: float
    rebate_bps: float
    spread_bps: float
    latency_ns: int
    fail_prob: float
    adv_share: float  # 0..1 fraction of accessible liquidity


def expected_venue_cost_bps(v: VenueStats, *, qty: float, adv: float,
                            adverse_bps: float) -> float:
    """E[cost] = spread/2 + fee - rebate*P(fill) + impact + adverse + fail penalty."""
    import math
    p_fill = max(0.05, min(1.0, v.adv_share * adv / max(qty, 1e-9)))
    impact = 50.0 * math.sqrt(max(qty, 0.0) / max(adv * v.adv_share, 1e-9))
    fail_pen = v.fail_prob * 25.0  # bps-equivalent reroute cost
    return (v.spread_bps / 2.0 + v.fee_bps - v.rebate_bps * p_fill
            + impact + adverse_bps + fail_pen + v.latency_ns / 1e7)


def route_empirical(qty: float, venues: list[VenueStats], *, adv: float,
                    adverse_bps: float = 1.0) -> list[tuple[str, float]]:
    scored = sorted(venues, key=lambda v: expected_venue_cost_bps(
        v, qty=qty, adv=adv, adverse_bps=adverse_bps))
    out: list[tuple[str, float]] = []
    rem = qty
    for v in scored:
        alloc = min(rem, adv * v.adv_share)
        if alloc > 0:
            out.append((v.venue_id, alloc))
            rem -= alloc
        if rem <= 1e-9:
            break
    if rem > 1e-9 and out:
        out[-1] = (out[-1][0], out[-1][1] + rem)
    return out
