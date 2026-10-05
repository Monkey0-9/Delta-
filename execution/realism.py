"""G16/G17/G18 — Micro replay wire + latency breakdown + cost calibration (thin slice)."""
from __future__ import annotations

from dataclasses import dataclass


def replay_events_to_book(events: list[dict], book) -> dict:
    """Deterministic events->book states. Returns final best bid/ask."""
    for e in events:
        if e.get("side") == "bid":
            book.bids[e["price"]] = book.bids.get(e["price"], 0) + e.get("qty", 0)
        elif e.get("side") == "ask":
            book.asks[e["price"]] = book.asks.get(e["price"], 0) + e.get("qty", 0)
    bids = sorted(book.bids) if getattr(book, "bids", None) else []
    asks = sorted(book.asks) if getattr(book, "asks", None) else []
    return {"bid": bids[-1] if bids else None, "ask": asks[0] if asks else None,
            "n": len(events)}


@dataclass
class LatencyBreakdown:
    gateway_ms: float = 0.0
    strategy_ms: float = 0.0
    risk_ms: float = 0.0
    exchange_ms: float = 0.0
    compute_ms: float = 0.0
    simulated_ms: float = 0.0


def check_latency_split(simulated_ms: float, compute_ms: float) -> bool:
    return simulated_ms >= 0 and compute_ms >= 0 and simulated_ms != compute_ms or (simulated_ms == 0 and compute_ms == 0)


def calibrate_cost(spread_bps: float, impact_bps: float, realized_bps: float) -> dict:
    err = abs((spread_bps + impact_bps) - realized_bps)
    return {"model_bps": spread_bps + impact_bps, "realized_bps": realized_bps,
            "err_bps": err, "bands_bps": err * 1.5}
